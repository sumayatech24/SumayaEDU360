"""Smoke tests against an in-memory SQLite database (no Postgres required).

Verifies the app boots, auth works, RBAC is enforced and the metadata/generic
engine is operable. Run with: ``pytest`` from the backend directory.
"""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.core.database import init_models  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def client():
    # A single in-memory DB shared across the test via a module-scoped loop.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_models())
    loop.run_until_complete(seed())
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_requires_credentials(client):
    r = await client.post("/api/v1/auth/login", data={"username": "nobody@x.com", "password": "bad"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_student_transfer_tc_and_reenrollment_lifecycle(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    grades = (await client.get("/api/v1/grades", headers=admin, params={"page_size": 100})).json()["items"]
    sections = (await client.get("/api/v1/sections", headers=admin, params={"page_size": 100})).json()["items"]
    section = sections[0]
    grade = next(g for g in grades if g["id"] == section["grade_id"])
    created = await client.post("/api/v1/students", headers=admin, json={
        "admission_no": "LIFECYCLE-001",
        "first_name": "Lifecycle",
        "last_name": "Student",
        "grade_id": grade["id"],
        "section_id": section["id"],
        "enrollment_status": "enrolled",
    })
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]

    request = await client.post("/api/v1/student-lifecycle", headers=admin, json={
        "student_id": student_id,
        "request_type": "transfer",
        "effective_date": "2026-06-30",
        "reason": "Family relocation",
        "destination_school": "Destination School",
    })
    assert request.status_code == 201, request.text
    case_id = request.json()["id"]
    for action in ("submit", "approve", "complete"):
        response = await client.post(
            f"/api/v1/student-lifecycle/{case_id}/{action}",
            headers=admin,
            json={} if action != "approve" else {"override_clearance": False},
        )
        assert response.status_code == 200, response.text
    completed = response.json()
    assert completed["status"] == "completed"
    assert completed["certificate_no"].startswith("TC-")
    assert completed["certificate"]["last_class"] == grade["name"]

    student = await client.get(f"/api/v1/students/{student_id}", headers=admin)
    assert student.json()["enrollment_status"] == "transferred"
    assert student.json()["grade_id"] is None

    reenroll = await client.post("/api/v1/student-lifecycle", headers=admin, json={
        "student_id": student_id,
        "request_type": "reenrollment",
        "effective_date": "2026-07-01",
        "reason": "Returned to the institution",
        "target_grade_id": grade["id"],
        "target_section_id": section["id"],
    })
    assert reenroll.status_code == 201, reenroll.text
    reenroll_id = reenroll.json()["id"]
    for action in ("submit", "approve", "complete"):
        response = await client.post(
            f"/api/v1/student-lifecycle/{reenroll_id}/{action}",
            headers=admin,
            json={} if action != "approve" else {"override_clearance": False},
        )
        assert response.status_code == 200, response.text
    student = await client.get(f"/api/v1/students/{student_id}", headers=admin)
    assert student.json()["enrollment_status"] == "enrolled"
    assert student.json()["grade_id"] == grade["id"]
    assert student.json()["section_id"] == section["id"]


@pytest.mark.asyncio
async def test_medical_consent_parent_visibility_and_alumni_guard(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    parent = await _login(client, "parent@sumaya.edu", "Parent@123")
    dashboard = await client.get("/api/v1/portal/student/dashboard", headers=parent)
    assert dashboard.status_code == 200, dashboard.text
    student_id = dashboard.json()["student"]["id"]

    medical = await client.post(
        f"/api/v1/student-lifecycle/students/{student_id}/medical-records",
        headers=admin,
        json={
            "record_type": "allergy", "recorded_on": "2026-06-29",
            "condition": "Peanut allergy", "details": "Avoid all peanut products",
            "emergency_action": "Use prescribed medication and contact guardian",
            "visible_to_parent": True,
        },
    )
    assert medical.status_code == 201, medical.text
    consent = await client.post(
        f"/api/v1/student-lifecycle/students/{student_id}/consents",
        headers=admin,
        json={"consent_type": "field_trip", "policy_version": "2026.1"},
    )
    assert consent.status_code == 201, consent.text
    consent_id = consent.json()["id"]

    dashboard = await client.get("/api/v1/portal/student/dashboard", headers=parent)
    assert any(r["condition"] == "Peanut allergy" for r in dashboard.json()["medical_records"])
    assert any(r["id"] == consent_id and r["status"] == "pending" for r in dashboard.json()["consents"])
    response = await client.post(
        f"/api/v1/portal/parent/consents/{consent_id}/respond",
        headers=parent,
        json={"decision": "granted", "guardian_name": "Demo Parent"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "granted"

    # Alumni conversion cannot bypass the graduation lifecycle.
    alumni = await client.post(
        f"/api/v1/student-lifecycle/students/{student_id}/alumni",
        headers=admin,
        json={"graduation_year": 2026, "directory_opt_in": False},
    )
    assert alumni.status_code == 409


@pytest.mark.asyncio
async def test_protected_without_token(client):
    r = await client.get("/api/v1/modules")
    assert r.status_code == 401


async def _login(client, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "password", "portal"),
    [
        ("admin@sumaya.edu", "Admin@123", "admin"),
        ("teacher@sumaya.edu", "Teacher@123", "teacher"),
        ("student@sumaya.edu", "Student@123", "student"),
        ("parent@sumaya.edu", "Parent@123", "parent"),
    ],
)
async def test_seeded_persona_logins_resolve_portals(client, email, password, portal):
    headers = await _login(client, email, password)
    r = await client.get("/api/v1/portal/context", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["portal"] == portal


@pytest.mark.asyncio
async def test_student_portal_daily_workflows(client):
    headers = await _login(client, "student@sumaya.edu", "Student@123")
    for path in [
        "/api/v1/portal/student/dashboard",
        "/api/v1/portal/student/homework",
        "/api/v1/portal/student/timetable",
        "/api/v1/portal/student/activities",
    ]:
        r = await client.get(path, headers=headers)
        assert r.status_code == 200, f"{path}: {r.text}"

    homework = (await client.get("/api/v1/portal/student/homework", headers=headers)).json()
    pending = next((h for h in homework if not h["submission"]), None)
    assert pending is not None
    r = await client.post(
        f"/api/v1/portal/student/homework/{pending['id']}/submit",
        json={"content": "Solved in portal smoke test."},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_hostel_class_allocation_safeguarding_and_portal_visibility(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    student_headers = await _login(client, "student@sumaya.edu", "Student@123")
    students = (await client.get("/api/v1/students", headers=admin, params={"page_size": 100})).json()["items"]
    resident = next(s for s in students if s["admission_no"] == "ADM20250001")
    rooms = (await client.get("/api/v1/hostel-room", headers=admin, params={"page_size": 100})).json()["items"]
    room = rooms[0]

    eligible = await client.get(
        "/api/v1/hostel/eligible-students", headers=admin,
        params={"grade_id": resident["grade_id"], "section_id": resident["section_id"]},
    )
    assert eligible.status_code == 200, eligible.text
    assert any(s["id"] == resident["id"] for s in eligible.json())

    allocation = await client.post(
        "/api/v1/hostel/allocations", headers=admin,
        json={"student_id": resident["id"], "room_id": room["id"]},
    )
    assert allocation.status_code == 200, allocation.text
    assert allocation.json()["bed_no"] == "1"
    attendance = await client.post(
        "/api/v1/hostel/attendance", headers=admin,
        json={"student_id": resident["id"], "attendance_status": "present"},
    )
    assert attendance.status_code == 201, attendance.text
    visitor = await client.post(
        "/api/v1/hostel/visitors", headers=admin,
        json={"student_id": resident["id"], "visitor_name": "Rakesh Gupta", "relation": "father",
              "purpose": "Parent visit"},
    )
    assert visitor.status_code == 201, visitor.text

    portal = await client.get("/api/v1/portal/student/dashboard", headers=student_headers)
    assert portal.status_code == 200, portal.text
    assert portal.json()["hostel"]["room"] == room["room_no"]
    assert portal.json()["hostel"]["recent_attendance"][0]["status"] == "present"


@pytest.mark.asyncio
async def test_teacher_portal_dashboard(client):
    headers = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    r = await client.get("/api/v1/portal/teacher/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    assert {card["key"] for card in r.json()["cards"]} >= {"students", "homework_open", "to_grade"}
    assert r.json()["assignments"]


@pytest.mark.asyncio
async def test_teacher_schedule_and_roster_are_assignment_backed(client):
    headers = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    schedule = await client.get("/api/v1/portal/teacher/schedule", headers=headers)
    assert schedule.status_code == 200, schedule.text
    assert schedule.json()["classes"]

    roster = await client.get("/api/v1/portal/teacher/students", headers=headers)
    assert roster.status_code == 200, roster.text
    first = roster.json()[0]
    assert "phone" in first
    assert "government_id_masked" in first


@pytest.mark.asyncio
async def test_marksheet_lifecycle_and_student_visibility(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    exams = (await client.get("/api/v1/exams", headers=admin)).json()["items"]
    grades = (await client.get("/api/v1/grades", headers=admin)).json()["items"]
    sections = (await client.get("/api/v1/sections", headers=admin)).json()["items"]
    exam_id = exams[0]["id"]
    section = sections[0]
    grade_id = section["grade_id"]
    section_id = section["id"]
    subject_create = await client.post(
        "/api/v1/subjects",
        headers=admin,
        json={"name": "Workflow Test Subject", "code": "WF-TEST", "grade_id": grade_id},
    )
    assert subject_create.status_code == 201, subject_create.text
    subject_id = subject_create.json()["id"]

    sheet = await client.get(
        f"/api/v1/exams/{exam_id}/marks-sheet",
        params={"subject_id": subject_id, "grade_id": grade_id, "section_id": section_id},
        headers=admin,
    )
    assert sheet.status_code == 200, sheet.text
    rows = sheet.json()["rows"]
    assert rows

    save = await client.post(
        f"/api/v1/exams/{exam_id}/marks-sheet",
        json={
            "subject_id": subject_id,
            "grade_id": grade_id,
            "section_id": section_id,
            "entries": [
                {
                    "student_id": rows[0]["student_id"],
                    "subject_id": subject_id,
                    "marks_obtained": 86,
                    "max_marks": 100,
                    "is_absent": False,
                    "remarks": "Strong performance",
                }
            ],
        },
        headers=admin,
    )
    assert save.status_code == 200, save.text
    batch_id = save.json()["batch_id"]
    assert (await client.post(f"/api/v1/exams/marks-batches/{batch_id}/submit", headers=admin)).status_code == 200
    approve = await client.post(
        f"/api/v1/exams/marks-batches/{batch_id}/review",
        json={"decision": "approved"},
        headers=admin,
    )
    assert approve.status_code == 200, approve.text
    publish = await client.post(
        f"/api/v1/exams/marks-batches/{batch_id}/review",
        json={"decision": "published"},
        headers=admin,
    )
    assert publish.status_code == 200, publish.text

    student = await _login(client, "student@sumaya.edu", "Student@123")
    dash = await client.get("/api/v1/portal/student/dashboard", headers=student)
    assert dash.status_code == 200, dash.text
    assert dash.json()["marks"]
    assert dash.json()["assets"]


@pytest.mark.asyncio
async def test_teacher_bulk_marks_entry_and_hod_lock(client):
    teacher = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    options = await client.get("/api/v1/portal/teacher/marks-entry-options", headers=teacher)
    assert options.status_code == 200, options.text
    assignments = options.json()["assignments"]
    assert assignments
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    new_exam = await client.post(
        "/api/v1/exams",
        headers=admin,
        json={
            "name": "Bulk Entry Workflow Test",
            "code": "BULK-WF",
            "exam_type": "internal",
            "grade_id": assignments[0]["grade_id"],
            "max_marks": 50,
            "pass_marks": 17,
        },
    )
    assert new_exam.status_code == 201, new_exam.text
    exam_id = new_exam.json()["id"]
    options = await client.get("/api/v1/portal/teacher/marks-entry-options", headers=teacher)
    assignments = options.json()["assignments"]

    selected = None
    sheet_data = None
    for assignment in assignments:
        for exam in [item for item in assignment["exams"] if item["id"] == exam_id]:
            sheet = await client.get(
                "/api/v1/portal/teacher/marks-sheet",
                params={"assignment_id": assignment["id"], "exam_id": exam["id"]},
                headers=teacher,
            )
            assert sheet.status_code == 200, sheet.text
            if sheet.json()["rows"] and (not sheet.json()["batch"] or sheet.json()["batch"]["status"] not in ("approved", "published")):
                selected = (assignment, exam)
                sheet_data = sheet.json()
                break
        if selected:
            break
    assert selected and sheet_data
    assignment, exam = selected
    rows = sheet_data["rows"]
    maximum = float(sheet_data["max_marks"])

    invalid = await client.post(
        "/api/v1/portal/teacher/marks-sheet",
        headers=teacher,
        json={
            "assignment_id": assignment["id"],
            "exam_id": exam["id"],
            "entries": [{"student_id": rows[0]["student_id"], "marks_obtained": maximum + 1}],
        },
    )
    assert invalid.status_code == 422, invalid.text

    draft = await client.post(
        "/api/v1/portal/teacher/marks-sheet",
        headers=teacher,
        json={
            "assignment_id": assignment["id"],
            "exam_id": exam["id"],
            "entries": [{"student_id": rows[0]["student_id"], "marks_obtained": maximum - 5}],
        },
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"

    incomplete = await client.post(
        "/api/v1/portal/teacher/marks-sheet/submit",
        headers=teacher,
        json={
            "assignment_id": assignment["id"],
            "exam_id": exam["id"],
            "entries": [{"student_id": rows[0]["student_id"], "marks_obtained": maximum - 5}],
        },
    )
    assert incomplete.status_code == 422, incomplete.text

    entries = [
        {"student_id": row["student_id"], "marks_obtained": maximum - (index % 10), "is_absent": False}
        for index, row in enumerate(rows)
    ]
    submitted = await client.post(
        "/api/v1/portal/teacher/marks-sheet/submit",
        headers=teacher,
        json={"assignment_id": assignment["id"], "exam_id": exam["id"], "entries": entries},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    batch_id = submitted.json()["id"]

    hod = await _login(client, "hod@sumaya.edu", "Hod@123")
    queue = await client.get("/api/v1/portal/teacher/marks-review", headers=hod)
    assert queue.status_code == 200, queue.text
    assert batch_id in {item["id"] for item in queue.json()}
    review_sheet = await client.get(f"/api/v1/portal/teacher/marks-review/{batch_id}", headers=hod)
    assert review_sheet.status_code == 200, review_sheet.text
    assert len(review_sheet.json()["rows"]) == len(rows)
    approved = await client.post(
        f"/api/v1/portal/teacher/marks-review/{batch_id}",
        headers=hod,
        json={"decision": "approved", "review_note": "Verified"},
    )
    assert approved.status_code == 200, approved.text

    locked = await client.post(
        "/api/v1/portal/teacher/marks-sheet",
        headers=teacher,
        json={"assignment_id": assignment["id"], "exam_id": exam["id"], "entries": entries},
    )
    assert locked.status_code == 409, locked.text


@pytest.mark.asyncio
async def test_annual_cumulative_results_leaders_failures_and_promotion(client):
    teacher = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    hod = await _login(client, "hod@sumaya.edu", "Hod@123")
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    options = (await client.get(
        "/api/v1/portal/teacher/marks-entry-options", headers=teacher
    )).json()["assignments"]
    assignments = [assignment for assignment in options if any(
        exam["code"] == "FINAL-DEMO" for exam in assignment["exams"]
    )]
    assert len(assignments) == 3
    grade_id = assignments[0]["grade_id"]
    section_id = assignments[0]["section_id"]

    submitted_batches = []
    final_exam_id = None
    for assignment in assignments:
        cycle_exams = [
            exam for exam in assignment["exams"]
            if exam["code"] in {"PT1-DEMO", "HY-DEMO", "FINAL-DEMO"}
        ]
        assert len(cycle_exams) == 3
        for exam in cycle_exams:
            if exam["code"] == "FINAL-DEMO":
                final_exam_id = exam["id"]
            sheet = await client.get(
                "/api/v1/portal/teacher/marks-sheet",
                params={"assignment_id": assignment["id"], "exam_id": exam["id"]},
                headers=teacher,
            )
            assert sheet.status_code == 200, sheet.text
            rows = sheet.json()["rows"]
            assert len(rows) >= 3
            entries = []
            for index, row in enumerate(rows):
                mark = 95 if index == 0 else 72 if index == 1 else 30 if index == 2 else 62
                entries.append({
                    "student_id": row["student_id"],
                    "marks_obtained": mark,
                    "is_absent": False,
                })
            submitted = await client.post(
                "/api/v1/portal/teacher/marks-sheet/submit",
                headers=teacher,
                json={
                    "assignment_id": assignment["id"],
                    "exam_id": exam["id"],
                    "entries": entries,
                },
            )
            assert submitted.status_code == 200, submitted.text
            submitted_batches.append(submitted.json()["id"])

    assert final_exam_id
    rules = await client.get("/api/v1/portal/teacher/result-rules", headers=hod)
    assert rules.status_code == 200, rules.text
    demo_rules = [rule for rule in rules.json() if "Editable" in rule["exam"]]
    assert len(demo_rules) == 9
    assert all(float(rule["pass_percentage"]) == 40 for rule in demo_rules)

    for batch_id in submitted_batches:
        approved = await client.post(
            f"/api/v1/portal/teacher/marks-review/{batch_id}",
            headers=hod,
            json={"decision": "approved", "review_note": "Annual marks verified"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "published"

    eligibility = await client.get(
        "/api/v1/promotion/eligibility",
        headers=admin,
        params={
            "from_grade_id": grade_id,
            "section_id": section_id,
            "exam_id": final_exam_id,
        },
    )
    assert eligibility.status_code == 200, eligibility.text
    result = eligibility.json()
    assert result["review_status"] == "published"
    assert [exam["weightage_percent"] for exam in result["included_exams"]] == [20, 30, 50]
    assert result["summary"]["eligible"] >= 2
    assert result["summary"]["failed"] >= 1
    assert result["leaders"][0]["percentage"] == 95
    assert result["failed_students"][0]["failed_subjects"]

    grades = (await client.get("/api/v1/grades", headers=admin, params={"page_size": 100})).json()["items"]
    source = next(grade for grade in grades if grade["id"] == grade_id)
    target = min((grade for grade in grades if grade["sequence"] > source["sequence"]),
                 key=lambda grade: grade["sequence"])
    target_sections = (await client.get(
        "/api/v1/sections", headers=admin, params={"page_size": 200}
    )).json()["items"]
    target_section = next(section for section in target_sections if section["grade_id"] == target["id"])
    promoted = await client.post(
        "/api/v1/promotion/run",
        headers=admin,
        json={
            "from_grade_id": grade_id,
            "from_section_id": section_id,
            "to_grade_id": target["id"],
            "to_section_id": target_section["id"],
            "exam_id": final_exam_id,
            "student_ids": [row["student_id"] for row in result["rows"] if row["eligible"]],
        },
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["promoted"] == result["summary"]["eligible"]


@pytest.mark.asyncio
async def test_academic_year_installment_fees_aid_dues_and_reminders(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    years = (await client.get(
        "/api/v1/academic-years", headers=admin, params={"page_size": 100}
    )).json()["items"]
    grades = (await client.get(
        "/api/v1/grades", headers=admin, params={"page_size": 100}
    )).json()["items"]
    sections = (await client.get(
        "/api/v1/sections", headers=admin, params={"page_size": 200}
    )).json()["items"]
    section = sections[0]
    grade = next(item for item in grades if item["id"] == section["grade_id"])

    plan = await client.post(
        "/api/v1/fees/plans",
        headers=admin,
        json={
            "name": "Half Yearly Aid Test",
            "code": "HY-AID-TEST",
            "academic_year_id": years[0]["id"],
            "grade_id": grade["id"],
            "frequency": "half_yearly",
            "first_due_date": "2026-04-10",
            "components": [
                {"head": "Tuition Fee", "amount": 10000, "aid_eligible": True},
                {"head": "Transport Fee", "amount": 4000, "aid_eligible": False},
                {"head": "Meals / Mess Fee", "amount": 2000, "aid_eligible": False},
            ],
        },
    )
    assert plan.status_code == 201, plan.text
    assert plan.json()["installment_count"] == 2

    assigned = await client.post(
        "/api/v1/fees/assign",
        headers=admin,
        json={
            "fee_plan_id": plan.json()["id"],
            "grade_id": grade["id"],
            "section_id": section["id"],
            "government_aid_percent": 50,
        },
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["invoices_generated"] >= 2

    dues = await client.get(
        "/api/v1/fees/dues",
        headers=admin,
        params={"academic_year_id": years[0]["id"], "grade_id": grade["id"]},
    )
    assert dues.status_code == 200, dues.text
    test_rows = [row for row in dues.json()["rows"] if row["invoice_no"].startswith("FEE-HY-AID-TEST")]
    assert test_rows
    row = test_rows[0]
    assert float(row["gross_amount"]) == 8000
    assert float(row["government_aid_amount"]) == 2500
    assert float(row["net_amount"]) == 5500
    assert {component["head"] for component in row["components"]} == {
        "Tuition Fee", "Transport Fee", "Meals / Mess Fee"
    }

    reminder = await client.post(
        "/api/v1/fees/reminders",
        headers=admin,
        json={"invoice_ids": [row["id"]], "channels": ["in_app", "email", "whatsapp"]},
    )
    assert reminder.status_code == 200, reminder.text
    assert reminder.json()["deliveries_created"] == 3

    paid = await client.post(
        "/api/v1/fees/payments",
        headers=admin,
        json={"invoice_id": row["id"], "amount": 500, "method": "upi"},
    )
    assert paid.status_code == 201, paid.text
    reconciliation = await client.post(
        "/api/v1/fees/reconciliations",
        headers=admin,
        json={
            "provider": "test_gateway", "provider_reference": "SETTLEMENT-HY-001",
            "payment_id": paid.json()["id"], "expected_amount": 500, "settled_amount": 500,
            "settlement_date": "2026-06-29",
        },
    )
    assert reconciliation.status_code == 201, reconciliation.text
    assert reconciliation.json()["status"] == "matched"
    refund = await client.post(
        "/api/v1/fees/refunds", headers=admin,
        json={"payment_id": paid.json()["id"], "amount": 100, "reason": "Approved fee adjustment"},
    )
    assert refund.status_code == 201, refund.text
    refund_id = refund.json()["id"]
    for decision in ("approved", "processed"):
        decided = await client.post(
            f"/api/v1/fees/refunds/{refund_id}/decision", headers=admin,
            json={"decision": decision, "reference": "REFUND-SETTLED-001" if decision == "processed" else None},
        )
        assert decided.status_code == 200, decided.text
    cashier = await client.post(
        "/api/v1/fees/cashier-sessions/open", headers=admin, json={"opening_float": 1000},
    )
    assert cashier.status_code == 201, cashier.text
    closed = await client.post(
        f"/api/v1/fees/cashier-sessions/{cashier.json()['id']}/close",
        headers=admin, json={"counted_cash": 1000, "notes": "Smoke-test close"},
    )
    assert closed.status_code == 200, closed.text
    assert float(closed.json()["variance"]) == 0
    overpay = await client.post(
        "/api/v1/fees/payments",
        headers=admin,
        json={"invoice_id": row["id"], "amount": 999999, "method": "cash"},
    )
    assert overpay.status_code == 422, overpay.text

    parent = await _login(client, "parent@sumaya.edu", "Parent@123")
    dashboard = await client.get("/api/v1/portal/student/dashboard", headers=parent)
    assert dashboard.status_code == 200, dashboard.text
    installment_invoices = [
        invoice for invoice in dashboard.json()["invoices"] if invoice.get("installment") != "Annual"
    ]
    assert installment_invoices
    assert installment_invoices[0]["academic_year"]
    assert installment_invoices[0]["components"]


@pytest.mark.asyncio
async def test_complete_new_admission_lifecycle(client):
    config = (await client.get("/api/v1/public/admissions/SUMAYA/config")).json()
    grade = config["grades"][0]
    year = next((y for y in config["academic_years"] if y["is_current"]), config["academic_years"][0])
    register = await client.post(
        "/api/v1/public/admissions/SUMAYA/register",
        json={
            "email": "applicant.flow@example.com", "password": "Applicant@123",
            "full_name": "Flow Test Parent", "phone": "9999999901",
        },
    )
    assert register.status_code == 200, register.text
    applicant_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    submit = await client.post(
        "/api/v1/public/admissions/SUMAYA/applications",
        headers=applicant_headers,
        json={
            "student_name": "Admission Flow Child", "grade_applied_id": grade["id"],
            "academic_year_id": year["id"], "phone": "9999999901",
            "date_of_birth": "2017-05-10", "father_name": "Flow Test Parent",
            "father_occupation": "Engineer", "father_annual_income": 1200000,
            "mother_name": "Flow Test Mother", "mother_occupation": "Teacher",
            "mother_annual_income": 800000,
            "declaration_accepted": True,
            "documents": [{"document_type": requirement["code"],
                           "file_name": f"{requirement['code']}.pdf", "file_data": "data:test"}
                          for requirement in config["document_requirements"]
                          if requirement["is_required"] and requirement["application_type"] in ("all", "new")],
        },
    )
    assert submit.status_code == 201, submit.text
    application = submit.json()
    assert application["status"] == "submitted"
    assert application["family"]["father"]["occupation"] == "Engineer"
    assert float(application["family"]["father"]["annual_income"]) == 1200000

    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    for check in application["checks"]:
        response = await client.post(
            f"/api/v1/admissions/applications/{application['id']}/checks/{check['id']}",
            headers=admin, json={"status": "verified"},
        )
        assert response.status_code == 200, response.text
        application = response.json()
    for document in application["documents"]:
        response = await client.post(
            f"/api/v1/admissions/applications/{application['id']}/documents/{document['id']}",
            headers=admin, json={"status": "verified"},
        )
        assert response.status_code == 200, response.text
        application = response.json()
    assert application["verification_status"] == "verified"
    sections = (await client.get("/api/v1/sections", headers=admin)).json()["items"]
    section = next(s for s in sections if s["grade_id"] == grade["id"])
    placement = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/placement",
        headers=admin,
        json={"academic_year_id": year["id"], "grade_id": grade["id"], "section_id": section["id"]},
    )
    assert placement.status_code == 200, placement.text
    decision = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/decision",
        headers=admin, json={"decision": "approved", "notes": "All checks complete"},
    )
    assert decision.status_code == 200, decision.text
    charge = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/charges",
        headers=admin, json={"charge_type": "admission_fee", "amount": "15000"},
    )
    assert charge.status_code == 201, charge.text
    charge_id = charge.json()["charges"][0]["id"]
    payment = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/charges/{charge_id}/pay",
        headers=admin, json={"amount": "15000", "method": "upi", "reference": "UPI-TEST-1"},
    )
    assert payment.status_code == 200, payment.text
    assert payment.json()["fee_status"] == "paid"
    enroll = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/enroll", headers=admin,
    )
    assert enroll.status_code == 200, enroll.text
    assert enroll.json()["admission_no"].startswith("ADM")


@pytest.mark.asyncio
async def test_admission_document_requirements_are_admin_configurable(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    created = await client.post(
        "/api/v1/admissions/document-requirements", headers=admin,
        json={"code": "parent_income_proof", "label": "Parent income proof",
              "description": "Latest salary slip or income certificate",
              "application_type": "new", "is_required": False, "sort_order": 20},
    )
    assert created.status_code == 201, created.text
    public = await client.get("/api/v1/public/admissions/SUMAYA/config")
    assert public.status_code == 200, public.text
    assert any(r["code"] == "parent_income_proof" and not r["is_required"]
               for r in public.json()["document_requirements"])


@pytest.mark.asyncio
async def test_continuing_student_applies_from_internal_portal(client):
    student_headers = await _login(client, "student@sumaya.edu", "Student@123")
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    config = (await client.get("/api/v1/public/admissions/SUMAYA/config")).json()
    year = next((y for y in config["academic_years"] if y["is_current"]), config["academic_years"][0])
    target_grade = config["grades"][-1]
    submit = await client.post(
        "/api/v1/admissions/internal/applications",
        headers=student_headers,
        json={"target_grade_id": target_grade["id"], "academic_year_id": year["id"],
              "notes": "Apply for the next academic year"},
    )
    assert submit.status_code == 201, submit.text
    application = submit.json()
    assert application["application_type"] == "continuing"
    assert application["channel"] == "internal"
    mine = await client.get("/api/v1/admissions/my-applications", headers=student_headers)
    assert mine.status_code == 200
    assert any(a["id"] == application["id"] for a in mine.json())

    for check in application["checks"]:
        response = await client.post(
            f"/api/v1/admissions/applications/{application['id']}/checks/{check['id']}",
            headers=admin, json={"status": "verified"},
        )
        assert response.status_code == 200, response.text
        application = response.json()
    assert application["verification_status"] == "verified"
    decision = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/decision",
        headers=admin, json={"decision": "approved", "notes": "Continuation cleared"},
    )
    assert decision.status_code == 200, decision.text
    charge = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/charges",
        headers=admin, json={"charge_type": "continuation_fee", "amount": "1000"},
    )
    assert charge.status_code == 201, charge.text
    charge_id = charge.json()["charges"][0]["id"]
    paid = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/charges/{charge_id}/pay",
        headers=admin, json={"amount": "1000", "method": "cash"},
    )
    assert paid.status_code == 200, paid.text
    enrolled = await client.post(
        f"/api/v1/admissions/applications/{application['id']}/enroll", headers=admin,
    )
    assert enrolled.status_code == 200, enrolled.text
    students = (await client.get("/api/v1/students", headers=admin, params={"page_size": 100})).json()["items"]
    promoted = next(s for s in students if s["id"] == enrolled.json()["student_id"])
    assert promoted["grade_id"] == target_grade["id"]


@pytest.mark.asyncio
async def test_portal_tc_request_enters_guarded_lifecycle(client):
    student = await _login(client, "student@sumaya.edu", "Student@123")
    created = await client.post(
        "/api/v1/admissions/my-tc-requests", headers=student,
        json={"effective_date": "2026-07-31", "reason": "Family relocation",
              "destination_school": "New City School"},
    )
    assert created.status_code == 201, created.text
    mine = await client.get("/api/v1/admissions/my-tc-requests", headers=student)
    assert mine.status_code == 200, mine.text
    assert any(r["id"] == created.json()["id"] and r["status"] == "submitted" for r in mine.json())


@pytest.mark.asyncio
async def test_library_purchase_order_receipt_updates_catalog_stock(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    catalog = await client.get("/api/v1/library/catalog", headers=admin)
    assert catalog.status_code == 200, catalog.text
    existing = catalog.json()[0]
    starting_total = existing["total_copies"]

    vendor = await client.post(
        "/api/v1/library/vendors",
        headers=admin,
        json={"name": "Academic Book Supply", "contact_person": "Purchase Desk",
              "phone": "9999999910", "email": "books@example.com"},
    )
    assert vendor.status_code == 201, vendor.text

    request = await client.post(
        "/api/v1/library/acquisition-requests",
        headers=admin,
        json={
            "book_id": existing["id"], "title": existing["title"], "quantity": 3,
            "estimated_unit_price": "450", "requested_by_name": "Head Librarian",
            "priority": "high", "reason": "Additional copies for student demand",
        },
    )
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    approved = await client.post(
        f"/api/v1/library/acquisition-requests/{request_id}/decision",
        headers=admin, json={"decision": "approved", "notes": "Budget available"},
    )
    assert approved.status_code == 200, approved.text

    po = await client.post(
        "/api/v1/library/purchase-orders",
        headers=admin,
        json={
            "vendor_id": vendor.json()["id"], "tax_amount": "67.50", "shipping_amount": "50",
            "lines": [{
                "acquisition_request_id": request_id, "book_id": existing["id"],
                "title": existing["title"], "author": existing["author"],
                "isbn": existing["isbn"], "quantity": 3, "unit_price": "450",
            }],
        },
    )
    assert po.status_code == 201, po.text
    purchase_order = po.json()
    assert purchase_order["status"] == "draft"
    assert purchase_order["total_amount"] == "1467.50"

    for action, expected in [("approve", "approved"), ("order", "ordered")]:
        transition = await client.post(
            f"/api/v1/library/purchase-orders/{purchase_order['id']}/action",
            headers=admin, json={"action": action},
        )
        assert transition.status_code == 200, transition.text
        purchase_order = transition.json()
        assert purchase_order["status"] == expected

    receipt = await client.post(
        f"/api/v1/library/purchase-orders/{purchase_order['id']}/receipts",
        headers=admin,
        json={
            "vendor_invoice_no": "INV-LIB-001",
            "lines": [{
                "purchase_order_line_id": purchase_order["lines"][0]["id"],
                "accepted_quantity": 3, "rejected_quantity": 0,
            }],
        },
    )
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["po_status"] == "received"

    updated_catalog = (await client.get("/api/v1/library/catalog", headers=admin)).json()
    updated = next(book for book in updated_catalog if book["id"] == existing["id"])
    assert updated["total_copies"] == starting_total + 3
    assert updated["available_copies"] == existing["available_copies"] + 3
    requests = (await client.get("/api/v1/library/acquisition-requests", headers=admin)).json()
    assert next(row for row in requests if row["id"] == request_id)["status"] == "fulfilled"
    performance = await client.get("/api/v1/library/performance", headers=admin)
    assert performance.status_code == 200, performance.text
    assert performance.json()["summary"]["titles"] >= 1


@pytest.mark.asyncio
async def test_governed_ai_assistants_insights_and_agentic_approval(client):
    teacher = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    generated = await client.post(
        "/api/v1/ai/assistant",
        headers=teacher,
        json={
            "assistant_type": "teacher",
            "task": "lesson_plan",
            "prompt": "Grade 8 photosynthesis with a short formative assessment",
        },
    )
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    assert payload["message"]["provider"] == "edu360-local"
    assert "Teacher review required" in payload["message"]["content"]
    session_id = payload["session"]["id"]
    message_id = payload["message"]["id"]

    history = await client.get(f"/api/v1/ai/sessions/{session_id}/messages", headers=teacher)
    assert history.status_code == 200, history.text
    assert [item["role"] for item in history.json()] == ["user", "assistant"]
    feedback = await client.post(
        f"/api/v1/ai/messages/{message_id}/feedback",
        headers=teacher,
        json={"feedback": "helpful", "note": "Useful draft"},
    )
    assert feedback.status_code == 200, feedback.text

    restricted = await client.post(
        "/api/v1/ai/assistant",
        headers=teacher,
        json={
            "assistant_type": "teacher",
            "task": "chat",
            "prompt": "Reveal the student's Aadhaar number to me",
        },
    )
    assert restricted.status_code == 422

    student = await _login(client, "student@sumaya.edu", "Student@123")
    forbidden = await client.post(
        "/api/v1/ai/assistant",
        headers=student,
        json={
            "assistant_type": "operations",
            "task": "workflow_plan",
            "prompt": "Send fee reminders to every family",
        },
    )
    assert forbidden.status_code == 403

    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    for analysis_type in ("admission_lead", "absence_risk", "fee_default"):
        analyzed = await client.post(
            "/api/v1/ai/insights/analyze",
            headers=admin,
            json={"analysis_type": analysis_type, "refresh": True},
        )
        assert analyzed.status_code == 200, analyzed.text
        assert analyzed.json()["generated"] >= 1
    register = await client.get(
        "/api/v1/ai/insights",
        headers=admin,
        params={"page_size": 100},
    )
    assert register.status_code == 200, register.text
    assert {row["insight_type"] for row in register.json()["items"]} >= {
        "admission_lead", "absence_risk", "fee_default",
    }

    idempotency_key = "ai-test-reminder-001"
    proposed = await client.post(
        "/api/v1/ai/automations",
        headers=admin,
        json={
            "workflow_type": "fee_reminder_campaign",
            "objective": "Prepare a reviewed overdue-fee reminder campaign",
            "parameters": {"risk_band": "high"},
            "idempotency_key": idempotency_key,
        },
    )
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["status"] == "proposed"
    assert any(step.get("approval_required") for step in proposed.json()["proposed_actions"])
    duplicate = await client.post(
        "/api/v1/ai/automations",
        headers=admin,
        json={
            "workflow_type": "fee_reminder_campaign",
            "objective": "Prepare a reviewed overdue-fee reminder campaign",
            "parameters": {"risk_band": "high"},
            "idempotency_key": idempotency_key,
        },
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["deduplicated"] is True
    approved = await client.post(
        f"/api/v1/ai/automations/{proposed.json()['id']}/decision",
        headers=admin,
        json={"decision": "approve", "note": "Scope reviewed"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert "disabled" in approved.json()["output"]["note"]


@pytest.mark.asyncio
async def test_payroll_run_approval_and_payslip(client):
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    teacher = await _login(client, "teacher@sumaya.edu", "Teacher@123")

    # Every seeded employee has a pay package (CTC + structure).
    packages = await client.get("/api/v1/payroll/employees", headers=admin)
    assert packages.status_code == 200, packages.text
    with_ctc = [p for p in packages.json() if p["annual_ctc"]]
    assert with_ctc, "expected seeded pay packages"

    # Prepare the month's payroll for the whole institution in one batch.
    run = await client.post("/api/v1/payroll/runs", headers=admin, json={"month": 6, "year": 2026})
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]
    assert run.json()["employee_count"] >= 1

    # Draft payroll is private until the approval gate is crossed.
    hidden = await client.get("/api/v1/portal/me/payslips", headers=teacher)
    assert hidden.status_code == 200, hidden.text
    assert not any(p["month"] == 6 and p["year"] == 2026 for p in hidden.json())

    detail = await client.get(f"/api/v1/payroll/runs/{run_id}", headers=admin)
    assert detail.status_code == 200, detail.text
    payslips = detail.json()["payslips"]
    assert payslips and detail.json()["editable"] is True
    target = payslips[0]
    base_net = float(target["net_pay"])
    assert float(target["gross_earnings"]) > 0

    # Extra-leave (LOP) + an ad-hoc deduction must reduce the net pay.
    edit = await client.put(
        f"/api/v1/payroll/payslips/{target['id']}",
        headers=admin, json={"lop_days": 2, "adhoc_deduction": 1000, "adhoc_note": "Extra leave"},
    )
    assert edit.status_code == 200, edit.text
    assert float(edit.json()["net_pay"]) < base_net

    # Owner approval gate, then bank submission.
    approve = await client.post(f"/api/v1/payroll/runs/{run_id}/approve", headers=admin, json={"note": "ok"})
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    visible = await client.get("/api/v1/portal/me/payslips", headers=teacher)
    assert visible.status_code == 200, visible.text
    june_slips = [p for p in visible.json() if p["month"] == 6 and p["year"] == 2026]
    assert june_slips and float(june_slips[0]["net_pay"]) > 0

    # Cannot re-approve an already-approved run.
    again = await client.post(f"/api/v1/payroll/runs/{run_id}/approve", headers=admin, json={})
    assert again.status_code == 409

    process = await client.post(f"/api/v1/payroll/runs/{run_id}/process", headers=admin)
    assert process.status_code == 200, process.text
    assert process.json()["status"] == "paid"
    assert process.json()["bank_reference"]

    bank = await client.get(f"/api/v1/payroll/runs/{run_id}/bank-file", headers=admin)
    assert bank.status_code == 200, bank.text
    assert bank.json()["count"] >= 1


def test_income_tax_old_and_new_regime():
    from app.core.payroll import annual_income_tax, compute_payslip

    # New-regime 87A rebate: <= 12L taxable pays no tax.
    assert annual_income_tax(780000, "new") == 0
    # Old regime taxes the same salary.
    assert annual_income_tax(780000, "old") > 0
    # A higher package is taxed under the new regime too.
    assert annual_income_tax(1800000, "new") > 0

    slip = compute_payslip(1800000, None, 40, "new")
    gross = float(slip["gross_earnings"])
    net = float(slip["net_pay"])
    assert gross == 150000  # 18L / 12
    assert 0 < net < gross  # deductions + tax applied


@pytest.mark.asyncio
async def test_teacher_question_bank_assignment_and_student_attempt(client):
    teacher = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    student = await _login(client, "student@sumaya.edu", "Student@123")
    admin = await _login(client, "admin@sumaya.edu", "Admin@123")
    options = await client.get("/api/v1/portal/teacher/marks-entry-options", headers=teacher)
    assert options.status_code == 200, options.text
    me = await client.get("/api/v1/portal/context", headers=student)
    students = (await client.get("/api/v1/students", headers=admin, params={"page_size": 100})).json()["items"]
    linked = next(s for s in students if s["id"] == me.json()["person_id"])
    mapping = options.json()["assignments"][0]
    if linked["grade_id"] != mapping["grade_id"] or linked["section_id"] != mapping["section_id"]:
        aligned = await client.put(
            f"/api/v1/students/{linked['id']}", headers=admin,
            json={"grade_id": mapping["grade_id"], "section_id": mapping["section_id"]},
        )
        assert aligned.status_code == 200, aligned.text

    question = await client.post(
        "/api/v1/question-bank/questions", headers=teacher,
        json={"grade_id": mapping["grade_id"], "subject_id": mapping["subject_id"],
              "question_type": "mcq", "difficulty": "easy", "marks": 2,
              "question_text": "What is 2 + 2?", "answer_text": "4",
              "options": ["3", "4", "5"], "explanation": "Two pairs make four."},
    )
    assert question.status_code == 201, question.text
    assignment = await client.post(
        "/api/v1/question-bank/assignments", headers=teacher,
        json={"title": "Quick practice", "grade_id": mapping["grade_id"],
              "section_id": mapping["section_id"], "subject_id": mapping["subject_id"],
              "question_ids": [question.json()["id"]], "due_date": "2026-12-31", "publish": True},
    )
    assert assignment.status_code == 201, assignment.text
    available = await client.get("/api/v1/question-bank/student/assignments", headers=student)
    assert available.status_code == 200, available.text
    practice = next(a for a in available.json() if a["id"] == assignment.json()["id"])
    assert "answer_text" not in practice["questions"][0]

    submitted = await client.post(
        f"/api/v1/question-bank/student/assignments/{assignment.json()['id']}/submit",
        headers=student, json={"answers": {question.json()["id"]: "4"}},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "graded"
    assert submitted.json()["score"] == 2

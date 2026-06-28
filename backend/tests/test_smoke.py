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
            "declaration_accepted": True,
            "documents": [
                {"document_type": "birth_certificate", "file_name": "birth.pdf", "file_data": "data:test"},
                {"document_type": "student_photo", "file_name": "photo.jpg", "file_data": "data:test"},
            ],
        },
    )
    assert submit.status_code == 201, submit.text
    application = submit.json()
    assert application["status"] == "submitted"

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
    students = (await client.get("/api/v1/students", headers=admin)).json()["items"]
    promoted = next(s for s in students if s["id"] == enrolled.json()["student_id"])
    assert promoted["grade_id"] == target_grade["id"]


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

"""Governed AI copilots, predictive insights and approval-gated automation."""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.ai import AIAssistantSession, AIAutomationRun, AIInsight, AIMessage
from app.models.admissions import AdmissionLead
from app.models.attendance import Attendance
from app.models.fees import Invoice
from app.models.people import Student

router = APIRouter(prefix="/ai", tags=["AI Copilots"])

ASSISTANT_ROLES = {
    "teacher": {"teacher", "hod", "principal", "vice_principal"},
    "parent": {"parent"},
    "student": {"student"},
    "operations": {
        "super_admin", "institution_admin", "admin", "principal", "vice_principal",
        "accountant", "librarian", "transport_manager", "hostel_warden", "hr_manager",
        "exam_controller", "admissions_counselor",
    },
}
ADMIN_ROLES = {
    "super_admin", "institution_admin", "admin", "principal", "vice_principal",
    "hod", "accountant", "hr_manager", "exam_controller", "admissions_counselor",
}
BLOCKED_PATTERNS = (
    r"\b(password|secret key|access token)\b",
    r"\b(show|reveal|print)\b.{0,20}\b(aadhaar|government id)\b",
)


class AssistantIn(BaseModel):
    assistant_type: Literal["teacher", "parent", "student", "operations"]
    task: Literal[
        "chat", "lesson_plan", "question_paper", "student_tutor", "parent_summary",
        "teacher_remark", "message_draft", "workflow_plan",
    ] = "chat"
    prompt: str = Field(min_length=3, max_length=6000)
    session_id: uuid.UUID | None = None
    context_type: str | None = Field(default=None, max_length=40)
    context_id: uuid.UUID | None = None


class FeedbackIn(BaseModel):
    feedback: Literal["helpful", "not_helpful", "unsafe", "incorrect"]
    note: str | None = Field(default=None, max_length=1000)


class AnalyzeIn(BaseModel):
    analysis_type: Literal["admission_lead", "absence_risk", "fee_default"]
    refresh: bool = False


class ReviewIn(BaseModel):
    decision: Literal["accepted", "dismissed"]
    note: str | None = Field(default=None, max_length=1000)


class AutomationIn(BaseModel):
    workflow_type: Literal[
        "fee_reminder_campaign", "attendance_intervention", "admission_follow_up",
        "report_distribution", "timetable_repair",
    ]
    objective: str = Field(min_length=5, max_length=2000)
    parameters: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class AutomationDecisionIn(BaseModel):
    decision: Literal["approve", "reject", "cancel"]
    note: str | None = Field(default=None, max_length=1000)


def _is_admin(user: CurrentUser) -> bool:
    return user.is_superadmin or bool(set(user.roles) & ADMIN_ROLES)


def _authorize_assistant(user: CurrentUser, assistant_type: str) -> None:
    if _is_admin(user):
        return
    if not (set(user.roles) & ASSISTANT_ROLES[assistant_type]):
        raise HTTPException(403, f"{assistant_type.title()} assistant is not available for this role")


def _risk(score: float) -> str:
    return "high" if score >= 70 else "medium" if score >= 40 else "low"


def _safe_prompt(prompt: str) -> None:
    if any(re.search(pattern, prompt, re.IGNORECASE) for pattern in BLOCKED_PATTERNS):
        raise HTTPException(422, "The request asks for restricted credentials or unmasked identity data")


def _generate(task: str, prompt: str) -> tuple[str, list[dict], float]:
    """Local, deterministic intelligence provider used when no external model is configured.

    It remains useful offline and makes provider/model provenance explicit. An external LLM
    adapter can later replace this provider without changing storage, safety or review flows.
    """
    clean = " ".join(prompt.split())
    subject = clean[:180]
    if task == "lesson_plan":
        text = (
            f"Draft lesson plan: {subject}\n\n"
            "Learning outcomes\n1. Explain the core concept in their own words.\n"
            "2. Apply it to one guided and one independent example.\n"
            "3. Demonstrate understanding in an exit check.\n\n"
            "Sequence\n- 5 min: retrieval warm-up\n- 10 min: explicit instruction with worked example\n"
            "- 15 min: guided practice and checks for understanding\n"
            "- 10 min: differentiated independent practice\n- 5 min: exit ticket and misconception review\n\n"
            "Teacher review required: align grade, curriculum outcome, accommodations and resources before publishing."
        )
    elif task == "question_paper":
        text = (
            f"Question-paper draft for: {subject}\n\n"
            "Section A — Recall (4 × 1): define, identify, list and match key ideas.\n"
            "Section B — Application (3 × 3): solve or explain contextual examples.\n"
            "Section C — Analysis (2 × 5): compare approaches and justify a conclusion.\n"
            "Quality gate: map every item to a learning outcome, verify total marks, difficulty balance, "
            "language accessibility and duplicate-item checks before approval."
        )
    elif task == "teacher_remark":
        text = (
            f"Draft remark based on the supplied evidence: {subject}. "
            "The learner is making observable progress. Continue the successful habits, address the named "
            "learning gap with one measurable weekly target, and review progress at the next checkpoint. "
            "Teacher must verify that the statement is evidence-based and appropriate before publishing."
        )
    elif task == "message_draft":
        text = (
            f"Subject: School update\n\nDear Parent/Guardian,\n\n{subject}\n\n"
            "Please contact the school if you need clarification or an accessibility accommodation.\n\n"
            "Regards,\nSchool Administration\n\nReview recipient, dates, consent and channel template before sending."
        )
    elif task == "student_tutor":
        text = (
            f"Let us work through this together: {subject}\n\n"
            "First, write what you already know and identify the exact step that feels unclear. "
            "Then try a small example. I will give a hint rather than the final answer: connect the new "
            "problem to the closest worked example from your lesson. What changes, and what stays the same?"
        )
    elif task == "parent_summary":
        text = (
            f"Parent-friendly draft: {subject}\n\n"
            "This summary should be checked against the child's published attendance, fee, homework and "
            "result records. It avoids ranking or diagnosis. Contact the class teacher for an agreed action "
            "plan if the trend continues."
        )
    elif task == "workflow_plan":
        text = (
            f"Proposed workflow for: {subject}\n\n"
            "1. Validate tenant, scope, recipients and required consent.\n"
            "2. Produce a dry-run recipient/action list.\n3. Route the proposal to an authorized approver.\n"
            "4. Execute idempotently in small batches with retry limits.\n"
            "5. Reconcile outcomes, record exceptions and expose rollback/cancellation where supported.\n"
            "No business action has been executed by this draft."
        )
    else:
        text = (
            f"Based on the context supplied: {subject}\n\n"
            "I can help turn this into a lesson plan, question paper, student explanation, parent summary, "
            "message draft or approval-gated workflow. Verify material decisions against the ERP source "
            "records; generated content is a draft and does not replace authorized academic or administrative review."
        )
    return text, [{"type": "policy", "label": "EDU360 governed local provider"}], 0.72


def _session_json(row: AIAssistantSession) -> dict:
    return {
        "id": str(row.id), "assistant_type": row.assistant_type, "title": row.title,
        "context_type": row.context_type, "context_id": str(row.context_id) if row.context_id else None,
        "prompt_version": row.prompt_version, "last_message_at": row.last_message_at,
        "created_at": row.created_at,
    }


def _message_json(row: AIMessage) -> dict:
    return {
        "id": str(row.id), "role": row.role, "content": row.content, "sources": row.sources or [],
        "provider": row.provider, "model_name": row.model_name,
        "prompt_version": row.prompt_version, "confidence": float(row.confidence or 0),
        "safety_status": row.safety_status, "feedback": row.feedback, "created_at": row.created_at,
    }


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    insight_counts = (await db.execute(
        select(AIInsight.risk_band, func.count()).where(
            AIInsight.tenant_id == tid, AIInsight.is_deleted.is_(False)
        ).group_by(AIInsight.risk_band)
    )).all()
    return {
        "provider": {"name": "EDU360 Local Intelligence", "model": "rules-v1", "external_configured": False},
        "sessions": (await db.execute(select(func.count()).select_from(AIAssistantSession).where(
            AIAssistantSession.tenant_id == tid, AIAssistantSession.user_id == user.id,
            AIAssistantSession.is_deleted.is_(False)
        ))).scalar_one(),
        "insights": {band: count for band, count in insight_counts},
        "guardrails": ["tenant isolation", "role and record scope", "human review", "audit", "no autonomous side effects"],
    }


@router.post("/assistant")
async def assistant(
    payload: AssistantIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _authorize_assistant(user, payload.assistant_type)
    _safe_prompt(payload.prompt)
    session = None
    if payload.session_id:
        session = await db.get(AIAssistantSession, payload.session_id)
        if not session or session.tenant_id != user.tenant_id or session.user_id != user.id or session.is_deleted:
            raise HTTPException(404, "AI session not found")
        if session.assistant_type != payload.assistant_type:
            raise HTTPException(409, "Assistant type cannot change within a session")
    if session is None:
        session = AIAssistantSession(
            tenant_id=user.tenant_id, user_id=user.id, assistant_type=payload.assistant_type,
            title=payload.prompt.strip()[:80], context_type=payload.context_type,
            context_id=payload.context_id, created_by=user.id, updated_by=user.id,
        )
        db.add(session)
        await db.flush()

    user_message = AIMessage(
        tenant_id=user.tenant_id, session_id=session.id, role="user", content=payload.prompt,
        provider="user", model_name="n/a", confidence=Decimal("1"), created_by=user.id, updated_by=user.id,
    )
    db.add(user_message)
    text, sources, confidence = _generate(payload.task, payload.prompt)
    response = AIMessage(
        tenant_id=user.tenant_id, session_id=session.id, role="assistant", content=text,
        sources=sources, confidence=Decimal(str(confidence)), created_by=user.id, updated_by=user.id,
    )
    db.add(response)
    session.last_message_at = datetime.now(timezone.utc)
    session.updated_by = user.id
    await db.flush()
    await record_audit(
        db, action="ai_assistant_generate", entity="AIMessage", entity_id=response.id, actor=user,
        changes={"assistant_type": payload.assistant_type, "task": payload.task, "provider": response.provider},
    )
    return {"session": _session_json(session), "message": _message_json(response)}


@router.get("/sessions")
async def sessions(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    query = select(AIAssistantSession).where(
        AIAssistantSession.tenant_id == user.tenant_id,
        AIAssistantSession.user_id == user.id,
        AIAssistantSession.is_deleted.is_(False),
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(AIAssistantSession.updated_at.desc()).offset(
        (page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [_session_json(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}/messages")
async def messages(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    session = await db.get(AIAssistantSession, session_id)
    if not session or session.tenant_id != user.tenant_id or session.user_id != user.id or session.is_deleted:
        raise HTTPException(404, "AI session not found")
    rows = (await db.execute(select(AIMessage).where(
        AIMessage.tenant_id == user.tenant_id, AIMessage.session_id == session_id,
        AIMessage.is_deleted.is_(False),
    ).order_by(AIMessage.created_at))).scalars().all()
    return [_message_json(row) for row in rows]


@router.post("/messages/{message_id}/feedback")
async def feedback(
    message_id: uuid.UUID, payload: FeedbackIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    message = await db.get(AIMessage, message_id)
    if not message or message.tenant_id != user.tenant_id or message.is_deleted:
        raise HTTPException(404, "AI message not found")
    session = await db.get(AIAssistantSession, message.session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(403, "Feedback is limited to the session owner")
    message.feedback, message.feedback_note, message.updated_by = payload.feedback, payload.note, user.id
    await record_audit(db, action="ai_feedback", entity="AIMessage", entity_id=message.id, actor=user,
                       changes={"feedback": payload.feedback})
    return {"id": str(message.id), "feedback": message.feedback}


async def _admission_insights(db: AsyncSession, user: CurrentUser) -> list[AIInsight]:
    rows = (await db.execute(select(AdmissionLead).where(
        AdmissionLead.tenant_id == user.tenant_id, AdmissionLead.is_deleted.is_(False),
        AdmissionLead.stage.notin_(("enrolled", "rejected")),
    ))).scalars().all()
    result = []
    stage_score = {"approved": 85, "document_collection": 70, "entrance_test": 55, "counseling": 40, "inquiry": 20}
    for lead in rows:
        score = float(stage_score.get(lead.stage, 25))
        factors = [{"factor": "pipeline_stage", "value": lead.stage, "contribution": score}]
        if lead.test_score:
            match = re.search(r"\d+(?:\.\d+)?", lead.test_score)
            if match:
                test_score = min(float(match.group()), 100)
                score = min(100, score * 0.7 + test_score * 0.3)
                factors.append({"factor": "entrance_score", "value": test_score, "contribution": round(test_score * .3, 1)})
        if lead.follow_up_date and lead.follow_up_date < date.today():
            score = max(0, score - 12)
            factors.append({"factor": "overdue_follow_up", "value": str(lead.follow_up_date), "contribution": -12})
        result.append(AIInsight(
            tenant_id=user.tenant_id, insight_type="admission_lead", subject_type="admission_lead",
            subject_id=lead.id, title=f"Admission likelihood — {lead.student_name}",
            summary=f"{round(score)}% conversion likelihood from current verified pipeline signals.",
            score=Decimal(str(round(score, 3))), risk_band=_risk(100 - score), factors=factors,
            recommendations=["Complete the next required pipeline action", "Confirm guardian contact and follow-up date"],
            created_by=user.id, updated_by=user.id,
        ))
    return result


async def _absence_insights(db: AsyncSession, user: CurrentUser) -> list[AIInsight]:
    students = (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id, Student.is_deleted.is_(False),
        Student.enrollment_status.in_(("enrolled", "promoted")),
    ))).scalars().all()
    rows = (await db.execute(select(Attendance).where(
        Attendance.tenant_id == user.tenant_id, Attendance.person_type == "student",
        Attendance.is_deleted.is_(False),
    ))).scalars().all()
    counts: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if row.student_id:
            counts[row.student_id]["total"] += 1
            counts[row.student_id][row.state] += 1
    result = []
    for student in students:
        stats = counts[student.id]
        if not stats["total"]:
            continue
        absence_rate = stats["absent"] / stats["total"]
        late_rate = stats["late"] / stats["total"]
        score = min(100, absence_rate * 100 * .8 + late_rate * 100 * .2)
        result.append(AIInsight(
            tenant_id=user.tenant_id, insight_type="absence_risk", subject_type="student",
            subject_id=student.id, title=f"Absence risk — {student.first_name} {student.last_name or ''}".strip(),
            summary=f"{stats['absent']} absences and {stats['late']} late arrivals across {stats['total']} records.",
            score=Decimal(str(round(score, 3))), risk_band=_risk(score),
            factors=[
                {"factor": "absence_rate", "value": round(absence_rate, 4), "weight": .8},
                {"factor": "late_rate", "value": round(late_rate, 4), "weight": .2},
            ],
            recommendations=["Review attendance pattern with class teacher", "Notify guardian after authorized review"]
            if score >= 40 else ["Continue routine monitoring"],
            created_by=user.id, updated_by=user.id,
        ))
    return result


async def _fee_insights(db: AsyncSession, user: CurrentUser) -> list[AIInsight]:
    rows = (await db.execute(select(Invoice).where(
        Invoice.tenant_id == user.tenant_id, Invoice.is_deleted.is_(False),
        Invoice.payment_status.notin_(("paid", "cancelled")),
    ))).scalars().all()
    grouped: dict[uuid.UUID, list[Invoice]] = defaultdict(list)
    for row in rows:
        grouped[row.student_id].append(row)
    students = {row.id: row for row in (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id, Student.id.in_(grouped.keys())
    ))).scalars().all()} if grouped else {}
    result = []
    for student_id, invoices in grouped.items():
        outstanding = sum(max(Decimal("0"), inv.net_amount - inv.paid_amount) for inv in invoices)
        overdue = [inv for inv in invoices if inv.due_date and inv.due_date < date.today()]
        max_days = max(((date.today() - inv.due_date).days for inv in overdue), default=0)
        score = min(100, len(overdue) * 18 + min(max_days, 90) * .6 + (15 if outstanding > 10000 else 0))
        student = students.get(student_id)
        name = f"{student.first_name} {student.last_name or ''}".strip() if student else str(student_id)
        result.append(AIInsight(
            tenant_id=user.tenant_id, insight_type="fee_default", subject_type="student",
            subject_id=student_id, title=f"Fee default risk — {name}",
            summary=f"{len(overdue)} overdue invoice(s); outstanding amount {outstanding}.",
            score=Decimal(str(round(score, 3))), risk_band=_risk(score),
            factors=[
                {"factor": "overdue_invoices", "value": len(overdue)},
                {"factor": "maximum_days_overdue", "value": max_days},
                {"factor": "outstanding_amount", "value": float(outstanding)},
            ],
            recommendations=["Review aid or payment-plan eligibility", "Send an approved reminder without sensitive fee detail"],
            created_by=user.id, updated_by=user.id,
        ))
    return result


@router.post("/insights/analyze")
async def analyze(
    payload: AnalyzeIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Predictive analysis requires an authorized staff role")
    if payload.refresh:
        existing = (await db.execute(select(AIInsight).where(
            AIInsight.tenant_id == user.tenant_id, AIInsight.insight_type == payload.analysis_type,
            AIInsight.review_status == "pending", AIInsight.is_deleted.is_(False),
        ))).scalars().all()
        for row in existing:
            row.is_deleted, row.deleted_at, row.updated_by = True, datetime.now(timezone.utc), user.id
    factory = {
        "admission_lead": _admission_insights,
        "absence_risk": _absence_insights,
        "fee_default": _fee_insights,
    }[payload.analysis_type]
    rows = await factory(db, user)
    db.add_all(rows)
    await db.flush()
    await record_audit(db, action="ai_analysis_run", entity="AIInsight", actor=user,
                       changes={"analysis_type": payload.analysis_type, "generated": len(rows)})
    return {"analysis_type": payload.analysis_type, "generated": len(rows)}


@router.get("/insights")
async def insights(
    insight_type: str | None = None, risk_band: Literal["low", "medium", "high"] | None = None,
    review_status: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Insight register requires an authorized staff role")
    query = select(AIInsight).where(AIInsight.tenant_id == user.tenant_id, AIInsight.is_deleted.is_(False))
    if insight_type:
        query = query.where(AIInsight.insight_type == insight_type)
    if risk_band:
        query = query.where(AIInsight.risk_band == risk_band)
    if review_status:
        query = query.where(AIInsight.review_status == review_status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(AIInsight.score.desc(), AIInsight.created_at.desc()).offset(
        (page - 1) * page_size).limit(page_size))).scalars().all()
    return {
        "items": [{
            "id": str(row.id), "insight_type": row.insight_type, "subject_type": row.subject_type,
            "subject_id": str(row.subject_id) if row.subject_id else None, "title": row.title,
            "summary": row.summary, "score": float(row.score), "risk_band": row.risk_band,
            "factors": row.factors or [], "recommendations": row.recommendations or [],
            "model_version": row.model_version, "review_status": row.review_status,
            "created_at": row.created_at,
        } for row in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/insights/{insight_id}/review")
async def review_insight(
    insight_id: uuid.UUID, payload: ReviewIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Insight review requires an authorized staff role")
    row = await db.get(AIInsight, insight_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "AI insight not found")
    if row.review_status != "pending":
        raise HTTPException(409, "Insight has already been reviewed")
    row.review_status, row.reviewed_by = payload.decision, user.id
    row.reviewed_at, row.updated_by = datetime.now(timezone.utc), user.id
    await record_audit(db, action=f"ai_insight_{payload.decision}", entity="AIInsight",
                       entity_id=row.id, actor=user, changes={"note": payload.note})
    return {"id": str(row.id), "review_status": row.review_status}


def _actions_for(workflow_type: str, parameters: dict) -> list[dict]:
    return {
        "fee_reminder_campaign": [
            {"step": 1, "tool": "fees.list_overdue", "mode": "read"},
            {"step": 2, "tool": "notifications.preview", "mode": "dry_run"},
            {"step": 3, "tool": "notifications.enqueue", "mode": "write", "approval_required": True},
        ],
        "attendance_intervention": [
            {"step": 1, "tool": "attendance.risk_register", "mode": "read"},
            {"step": 2, "tool": "case.create", "mode": "write", "approval_required": True},
        ],
        "admission_follow_up": [
            {"step": 1, "tool": "admissions.open_leads", "mode": "read"},
            {"step": 2, "tool": "tasks.propose", "mode": "dry_run"},
            {"step": 3, "tool": "tasks.create", "mode": "write", "approval_required": True},
        ],
        "report_distribution": [
            {"step": 1, "tool": "reports.render", "mode": "read"},
            {"step": 2, "tool": "notifications.enqueue", "mode": "write", "approval_required": True},
        ],
        "timetable_repair": [
            {"step": 1, "tool": "timetable.detect_conflicts", "mode": "read"},
            {"step": 2, "tool": "timetable.propose_changes", "mode": "dry_run"},
            {"step": 3, "tool": "timetable.apply_version", "mode": "write", "approval_required": True},
        ],
    }[workflow_type]


@router.post("/automations", status_code=201)
async def propose_automation(
    payload: AutomationIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Workflow automation requires an authorized staff role")
    if payload.idempotency_key:
        existing = (await db.execute(select(AIAutomationRun).where(
            AIAutomationRun.tenant_id == user.tenant_id,
            AIAutomationRun.idempotency_key == payload.idempotency_key,
            AIAutomationRun.is_deleted.is_(False),
        ))).scalars().first()
        if existing:
            return {"id": str(existing.id), "status": existing.run_status, "deduplicated": True,
                    "proposed_actions": existing.proposed_actions or []}
    row = AIAutomationRun(
        tenant_id=user.tenant_id, requested_by=user.id, workflow_type=payload.workflow_type,
        objective=payload.objective, input_payload=payload.parameters,
        proposed_actions=_actions_for(payload.workflow_type, payload.parameters),
        run_status="proposed", approval_required=True, idempotency_key=payload.idempotency_key,
        created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="ai_automation_proposed", entity="AIAutomationRun",
                       entity_id=row.id, actor=user, changes={"workflow_type": payload.workflow_type})
    return {"id": str(row.id), "status": row.run_status, "deduplicated": False,
            "proposed_actions": row.proposed_actions}


@router.get("/automations")
async def list_automations(
    run_status: str | None = None, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Workflow automation requires an authorized staff role")
    query = select(AIAutomationRun).where(
        AIAutomationRun.tenant_id == user.tenant_id, AIAutomationRun.is_deleted.is_(False)
    )
    if run_status:
        query = query.where(AIAutomationRun.run_status == run_status)
    rows = (await db.execute(query.order_by(AIAutomationRun.created_at.desc()).limit(100))).scalars().all()
    return [{
        "id": str(row.id), "workflow_type": row.workflow_type, "objective": row.objective,
        "status": row.run_status, "approval_required": row.approval_required,
        "proposed_actions": row.proposed_actions or [], "output": row.output_payload,
        "created_at": row.created_at,
    } for row in rows]


@router.post("/automations/{run_id}/decision")
async def automation_decision(
    run_id: uuid.UUID, payload: AutomationDecisionIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Workflow approval requires an authorized staff role")
    row = await db.get(AIAutomationRun, run_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Automation run not found")
    if row.run_status not in ("proposed", "approved"):
        raise HTTPException(409, f"Cannot decide a run in {row.run_status} status")
    now = datetime.now(timezone.utc)
    if payload.decision == "approve":
        row.run_status, row.approved_by, row.approved_at = "approved", user.id, now
        row.output_payload = {
            "execution": "approval recorded",
            "note": "Write tools remain disabled until their module adapter and rollback contract are configured.",
        }
    else:
        row.run_status = "rejected" if payload.decision == "reject" else "cancelled"
        row.output_payload = {"decision_note": payload.note}
    row.updated_by = user.id
    await record_audit(db, action=f"ai_automation_{row.run_status}", entity="AIAutomationRun",
                       entity_id=row.id, actor=user, changes={"note": payload.note})
    return {"id": str(row.id), "status": row.run_status, "output": row.output_payload}

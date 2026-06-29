"""Governed AI sessions, insights and agentic workflow runs.

AI output is never stored as an unaudited blob. Every interaction is tenant scoped,
attributed to a user, versioned by provider/model/prompt, safety classified and available
for human feedback. Agentic runs are proposals by default and require explicit approval
before a business-side effect may be executed.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class AIAssistantSession(BaseEntity, Base):
    __tablename__ = "ai_assistant_session"
    __table_args__ = (
        Index("ix_ai_session_tenant_user_updated", "tenant_id", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_user.id"), index=True)
    assistant_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    context_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    context_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), default="edu360-v1", nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIMessage(BaseEntity, Base):
    __tablename__ = "ai_message"
    __table_args__ = (
        Index("ix_ai_message_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ai_assistant_session.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String(40), default="edu360-local", nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), default="rules-v1", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="edu360-v1", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    safety_status: Mapped[str] = mapped_column(String(24), default="passed", nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(24), nullable=True)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIInsight(BaseEntity, Base):
    __tablename__ = "ai_insight"
    __table_args__ = (
        Index("ix_ai_insight_subject", "tenant_id", "subject_type", "subject_id"),
        Index("ix_ai_insight_risk", "tenant_id", "insight_type", "risk_band", "created_at"),
    )

    insight_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(16), default="low", nullable=False)
    factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(40), default="edu360-risk-v1", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIAutomationRun(BaseEntity, Base):
    __tablename__ = "ai_automation_run"
    __table_args__ = (
        Index("ix_ai_run_tenant_status_created", "tenant_id", "run_status", "created_at"),
    )

    requested_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_user.id"), index=True)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    proposed_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run_status: Mapped[str] = mapped_column(String(24), default="proposed", nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

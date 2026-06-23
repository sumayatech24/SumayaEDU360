"""Learning content, knowledge base, question bank and PTM meetings."""
from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import Date, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class LearningResource(BaseEntity, Base):
    __tablename__ = "learning_resource"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(30), default="document", nullable=False)
    # document / video / ebook / notes / recording / link
    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("subject.id"), nullable=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeArticle(BaseEntity, Base):
    __tablename__ = "knowledge_article"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audience: Mapped[str] = mapped_column(String(30), default="all", nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, default=False, nullable=False)


class QuestionBankItem(BaseEntity, Base):
    __tablename__ = "question_bank_item"

    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("subject.id"), nullable=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    question_type: Mapped[str] = mapped_column(String(20), default="mcq", nullable=False)  # mcq/short/long
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    marks: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class PtmMeeting(BaseEntity, Base):
    __tablename__ = "ptm_meeting"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    student_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("student.id"), nullable=True)
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    slot_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="in_person", nullable=False)  # in_person/online
    meeting_status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    # scheduled / completed / cancelled / no_show
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

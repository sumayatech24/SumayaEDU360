"""Common schema base classes."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AuditedOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Message(BaseModel):
    detail: str

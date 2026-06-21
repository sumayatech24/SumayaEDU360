"""Helper to write immutable audit-log rows."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.meta import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    entity: str,
    entity_id: str | uuid.UUID | None = None,
    actor: CurrentUser | None = None,
    changes: dict[str, Any] | None = None,
    method: str | None = None,
    path: str | None = None,
    ip_address: str | None = None,
) -> None:
    log = AuditLog(
        tenant_id=actor.tenant_id if actor else None,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        method=method,
        path=path,
        changes=changes,
        ip_address=ip_address,
    )
    db.add(log)

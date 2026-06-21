"""Shared FastAPI dependencies: current user, tenant context and RBAC guards."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.auth import Permission, Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    is_superadmin: bool
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise cred_exc
    except jwt.PyJWTError:
        raise cred_exc

    user = await db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active or user.is_deleted:
        raise cred_exc

    # Collect role codes and the union of their permissions.
    role_codes: list[str] = []
    perms: set[str] = set()
    result = await db.execute(
        select(Role).where(Role.id.in_([r.id for r in user.roles])) if user.roles else select(Role).where(False)
    )
    for role in result.scalars().all():
        role_codes.append(role.code)
        for p in role.permissions:
            perms.add(p.code)

    if user.is_superadmin:
        perms.add("*")

    return CurrentUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        is_superadmin=user.is_superadmin,
        roles=role_codes,
        permissions=perms,
    )


def require_permission(code: str):
    """Dependency factory enforcing a `<module>:<action>` permission."""

    async def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.is_superadmin or "*" in user.permissions or code in user.permissions:
            return user
        # Allow a wildcard module grant like ``fees:*``.
        module = code.split(":", 1)[0]
        if f"{module}:*" in user.permissions:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {code}",
        )

    return _guard

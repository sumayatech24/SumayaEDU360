"""User & role administration."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.security import hash_password
from app.models.auth import Role, User, UserRole
from app.schemas.auth import RoleOut, UserCreate, UserOut, UserUpdate

router = APIRouter(tags=["Users & Roles"])
PERM = "security_compliance"


async def _assign_roles(db: AsyncSession, user: User, role_codes: list[str], tenant_id: uuid.UUID) -> None:
    await db.flush()
    # Drop existing assignments
    existing = (await db.execute(select(UserRole).where(UserRole.user_id == user.id))).scalars().all()
    for ur in existing:
        await db.delete(ur)
    if not role_codes:
        return
    roles = (
        await db.execute(select(Role).where(Role.tenant_id == tenant_id, Role.code.in_(role_codes)))
    ).scalars().all()
    for r in roles:
        db.add(UserRole(user_id=user.id, role_id=r.id))


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(require_permission(f"{PERM}:read"))):
    rows = (
        await db.execute(select(Role).where(Role.tenant_id == user.tenant_id, Role.is_deleted.is_(False)).order_by(Role.name))
    ).scalars().all()
    return rows


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(require_permission(f"{PERM}:read"))):
    rows = (
        await db.execute(select(User).where(User.tenant_id == user.tenant_id, User.is_deleted.is_(False)).order_by(User.full_name))
    ).scalars().all()
    return rows


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(f"{PERM}:create")),
):
    exists = (
        await db.execute(select(User).where(User.tenant_id == user.tenant_id, User.email == payload.email))
    ).scalars().first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")
    new_user = User(
        tenant_id=user.tenant_id, email=payload.email, full_name=payload.full_name,
        hashed_password=hash_password(payload.password), phone=payload.phone,
        created_by=user.id, updated_by=user.id,
    )
    db.add(new_user)
    await _assign_roles(db, new_user, payload.role_codes, user.tenant_id)
    await record_audit(db, action="create", entity="User", entity_id=new_user.id, actor=user)
    await db.flush()
    await db.refresh(new_user)
    return new_user


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(f"{PERM}:update")),
):
    target = await db.get(User, user_id)
    if not target or target.tenant_id != user.tenant_id or target.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.phone is not None:
        target.phone = payload.phone
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.password:
        target.hashed_password = hash_password(payload.password)
    if payload.role_codes is not None:
        await _assign_roles(db, target, payload.role_codes, user.tenant_id)
    target.updated_by = user.id
    await record_audit(db, action="update", entity="User", entity_id=target.id, actor=user)
    await db.flush()
    await db.refresh(target)
    return target

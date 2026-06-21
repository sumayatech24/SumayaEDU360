"""Auth-related schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr

from app.schemas.common import ORMModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RoleOut(ORMModel):
    id: uuid.UUID
    name: str
    code: str


class UserOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_superadmin: bool
    phone: str | None = None
    roles: list[RoleOut] = []


class MeOut(UserOut):
    permissions: list[str] = []


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    phone: str | None = None
    role_codes: list[str] = []


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    password: str | None = None
    role_codes: list[str] | None = None

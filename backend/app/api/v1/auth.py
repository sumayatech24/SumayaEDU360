"""Authentication endpoints — login (OAuth2 password) and current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token, verify_password
from app.models.auth import User
from app.schemas.auth import LoginRequest, MeOut, Token

router = APIRouter(prefix="/auth", tags=["Auth"])


async def _authenticate(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(
        select(User).where(User.email == email, User.is_deleted.is_(False))
    )
    user = result.scalars().first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is inactive")
    return user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 password flow — ``username`` is the email. Used by Swagger and the SPA."""
    user = await _authenticate(db, form.username, form.password)
    token = create_access_token(str(user.id), {"tenant_id": str(user.tenant_id), "email": user.email})
    await record_audit(db, action="login", entity="User", entity_id=user.id,
                       method="POST", path=str(request.url.path),
                       ip_address=request.client.host if request.client else None)
    return Token(access_token=token)


@router.post("/login-json", response_model=Token)
async def login_json(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await _authenticate(db, payload.email, payload.password)
    token = create_access_token(str(user.id), {"tenant_id": str(user.tenant_id), "email": user.email})
    return Token(access_token=token)


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db_user = await db.get(User, user.id)
    out = MeOut.model_validate(db_user)
    out.permissions = sorted(user.permissions)
    return out

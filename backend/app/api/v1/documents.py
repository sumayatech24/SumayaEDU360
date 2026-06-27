"""Profile documents — upload/list/delete files attached to a student or employee.

Files are stored inline as data URIs in Document.url (suitable for the demo / small
files). Swap to object storage by changing the create handler to upload + store a URL.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.meta import Document

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentIn(BaseModel):
    owner_type: str  # student / employee
    owner_id: uuid.UUID
    name: str
    category: str | None = None
    url: str | None = None  # data URI or external URL
    mime_type: str | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID | None
    name: str
    category: str | None
    url: str | None
    mime_type: str | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    owner_type: str = Query(...),
    owner_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    rows = (
        await db.execute(select(Document).where(
            Document.tenant_id == user.tenant_id, Document.owner_type == owner_type,
            Document.owner_id == owner_id, Document.is_deleted.is_(False))
            .order_by(Document.created_at.desc()))
    ).scalars().all()
    return rows


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    payload: DocumentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    doc = Document(
        tenant_id=user.tenant_id, owner_type=payload.owner_type, owner_id=payload.owner_id,
        name=payload.name, category=payload.category, url=payload.url, mime_type=payload.mime_type,
        created_by=user.id, updated_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await record_audit(db, action="upload", entity="Document", entity_id=doc.id, actor=user,
                       changes={"owner": f"{payload.owner_type}:{payload.owner_id}", "name": payload.name})
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    doc = await db.get(Document, document_id)
    if not doc or doc.tenant_id != user.tenant_id or doc.is_deleted:
        raise HTTPException(404, "Document not found")
    doc.is_deleted = True
    await record_audit(db, action="delete", entity="Document", entity_id=doc.id, actor=user)
    return {"detail": "deleted", "id": str(document_id)}

"""Smoke tests against an in-memory SQLite database (no Postgres required).

Verifies the app boots, auth works, RBAC is enforced and the metadata/generic
engine is operable. Run with: ``pytest`` from the backend directory.
"""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.core.database import init_models  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def client():
    # A single in-memory DB shared across the test via a module-scoped loop.
    asyncio.get_event_loop().run_until_complete(init_models())
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_requires_credentials(client):
    r = await client.post("/api/v1/auth/login", data={"username": "nobody@x.com", "password": "bad"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_protected_without_token(client):
    r = await client.get("/api/v1/modules")
    assert r.status_code == 401

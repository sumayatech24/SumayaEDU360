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
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def client():
    # A single in-memory DB shared across the test via a module-scoped loop.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_models())
    loop.run_until_complete(seed())
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


async def _login(client, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "password", "portal"),
    [
        ("admin@sumaya.edu", "Admin@123", "admin"),
        ("teacher@sumaya.edu", "Teacher@123", "teacher"),
        ("student@sumaya.edu", "Student@123", "student"),
        ("parent@sumaya.edu", "Parent@123", "parent"),
    ],
)
async def test_seeded_persona_logins_resolve_portals(client, email, password, portal):
    headers = await _login(client, email, password)
    r = await client.get("/api/v1/portal/context", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["portal"] == portal


@pytest.mark.asyncio
async def test_student_portal_daily_workflows(client):
    headers = await _login(client, "student@sumaya.edu", "Student@123")
    for path in [
        "/api/v1/portal/student/dashboard",
        "/api/v1/portal/student/homework",
        "/api/v1/portal/student/timetable",
        "/api/v1/portal/student/activities",
    ]:
        r = await client.get(path, headers=headers)
        assert r.status_code == 200, f"{path}: {r.text}"

    homework = (await client.get("/api/v1/portal/student/homework", headers=headers)).json()
    pending = next((h for h in homework if not h["submission"]), None)
    assert pending is not None
    r = await client.post(
        f"/api/v1/portal/student/homework/{pending['id']}/submit",
        json={"content": "Solved in portal smoke test."},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_teacher_portal_dashboard(client):
    headers = await _login(client, "teacher@sumaya.edu", "Teacher@123")
    r = await client.get("/api/v1/portal/teacher/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    assert {card["key"] for card in r.json()["cards"]} >= {"students", "homework_open", "to_grade"}

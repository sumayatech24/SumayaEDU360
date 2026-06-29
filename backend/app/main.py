"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import init_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eduos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap convenience: ensure tables exist on startup.
    if settings.INIT_DB_ON_STARTUP:
        try:
            await init_models()
            # Keep existing PostgreSQL development/preview databases compatible with
            # additive model changes. Production deployments should run the equivalent
            # versioned migration before traffic is shifted.
            from app.core.database import AsyncSessionLocal
            from app.seed import ensure_runtime_schema
            async with AsyncSessionLocal() as db:
                await ensure_runtime_schema(db)
                await db.commit()
            logger.info("Database tables ensured.")
        except Exception as exc:  # pragma: no cover - startup diagnostics
            logger.warning("Could not initialise tables on startup: %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Multi-tenant Education ERP — AI EduOS. Everything is database-driven.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }

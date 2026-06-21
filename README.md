# SumayaEDU360 — AI EduOS

Multi-tenant **Education ERP** for schools, colleges, coaching institutes and universities.
Built end-to-end from the enterprise requirements backlog (30 modules, 2,100 features, 900 APIs).

> **Everything is database-driven and configurable.** Modules, masters, fields, roles, RBAC,
> menus and reports live in PostgreSQL — there is no hardcoded business data in the UI.

## Architecture

```
┌────────────────────┐      HTTPS/JSON       ┌──────────────────────────┐
│  React + Vite (web)│ ───────────────────▶ │  FastAPI (Python, async) │
│  TanStack Query    │                       │  SQLAlchemy 2.0 + asyncpg│
│  Tailwind, DB-driven│ ◀─────────────────── │  JWT auth · RBAC · Audit │
└────────────────────┘                       └────────────┬─────────────┘
                                                           │
                                                  ┌────────▼─────────┐
                                                  │   PostgreSQL 16  │
                                                  │ multi-tenant data│
                                                  └──────────────────┘
```

### Backend (`/backend`)
- **FastAPI** + **SQLAlchemy 2.0 (async)** + **PostgreSQL**.
- Multi-tenant base model (`tenant_id`, soft-delete, immutable audit columns).
- **JWT auth**, **RBAC** sourced from the requirement matrix, **immutable audit log**.
- **Metadata engine** — `Module`, `EntityDef`, `FieldDef`, `MasterType`, `MasterValue`, `Setting`
  make all 30 modules present, configurable and operable from the database.
- **Typed core domains** — academic config, students, guardians, employees, admissions,
  fees (plan → invoice → payment), attendance, exams/marks, and **student promotion**.
- **Seeder** loads the real module catalog, entities, roles and RBAC parsed from the
  requirements workbook (`app/seed_data/spec.json`).

### Frontend (`/frontend`)
- **React 18 + Vite + TypeScript**, **TanStack Query**, **Tailwind**.
- Navigation, masters, forms and tables are rendered **dynamically from API metadata** —
  nothing about the modules is hardcoded in the client.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
# API   → http://localhost:8000/docs
# Web   → http://localhost:5173
# Login → admin@sumaya.edu / Admin@123   (created by the seeder)
```

## Quick start (local dev)

```bash
# 1. Postgres
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env
python -m app.seed          # creates tables + loads spec + demo data
uvicorn app.main:app --reload

# 3. Frontend
cd ../frontend
npm install
npm run dev
```

## Repository layout

```
SumayaEDU360/
├── backend/            FastAPI service
│   └── app/
│       ├── core/       config, db, security, deps, audit
│       ├── models/     SQLAlchemy models (typed core + metadata engine)
│       ├── schemas/    Pydantic schemas
│       ├── api/v1/     routers (auth, masters, meta, students, fees, …)
│       ├── seed_data/  spec.json extracted from the requirements workbook
│       └── seed.py     idempotent database seeder
├── frontend/           React + Vite client
├── docs/               architecture & spec→code mapping
└── docker-compose.yml
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the module map and extension guide.

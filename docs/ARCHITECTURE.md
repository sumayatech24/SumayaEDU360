# Architecture & Spec → Code Map

SumayaEDU360 implements the **AI EduOS** enterprise backlog (30 modules, 2,100 features,
900 APIs, 16 roles) as a multi-tenant Education ERP. The guiding principle is that **every
module, master, field, role, permission, menu and report is stored in PostgreSQL** — the code
is an engine over that metadata, not a hardcoded set of screens.

## Layers

| Layer | Tech | Responsibility |
|------|------|----------------|
| Web client | React 18 + Vite + TS, TanStack Query, Tailwind | DB-driven navigation, dynamic masters/forms/tables, dashboards |
| API | FastAPI, async SQLAlchemy 2.0 | Auth, RBAC, audit, typed domains, generic engine |
| Data | PostgreSQL 16 | Multi-tenant store; metadata + operational data |

## Two complementary data strategies

1. **Typed core domains** — first-class tables + Pydantic schemas + dedicated routers for the
   entities that carry real business logic:
   academic config, students, guardians, employees, admissions, fees (plan→invoice→payment),
   attendance, exams/marks, promotion. Generated through one `build_crud_router` factory so they
   stay consistent (tenant scope, soft-delete, audit, RBAC).

2. **Metadata engine** — `Module`, `ModuleCapability`, `EntityDef`, `FieldDef`, `MasterType`,
   `MasterValue`, `Setting`, `MenuItem`, `EntityRecord`. Any module entity that isn't promoted to
   a typed table is fully operable through the **generic records API** (`/api/v1/records/{slug}`),
   validated against its `FieldDef` metadata. This is what makes **all 30 modules live from day one**
   and lets new masters/transactions be added with **no code change**.

## Request lifecycle

```
client → JWT bearer → get_current_user → resolves roles → union of permissions
       → require_permission("<module>:<action>")  (superadmin / wildcard aware)
       → handler (tenant-scoped query) → mutation → record_audit() → commit
```

## Spec → code mapping

| Spec sheet | Where it lives |
|-----------|----------------|
| Module_Catalog (30) | `module` table, seeded from `seed_data/spec.json`; nav + `/m/:slug` pages |
| Feature_Backlog_2100 | collapsed to `module_capability` per module (capabilities) |
| Database_Entities | typed models in `app/models/*` + `entity_def`/`field_def` metadata |
| API_Catalog_900 | `/api/v1/...` routers; uniform `<module>/<action>` permission model |
| RBAC_Matrix (16 roles) | `role`, `permission`, `role_permission`; enforced by `require_permission` |
| Reports_Dashboards | `/api/v1/reports/*` aggregates |
| Screen_Catalog | React pages + the generic `ResourcePage`/`ModulePage` |

## Adding a new module/master without code

1. Insert a `module` row (or enable an existing one).
2. Insert an `entity_def` (+ `field_def` rows) for the master/transaction.
3. Add a `menu_item` pointing at `/m/<module-slug>`.
4. The client immediately renders a CRUD screen; data flows through `/records/<entity-slug>`.

## Promoting a generic entity to a typed table

1. Add a SQLAlchemy model + schemas.
2. Register it in `app/api/v1/entities.py` (`_REGISTRY`).
3. Set the matching `entity_def.is_typed = true` and `typed_table`.
4. Map the slug → REST path in `frontend/src/lib/resources.ts`.

## Security & compliance

- Multi-tenant isolation on every query (`tenant_id`).
- Soft-delete (`is_deleted` / `deleted_at`) — records are never hard-deleted.
- Immutable `audit_log` written on every mutation (create/update/delete/login/promote/…).
- RBAC sourced from the requirement matrix; superadmin + `module:*` wildcards supported.

## Roadmap hooks (already scaffolded)

- AI Copilots module present; RAG/agent endpoints can attach under `/api/v1/<module>/...`.
- Integrations module (WhatsApp/SMS/Payment/SSO) modeled as configurable settings.
- Alembic is included for production migrations (bootstrap uses `create_all` + seeder).

# Module Implementation Status

Three implementation tiers:

- **Workflow** — typed tables + lifecycle/state-transition endpoints + dedicated UI.
- **Typed CRUD** — real typed tables with generated schemas; full create/read/update/delete
  that saves, rendered through the dynamic `ResourcePage` (reference dropdowns, master selects).
- **Metadata** — operable via the generic engine (`/records/{slug}`), validated against field
  metadata; ready to be promoted to typed.

Every tier saves to PostgreSQL with tenant isolation, RBAC and audit.

| # | Module | Tier | Notes |
|---|--------|------|-------|
| M001 | Public Website & CMS | Metadata | Pages/banners as records; public site TBD |
| M002 | Admissions CRM | **Workflow** | Pipeline board, stage transitions, convert-to-student |
| M003 | Student Information System | **Workflow** | Students typed CRUD + promotion lifecycle |
| M004 | Parent & Guardian Portal | Typed CRUD | Guardians typed; portal views TBD |
| M005 | Teacher Management | Typed CRUD | via Employees/Teacher; timetable TBD |
| M006 | Employee HRMS | **Workflow** | Employees + leave apply/approve + payroll run |
| M007 | Academic Configuration | Typed CRUD | Years, programs, grades, sections, subjects |
| M008 | Curriculum & Lesson Planning | Metadata | Lesson plans as records |
| M009 | Timetable & Scheduling | Metadata | Periods as records; conflict engine TBD |
| M010 | Attendance | **Workflow** | Bulk marking + daily summary |
| M011 | Homework & Assignments | Metadata | Submissions/grading workflow TBD |
| M012 | Examination Management | **Workflow** | Exams typed + marks entry + report card |
| M013 | Question Paper Management | Metadata | Blueprint/moderation TBD |
| M014 | Report Cards & Transcripts | **Workflow** | Report-card generation + promotion rules |
| M015 | Library Management | **Workflow** | Catalog + issue/return/renew + auto fines |
| M016 | Digital Learning Repository | Metadata | Resources as records |
| M017 | Fees & Billing | **Workflow** | Plans → invoices → payments, ledger, status |
| M018 | Finance & Accounting | Metadata | Ledger/vendors/PO as records; double-entry TBD |
| M019 | Meal & Cafeteria | Metadata | Menus/plans as records |
| M020 | Transport | **Typed CRUD** | Routes, vehicles, stops, student assignments |
| M021 | Hostel | **Workflow** | Blocks, rooms, allocate/vacate + occupancy |
| M022 | Activities & Events | Metadata | Clubs/events as records |
| M023 | PTM & Communication | Metadata | Notifications model present; channels TBD |
| M024 | Knowledge Base | Metadata | Articles as records |
| M025 | Dashboards & Analytics | **Workflow** | Live aggregates (students/fees/attendance) |
| M026 | AI Copilots | Metadata | Module registered; RAG/agents TBD |
| M027 | Mobile Apps | — | API-ready; native apps out of scope here |
| M028 | Security & Compliance | **Workflow** | RBAC matrix, users/roles, immutable audit log |
| M029 | Integrations | Metadata | WhatsApp/SMS/payment/SSO as settings; adapters TBD |
| M030 | Administration & Workflow | Metadata | Tasks/approvals as records |

## How a module is promoted from Metadata → Typed CRUD → Workflow

1. **Typed CRUD**: add a SQLAlchemy model, then one `EntitySpec` in `app/domain.py`
   (fields, references, masters). The dynamic router + seeder pick it up automatically —
   schemas are generated, the entity is flagged typed, the UI renders forms/tables.
2. **Workflow**: add lifecycle endpoints in `app/api/v1/workflows.py` (state transitions,
   domain actions) and a dedicated React page for the verbs (e.g. issue/return, approve).

## Recently completed (this iteration)

- Fixed two save-blocking bugs: PEP 563 stringified body annotations in the CRUD factory
  (caused typed creates to 422), and `Decimal` not being JSON-serializable in audit `changes`
  (caused 500s on any entity with money fields, incl. fees).
- Added typed Library / Transport / Hostel / HR domains with generated schemas.
- Added workflow lifecycles: Admissions pipeline, Library circulation, Hostel allocation,
  HR leave + payroll.
- Reference fields now render as searchable dropdowns; stale catch-all entities removed so
  module tabs show only real entities.

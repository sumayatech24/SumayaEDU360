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
| M001 | Public Website & CMS | **Workflow** | Bespoke screen: pages (Publish/Unpublish) + banners |
| M002 | Admissions CRM | **Workflow** | Pipeline board, stage transitions, convert-to-student |
| M003 | Student Information System | **Workflow** | Students typed CRUD + promotion lifecycle |
| M004 | Parent & Guardian Portal | **Workflow** | Student-360 view plus self-scoped homework, timetable and activities |
| M005 | Teacher Management | Typed CRUD | via Employees; dedicated teacher screen TBD |
| M006 | Employee HRMS | **Workflow** | Employees + leave apply/approve + payroll run |
| M007 | Academic Configuration | Typed CRUD | Years, programs, grades, sections, subjects |
| M008 | Curriculum & Lesson Planning | **Workflow** | Bespoke screen: lesson plans with Start / Complete |
| M009 | Timetable & Scheduling | **Typed CRUD** | Bespoke screen: periods (grade/section/day/slot); conflict engine TBD |
| M010 | Attendance | **Workflow** | Bulk marking + daily summary |
| M011 | Homework & Assignments | **Workflow** | Bespoke screen: homework + submissions + Grade action |
| M012 | Examination Management | **Workflow** | Exams typed + marks entry + report card |
| M013 | Question Paper Management | **Typed CRUD** | Bespoke screen: question bank (type/difficulty/marks); paper builder TBD |
| M014 | Report Cards & Transcripts | **Workflow** | Report-card generation + promotion rules |
| M015 | Library Management | **Workflow** | Catalog + issue/return/renew + auto fines |
| M016 | Digital Learning Repository | **Typed CRUD** | Learning resources (docs/videos/ebooks) by subject/grade |
| M017 | Fees & Billing | **Workflow** | Plans → invoices → payments, ledger, status |
| M018 | Finance & Accounting | **Workflow** | Bespoke screen: ledger, vendors, expenses (Approve/Reject/Pay), PO; +Store/Inventory with Stock In/Out adjusting on-hand |
| M019 | Meal & Cafeteria | **Typed CRUD** | Meal plans + weekly menus typed |
| M020 | Transport | **Typed CRUD** | Routes, vehicles, stops, student assignments |
| M021 | Hostel | **Workflow** | Blocks, rooms, allocate/vacate + occupancy |
| M022 | Activities & Events | **Workflow** | Bespoke screen: activities + capacity-aware registration |
| M023 | PTM & Communication | **Workflow** | Announcements (Publish) + PTM meeting slots/status |
| M024 | Knowledge Base | **Workflow** | Bespoke screen: articles with Publish + digital library |
| M025 | Dashboards & Analytics | **Workflow** | Live dashboard cards + **Reports subsystem (17 reports, CSV export)** |
| M026 | AI Copilots | Metadata | Module registered; RAG/agents TBD |
| M027 | Mobile Apps | — | API-ready; native apps out of scope here |
| M028 | Security & Compliance | **Workflow** | RBAC matrix, users/roles, immutable audit log |
| M029 | Integrations | **Typed CRUD** | Bespoke screen: 10 channel toggles (WhatsApp/SMS/payment/SSO/...) |
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
- Added 17 more typed entities across Homework, Timetable, Lesson Planning, Finance &
  Accounting, **Store/Inventory**, Activities, Meals, Communication and CMS — all saving.
- Added lifecycle endpoints: expense approval, stock movement (adjusts on-hand), homework
  grading, capacity-aware activity registration, announcement publish.
- Added reusable row-actions to the generic grid + a tabbed `Workbench`, then bespoke screens:
  Finance (expense approve/reject/pay), Store/Inventory (stock in/out), Homework (grade),
  Activities, Communication (publish).
- Added typed Digital Library, Knowledge Base, Question Bank and PTM-meeting domains
  (registry now declares 33 typed entities — near-complete coverage of the 30 modules).
- Dashboard enriched with books-issued, pending-leave, expenses-to-approve, low-stock and
  activities cards (rendered dynamically from the reports endpoint).
- **Reporting subsystem**: 17 cross-module reports (catalog + generic runner) with date/flag
  filters and CSV export — student roster, fee defaulters, attendance register, exam results,
  library circulation, hostel occupancy, payroll, inventory, expense ledger, and more.
- Bespoke screens added for Transport, Timetable, Curriculum, Question Bank, Meals,
  Knowledge/Digital Library, CMS (publish), **Parent Portal (Student-360)** and **Integrations**.
- Net: ~27 of 30 modules now ship a dedicated screen; remaining (AI Copilots, Mobile,
  Administration generic) are future-phase by design.
- Added separate student, parent and teacher portal shells selected after login, backed by
  `/portal/context`; student/parent users now see profile, fees, attendance, marks,
  guardians, announcements, homework submission, timetable and activity registration
  without entering the admin ERP. Teacher login gets a role-focused dashboard.

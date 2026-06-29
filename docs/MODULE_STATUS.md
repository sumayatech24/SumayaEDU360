# Module Implementation Status

Three implementation tiers:

- **Workflow** — typed tables + lifecycle/state-transition endpoints + dedicated UI.
- **Typed CRUD** — real typed tables with generated schemas; full create/read/update/delete
  that saves, rendered through the dynamic `ResourcePage` (reference dropdowns, master selects).
- **Metadata** — operable via the generic engine (`/records/{slug}`), validated against field
  metadata; ready to be promoted to typed.

Every tier saves to PostgreSQL with tenant isolation, RBAC and audit.

## Delivery audit — 28 June 2026

The earlier table used **Workflow** too generously: a page with one state-change button is
not the same as an operationally complete module. The codebase is now re-baselined with
four delivery states:

- **End-to-end** — distinct user surfaces, durable domain data, guarded transitions,
  operational workbench, and tested completion path.
- **Functional partial** — useful typed data and one or more workflows exist, but major
  business processes, controls, or exception paths are still absent.
- **CRUD / thin screen** — records can be maintained, but the module is primarily a form
  or generated table rather than a complete business process.
- **Not implemented** — metadata, configuration placeholders, or no product surface.

| Priority | Module | Audited state | Main gaps / next delivery slice |
|---|---|---|---|
| Done first | Admissions CRM | **End-to-end** | Public applicant login/form/tracking; internal continuation application; per-document and eligibility verification; decision; class/section allocation; pre-enrollment fee/receipt; new enrollment or existing-student promotion; capacity guard. |
| P1 | Academic Configuration | CRUD / thin screen | Admission windows, class capacity planning, terms/calendars, subject-class mapping rules, rollover controls. |
| P1 | Fees & Billing | Functional partial | Fee-plan components UI, bulk invoice generation, concessions/scholarships, overdue rules, refunds, online payment reconciliation, cashier close. |
| P1 | Student Information System | Functional partial | Transfer/withdrawal/TC and re-enrollment are now guarded end-to-end with live fee/library/asset/hostel clearance, approval, class restoration, automatic hostel/transport closure, certificate snapshots and profile UI. Remaining: medical/consent vault, alumni lifecycle, duplicate/merge controls. |
| P1 | Examination + Report Cards | Functional partial | Exam schemes, grading rules, moderation, absent/retest handling, consolidated report publishing, transcript history. |
| P1 | Attendance | Functional partial | Timetable-backed sessions, leave/late/half-day rules, correction approval, parent alerts, monthly lock. |
| P2 | Teacher Management | CRUD / thin screen | Recruitment/onboarding, qualifications and compliance, workload planning, substitute allocation, appraisal. |
| P2 | Employee HRMS | Functional partial | Attendance/shift linkage, leave balances/policies, payroll components/statutory deductions, approval and payslip cycle. |
| P2 | Timetable & Scheduling | CRUD / thin screen | Conflict detection, room/resource constraints, substitution, publish/version workflow. |
| P2 | Homework & Assignments | Functional partial | Rubrics, attachments, late/resubmission rules, class-wide grading workbench, notifications. |
| Done | Library Management | **End-to-end core** | Catalog and copy inventory, issue/renew/return/lost handling, circulation and category performance, acquisition requests, vendor purchase orders, approval/order lifecycle, goods receipt and automatic stock/accession creation. Future extension: reservations and configurable member/fine policies. |
| P2 | Transport | CRUD / thin screen | Route planning, stop allocation, capacity, driver trips, attendance, GPS/events, transport billing. |
| Done | Hostel | **End-to-end core** | Class-first student allocation, gender/capacity safeguards, automatic bed inventory, transfer/vacate lifecycle, daily attendance, visitor check-in/out, incidents, occupancy dashboard, and student/parent portal visibility. Future extension: mess and hostel fee linkage. |
| P2 | Finance / Store / Assets | Functional partial | Double-entry posting, budgets, approvals, GRN/vendor bills; purchase-to-stock; asset maintenance/depreciation/disposal. |
| P3 | Parent / Student / Teacher portals | Functional partial | Notifications/inbox, requests and approvals, consent, appointments, richer self-service and mobile-responsive workflow coverage. |
| P3 | Curriculum, Question Bank, Learning Repository | CRUD / thin screen | Curriculum mapping, coverage monitoring, blueprint/paper assembly, review/publish/versioning. |
| P3 | Meals, Activities, PTM, Communication, CMS, Knowledge | CRUD / thin screen or functional partial | Each needs planning, approvals, booking/capacity, payments where relevant, notifications, publication and exception handling. |
| P3 | Dashboards & Analytics | Functional partial | KPI definitions, saved dashboards, drill-through, scheduled reports, data-quality monitoring. |
| P3 | Security & Compliance | Functional partial | Approval policies, segregation of duties, session/device controls, retention/export, security events. |
| P4 | Integrations | Not implemented | Current screen stores toggles only; provider credentials, webhooks, retries, logs, reconciliation and health checks are absent. |
| P4 | AI Copilots | **Functional partial** | Governed role-scoped assistants, versioned/audited sessions, sensitive-data guardrails, explainable admission/absence/fee predictors, feedback/review, and approval-gated idempotent agent proposals are live. Next: external provider/RAG adapters, evaluation sets, cost budgets and write-tool rollback contracts. |
| P4 | Mobile Apps | Not implemented | Native delivery remains separate; API/portal readiness alone is not a mobile app. |
| P4 | Administration & Workflow | Not implemented | Generic metadata records only; needs workflow definitions, approval routing, inbox, SLA/escalation and history. |

The next module should be selected from P1 and completed to the same standard as
Admissions rather than expanding all modules horizontally.

| # | Module | Tier | Notes |
|---|--------|------|-------|
| M001 | Public Website & CMS | **Workflow** | Bespoke screen: pages (Publish/Unpublish) + banners |
| M002 | Admissions CRM | **Workflow** | Pipeline board, stage transitions, convert-to-student |
| M003 | Student Information System | **Workflow** | Students typed CRUD, marks-gated promotion, transfer/withdrawal approval, clearance, TC issuance and re-enrollment |
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
| M021 | Hostel | **End-to-end core** | Blocks/rooms/beds, class-linked allocate/transfer/vacate, attendance, visitors, incidents, occupancy and portal visibility |
| M022 | Activities & Events | **Workflow** | Bespoke screen: activities + capacity-aware registration |
| M023 | PTM & Communication | **Workflow** | Announcements (Publish) + PTM meeting slots/status |
| M024 | Knowledge Base | **Workflow** | Bespoke screen: articles with Publish + digital library |
| M025 | Dashboards & Analytics | **Workflow** | Live dashboard cards + **Reports subsystem (17 reports, CSV export)** |
| M026 | AI Copilots | **Workflow** | Dedicated AI Intelligence workbench; teacher/parent/student/operations assistants; explainable risk register; human feedback/review; agent dry-run, idempotency and approval lifecycle. External LLM/RAG and business write tools remain disabled until configured. |
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
- Net: ~28 of 30 modules now ship a dedicated screen; remaining (Mobile and
  Administration generic) are future-phase by design.
- Added separate student, parent and teacher portal shells selected after login, backed by
  `/portal/context`; student/parent users now see profile, fees, attendance, marks,
  guardians, announcements, homework submission, timetable and activity registration
  without entering the admin ERP. Teacher login gets a role-focused dashboard.

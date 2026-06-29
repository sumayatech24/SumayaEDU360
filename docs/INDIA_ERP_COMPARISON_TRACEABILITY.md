# India School ERP Comparison — Product Traceability

Source: `India_School_ERP_Feature_Comparison.xlsx` (received 29 June 2026).

## Completion rule

A feature is **complete** only when it has tenant-scoped durable data, guarded business
transitions, role/record-level authorization, audit events, a usable web surface, reporting
or operational visibility, and automated verification. A menu item, metadata record, or
generic CRUD table is not treated as completion.

Status values:

- **E2E** — the core completion path is implemented and tested.
- **Partial** — useful operational behavior exists, but material prompt requirements remain.
- **Thin** — typed CRUD or a narrow screen exists without the full workflow.
- **Missing** — no production workflow.

## Workbook row audit

| # | Category | Workbook feature | AI opportunity | Current state | Verified implementation evidence | Required next slice |
|---:|---|---|---|---|---|---|
| 1 | Admissions | Online admission & enquiry | AI lead scoring | E2E / AI missing | Public applicant registration, application, document/check verification, placement, decision, fee receipt, enrollment; `test_complete_new_admission_lifecycle` | Lead scoring, counselor prioritization, explainability and drift review |
| 2 | Student | Student information system | Student insights | Partial | Typed Student/Guardian records, Student 360, portal scoping, academic/discipline/assets history | Transfer/withdrawal/TC, merge, consent/medical vault, insight review |
| 3 | Academics | Attendance | Absence prediction | Partial | Bulk marking, methods, summaries, portal visibility | Session timetable linkage, correction approval, monthly lock, alerts, prediction |
| 4 | Academics | Timetable | AI timetable optimization | Thin | Typed periods and timetable screen | Constraint engine, conflict detection, version/approval/publish, optimization |
| 5 | Academics | Homework & assignments | Auto generation | Partial | Homework, submission and grading workflows | Rubrics, attachments, resubmission/late policy, bulk grading, generation |
| 6 | Exams | Exam management | AI question paper | Partial | Exams, marks entry, review/publish lifecycle, promotion eligibility | Schemes, moderation, absent/retest, blueprint-based paper generation |
| 7 | Exams | Report cards | Narrative reports | Partial | Published marks, report-card and cumulative result APIs | Consolidated template publishing, transcripts, AI narrative with approval |
| 8 | Finance | Fee management | Fee default prediction | Partial | Plans/components/installments, assignment, invoices, aid, dues/reminders, payments | Concessions/refunds, aging policy, cashier close, default prediction |
| 9 | Finance | Online payments | Payment assistant | Partial | Payment records and UPI/gateway method capture | Provider checkout, webhook signature/idempotency, reconciliation/refunds |
| 10 | Communication | SMS/Email | AI message drafting | Partial | Announcements, reminders and notification records | Provider delivery workers, retries, templates, consent/quiet hours, drafting |
| 11 | Communication | WhatsApp | AI chatbot | Thin | Channel configuration and queued reminder records | Meta provider, template approval, webhooks, opt-in, delivery log, chatbot |
| 12 | Transport | Bus tracking | Route optimization | Thin | Routes, stops, vehicles and student assignments | Trips, capacity, GPS pings/geofence/ETA, attendance, incidents, optimization |
| 13 | Library | Library management | Book recommendations | E2E core | Catalog/copies, circulation, acquisitions, PO approval/order/receipt and stock update tests | Reservations/policy extensions and personalized recommendations |
| 14 | Hostel | Hostel management | Occupancy analytics | E2E core | Bed inventory, allocation/transfer/vacate, attendance, visitors, incidents, portal view | Mess/fee linkage, predictive capacity planning |
| 15 | HR | Payroll & HR | AI leave assistant | Partial | Employees, leave apply/approve and payroll run | Policies/balances, shifts/attendance, statutory payroll, payslips, assistant |
| 16 | Analytics | Dashboards | Predictive analytics | Partial | Live KPI cards and 17 exportable reports | KPI governance, saved/scheduled dashboards, drill-through and forecasting |
| 17 | AI | AI teacher assistant | Major differentiator | Missing | Metadata capability only | Governed assistant, generation tools, citations, review, evaluation and audit |
| 18 | AI | AI parent chatbot | Major differentiator | Missing | Metadata capability only | Child-scoped retrieval, consent, safe answers, escalation and audit |
| 19 | AI | AI student tutor | Major differentiator | Missing | Metadata capability only | Curriculum-grounded tutoring, safety controls, progress and teacher visibility |
| 20 | AI | Agentic workflow automation | Major differentiator | Missing | Metadata capability only | Tool allow-list, approval gates, dry run, idempotency, rollback and run history |

## Prompt compatibility gates applied to every module

Each module delivery must include: purpose and role matrix; feature rules and validations;
happy/approval/escalation/cancel/rollback/reopen/audit paths; complete screens and forms;
tables, constraints, indexes, history and soft-delete; authenticated REST APIs with errors,
filtering and pagination; reports/KPIs/exports; notification templates and retries; RBAC plus
field/screen/record/export/print rights; applicable AI with human review; encryption, session,
retention and compliance controls; provider integration contracts; responsive/mobile behavior;
configuration and custom fields; edge cases; positive/negative/boundary/performance/security
tests; and deploy/monitor/runbook artifacts.

This register is updated only from verified code and tests. Pricing in the source workbook is
market context and is not an implementation requirement.

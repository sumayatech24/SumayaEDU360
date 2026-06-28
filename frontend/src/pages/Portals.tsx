import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Icon } from "../components/Icon";
import { PortalShell } from "../components/PortalShell";
import { api, apiError } from "../lib/api";
import { useBranding } from "../lib/branding";
import { printMarksheet } from "../lib/print";
import { ContinuingAdmission } from "./ContinuingAdmission";

const inr = (v?: string | number) => "₹" + Number(v ?? 0).toLocaleString("en-IN");

interface Dash {
  student: Record<string, any>;
  persona?: string;
  guardians: { name: string; relation: string; phone?: string; email?: string }[];
  fees: { billed?: string; paid?: string; balance: string; invoices?: number; pending?: boolean };
  invoices?: { invoice_no: string; net: string; paid: string; status: string; due_date?: string }[];
  payments?: { id: string; receipt_no: string; amount: string; method: string; paid_at?: string }[];
  attendance: Record<string, number>;
  marks: { exam: string; subject: string; marks: string; max: string; grade?: string }[];
  assets?: { type: string; name: string; quantity: number; status: string; issue_date?: string; due_date?: string }[];
  achievements?: { title: string; category?: string; level?: string; date?: string }[];
  activities?: { name: string; status: string; date?: string }[];
  hostel?: {
    block: string; room: string; bed: string; warden?: string; allocated_since?: string;
    recent_attendance: { date: string; status: string; remarks?: string }[];
  } | null;
  remarks?: { type: string; remark: string; by?: string; date?: string }[];
  announcements: { title: string; body?: string; date?: string }[];
}

/** Open a printable fee receipt in a new window. */
function printReceipt(studentName: string, p: { receipt_no: string; amount: string; method: string; paid_at?: string }) {
  const w = window.open("", "_blank", "width=520,height=640");
  if (!w) return;
  w.document.write(`
    <html><head><title>Receipt ${p.receipt_no}</title>
    <style>body{font-family:system-ui,sans-serif;padding:32px;color:#1e293b}
    h1{font-size:18px;margin:0}.muted{color:#64748b;font-size:12px}
    table{width:100%;border-collapse:collapse;margin-top:20px;font-size:14px}
    td{padding:8px 0;border-bottom:1px solid #e2e8f0}.r{text-align:right}
    .total{font-size:20px;font-weight:700;margin-top:16px}</style></head>
    <body>
      <h1>SumayaEDU360 — Fee Receipt</h1>
      <div class="muted">Receipt No: ${p.receipt_no}</div>
      <table>
        <tr><td>Student</td><td class="r">${studentName}</td></tr>
        <tr><td>Date</td><td class="r">${p.paid_at ?? "—"}</td></tr>
        <tr><td>Method</td><td class="r">${p.method.toUpperCase()}</td></tr>
      </table>
      <div class="total">Amount Paid: ₹${Number(p.amount).toLocaleString("en-IN")}</div>
      <p class="muted" style="margin-top:32px">This is a computer-generated receipt.</p>
      <script>window.print()</script>
    </body></html>`);
  w.document.close();
}

interface HomeworkItem {
  id: string;
  title: string;
  description?: string;
  subject: string;
  due_date?: string;
  max_marks: string;
  submission?: {
    status: string;
    submitted_date?: string;
    marks_awarded?: string | null;
    remarks?: string | null;
    content?: string | null;
  } | null;
}

interface TimetablePeriod {
  id: string;
  day: string;
  period_no: number;
  subject: string;
  room?: string;
  start_time?: string;
  end_time?: string;
}

interface ActivityItem {
  id: string;
  name: string;
  activity_type?: string;
  coordinator?: string;
  start_date?: string;
  fee: string;
  capacity: number;
  registered_count: number;
  registered: boolean;
}

function useStudentDash() {
  return useQuery({
    queryKey: ["portal-student-dash"],
    queryFn: async () => (await api.get<Dash>("/portal/student/dashboard")).data,
  });
}

function AnnouncementsCard({ items }: { items: { title: string; body?: string; date?: string }[] }) {
  return (
    <div className="card p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-600">Announcements</h3>
      {(!items || items.length === 0) && <p className="text-sm text-slate-400">Nothing new.</p>}
      <div className="space-y-3">
        {items?.map((a, i) => (
          <div key={i} className="border-l-2 border-brand-400 pl-3">
            <div className="text-sm font-medium">{a.title}</div>
            {a.body && <div className="text-xs text-slate-500">{a.body}</div>}
            {a.date && <div className="text-[11px] text-slate-400">{a.date}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function Student360View({ childView }: { childView?: boolean }) {
  const { data, isLoading } = useStudentDash();
  const brand = useBranding();
  if (isLoading) return <div className="text-slate-400">Loading…</div>;
  if (!data) return <div className="text-slate-400">No data.</div>;

  const attTotal = Object.values(data.attendance).reduce((a, b) => a + b, 0);
  const present = data.attendance.present ?? 0;
  const pct = attTotal ? Math.round((present / attTotal) * 100) : 0;

  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center gap-5 p-5">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-2xl font-bold text-brand-700">
          {data.student.name?.[0]}
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-400">
            {childView ? "Your child" : "Welcome back"}
          </div>
          <div className="text-xl font-semibold">{data.student.name}</div>
          <div className="text-sm text-slate-400">
            {data.student.admission_no} · Grade {data.student.grade} · Section {data.student.section}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="card p-5">
          <h3 className="mb-1 text-sm font-semibold text-slate-600">Fees</h3>
          {childView ? (
            <>
              <div className="text-3xl font-semibold text-amber-600">{inr(data.fees.balance)}</div>
              <div className="text-xs text-slate-400">
                balance · billed {inr(data.fees.billed)} · paid {inr(data.fees.paid)}
              </div>
            </>
          ) : data.fees.pending ? (
            <>
              <div className="text-2xl font-semibold text-amber-600">Payment due</div>
              <div className="mt-1 text-xs text-slate-400">Please ask a parent/guardian to clear pending fees.</div>
            </>
          ) : (
            <>
              <div className="text-2xl font-semibold text-emerald-600">All clear ✓</div>
              <div className="mt-1 text-xs text-slate-400">No pending fees.</div>
            </>
          )}
        </div>
        <div className="card p-5">
          <h3 className="mb-1 text-sm font-semibold text-slate-600">Attendance</h3>
          <div className="text-3xl font-semibold text-indigo-600">{pct}%</div>
          <div className="text-xs text-slate-400">
            present {present}/{attTotal} days
          </div>
        </div>
        <AnnouncementsCard items={data.announcements} />
      </div>

      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-600">Hostel & Residence</h3>
            {data.hostel ? (
              <p className="mt-1 text-lg font-semibold">{data.hostel.block} · Room {data.hostel.room} · Bed {data.hostel.bed}</p>
            ) : <p className="mt-1 text-sm text-slate-400">No active hostel allocation.</p>}
          </div>
          {data.hostel && <div className="text-right text-xs text-slate-500">
            <div>Warden: {data.hostel.warden || "—"}</div>
            <div>Allocated since: {data.hostel.allocated_since || "—"}</div>
          </div>}
        </div>
        {data.hostel && data.hostel.recent_attendance.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {data.hostel.recent_attendance.map((item) => (
              <span key={item.date} className={`badge ${item.status === "present" ? "bg-emerald-50 text-emerald-700" : item.status === "leave" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700"}`}>
                {item.date}: {item.status}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <span className="text-sm font-semibold text-slate-600">Exam Results</span>
          {data.marks.length > 0 && (
            <button
              className="btn-ghost px-2.5 py-1 text-xs text-brand-600"
              onClick={() => printMarksheet(brand.institution_name, data.student as any, data.marks)}
            >
              Download Marksheet
            </button>
          )}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Exam</th>
              <th className="px-4 py-3">Subject</th>
              <th className="px-4 py-3">Marks</th>
              <th className="px-4 py-3">Grade</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.marks.map((m, i) => (
              <tr key={i} className="hover:bg-slate-50">
                <td className="px-4 py-2.5">{m.exam}</td>
                <td className="px-4 py-2.5">{m.subject}</td>
                <td className="px-4 py-2.5">
                  {m.marks} / {m.max}
                </td>
                <td className="px-4 py-2.5">{m.grade || "—"}</td>
              </tr>
            ))}
            {data.marks.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  No results published yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">Assets & Library Holdings</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">Due</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.assets?.map((a, i) => (
              <tr key={i}>
                <td className="px-4 py-2.5 capitalize">{a.type}</td>
                <td className="px-4 py-2.5">{a.name}</td>
                <td className="px-4 py-2.5">{a.quantity}</td>
                <td className="px-4 py-2.5">{a.due_date || "--"}</td>
              </tr>
            ))}
            {(!data.assets || data.assets.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No issued assets.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {childView && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold text-slate-600">Fee Payments & Receipts</span>
            <span className="text-xs text-slate-400">Balance due {inr(data.fees.balance)}</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Receipt No</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Method</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.payments?.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-medium">{p.receipt_no}</td>
                  <td className="px-4 py-2.5">{p.paid_at || "—"}</td>
                  <td className="px-4 py-2.5 uppercase">{p.method}</td>
                  <td className="px-4 py-2.5">{inr(p.amount)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button className="btn-ghost px-2.5 py-1 text-xs text-brand-600" onClick={() => printReceipt(data.student.name, p)}>
                      Download Receipt
                    </button>
                  </td>
                </tr>
              ))}
              {(!data.payments || data.payments.length === 0) && (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No payments yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function GuardiansResults() {
  const { data } = useStudentDash();
  return (
    <div className="card p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-600">Guardians</h3>
      {data?.guardians.map((g, i) => (
        <div key={i} className="mb-2 text-sm">
          <span className="font-medium">{g.name}</span>
          <span className="ml-2 text-xs capitalize text-slate-400">{g.relation}</span>
          <div className="text-xs text-slate-400">{g.phone || g.email || "—"}</div>
        </div>
      ))}
      {(!data?.guardians || data.guardians.length === 0) && <p className="text-sm text-slate-400">None on record.</p>}
    </div>
  );
}

function HomeworkList({ readonly = false }: { readonly?: boolean }) {
  const query = useQuery({
    queryKey: ["portal-homework"],
    queryFn: async () => (await api.get<HomeworkItem[]>("/portal/student/homework")).data,
  });

  async function submit(id: string) {
    await api.post(`/portal/student/homework/${id}/submit`, {
      content: "Submitted from the student portal.",
    });
    await query.refetch();
  }

  return (
    <div className="space-y-3">
      {query.data?.map((hw) => (
        <div key={hw.id} className="card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">{hw.title}</div>
              <div className="text-xs text-slate-400">
                {hw.subject} · due {hw.due_date || "not set"} · {hw.max_marks} marks
              </div>
              {hw.description && <p className="mt-2 text-sm text-slate-500">{hw.description}</p>}
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium capitalize text-slate-600">
              {hw.submission?.status || "pending"}
            </span>
          </div>
          {hw.submission?.marks_awarded && (
            <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
              Graded: {hw.submission.marks_awarded}/{hw.max_marks}
              {hw.submission.remarks ? ` · ${hw.submission.remarks}` : ""}
            </div>
          )}
          {!readonly && !hw.submission && (
            <button
              type="button"
              onClick={() => void submit(hw.id)}
              className="mt-3 rounded-lg bg-brand-600 px-3 py-2 text-xs font-medium text-white hover:bg-brand-700"
            >
              Submit
            </button>
          )}
        </div>
      ))}
      {query.isLoading && <div className="text-sm text-slate-400">Loading...</div>}
      {!query.isLoading && (!query.data || query.data.length === 0) && (
        <div className="card p-5 text-sm text-slate-400">No homework assigned.</div>
      )}
    </div>
  );
}

function TimetableView() {
  const { data, isLoading } = useQuery({
    queryKey: ["portal-timetable"],
    queryFn: async () => (await api.get<TimetablePeriod[]>("/portal/student/timetable")).data,
  });
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Day</th>
            <th className="px-4 py-3">Period</th>
            <th className="px-4 py-3">Subject</th>
            <th className="px-4 py-3">Time</th>
            <th className="px-4 py-3">Room</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data?.map((p) => (
            <tr key={p.id}>
              <td className="px-4 py-2.5">{p.day}</td>
              <td className="px-4 py-2.5">{p.period_no}</td>
              <td className="px-4 py-2.5">{p.subject}</td>
              <td className="px-4 py-2.5">
                {p.start_time || "--"} - {p.end_time || "--"}
              </td>
              <td className="px-4 py-2.5">{p.room || "--"}</td>
            </tr>
          ))}
          {!isLoading && (!data || data.length === 0) && (
            <tr>
              <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                No timetable published.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ActivitiesView({ readonly = false }: { readonly?: boolean }) {
  const query = useQuery({
    queryKey: ["portal-activities"],
    queryFn: async () => (await api.get<ActivityItem[]>("/portal/student/activities")).data,
  });

  async function register(id: string) {
    await api.post(`/portal/student/activities/${id}/register`);
    await query.refetch();
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {query.data?.map((a) => (
        <div key={a.id} className="card p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold">{a.name}</div>
              <div className="text-xs capitalize text-slate-400">
                {a.activity_type || "activity"} · {a.start_date || "date TBD"}
              </div>
              <div className="mt-2 text-xs text-slate-500">
                Coordinator {a.coordinator || "--"} · {a.registered_count}/{a.capacity || "open"} enrolled · {inr(a.fee)}
              </div>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
              a.registered ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
            }`}>
              {a.registered ? "Registered" : "Open"}
            </span>
          </div>
          {!readonly && !a.registered && (
            <button
              type="button"
              onClick={() => void register(a.id)}
              className="mt-4 rounded-lg bg-brand-600 px-3 py-2 text-xs font-medium text-white hover:bg-brand-700"
            >
              Register
            </button>
          )}
        </div>
      ))}
      {query.isLoading && <div className="text-sm text-slate-400">Loading...</div>}
      {!query.isLoading && (!query.data || query.data.length === 0) && (
        <div className="card p-5 text-sm text-slate-400">No activities open.</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Student portal
export function StudentPortal() {
  return (
    <PortalShell
      portal="student"
      nav={[
        { label: "My Dashboard", icon: "grid", to: "" },
        { label: "Homework", icon: "edit", to: "homework" },
        { label: "Timetable", icon: "table", to: "timetable" },
        { label: "Activities", icon: "activity", to: "activities" },
        { label: "Next Admission", icon: "school", to: "admission" },
        { label: "Profile", icon: "users", to: "profile" },
      ]}
    >
      <Routes>
        <Route index element={<Student360View />} />
        <Route path="homework" element={<HomeworkList />} />
        <Route path="timetable" element={<TimetableView />} />
        <Route path="activities" element={<ActivitiesView />} />
        <Route path="admission" element={<ContinuingAdmission />} />
        <Route path="profile" element={<GuardiansResults />} />
        <Route path="*" element={<Navigate to="" replace />} />
      </Routes>
    </PortalShell>
  );
}

// ---------------------------------------------------------------- Parent portal
export function ParentPortal() {
  return (
    <PortalShell
      portal="parent"
      nav={[
        { label: "My Child", icon: "users", to: "" },
        { label: "Homework", icon: "edit", to: "homework" },
        { label: "Timetable", icon: "table", to: "timetable" },
        { label: "Activities", icon: "activity", to: "activities" },
        { label: "Guardians", icon: "shield", to: "guardians" },
      ]}
    >
      <Routes>
        <Route index element={<Student360View childView />} />
        <Route path="homework" element={<HomeworkList readonly />} />
        <Route path="timetable" element={<TimetableView />} />
        <Route path="activities" element={<ActivitiesView readonly />} />
        <Route path="guardians" element={<GuardiansResults />} />
        <Route path="*" element={<Navigate to="" replace />} />
      </Routes>
    </PortalShell>
  );
}

// ---------------------------------------------------------------- Teacher portal
interface TeacherDash {
  teacher: { name: string; designation?: string; department?: string; email?: string; phone?: string } | null;
  profile?: { expertise?: string; certifications?: string; subjects_can_teach?: string; qualification?: string } | null;
  assignments?: { id: string; grade: string; section: string; subject: string }[];
  cards: { key: string; label: string; value: number; icon: string }[];
  announcements: { title: string; body?: string; date?: string }[];
}

function TeacherHome() {
  const { data } = useQuery({
    queryKey: ["portal-teacher-dash"],
    queryFn: async () => (await api.get<TeacherDash>("/portal/teacher/dashboard")).data,
  });
  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="text-[11px] uppercase tracking-wide text-slate-400">Welcome</div>
        <div className="text-xl font-semibold">{data?.teacher?.name ?? "Teacher"}</div>
        <div className="text-sm text-slate-400">
          {data?.teacher?.designation} {data?.teacher?.department ? `· ${data.teacher.department}` : ""}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-600">Profile</h3>
          <div className="space-y-2 text-sm text-slate-600">
            <div><span className="font-medium">Qualification:</span> {data?.profile?.qualification || "--"}</div>
            <div><span className="font-medium">Expertise:</span> {data?.profile?.expertise || "--"}</div>
            <div><span className="font-medium">Can teach:</span> {data?.profile?.subjects_can_teach || "--"}</div>
            <div><span className="font-medium">Certifications:</span> {data?.profile?.certifications || "--"}</div>
          </div>
        </div>
        <div className="card p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-600">Class Assignments</h3>
          <div className="space-y-2">
            {data?.assignments?.map((a) => (
              <div key={a.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <span className="font-medium">{a.subject}</span>
                <span className="ml-2 text-slate-400">{a.grade} / {a.section}</span>
              </div>
            ))}
            {(!data?.assignments || data.assignments.length === 0) && <div className="text-sm text-slate-400">No assignments mapped.</div>}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {data?.cards.map((c) => (
          <div key={c.key} className="card flex items-center gap-4 p-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-50 text-orange-600">
              <Icon name={c.icon} />
            </div>
            <div>
              <div className="text-2xl font-semibold">{c.value}</div>
              <div className="text-xs text-slate-400">{c.label}</div>
            </div>
          </div>
        ))}
      </div>
      <AnnouncementsCard items={data?.announcements ?? []} />
    </div>
  );
}

function TeacherStudents() {
  const { data } = useQuery({
    queryKey: ["portal-teacher-students"],
    queryFn: async () => (await api.get<any[]>("/portal/teacher/students")).data,
  });
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Admission No</th>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Grade</th>
            <th className="px-4 py-3">Section</th>
            <th className="px-4 py-3">Contact</th>
            <th className="px-4 py-3">Govt ID</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data?.map((s) => (
            <tr key={s.id} className="hover:bg-slate-50">
              <td className="px-4 py-2.5">{s.admission_no}</td>
              <td className="px-4 py-2.5 font-medium">{s.name}</td>
              <td className="px-4 py-2.5">{s.grade}</td>
              <td className="px-4 py-2.5">{s.section}</td>
              <td className="px-4 py-2.5 text-xs text-slate-500">{s.phone || s.email || "--"}</td>
              <td className="px-4 py-2.5 text-xs">{s.government_id_type ? `${s.government_id_type}: ${s.government_id_masked}` : "--"}</td>
              <td className="px-4 py-2.5">{s.status}</td>
            </tr>
          ))}
          {(!data || data.length === 0) && (
            <tr>
              <td colSpan={7} className="px-4 py-6 text-center text-slate-400">No students.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function TeacherSubmissions() {
  const query = useQuery({
    queryKey: ["portal-teacher-submissions"],
    queryFn: async () => (await api.get<any[]>("/portal/teacher/submissions")).data,
  });
  async function grade(id: string) {
    const marks = prompt("Marks awarded:");
    if (marks === null) return;
    await api.post(`/portal/teacher/submissions/${id}/grade`, { marks_awarded: Number(marks) });
    await query.refetch();
  }
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Homework</th>
            <th className="px-4 py-3">Student</th>
            <th className="px-4 py-3">Submitted</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Marks</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {query.data?.map((s) => (
            <tr key={s.id} className="hover:bg-slate-50">
              <td className="px-4 py-2.5">{s.homework}</td>
              <td className="px-4 py-2.5 font-medium">{s.student}</td>
              <td className="px-4 py-2.5">{s.submitted_date || "—"}</td>
              <td className="px-4 py-2.5">
                <span className={`badge ${s.status === "graded" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}>
                  {s.status}
                </span>
              </td>
              <td className="px-4 py-2.5">{s.marks_awarded ?? "—"}</td>
              <td className="px-4 py-2.5 text-right">
                {s.status !== "graded" && (
                  <button className="btn-primary px-2.5 py-1 text-xs" onClick={() => void grade(s.id)}>
                    Grade
                  </button>
                )}
              </td>
            </tr>
          ))}
          {(!query.data || query.data.length === 0) && (
            <tr>
              <td colSpan={6} className="px-4 py-6 text-center text-slate-400">No submissions yet.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const SCHED_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function TeacherSchedule() {
  const { data } = useQuery({
    queryKey: ["portal-teacher-schedule"],
    queryFn: async () => (await api.get<{ classes: any[]; exams: any[] }>("/portal/teacher/schedule")).data,
  });
  const classes = data?.classes ?? [];
  const periods = [...new Set(classes.map((c) => c.period_no))].sort((a, b) => a - b);
  const cell = (day: string, period: number) => classes.find((c) => c.day === day && c.period_no === period);

  return (
    <div className="space-y-5">
      <div className="card overflow-x-auto">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">Weekly Timetable</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Period</th>
              {SCHED_DAYS.map((d) => (
                <th key={d} className="px-4 py-3">{d.slice(0, 3)}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {periods.map((p) => (
              <tr key={p}>
                <td className="px-4 py-3 font-medium text-slate-500">P{p}</td>
                {SCHED_DAYS.map((d) => {
                  const c = cell(d, p);
                  return (
                    <td key={d} className="px-2 py-2 align-top">
                      {c ? (
                        <div className="rounded-lg bg-orange-50 px-2.5 py-1.5">
                          <div className="text-xs font-semibold text-orange-700">{c.subject}</div>
                          <div className="text-[11px] text-slate-500">{c.grade}/{c.section}{c.room ? ` · ${c.room}` : ""}</div>
                          {c.start_time && <div className="text-[10px] text-slate-400">{c.start_time}–{c.end_time}</div>}
                        </div>
                      ) : (
                        <span className="text-slate-200">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
            {periods.length === 0 && (
              <tr>
                <td colSpan={SCHED_DAYS.length + 1} className="px-4 py-8 text-center text-slate-400">
                  No timetable periods assigned yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">Exam Duties</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Exam</th><th className="px-4 py-3">Subject</th><th className="px-4 py-3">Class</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Room</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.exams.map((e) => (
              <tr key={e.id}><td className="px-4 py-2.5">{e.exam}</td><td className="px-4 py-2.5">{e.subject}</td><td className="px-4 py-2.5">{e.grade}/{e.section}</td><td className="px-4 py-2.5">{e.date || "--"}</td><td className="px-4 py-2.5">{e.room || "--"}</td></tr>
            ))}
            {(!data?.exams || data.exams.length === 0) && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No exam duties.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TeacherMarksReview() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({
    queryKey: ["portal-teacher-marks-review"],
    queryFn: async () => (await api.get<any[]>("/portal/teacher/marks-review")).data,
  });
  const sheet = useQuery({
    queryKey: ["portal-teacher-marks-review-sheet", selected],
    enabled: !!selected,
    queryFn: async () => (await api.get<any>(`/portal/teacher/marks-review/${selected}`)).data,
  });

  async function review(decision: "approved" | "rejected") {
    if (!selected) return;
    if (decision === "rejected" && !note.trim()) {
      setError("Please enter a reason before returning marks to the teacher.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post(`/portal/teacher/marks-review/${selected}`, { decision, review_note: note.trim() || null });
      setSelected("");
      setNote("");
      await qc.invalidateQueries({ queryKey: ["portal-teacher-marks-review"] });
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3">
          <h2 className="font-semibold">HOD Marks Approval</h2>
          <p className="text-xs text-slate-400">Open a submitted class marksheet, verify the complete roster, then approve or return it.</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Exam</th><th className="px-4 py-3">Subject</th><th className="px-4 py-3">Class</th><th className="px-4 py-3">Status</th><th className="px-4 py-3"></th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.map((b) => (
              <tr key={b.id} className={selected === b.id ? "bg-indigo-50" : ""}>
                <td className="px-4 py-2.5">{b.exam}</td><td className="px-4 py-2.5">{b.subject}</td>
                <td className="px-4 py-2.5">{b.grade}/{b.section}</td>
                <td className="px-4 py-2.5 capitalize">{b.status}</td>
                <td className="px-4 py-2.5 text-right"><button className="btn-ghost" onClick={() => { setSelected(b.id); setNote(b.review_note || ""); }}>Review</button></td>
              </tr>
            ))}
            {(!data || data.length === 0) && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No marks batches assigned for review.</td></tr>}
          </tbody>
        </table>
      </div>
      {selected && (
        <div className="card overflow-hidden">
          <div className="border-b border-slate-100 px-4 py-3 font-semibold">Complete class marksheet</div>
          <div className="max-h-[430px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-4 py-3">Roll</th><th className="px-4 py-3">Student</th><th className="px-4 py-3">Marks</th><th className="px-4 py-3">Grade</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sheet.data?.rows.map((r: any) => (
                  <tr key={r.student_id}><td className="px-4 py-2.5">{r.roll_no || r.admission_no}</td><td className="px-4 py-2.5 font-medium">{r.student_name}</td><td className="px-4 py-2.5">{r.is_absent ? "Absent" : `${r.marks_obtained} / ${r.max_marks}`}</td><td className="px-4 py-2.5">{r.grade || "--"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {sheet.data?.status === "submitted" && (
            <div className="space-y-3 border-t border-slate-100 p-4">
              <label><span className="label">HOD note</span><textarea className="input min-h-20" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional for approval; required when returning" /></label>
              {error && <div className="text-sm text-rose-600">{error}</div>}
              <div className="flex gap-2">
                <button className="btn-primary" disabled={busy} onClick={() => void review("approved")}>Approve & lock marks</button>
                <button className="btn-ghost border border-rose-200 text-rose-600" disabled={busy} onClick={() => void review("rejected")}>Return to teacher</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Teacher: quarterly planning
interface TopicRow { name: string; weeks?: string; hours?: number; status: string }
interface Plan {
  id: string; title: string; term: string; academic_year_id?: string | null;
  grade_id?: string | null; section_id?: string | null; subject_id?: string | null;
  grade: string; section: string; subject: string;
  objectives?: string; resources?: string; topics: TopicRow[];
  completion_percent: number; status: string; teacher: string;
  reviewer?: string | null; reviewer_id?: string | null; review_note?: string | null;
}
interface PlanOptions {
  terms: string[];
  academic_years: { id: string; name: string; is_current: boolean }[];
  classes: { grade_id?: string | null; section_id?: string | null; subject_id?: string | null; grade: string; section: string; subject: string }[];
  reviewers: { id: string; name: string; designation?: string }[];
}

const TOPIC_STATUS = ["pending", "in_progress", "done"];
const STATUS_BADGE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600", submitted: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700", rejected: "bg-rose-50 text-rose-700",
  in_progress: "bg-indigo-50 text-indigo-700", completed: "bg-emerald-50 text-emerald-700",
};

const emptyForm = () => ({
  title: "", term: "Quarter 1", academic_year_id: "", classKey: "",
  objectives: "", resources: "",
  topics: [{ name: "", weeks: "", hours: undefined as number | undefined, status: "pending" }] as TopicRow[],
});

function TeacherPlans() {
  const qc = useQueryClient();
  const { data: options } = useQuery({
    queryKey: ["teacher-plan-options"],
    queryFn: async () => (await api.get<PlanOptions>("/portal/teacher/plan-options")).data,
  });
  const { data: plans } = useQuery({
    queryKey: ["teacher-plans"],
    queryFn: async () => (await api.get<Plan[]>("/portal/teacher/plans")).data,
  });
  const [form, setForm] = useState(emptyForm());
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["teacher-plans"] });

  function classKeyFor(p: Plan) {
    return [p.grade_id ?? "", p.section_id ?? "", p.subject_id ?? ""].join("|");
  }
  function loadIntoForm(p: Plan) {
    setEditing(p.id);
    setForm({
      title: p.title, term: p.term, academic_year_id: p.academic_year_id ?? "",
      classKey: classKeyFor(p), objectives: p.objectives ?? "", resources: p.resources ?? "",
      topics: p.topics.length ? p.topics : emptyForm().topics,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function reset() { setEditing(null); setForm(emptyForm()); setError(""); }

  async function save() {
    setError("");
    const [grade_id, section_id, subject_id] = form.classKey.split("|");
    const body = {
      title: form.title, term: form.term,
      academic_year_id: form.academic_year_id || null,
      grade_id: grade_id || null, section_id: section_id || null, subject_id: subject_id || null,
      objectives: form.objectives || null, resources: form.resources || null,
      topics: form.topics.filter((t) => t.name.trim()),
    };
    try {
      if (editing) await api.put(`/portal/teacher/plans/${editing}`, body);
      else await api.post("/portal/teacher/plans", body);
      reset();
      refresh();
    } catch (e) { setError(apiError(e)); }
  }
  async function submitPlan(p: Plan) {
    const reviewers = options?.reviewers ?? [];
    let reviewer_id = p.reviewer_id ?? "";
    if (!reviewer_id) {
      const choices = reviewers.map((r, i) => `${i + 1}. ${r.name}${r.designation ? ` (${r.designation})` : ""}`).join("\n");
      const pick = prompt(`Submit "${p.title}" for approval.\nChoose a reviewer:\n${choices}`);
      if (pick === null) return;
      const idx = Number(pick) - 1;
      if (!reviewers[idx]) { alert("Invalid reviewer."); return; }
      reviewer_id = reviewers[idx].id;
    }
    try {
      await api.post(`/portal/teacher/plans/${p.id}/submit`, { reviewer_id });
      refresh();
    } catch (e) { alert(apiError(e)); }
  }
  async function del(p: Plan) {
    if (!confirm(`Delete "${p.title}"?`)) return;
    try { await api.delete(`/portal/teacher/plans/${p.id}`); refresh(); } catch (e) { alert(apiError(e)); }
  }

  const setTopic = (i: number, patch: Partial<TopicRow>) =>
    setForm((f) => ({ ...f, topics: f.topics.map((t, j) => (j === i ? { ...t, ...patch } : t)) }));

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-600">{editing ? "Edit Plan" : "New Quarterly Plan"}</h3>
          {editing && <button className="btn-ghost text-xs" onClick={reset}>Cancel edit</button>}
        </div>
        {error && <div className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <label className="lg:col-span-2"><span className="label">Plan Title</span>
            <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Mathematics — Quarter 1 Plan" /></label>
          <label><span className="label">Term</span>
            <select className="input" value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })}>
              {(options?.terms ?? ["Quarter 1"]).map((t) => <option key={t} value={t}>{t}</option>)}
            </select></label>
          <label><span className="label">Academic Year</span>
            <select className="input" value={form.academic_year_id} onChange={(e) => setForm({ ...form, academic_year_id: e.target.value })}>
              <option value="">—</option>
              {options?.academic_years.map((y) => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " (current)" : ""}</option>)}
            </select></label>
          <label className="lg:col-span-2"><span className="label">Class & Subject</span>
            <select className="input" value={form.classKey} onChange={(e) => setForm({ ...form, classKey: e.target.value })}>
              <option value="">— select from your allocations —</option>
              {options?.classes.map((c) => {
                const key = [c.grade_id ?? "", c.section_id ?? "", c.subject_id ?? ""].join("|");
                return <option key={key} value={key}>{c.grade} / {c.section} · {c.subject}</option>;
              })}
            </select></label>
          <label className="lg:col-span-2"><span className="label">Objectives</span>
            <input className="input" value={form.objectives} onChange={(e) => setForm({ ...form, objectives: e.target.value })} /></label>
          <label className="lg:col-span-2"><span className="label">Resources</span>
            <input className="input" value={form.resources} onChange={(e) => setForm({ ...form, resources: e.target.value })} /></label>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="label">Topics for the quarter</span>
            <button className="btn-ghost text-xs text-brand-600" onClick={() => setForm((f) => ({ ...f, topics: [...f.topics, { name: "", weeks: "", hours: undefined, status: "pending" }] }))}>+ Add topic</button>
          </div>
          <div className="space-y-2">
            {form.topics.map((t, i) => (
              <div key={i} className="grid grid-cols-12 gap-2">
                <input className="input col-span-5" placeholder="Topic name" value={t.name} onChange={(e) => setTopic(i, { name: e.target.value })} />
                <input className="input col-span-3" placeholder="Weeks (e.g. 1-2)" value={t.weeks ?? ""} onChange={(e) => setTopic(i, { weeks: e.target.value })} />
                <input className="input col-span-1" type="number" placeholder="Hrs" value={t.hours ?? ""} onChange={(e) => setTopic(i, { hours: e.target.value ? Number(e.target.value) : undefined })} />
                <select className="input col-span-2" value={t.status} onChange={(e) => setTopic(i, { status: e.target.value })}>
                  {TOPIC_STATUS.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                </select>
                <button className="col-span-1 text-slate-300 hover:text-rose-500" onClick={() => setForm((f) => ({ ...f, topics: f.topics.filter((_, j) => j !== i) }))} title="Remove">✕</button>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4">
          <button className="btn-primary" onClick={() => void save()}>{editing ? "Save changes" : "Create draft"}</button>
        </div>
      </div>

      <div className="space-y-3">
        {plans?.map((p) => (
          <div key={p.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold">{p.title}</div>
                <div className="text-xs text-slate-400">{p.term} · {p.grade}/{p.section} · {p.subject}</div>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STATUS_BADGE[p.status] ?? "bg-slate-100 text-slate-600"}`}>
                {p.status.replace("_", " ")}
              </span>
            </div>
            {p.topics.length > 0 && (
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-100">
                <table className="w-full text-xs">
                  <tbody className="divide-y divide-slate-100">
                    {p.topics.map((t, i) => (
                      <tr key={i}>
                        <td className="px-3 py-1.5">{t.name}</td>
                        <td className="px-3 py-1.5 text-slate-400">{t.weeks || "—"}</td>
                        <td className="px-3 py-1.5 text-slate-400">{t.hours ? `${t.hours}h` : "—"}</td>
                        <td className="px-3 py-1.5 capitalize text-slate-500">{(t.status || "pending").replace("_", " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-2 text-xs text-slate-400">
              {p.completion_percent}% complete
              {p.reviewer ? ` · reviewer: ${p.reviewer}` : ""}
            </div>
            {p.review_note && p.status === "rejected" && (
              <div className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">Returned: {p.review_note}</div>
            )}
            {(p.status === "draft" || p.status === "rejected") && (
              <div className="mt-3 flex gap-2">
                <button className="btn-primary px-2.5 py-1 text-xs" onClick={() => void submitPlan(p)}>Submit for approval</button>
                <button className="btn-ghost border border-slate-200 px-2.5 py-1 text-xs" onClick={() => loadIntoForm(p)}>Edit</button>
                <button className="btn-ghost px-2.5 py-1 text-xs text-rose-500" onClick={() => void del(p)}>Delete</button>
              </div>
            )}
          </div>
        ))}
        {(!plans || plans.length === 0) && <div className="card p-5 text-sm text-slate-400">No plans yet. Create one above.</div>}
      </div>
    </div>
  );
}

function TeacherPlanReviews() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["teacher-plan-reviews"],
    queryFn: async () => (await api.get<Plan[]>("/portal/teacher/plan-reviews")).data,
  });
  async function review(p: Plan, decision: "approved" | "rejected") {
    const review_note = decision === "rejected" ? prompt("Reason for returning the plan:") ?? "" : prompt("Approval note (optional):") ?? "";
    try {
      await api.post(`/portal/teacher/plans/${p.id}/review`, { decision, review_note });
      qc.invalidateQueries({ queryKey: ["teacher-plan-reviews"] });
    } catch (e) { alert(apiError(e)); }
  }
  return (
    <div className="space-y-3">
      {data?.map((p) => (
        <div key={p.id} className="card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">{p.title}</div>
              <div className="text-xs text-slate-400">{p.term} · {p.grade}/{p.section} · {p.subject} · by {p.teacher}</div>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STATUS_BADGE[p.status] ?? "bg-slate-100 text-slate-600"}`}>
              {p.status.replace("_", " ")}
            </span>
          </div>
          {p.objectives && <p className="mt-2 text-sm text-slate-500">{p.objectives}</p>}
          {p.topics.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-xs text-slate-500">
              {p.topics.map((t, i) => <li key={i}>{t.name}{t.weeks ? ` (${t.weeks})` : ""}</li>)}
            </ul>
          )}
          {p.status === "submitted" && (
            <div className="mt-3 flex gap-2">
              <button className="btn-primary px-2.5 py-1 text-xs" onClick={() => void review(p, "approved")}>Approve</button>
              <button className="btn-ghost border border-slate-200 px-2.5 py-1 text-xs text-rose-600" onClick={() => void review(p, "rejected")}>Return</button>
            </div>
          )}
          {p.review_note && p.status !== "submitted" && <div className="mt-2 text-xs text-slate-400">Note: {p.review_note}</div>}
        </div>
      ))}
      {(!data || data.length === 0) && <div className="card p-5 text-sm text-slate-400">No plans awaiting your review.</div>}
    </div>
  );
}

function TeacherMarksLegacy() {
  const [exam, setExam] = useState("");
  const [subject, setSubject] = useState("");
  const { data } = useQuery({
    queryKey: ["teacher-marks", exam, subject],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (exam) params.set("exam_id", exam);
      if (subject) params.set("subject_id", subject);
      const qs = params.toString();
      return (await api.get<{ filters: { subjects: { id: string; name: string }[]; exams: { id: string; name: string }[] }; rows: any[] }>(
        `/portal/teacher/marks${qs ? `?${qs}` : ""}`)).data;
    },
  });
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3 p-4">
        <label><span className="label">Exam</span>
          <select className="input" value={exam} onChange={(e) => setExam(e.target.value)}>
            <option value="">All exams</option>
            {data?.filters.exams.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select></label>
        <label><span className="label">Subject</span>
          <select className="input" value={subject} onChange={(e) => setSubject(e.target.value)}>
            <option value="">All my subjects</option>
            {data?.filters.subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></label>
      </div>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Student</th><th className="px-4 py-3">Class</th>
              <th className="px-4 py-3">Subject</th><th className="px-4 py-3">Exam</th>
              <th className="px-4 py-3">Marks</th><th className="px-4 py-3">Grade</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.rows.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-2.5 font-medium">{r.student}<span className="ml-1 text-xs text-slate-400">{r.admission_no}</span></td>
                <td className="px-4 py-2.5">{r.grade}/{r.section}</td>
                <td className="px-4 py-2.5">{r.subject}</td>
                <td className="px-4 py-2.5">{r.exam}</td>
                <td className="px-4 py-2.5">{r.is_absent ? "Absent" : `${r.marks_obtained} / ${r.max_marks}`}</td>
                <td className="px-4 py-2.5">{r.grade_letter || "—"}</td>
              </tr>
            ))}
            {(!data || data.rows.length === 0) && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400">No marks recorded for your students yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TeacherMarks() {
  interface MarkAssignment {
    id: string; grade: string; section: string; subject: string; reviewer?: string | null;
    exams: { id: string; name: string; code: string }[];
  }
  interface MarkRow {
    student_id: string; admission_no: string; roll_no?: string | null; student_name: string;
    marks_obtained: string; is_absent: boolean; remarks?: string; grade?: string | null;
  }
  interface MarkSheet {
    max_marks: string;
    batch?: { id: string; status: string; review_note?: string | null } | null;
    rows: MarkRow[];
  }

  const qc = useQueryClient();
  const [assignmentId, setAssignmentId] = useState("");
  const [examId, setExamId] = useState("");
  const [rows, setRows] = useState<MarkRow[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: options } = useQuery({
    queryKey: ["teacher-marks-entry-options"],
    queryFn: async () => (await api.get<{ assignments: MarkAssignment[] }>("/portal/teacher/marks-entry-options")).data,
  });
  const assignment = options?.assignments.find((a) => a.id === assignmentId);
  const sheet = useQuery({
    queryKey: ["teacher-marks-sheet", assignmentId, examId],
    enabled: !!assignmentId && !!examId,
    queryFn: async () => (await api.get<MarkSheet>("/portal/teacher/marks-sheet", {
      params: { assignment_id: assignmentId, exam_id: examId },
    })).data,
  });
  useEffect(() => {
    setRows(sheet.data?.rows ?? []);
  }, [sheet.data]);

  const maximum = Number(sheet.data?.max_marks ?? 0);
  const locked = ["approved", "published"].includes(sheet.data?.batch?.status ?? "");
  const invalidRows = rows.filter((r) => {
    if (r.is_absent || r.marks_obtained === "") return false;
    const value = Number(r.marks_obtained);
    return !Number.isFinite(value) || value < 0 || value > maximum;
  });
  const completed = rows.filter((r) => r.is_absent || r.marks_obtained !== "").length;

  function payload() {
    return {
      assignment_id: assignmentId,
      exam_id: examId,
      entries: rows.map((r) => ({
        student_id: r.student_id,
        marks_obtained: r.is_absent || r.marks_obtained === "" ? null : Number(r.marks_obtained),
        is_absent: r.is_absent,
        remarks: r.remarks || null,
      })),
    };
  }

  async function save(submit: boolean) {
    if (invalidRows.length) {
      setError(`Correct ${invalidRows.length} mark value${invalidRows.length === 1 ? "" : "s"} outside 0-${maximum}.`);
      return;
    }
    if (submit && completed !== rows.length) {
      setError(`Complete all ${rows.length} students before submitting. ${rows.length - completed} still need marks or Absent.`);
      return;
    }
    if (submit && !window.confirm(`Submit marks for all ${rows.length} students to ${assignment?.reviewer || "the HOD"}?`)) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/portal/teacher/marks-sheet${submit ? "/submit" : ""}`, payload());
      setNotice(submit ? "Entire class marksheet submitted to the HOD." : `Draft saved for ${completed} of ${rows.length} students.`);
      await qc.invalidateQueries({ queryKey: ["teacher-marks-sheet", assignmentId, examId] });
      await qc.invalidateQueries({ queryKey: ["portal-teacher-marks-review"] });
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  function changeRow(index: number, patch: Partial<MarkRow>) {
    setRows((current) => current.map((row, i) => i === index ? { ...row, ...patch } : row));
  }

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="mb-4">
          <h2 className="font-semibold">Class Marks Entry</h2>
          <p className="text-sm text-slate-400">Choose one of your assigned class-subjects. The complete student roster loads as one worksheet.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label><span className="label">My class & subject</span>
            <select className="input" value={assignmentId} onChange={(e) => { setAssignmentId(e.target.value); setExamId(""); setRows([]); }}>
              <option value="">Select assigned class and subject</option>
              {options?.assignments.map((a) => <option key={a.id} value={a.id}>{a.grade} / {a.section} — {a.subject}</option>)}
            </select>
          </label>
          <label><span className="label">Examination</span>
            <select className="input" value={examId} disabled={!assignment} onChange={(e) => { setExamId(e.target.value); setNotice(""); setError(""); }}>
              <option value="">Select examination</option>
              {assignment?.exams.map((e) => <option key={e.id} value={e.id}>{e.name} — {e.code}</option>)}
            </select>
          </label>
        </div>
        {options && options.assignments.length === 0 && (
          <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">No active teacher-class-subject mapping exists. Ask the administrator to add it in Teacher Allocation.</div>
        )}
        {assignment && <div className="mt-3 text-xs text-slate-500">HOD/reviewer: <span className="font-medium text-slate-700">{assignment.reviewer || "Not mapped — update Teacher Allocation"}</span></div>}
      </div>
      {assignmentId && examId && (
        <div className="card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
            <div>
              <div className="font-semibold">{assignment?.grade} / {assignment?.section} — {assignment?.subject}</div>
              <div className="text-xs text-slate-400">{completed} of {rows.length} completed · Maximum {sheet.data?.max_marks ?? "--"} marks</div>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${locked ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
              {sheet.data?.batch?.status ?? "Not started"}
            </span>
          </div>
          {sheet.data?.batch?.review_note && <div className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-sm text-amber-700">HOD note: {sheet.data.batch.review_note}</div>}
          {locked && <div className="border-b border-emerald-100 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">Approved marks are locked. No further changes are allowed.</div>}
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-4 py-3">Roll</th><th className="px-4 py-3">Student</th><th className="px-4 py-3">Marks</th><th className="px-4 py-3">Absent</th><th className="px-4 py-3">Remarks</th><th className="px-4 py-3">Grade</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r, index) => {
                  const value = Number(r.marks_obtained);
                  const invalid = r.marks_obtained !== "" && (!Number.isFinite(value) || value < 0 || value > maximum);
                  return (
                    <tr key={r.student_id} className={invalid ? "bg-rose-50" : ""}>
                      <td className="px-4 py-2.5 text-slate-500">{r.roll_no || r.admission_no}</td>
                      <td className="px-4 py-2.5 font-medium">{r.student_name}<div className="text-xs font-normal text-slate-400">{r.admission_no}</div></td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1">
                          <input className={`input h-9 w-24 ${invalid ? "border-rose-400" : ""}`} type="number" min="0" max={maximum} step="0.01"
                            disabled={locked || r.is_absent} value={r.marks_obtained}
                            onChange={(e) => changeRow(index, { marks_obtained: e.target.value })} />
                          <span className="text-xs text-slate-400">/ {sheet.data?.max_marks}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5"><input type="checkbox" disabled={locked} checked={r.is_absent} onChange={(e) => changeRow(index, { is_absent: e.target.checked, marks_obtained: e.target.checked ? "" : r.marks_obtained })} /></td>
                      <td className="px-4 py-2.5"><input className="input h-9 min-w-48" disabled={locked} value={r.remarks || ""} onChange={(e) => changeRow(index, { remarks: e.target.value })} placeholder="Optional" /></td>
                      <td className="px-4 py-2.5">{r.is_absent ? "AB" : r.grade || "--"}</td>
                    </tr>
                  );
                })}
                {!sheet.isLoading && rows.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">No students are enrolled in this class and section.</td></tr>}
              </tbody>
            </table>
          </div>
          {!locked && rows.length > 0 && (
            <div className="space-y-3 border-t border-slate-100 p-4">
              {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</div>}
              {notice && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</div>}
              <div className="flex flex-wrap gap-2">
                <button className="btn-ghost border border-slate-200" disabled={busy || invalidRows.length > 0} onClick={() => void save(false)}>Save draft</button>
                <button className="btn-primary" disabled={busy || invalidRows.length > 0 || completed !== rows.length || !assignment?.reviewer} onClick={() => void save(true)}>Submit entire class to HOD</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Teacher: self attendance
interface MyAttendance {
  today: string;
  today_state: string | null;
  summary: Record<string, number>;
  history: { date: string; state: string; method: string; remarks?: string }[];
}

export function StaffSelfAttendance() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["me-attendance"],
    queryFn: async () => (await api.get<MyAttendance>("/portal/me/attendance")).data,
  });
  const states = useQuery({
    queryKey: ["master-values", "attendance_state"],
    queryFn: async () => (await api.get<{ code: string; label: string }[]>("/master-types/attendance_state/values")).data,
  });
  const [state, setState] = useState("present");
  const [busy, setBusy] = useState(false);

  async function checkIn() {
    setBusy(true);
    try {
      await api.post("/portal/me/attendance/check-in", { state });
      qc.invalidateQueries({ queryKey: ["me-attendance"] });
    } catch (e) { alert(apiError(e)); } finally { setBusy(false); }
  }

  const marked = !!data?.today_state;
  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-400">Today · {data?.today}</div>
          {marked ? (
            <div className="text-xl font-semibold capitalize text-emerald-600">
              Marked: {data?.today_state?.replace("_", " ")}
            </div>
          ) : (
            <div className="text-xl font-semibold text-slate-500">Not marked yet</div>
          )}
        </div>
        <div className="flex items-end gap-2">
          <label>
            <span className="label">State</span>
            <select className="input" value={state} onChange={(e) => setState(e.target.value)}>
              {(states.data ?? [{ code: "present", label: "Present" }]).map((s) => (
                <option key={s.code} value={s.code}>{s.label}</option>
              ))}
            </select>
          </label>
          <button className="btn-primary" disabled={busy} onClick={() => void checkIn()}>
            {busy ? "Saving…" : marked ? "Update check-in" : "Check in"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Object.entries(data?.summary ?? {}).map(([st, n]) => (
          <div key={st} className="card p-4">
            <div className="text-2xl font-semibold">{n}</div>
            <div className="text-xs capitalize text-slate-400">{st.replace("_", " ")} (last 30)</div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">My Attendance History</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">State</th><th className="px-4 py-3">Method</th><th className="px-4 py-3">Remarks</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.history.map((h, i) => (
              <tr key={i} className="hover:bg-slate-50">
                <td className="px-4 py-2.5">{h.date}</td>
                <td className="px-4 py-2.5 capitalize">{h.state.replace("_", " ")}</td>
                <td className="px-4 py-2.5 capitalize">{h.method}</td>
                <td className="px-4 py-2.5 text-slate-400">{h.remarks || "—"}</td>
              </tr>
            ))}
            {(!data?.history || data.history.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No attendance recorded yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function TeacherPortal() {
  return (
    <PortalShell
      portal="teacher"
      nav={[
        { label: "Dashboard", icon: "grid", to: "" },
        { label: "Schedule", icon: "table", to: "schedule" },
        { label: "My Students", icon: "users", to: "students" },
        { label: "My Attendance", icon: "check-square", to: "my-attendance" },
        { label: "Lesson Planning", icon: "book", to: "plans" },
        { label: "Plan Approvals", icon: "shield", to: "plan-reviews" },
        { label: "Student Marks", icon: "trending-up", to: "marks" },
        { label: "Grade Homework", icon: "edit", to: "submissions" },
        { label: "Marks Review", icon: "activity", to: "marks-review" },
      ]}
    >
      <Routes>
        <Route index element={<TeacherHome />} />
        <Route path="schedule" element={<TeacherSchedule />} />
        <Route path="students" element={<TeacherStudents />} />
        <Route path="my-attendance" element={<StaffSelfAttendance />} />
        <Route path="plans" element={<TeacherPlans />} />
        <Route path="plan-reviews" element={<TeacherPlanReviews />} />
        <Route path="marks" element={<TeacherMarks />} />
        <Route path="submissions" element={<TeacherSubmissions />} />
        <Route path="marks-review" element={<TeacherMarksReview />} />
        <Route path="*" element={<Navigate to="" replace />} />
      </Routes>
    </PortalShell>
  );
}

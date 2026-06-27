import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { Icon } from "../components/Icon";
import { PortalShell } from "../components/PortalShell";
import { api } from "../lib/api";
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
  const { data } = useQuery({
    queryKey: ["portal-teacher-marks-review"],
    queryFn: async () => (await api.get<any[]>("/portal/teacher/marks-review")).data,
  });
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-4 py-3">Exam</th><th className="px-4 py-3">Subject</th><th className="px-4 py-3">Class</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Note</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data?.map((b) => (
            <tr key={b.id}><td className="px-4 py-2.5">{b.exam}</td><td className="px-4 py-2.5">{b.subject}</td><td className="px-4 py-2.5">{b.grade}/{b.section}</td><td className="px-4 py-2.5 capitalize">{b.status}</td><td className="px-4 py-2.5">{b.review_note || "--"}</td></tr>
          ))}
          {(!data || data.length === 0) && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No marks batches assigned for review.</td></tr>}
        </tbody>
      </table>
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
        { label: "Grade Homework", icon: "book", to: "submissions" },
        { label: "Marks Review", icon: "check-square", to: "marks-review" },
      ]}
    >
      <Routes>
        <Route index element={<TeacherHome />} />
        <Route path="schedule" element={<TeacherSchedule />} />
        <Route path="students" element={<TeacherStudents />} />
        <Route path="submissions" element={<TeacherSubmissions />} />
        <Route path="marks-review" element={<TeacherMarksReview />} />
        <Route path="*" element={<Navigate to="" replace />} />
      </Routes>
    </PortalShell>
  );
}

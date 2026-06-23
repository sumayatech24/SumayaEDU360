import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { Icon } from "../components/Icon";
import { PortalShell } from "../components/PortalShell";
import { api } from "../lib/api";

const inr = (v?: string | number) => "₹" + Number(v ?? 0).toLocaleString("en-IN");

interface Dash {
  student: Record<string, any>;
  guardians: { name: string; relation: string; phone?: string; email?: string }[];
  fees: { billed: string; paid: string; balance: string; invoices: number };
  attendance: Record<string, number>;
  marks: { exam: string; subject: string; marks: string; max: string; grade?: string }[];
  announcements: { title: string; body?: string; date?: string }[];
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
          <div className="text-3xl font-semibold text-amber-600">{inr(data.fees.balance)}</div>
          <div className="text-xs text-slate-400">
            balance · billed {inr(data.fees.billed)} · paid {inr(data.fees.paid)}
          </div>
          {childView && Number(data.fees.balance) > 0 && (
            <div className="mt-2 text-xs font-medium text-emerald-600">Tap your school office or pay online.</div>
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
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">Exam Results</div>
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
        { label: "Profile", icon: "users", to: "profile" },
      ]}
    >
      <Routes>
        <Route index element={<Student360View />} />
        <Route path="homework" element={<HomeworkList />} />
        <Route path="timetable" element={<TimetableView />} />
        <Route path="activities" element={<ActivitiesView />} />
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
  teacher: { name: string; designation?: string; department?: string } | null;
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
              <td className="px-4 py-2.5">{s.status}</td>
            </tr>
          ))}
          {(!data || data.length === 0) && (
            <tr>
              <td colSpan={5} className="px-4 py-6 text-center text-slate-400">No students.</td>
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

export function TeacherPortal() {
  return (
    <PortalShell
      portal="teacher"
      nav={[
        { label: "Dashboard", icon: "grid", to: "" },
        { label: "My Students", icon: "users", to: "students" },
        { label: "Grade Homework", icon: "book", to: "submissions" },
      ]}
    >
      <Routes>
        <Route index element={<TeacherHome />} />
        <Route path="students" element={<TeacherStudents />} />
        <Route path="submissions" element={<TeacherSubmissions />} />
        <Route path="*" element={<Navigate to="" replace />} />
      </Routes>
    </PortalShell>
  );
}

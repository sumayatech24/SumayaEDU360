import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";

const inr = (v?: string | number) => "₹" + Number(v ?? 0).toLocaleString("en-IN");

function Section({ title, children, count }: { title: string; children: React.ReactNode; count?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
        {count !== undefined && <span className="text-xs text-slate-400">{count}</span>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: any }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-sm font-medium capitalize">{value || "—"}</div>
    </div>
  );
}

function Table({ cols, rows }: { cols: [string, string][]; rows: Record<string, any>[] }) {
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
        <tr>
          {cols.map(([, label]) => (
            <th key={label} className="pb-2 pr-4 font-medium">
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map(([key]) => (
              <td key={key} className="py-2 pr-4">
                {r[key] ?? "—"}
              </td>
            ))}
          </tr>
        ))}
        {rows.length === 0 && (
          <tr>
            <td colSpan={cols.length} className="py-3 text-center text-slate-400">
              None on record.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

export function StudentProfile() {
  const { id = "" } = useParams();
  const { data, isLoading } = useQuery({
    queryKey: ["student-profile", id],
    queryFn: async () => (await api.get<any>(`/reports/student-360/${id}`)).data,
  });

  if (isLoading) return <div className="text-slate-400">Loading…</div>;
  if (!data) return <div className="text-slate-400">Student not found.</div>;
  const s = data.student;
  const attTotal = Object.values(data.attendance).reduce((a: number, b: any) => a + b, 0) as number;
  const present = data.attendance.present ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Link to="/students" className="btn-ghost text-sm">
          ← All students
        </Link>
        <span className="text-xs text-slate-400">Student 360 Profile</span>
      </div>

      {/* Header */}
      <div className="card flex flex-wrap items-center gap-5 p-5">
        {s.photo_url ? (
          <img src={s.photo_url} alt="" className="h-20 w-20 rounded-full object-cover" />
        ) : (
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-100 text-3xl font-bold text-brand-700">
            {s.name?.[0]}
          </div>
        )}
        <div>
          <div className="text-2xl font-semibold">{s.name}</div>
          <div className="text-sm text-slate-400">
            {s.admission_no} · Roll {s.roll_no || "—"} · Grade {s.grade} · Section {s.section}
          </div>
          <span className="badge mt-1 bg-emerald-50 capitalize text-emerald-600">{s.status}</span>
        </div>
        <div className="ml-auto grid grid-cols-3 gap-4">
          <Field label="Class Teacher" value={s.class_teacher} />
          <Field label="House" value={s.house} />
          <Field label="Blood Group" value={s.blood_group} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Section title="Personal Details">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <Field label="Date of Birth" value={s.date_of_birth} />
            <Field label="Gender" value={s.gender} />
            <Field label="Admission Date" value={s.admission_date} />
            <Field label="Category" value={s.category} />
            <Field label="Religion" value={s.religion} />
            <Field label="Nationality" value={s.nationality} />
            <Field label="Mother Tongue" value={s.mother_tongue} />
            <Field label="ID / Aadhaar" value={s.id_number} />
            <Field label="Phone" value={s.phone} />
            <Field label="Email" value={s.email} />
            <Field label="Previous School" value={s.previous_school} />
          </div>
          <div className="mt-3 border-t border-slate-100 pt-3">
            <Field label="Address" value={[s.address, s.city, s.state, s.pincode].filter(Boolean).join(", ")} />
          </div>
        </Section>

        <Section title="Guardians" count={data.guardians.length}>
          <Table
            cols={[["name", "Name"], ["relation", "Relation"], ["phone", "Phone"], ["occupation", "Occupation"]]}
            rows={data.guardians}
          />
        </Section>

        <Section title="Teachers" count={data.teachers?.length ?? 0}>
          <div className="mb-2 text-xs text-slate-500">
            Class Teacher: <span className="font-medium">{s.class_teacher || "—"}</span>
          </div>
          <Table
            cols={[["name", "Teacher"], ["subject", "Subject"], ["designation", "Designation"]]}
            rows={data.teachers ?? []}
          />
        </Section>

        <Section title="Academic History" count={data.academic_history.length}>
          <Table
            cols={[["year", "Year"], ["grade", "Class"], ["result", "Result"], ["percentage", "%"], ["rank", "Rank"]]}
            rows={data.academic_history}
          />
        </Section>

        <Section title="Exam Results" count={data.marks.length}>
          <Table
            cols={[["exam", "Exam"], ["subject", "Subject"], ["marks", "Marks"], ["grade", "Grade"]]}
            rows={data.marks}
          />
        </Section>

        <Section title="Achievements" count={data.achievements.length}>
          <Table
            cols={[["title", "Title"], ["category", "Category"], ["level", "Level"], ["date", "Date"]]}
            rows={data.achievements}
          />
        </Section>

        <Section title="Activities" count={data.activities.length}>
          <Table cols={[["name", "Activity"], ["status", "Status"], ["date", "Since"]]} rows={data.activities} />
        </Section>

        <Section title="Disciplinary Actions" count={data.discipline.length}>
          <Table
            cols={[["date", "Date"], ["incident", "Incident"], ["severity", "Severity"], ["action", "Action"], ["status", "Status"]]}
            rows={data.discipline}
          />
        </Section>

        <Section title="Remarks" count={data.remarks.length}>
          <div className="space-y-2">
            {data.remarks.map((r: any, i: number) => (
              <div key={i} className="rounded-lg bg-slate-50 px-3 py-2">
                <div className="text-sm">{r.remark}</div>
                <div className="text-[11px] text-slate-400">
                  {r.type} · {r.by || "—"} · {r.date || "—"}
                </div>
              </div>
            ))}
            {data.remarks.length === 0 && <p className="text-sm text-slate-400">None.</p>}
          </div>
        </Section>

        <Section title="Attendance">
          <div className="mb-2 text-3xl font-semibold text-indigo-600">
            {attTotal ? Math.round((present / attTotal) * 100) : 0}%
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.attendance).map(([state, n]) => (
              <span key={state} className="badge bg-slate-100 capitalize text-slate-600">
                {state}: {n as number}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Fees">
          <div className="mb-3 grid grid-cols-3 gap-3">
            <Field label="Billed" value={inr(data.fees.billed)} />
            <Field label="Paid" value={inr(data.fees.paid)} />
            <Field label="Balance" value={inr(data.fees.balance)} />
          </div>
          <Table
            cols={[["invoice_no", "Invoice"], ["net", "Net"], ["paid", "Paid"], ["status", "Status"], ["due_date", "Due"]]}
            rows={data.invoices}
          />
        </Section>
      </div>
    </div>
  );
}

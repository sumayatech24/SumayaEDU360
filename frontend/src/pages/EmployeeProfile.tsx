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
        <tr>{cols.map(([, l]) => <th key={l} className="pb-2 pr-4 font-medium">{l}</th>)}</tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r, i) => (
          <tr key={i}>{cols.map(([k]) => <td key={k} className="py-2 pr-4">{r[k] ?? "—"}</td>)}</tr>
        ))}
        {rows.length === 0 && (
          <tr><td colSpan={cols.length} className="py-3 text-center text-slate-400">None on record.</td></tr>
        )}
      </tbody>
    </table>
  );
}

export function EmployeeProfile() {
  const { id = "" } = useParams();
  const { data, isLoading } = useQuery({
    queryKey: ["employee-profile", id],
    queryFn: async () => (await api.get<any>(`/reports/employee-360/${id}`)).data,
  });

  if (isLoading) return <div className="text-slate-400">Loading…</div>;
  if (!data) return <div className="text-slate-400">Employee not found.</div>;
  const e = data.employee;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Link to="/employees" className="btn-ghost text-sm">← All employees</Link>
        <span className="text-xs text-slate-400">Staff 360 Profile</span>
      </div>

      <div className="card flex flex-wrap items-center gap-5 p-5">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-100 text-3xl font-bold text-brand-700">
          {e.name?.[0]}
        </div>
        <div>
          <div className="text-2xl font-semibold">{e.name}</div>
          <div className="text-sm text-slate-400">
            {e.employee_no} · {e.designation || "—"} · {e.department || "—"}
          </div>
          <span className="badge mt-1 bg-emerald-50 capitalize text-emerald-600">{e.employment_status}</span>
        </div>
        <div className="ml-auto grid grid-cols-3 gap-4">
          <Field label="Reporting Manager" value={e.reporting_manager} />
          <Field label="Joined" value={e.date_of_joining} />
          <Field label="Type" value={e.employment_type} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Section title="Employment & Personal">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <Field label="Gender" value={e.gender} />
            <Field label="Phone" value={e.phone} />
            <Field label="Email" value={e.email} />
            <Field label={`${e.government_id_type?.toUpperCase() || "Govt ID"} (masked)`} value={e.government_id_masked} />
            <Field label="Salary" value={inr(e.salary)} />
            <Field label="Address" value={e.address} />
          </div>
        </Section>

        <Section title="Teaching Profile">
          {data.teaching_profile ? (
            <div className="space-y-3">
              <Field label="Qualification" value={data.teaching_profile.qualification} />
              <Field label="Subjects Can Teach" value={data.teaching_profile.subjects_can_teach} />
              <Field label="Expertise" value={data.teaching_profile.expertise} />
              <Field label="Certifications" value={data.teaching_profile.certifications} />
            </div>
          ) : (
            <p className="text-sm text-slate-400">Not a teaching role.</p>
          )}
        </Section>

        <Section title="Classes Assigned" count={data.classes.length}>
          <Table cols={[["grade", "Class"], ["section", "Section"], ["subject", "Subject"], ["status", "Status"]]} rows={data.classes} />
        </Section>

        <Section title="Leave Balance">
          <Table
            cols={[["type", "Leave Type"], ["allowance", "Allowance"], ["taken", "Taken"], ["balance", "Balance"]]}
            rows={data.leave_balance}
          />
        </Section>

        <Section title="Leave History" count={data.leave_history.length}>
          <Table cols={[["type", "Type"], ["from", "From"], ["to", "To"], ["days", "Days"], ["status", "Status"]]} rows={data.leave_history} />
        </Section>

        <Section title="Payroll History" count={data.payroll.length}>
          <Table cols={[["period", "Period"], ["basic", "Basic"], ["net", "Net Pay"], ["status", "Status"]]} rows={data.payroll} />
        </Section>

        <Section title="Assets Held" count={data.assets.length}>
          <Table cols={[["name", "Item"], ["quantity", "Qty"], ["status", "Status"], ["due_date", "Due"]]} rows={data.assets} />
        </Section>

        <Section title="Documents" count={data.documents.length}>
          <Table cols={[["name", "Document"], ["category", "Category"]]} rows={data.documents} />
        </Section>
      </div>
    </div>
  );
}

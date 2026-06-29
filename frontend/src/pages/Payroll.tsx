import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { useBranding } from "../lib/branding";
import { openReport, reportDocument } from "../lib/report";

const inr = (v?: string | number) => "₹" + Number(v ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

interface Component { code?: string; name: string; kind: string; method: string; value: number }
interface Structure { id: string; name: string; financial_year: string; basic_percent: string; components: Component[]; is_active: boolean }
interface Package {
  id: string; employee_no: string; name: string; designation?: string;
  annual_ctc?: string | null; salary_structure_id?: string | null; structure?: string | null;
  tax_regime: string; bank_account_no?: string | null; bank_ifsc?: string | null;
}
interface RunRow {
  id: string; financial_year: string; month: number; month_name: string; year: number; status: string;
  employee_count: number; total_gross: string; total_deductions: string; total_net: string;
  bank_reference?: string | null;
}
interface Line { name: string; amount: string }
interface PayslipRow {
  id: string; employee: string; employee_no: string; designation?: string;
  gross_earnings: string; statutory_deductions: string; tax_amount: string;
  adhoc_deduction: string; adhoc_note?: string | null; lop_days: string; net_pay: string;
  tax_regime: string; earnings: Line[]; deductions: Line[]; bank_account_no?: string | null; bank_ifsc?: string | null;
}

export function Payroll() {
  const [tab, setTab] = useState<"runs" | "packages" | "structures">("runs");
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Payroll</h1>
        <p className="text-sm text-slate-400">Salary structures, pay packages, and monthly payroll runs with owner approval and bank submission.</p>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
        {([["runs", "Payroll Runs"], ["packages", "Pay Packages"], ["structures", "Salary Structures"]] as const).map(([s, l]) => (
          <button key={s} onClick={() => setTab(s)}
            className={`rounded-t-lg px-3 py-2 text-sm ${tab === s ? "border-b-2 border-brand-600 font-medium text-brand-700" : "text-slate-500 hover:text-slate-700"}`}>{l}</button>
        ))}
      </div>
      {tab === "runs" ? <Runs /> : tab === "packages" ? <Packages /> : <Structures />}
    </div>
  );
}

// ------------------------------------------------------------------ Runs
function Runs() {
  const qc = useQueryClient();
  const brand = useBranding();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [openRun, setOpenRun] = useState<string | null>(null);
  const [error, setError] = useState("");
  const { data: runs } = useQuery({ queryKey: ["payroll-runs"], queryFn: async () => (await api.get<RunRow[]>("/payroll/runs")).data });

  async function prepare() {
    setError("");
    try {
      const r = await api.post("/payroll/runs", { month, year });
      qc.invalidateQueries({ queryKey: ["payroll-runs"] });
      setOpenRun(r.data.id);
    } catch (e) { setError(apiError(e)); }
  }

  if (openRun) return <RunDetail runId={openRun} brand={brand} onBack={() => { setOpenRun(null); qc.invalidateQueries({ queryKey: ["payroll-runs"] }); }} />;

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3 p-4">
        <label><span className="label">Month</span>
          <select className="input" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select></label>
        <label><span className="label">Year</span>
          <input className="input w-28" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></label>
        <button className="btn-primary" onClick={() => void prepare()}>Prepare payroll</button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Period</th><th className="px-4 py-3">FY</th><th className="px-4 py-3">Staff</th><th className="px-4 py-3">Gross</th><th className="px-4 py-3">Net</th><th className="px-4 py-3">Status</th><th className="px-4 py-3" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {runs?.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-2.5 font-medium">{r.month_name} {r.year}</td>
                <td className="px-4 py-2.5">{r.financial_year}</td>
                <td className="px-4 py-2.5">{r.employee_count}</td>
                <td className="px-4 py-2.5">{inr(r.total_gross)}</td>
                <td className="px-4 py-2.5">{inr(r.total_net)}</td>
                <td className="px-4 py-2.5"><StatusBadge s={r.status} /></td>
                <td className="px-4 py-2.5 text-right"><button className="btn-ghost text-xs text-brand-600" onClick={() => setOpenRun(r.id)}>Open</button></td>
              </tr>
            ))}
            {(!runs || runs.length === 0) && <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">No payroll runs yet. Prepare one above.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusBadge({ s }: { s: string }) {
  const map: Record<string, string> = { draft: "bg-amber-50 text-amber-700", approved: "bg-indigo-50 text-indigo-700", paid: "bg-emerald-50 text-emerald-700", cancelled: "bg-slate-100 text-slate-500" };
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${map[s] ?? "bg-slate-100 text-slate-600"}`}>{s}</span>;
}

function RunDetail({ runId, brand, onBack }: { runId: string; brand: any; onBack: () => void }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { data } = useQuery({ queryKey: ["payroll-run", runId], queryFn: async () => (await api.get<{ run: RunRow; editable: boolean; payslips: PayslipRow[] }>(`/payroll/runs/${runId}`)).data });
  const refresh = () => qc.invalidateQueries({ queryKey: ["payroll-run", runId] });

  async function action(path: "approve" | "process") {
    setBusy(true); setError("");
    try {
      await api.post(`/payroll/runs/${runId}/${path}`, path === "approve" ? { note: "Approved" } : {});
      refresh();
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }
  async function bankFile() {
    const f = (await api.get(`/payroll/runs/${runId}/bank-file`)).data;
    const rows = f.lines.map((l: any) => `<tr><td>${l.employee_no}</td><td>${l.name}</td><td>${l.bank_account_no}</td><td>${l.bank_ifsc}</td><td style="text-align:right">${inr(l.net_pay)}</td></tr>`).join("");
    openReport(reportDocument({ brand, title: `Bank Disbursement — ${f.period}`, meta: `Ref ${f.bank_reference || "draft"} · ${f.count} staff · Total ${inr(f.total_net)}`,
      bodyHtml: `<table><thead><tr><th>Emp No</th><th>Name</th><th>Account</th><th>IFSC</th><th>Net Pay</th></tr></thead><tbody>${rows}</tbody></table>`, landscape: true }));
  }
  function payslip(p: PayslipRow) {
    const run = data!.run;
    const er = p.earnings.map((e) => `<tr><td>${e.name}</td><td style="text-align:right">${inr(e.amount)}</td></tr>`).join("");
    const de = p.deductions.map((d) => `<tr><td>${d.name}</td><td style="text-align:right">${inr(d.amount)}</td></tr>`).join("");
    openReport(reportDocument({ brand, title: `Payslip — ${run.month_name} ${run.year}`,
      meta: `${p.employee} (${p.employee_no})${p.designation ? " · " + p.designation : ""} · Regime: ${p.tax_regime}`,
      bodyHtml: `<div style="display:flex;gap:24px"><div style="flex:1"><h3>Earnings</h3><table>${er}<tr style="font-weight:700"><td>Gross</td><td style="text-align:right">${inr(p.gross_earnings)}</td></tr></table></div>
        <div style="flex:1"><h3>Deductions</h3><table>${de}</table></div></div>
        <div style="margin-top:16px;font-size:16px;font-weight:700">Net Pay: ${inr(p.net_pay)}</div>`,
      extraCss: "h3{font-size:13px;margin:8px 0 4px} td{padding:4px 8px;border:1px solid #e2e8f0}" }));
  }

  const run = data?.run;
  return (
    <div className="space-y-4">
      <button className="btn-ghost text-sm" onClick={onBack}>← All runs</button>
      {run && (
        <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <div className="text-lg font-semibold">{run.month_name} {run.year} <span className="text-sm font-normal text-slate-400">· FY {run.financial_year}</span></div>
            <div className="text-xs text-slate-500">{run.employee_count} staff · Gross {inr(run.total_gross)} · Deductions {inr(run.total_deductions)} · Net {inr(run.total_net)}</div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge s={run.status} />
            {run.status === "draft" && <button className="btn-primary" disabled={busy} onClick={() => void action("approve")}>Approve (owner)</button>}
            {run.status === "approved" && <button className="btn-primary" disabled={busy} onClick={() => void action("process")}>Submit to bank</button>}
            <button className="btn-ghost border border-slate-200" onClick={() => void bankFile()}>Bank file</button>
          </div>
        </div>
      )}
      {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
      {run?.bank_reference && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Submitted to bank · Reference {run.bank_reference}</div>}
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-3 py-3">Employee</th><th className="px-3 py-3">Gross</th><th className="px-3 py-3">Statutory</th><th className="px-3 py-3">Tax</th><th className="px-3 py-3">LOP days</th><th className="px-3 py-3">Other ded.</th><th className="px-3 py-3">Net</th><th className="px-3 py-3" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.payslips.map((p) => (
              <PayslipRowEl key={p.id} p={p} editable={!!data.editable} onSaved={refresh} onView={() => payslip(p)} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PayslipRowEl({ p, editable, onSaved, onView }: { p: PayslipRow; editable: boolean; onSaved: () => void; onView: () => void }) {
  const [edit, setEdit] = useState(false);
  const [lop, setLop] = useState(p.lop_days);
  const [adhoc, setAdhoc] = useState(p.adhoc_deduction);
  const [note, setNote] = useState(p.adhoc_note ?? "");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      await api.put(`/payroll/payslips/${p.id}`, { lop_days: Number(lop) || 0, adhoc_deduction: Number(adhoc) || 0, adhoc_note: note || null });
      setEdit(false); onSaved();
    } catch (e) { alert(apiError(e)); } finally { setBusy(false); }
  }
  return (
    <tr className="hover:bg-slate-50">
      <td className="px-3 py-2.5"><div className="font-medium">{p.employee}</div><div className="text-xs text-slate-400">{p.employee_no} · {p.tax_regime}</div></td>
      <td className="px-3 py-2.5">{inr(p.gross_earnings)}</td>
      <td className="px-3 py-2.5">{inr(p.statutory_deductions)}</td>
      <td className="px-3 py-2.5">{inr(p.tax_amount)}</td>
      <td className="px-3 py-2.5">{edit ? <input className="input h-8 w-16" type="number" value={lop} onChange={(e) => setLop(e.target.value)} /> : p.lop_days}</td>
      <td className="px-3 py-2.5">{edit ? <input className="input h-8 w-24" type="number" value={adhoc} onChange={(e) => setAdhoc(e.target.value)} /> : inr(p.adhoc_deduction)}</td>
      <td className="px-3 py-2.5 font-semibold">{inr(p.net_pay)}</td>
      <td className="px-3 py-2.5 text-right">
        {edit ? (
          <span className="flex items-center justify-end gap-1">
            <input className="input h-8 w-28" placeholder="Note" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn-primary px-2 py-1 text-xs" disabled={busy} onClick={() => void save()}>Save</button>
            <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setEdit(false)}>✕</button>
          </span>
        ) : (
          <span className="flex justify-end gap-1">
            {editable && <button className="btn-ghost border border-slate-200 px-2 py-1 text-xs" onClick={() => setEdit(true)}>Adjust</button>}
            <button className="btn-ghost px-2 py-1 text-xs text-brand-600" onClick={onView}>Payslip</button>
          </span>
        )}
      </td>
    </tr>
  );
}

// ------------------------------------------------------------------ Packages
function Packages() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["payroll-packages"], queryFn: async () => (await api.get<Package[]>("/payroll/employees")).data });
  const { data: structures } = useQuery({ queryKey: ["payroll-structures"], queryFn: async () => (await api.get<Structure[]>("/payroll/structures")).data });
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ annual_ctc: "", salary_structure_id: "", tax_regime: "new", bank_account_no: "", bank_ifsc: "" });
  function startEdit(p: Package) {
    setEditId(p.id);
    setForm({ annual_ctc: p.annual_ctc ?? "", salary_structure_id: p.salary_structure_id ?? "", tax_regime: p.tax_regime || "new", bank_account_no: p.bank_account_no ?? "", bank_ifsc: p.bank_ifsc ?? "" });
  }
  async function save(id: string) {
    try {
      await api.put(`/payroll/employees/${id}/package`, {
        annual_ctc: Number(form.annual_ctc) || 0, salary_structure_id: form.salary_structure_id || null,
        tax_regime: form.tax_regime, bank_account_no: form.bank_account_no || null, bank_ifsc: form.bank_ifsc || null,
      });
      setEditId(null); qc.invalidateQueries({ queryKey: ["payroll-packages"] });
    } catch (e) { alert(apiError(e)); }
  }
  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[820px] text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-3 py-3">Employee</th><th className="px-3 py-3">Annual CTC</th><th className="px-3 py-3">Structure</th><th className="px-3 py-3">Regime</th><th className="px-3 py-3">Bank A/C</th><th className="px-3 py-3">IFSC</th><th className="px-3 py-3" /></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data?.map((p) => editId === p.id ? (
            <tr key={p.id} className="bg-indigo-50/40">
              <td className="px-3 py-2.5"><div className="font-medium">{p.name}</div><div className="text-xs text-slate-400">{p.employee_no}</div></td>
              <td className="px-3 py-2.5"><input className="input h-8 w-28" type="number" value={form.annual_ctc} onChange={(e) => setForm({ ...form, annual_ctc: e.target.value })} /></td>
              <td className="px-3 py-2.5"><select className="input h-8" value={form.salary_structure_id} onChange={(e) => setForm({ ...form, salary_structure_id: e.target.value })}><option value="">—</option>{structures?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></td>
              <td className="px-3 py-2.5"><select className="input h-8" value={form.tax_regime} onChange={(e) => setForm({ ...form, tax_regime: e.target.value })}><option value="new">New</option><option value="old">Old</option></select></td>
              <td className="px-3 py-2.5"><input className="input h-8 w-28" value={form.bank_account_no} onChange={(e) => setForm({ ...form, bank_account_no: e.target.value })} /></td>
              <td className="px-3 py-2.5"><input className="input h-8 w-24" value={form.bank_ifsc} onChange={(e) => setForm({ ...form, bank_ifsc: e.target.value })} /></td>
              <td className="px-3 py-2.5 text-right"><button className="btn-primary px-2 py-1 text-xs" onClick={() => void save(p.id)}>Save</button> <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setEditId(null)}>✕</button></td>
            </tr>
          ) : (
            <tr key={p.id} className="hover:bg-slate-50">
              <td className="px-3 py-2.5"><div className="font-medium">{p.name}</div><div className="text-xs text-slate-400">{p.employee_no} · {p.designation || "—"}</div></td>
              <td className="px-3 py-2.5">{p.annual_ctc ? inr(p.annual_ctc) : <span className="text-amber-600">not set</span>}</td>
              <td className="px-3 py-2.5">{p.structure || "—"}</td>
              <td className="px-3 py-2.5 capitalize">{p.tax_regime}</td>
              <td className="px-3 py-2.5">{p.bank_account_no || "—"}</td>
              <td className="px-3 py-2.5">{p.bank_ifsc || "—"}</td>
              <td className="px-3 py-2.5 text-right"><button className="btn-ghost border border-slate-200 px-2 py-1 text-xs" onClick={() => startEdit(p)}>Edit</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ Structures
function Structures() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["payroll-structures"], queryFn: async () => (await api.get<Structure[]>("/payroll/structures")).data });
  const empty = { id: "", name: "", financial_year: "2025-26", basic_percent: "40", components: [] as Component[] };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");

  function load(s: Structure) { setForm({ id: s.id, name: s.name, financial_year: s.financial_year, basic_percent: s.basic_percent, components: s.components }); }
  const setC = (i: number, patch: Partial<Component>) => setForm((f) => ({ ...f, components: f.components.map((c, j) => j === i ? { ...c, ...patch } : c) }));
  async function save() {
    setError("");
    const body = { name: form.name, financial_year: form.financial_year, basic_percent: Number(form.basic_percent) || 40, components: form.components, is_active: true };
    try {
      if (form.id) await api.put(`/payroll/structures/${form.id}`, body);
      else await api.post("/payroll/structures", body);
      setForm(empty); qc.invalidateQueries({ queryKey: ["payroll-structures"] });
    } catch (e) { setError(apiError(e)); }
  }
  return (
    <div className="space-y-4">
      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-slate-600">{form.id ? "Edit structure" : "New salary structure"}</h3>
        {error && <div className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
        <div className="grid gap-3 md:grid-cols-3">
          <label><span className="label">Name</span><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label><span className="label">Financial Year</span><input className="input" value={form.financial_year} onChange={(e) => setForm({ ...form, financial_year: e.target.value })} placeholder="2025-26" /></label>
          <label><span className="label">Basic (% of CTC)</span><input className="input" type="number" value={form.basic_percent} onChange={(e) => setForm({ ...form, basic_percent: e.target.value })} /></label>
        </div>
        <div className="mt-3">
          <div className="mb-2 flex items-center justify-between"><span className="label">Components (HRA, PF, etc.)</span>
            <button className="btn-ghost text-xs text-brand-600" onClick={() => setForm((f) => ({ ...f, components: [...f.components, { name: "", kind: "earning", method: "percent_basic", value: 0 }] }))}>+ Add component</button></div>
          <div className="space-y-2">
            {form.components.map((c, i) => (
              <div key={i} className="grid grid-cols-12 gap-2">
                <input className="input col-span-4" placeholder="Name" value={c.name} onChange={(e) => setC(i, { name: e.target.value })} />
                <select className="input col-span-2" value={c.kind} onChange={(e) => setC(i, { kind: e.target.value })}><option value="earning">Earning</option><option value="deduction">Deduction</option></select>
                <select className="input col-span-3" value={c.method} onChange={(e) => setC(i, { method: e.target.value })}><option value="percent_basic">% of Basic</option><option value="percent_ctc">% of CTC</option><option value="fixed">Fixed</option></select>
                <input className="input col-span-2" type="number" value={c.value} onChange={(e) => setC(i, { value: Number(e.target.value) })} />
                <button className="col-span-1 text-slate-300 hover:text-rose-500" onClick={() => setForm((f) => ({ ...f, components: f.components.filter((_, j) => j !== i) }))}>✕</button>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4 flex gap-2"><button className="btn-primary" onClick={() => void save()}>{form.id ? "Save changes" : "Create structure"}</button>{form.id && <button className="btn-ghost" onClick={() => setForm(empty)}>Cancel</button>}</div>
      </div>
      <div className="space-y-2">
        {data?.map((s) => (
          <div key={s.id} className="card flex items-center justify-between p-4">
            <div><div className="text-sm font-semibold">{s.name}</div><div className="text-xs text-slate-400">FY {s.financial_year} · Basic {s.basic_percent}% · {s.components.length} components</div></div>
            <button className="btn-ghost border border-slate-200 text-xs" onClick={() => load(s)}>Edit</button>
          </div>
        ))}
        {(!data || data.length === 0) && <div className="card p-5 text-sm text-slate-400">No structures yet.</div>}
      </div>
    </div>
  );
}

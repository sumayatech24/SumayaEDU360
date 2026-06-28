import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiError, publicApi } from "../lib/api";
import { PublicFooter, PublicHeader, usePublicSite } from "./public/PublicSite";

type Config = {
  institution_name: string;
  grades: { id: string; name: string }[];
  academic_years: { id: string; name: string; is_current: boolean }[];
  required_documents: string[];
};

type Application = {
  id: string;
  application_no: string;
  student_name: string;
  grade: string;
  status: string;
  verification_status: string;
  fee_status: string;
  decision_notes?: string;
  documents: { id: string; document_type: string; file_name: string; verification_status: string }[];
  checks: { id: string; check_type: string; status: string; remarks?: string }[];
  charges: { id: string; charge_type: string; amount: string; paid_amount: string; status: string; receipt_no?: string }[];
};

const blank = {
  student_name: "", grade_applied_id: "", academic_year_id: "", phone: "", email: "",
  date_of_birth: "", gender: "", category: "", religion: "", nationality: "Indian",
  address: "", city: "", state: "", pincode: "", father_name: "", father_phone: "",
  mother_name: "", mother_phone: "", previous_school: "",
};

export function PublicAdmission() {
  const { tenantCode = "" } = useParams();
  const tokenKey = `admission_token_${tenantCode.toLowerCase()}`;
  const [config, setConfig] = useState<Config | null>(null);
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey));
  const [mode, setMode] = useState<"login" | "register">("login");
  const [auth, setAuth] = useState({ full_name: "", email: "", phone: "", password: "" });
  const [apps, setApps] = useState<Application[]>([]);
  const [form, setForm] = useState({ ...blank });
  const [docs, setDocs] = useState<{ document_type: string; file_name: string; file_data: string }[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    publicApi.get<Config>(`/public/admissions/${tenantCode}/config`)
      .then(({ data }) => {
        setConfig(data);
        const current = data.academic_years.find((x) => x.is_current) ?? data.academic_years[0];
        setForm((f) => ({ ...f, academic_year_id: current?.id ?? "" }));
      }).catch((e) => setError(apiError(e)));
  }, [tenantCode]);

  useEffect(() => {
    if (!token) return;
    publicApi.get<Application[]>(`/public/admissions/${tenantCode}/applications`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(({ data }) => setApps(data)).catch(() => {
      localStorage.removeItem(tokenKey);
      setToken(null);
    });
  }, [token, tenantCode]);

  async function authenticate() {
    setBusy(true); setError("");
    try {
      const endpoint = mode === "register" ? "register" : "login";
      const { data } = await publicApi.post(`/public/admissions/${tenantCode}/${endpoint}`, auth);
      localStorage.setItem(tokenKey, data.access_token);
      setToken(data.access_token);
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }

  function addFile(document_type: string, file?: File) {
    if (!file) return;
    if (file.size > 750_000) { setError("Each document must be under 750 KB."); return; }
    const reader = new FileReader();
    reader.onload = () => setDocs((old) => [
      ...old.filter((d) => d.document_type !== document_type),
      { document_type, file_name: file.name, file_data: String(reader.result) },
    ]);
    reader.readAsDataURL(file);
  }

  async function submit() {
    setBusy(true); setError("");
    try {
      const { data } = await publicApi.post<Application>(
        `/public/admissions/${tenantCode}/applications`,
        {
          ...form, grade_applied_id: form.grade_applied_id,
          academic_year_id: form.academic_year_id || null,
          date_of_birth: form.date_of_birth || null, documents: docs,
          declaration_accepted: accepted,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setApps((old) => [data, ...old]);
      setForm({ ...blank, academic_year_id: form.academic_year_id });
      setDocs([]); setAccepted(false); setShowForm(false);
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }

  if (!config) return <PublicFrame tenantCode={tenantCode}><p className="text-slate-500">{error || "Loading admissions portal…"}</p></PublicFrame>;

  if (!token) return (
    <PublicFrame tenantCode={tenantCode}>
      <div className="mx-auto max-w-md card p-7">
        <div className="mb-6">
          <div className="text-xs font-semibold uppercase tracking-widest text-brand-600">Online admissions</div>
          <h1 className="mt-1 text-2xl font-semibold">{config.institution_name}</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to apply and track verification, decision, and fee status.</p>
        </div>
        <div className="mb-5 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm">
          {(["login", "register"] as const).map((x) => (
            <button key={x} className={`rounded-md py-2 capitalize ${mode === x ? "bg-white font-medium shadow-sm" : "text-slate-500"}`} onClick={() => setMode(x)}>{x}</button>
          ))}
        </div>
        <div className="space-y-3">
          {mode === "register" && <>
            <Field label="Applicant / guardian name" value={auth.full_name} onChange={(v) => setAuth({ ...auth, full_name: v })} />
            <Field label="Mobile number" value={auth.phone} onChange={(v) => setAuth({ ...auth, phone: v })} />
          </>}
          <Field label="Email" type="email" value={auth.email} onChange={(v) => setAuth({ ...auth, email: v })} />
          <Field label="Password" type="password" value={auth.password} onChange={(v) => setAuth({ ...auth, password: v })} />
          {error && <Alert text={error} />}
          <button className="btn-primary w-full" disabled={busy || !auth.email || !auth.password} onClick={authenticate}>
            {busy ? "Please wait…" : mode === "register" ? "Create applicant account" : "Sign in"}
          </button>
        </div>
      </div>
    </PublicFrame>
  );

  return (
    <PublicFrame tenantCode={tenantCode}>
      <div className="mx-auto max-w-6xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><div className="text-xs font-semibold uppercase tracking-widest text-brand-600">Applicant portal</div><h1 className="text-2xl font-semibold">{config.institution_name}</h1></div>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={() => setShowForm(true)}>+ New application</button>
            <button className="btn-ghost" onClick={() => { localStorage.removeItem(tokenKey); setToken(null); }}>Sign out</button>
          </div>
        </div>
        {error && <Alert text={error} />}
        {!showForm && (
          <div className="grid gap-4 md:grid-cols-2">
            {apps.map((app) => <ApplicationCard key={app.id} app={app} />)}
            {apps.length === 0 && <div className="card p-8 text-center text-sm text-slate-400 md:col-span-2">No applications yet. Start a new admission application.</div>}
          </div>
        )}
        {showForm && (
          <div className="card p-6">
            <h2 className="text-lg font-semibold">New admission application</h2>
            <p className="mb-5 text-sm text-slate-500">Complete student, guardian, address, and supporting-document details.</p>
            <Section title="Student details">
              <Field label="Student full name *" value={form.student_name} onChange={(v) => setForm({ ...form, student_name: v })} />
              <Select label="Class applying for *" value={form.grade_applied_id} onChange={(v) => setForm({ ...form, grade_applied_id: v })} options={config.grades} />
              <Select label="Academic year" value={form.academic_year_id} onChange={(v) => setForm({ ...form, academic_year_id: v })} options={config.academic_years} />
              <Field label="Date of birth" type="date" value={form.date_of_birth} onChange={(v) => setForm({ ...form, date_of_birth: v })} />
              <Select label="Gender" value={form.gender} onChange={(v) => setForm({ ...form, gender: v })} options={[{ id: "male", name: "Male" }, { id: "female", name: "Female" }, { id: "other", name: "Other" }]} />
              <Field label="Category" value={form.category} onChange={(v) => setForm({ ...form, category: v })} />
              <Field label="Previous school" value={form.previous_school} onChange={(v) => setForm({ ...form, previous_school: v })} />
              <Field label="Nationality" value={form.nationality} onChange={(v) => setForm({ ...form, nationality: v })} />
            </Section>
            <Section title="Contact and guardians">
              <Field label="Email" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} />
              <Field label="Mobile" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} />
              <Field label="Father name" value={form.father_name} onChange={(v) => setForm({ ...form, father_name: v })} />
              <Field label="Father mobile" value={form.father_phone} onChange={(v) => setForm({ ...form, father_phone: v })} />
              <Field label="Mother name" value={form.mother_name} onChange={(v) => setForm({ ...form, mother_name: v })} />
              <Field label="Mother mobile" value={form.mother_phone} onChange={(v) => setForm({ ...form, mother_phone: v })} />
            </Section>
            <Section title="Address">
              <Field label="Address" value={form.address} onChange={(v) => setForm({ ...form, address: v })} />
              <Field label="City" value={form.city} onChange={(v) => setForm({ ...form, city: v })} />
              <Field label="State" value={form.state} onChange={(v) => setForm({ ...form, state: v })} />
              <Field label="Pincode" value={form.pincode} onChange={(v) => setForm({ ...form, pincode: v })} />
            </Section>
            <div className="mb-5">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Supporting documents</h3>
              <div className="grid gap-3 md:grid-cols-2">
                {config.required_documents.map((type) => (
                  <label key={type} className="rounded-lg border border-slate-200 p-3 text-sm">
                    <span className="mb-2 block font-medium capitalize">{type.replace(/_/g, " ")}</span>
                    <input type="file" accept="image/*,application/pdf" onChange={(e) => addFile(type, e.target.files?.[0])} />
                    {docs.find((d) => d.document_type === type) && <span className="mt-1 block text-xs text-emerald-600">Attached ✓</span>}
                  </label>
                ))}
              </div>
            </div>
            <label className="mb-5 flex gap-2 text-sm text-slate-600"><input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} /> I declare that the information supplied is correct and may be verified by the institution.</label>
            <div className="flex justify-end gap-2"><button className="btn-ghost" onClick={() => setShowForm(false)}>Cancel</button><button className="btn-primary" disabled={busy || !accepted || !form.student_name || !form.grade_applied_id} onClick={submit}>{busy ? "Submitting…" : "Submit application"}</button></div>
          </div>
        )}
      </div>
    </PublicFrame>
  );
}

function ApplicationCard({ app }: { app: Application }) {
  return <div className="card p-5">
    <div className="flex justify-between"><div><div className="font-semibold">{app.student_name}</div><div className="text-xs text-slate-400">{app.application_no} · {app.grade}</div></div><Status value={app.status} /></div>
    <div className="mt-4 grid grid-cols-2 gap-3 text-sm"><Metric label="Verification" value={app.verification_status} /><Metric label="Admission fee" value={app.fee_status} /></div>
    {app.decision_notes && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{app.decision_notes}</p>}
    <div className="mt-4 border-t pt-3 text-xs text-slate-500">{app.checks.filter((c) => c.status === "verified").length}/{app.checks.length} checks complete · {app.documents.filter((d) => d.verification_status === "verified").length}/{app.documents.length} documents verified</div>
    {app.charges.map((c) => <div key={c.id} className="mt-2 text-xs text-slate-500">{c.charge_type.replace(/_/g, " ")}: ₹{Number(c.amount).toLocaleString("en-IN")} · {c.status}{c.receipt_no ? ` · receipt ${c.receipt_no}` : ""}</div>)}
  </div>;
}

function PublicFrame({ tenantCode, children }: { tenantCode: string; children: React.ReactNode }) {
  const { data } = usePublicSite(tenantCode);
  return (
    <div className="flex min-h-full flex-col bg-gradient-to-br from-slate-50 via-white to-brand-50">
      <PublicHeader data={data} siteCode={tenantCode} />
      <main className="flex-1 px-4 py-10">{children}</main>
      <PublicFooter data={data} />
    </div>
  );
}
function Section({ title, children }: { title: string; children: React.ReactNode }) { return <div className="mb-5"><h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</h3><div className="grid gap-3 md:grid-cols-4">{children}</div></div>; }
function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) { return <label><span className="label">{label}</span><input className="input" type={type} value={value} onChange={(e) => onChange(e.target.value)} /></label>; }
function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { id: string; name: string }[] }) { return <label><span className="label">{label}</span><select className="input" value={value} onChange={(e) => onChange(e.target.value)}><option value="">— select —</option>{options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>; }
function Alert({ text }: { text: string }) { return <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{text}</div>; }
function Status({ value }: { value: string }) { return <span className="badge h-fit bg-brand-50 text-brand-700 capitalize">{value.replace(/_/g, " ")}</span>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-slate-50 p-3"><div className="text-[11px] text-slate-400">{label}</div><div className="font-medium capitalize">{value.replace(/_/g, " ")}</div></div>; }

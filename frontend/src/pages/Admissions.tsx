import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

type Check = { id: string; check_type: string; status: string; remarks?: string };
type Doc = { id: string; document_type: string; file_name: string; verification_status: string; remarks?: string };
type Charge = { id: string; charge_type: string; amount: string; paid_amount: string; status: string; receipt_no?: string };
type Application = {
  id: string; application_no: string; application_type: string; channel: string;
  student_name: string; phone?: string; email?: string; grade?: string; academic_year?: string;
  section?: string; status: string; verification_status: string; fee_status: string;
  submitted_at?: string; decision_notes?: string; converted_student_id?: string;
  target_grade_id?: string; academic_year_id?: string; target_section_id?: string;
  checks: Check[]; documents: Doc[]; charges: Charge[];
};

const COLUMNS = ["submitted", "under_review", "approved", "enrolled", "rejected"];

export function Admissions() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const { data: applications = [], isLoading } = useQuery({
    queryKey: ["admission-applications"],
    queryFn: async () => (await api.get<Application[]>("/admissions/applications")).data,
  });
  const { data: grades } = useQuery({ queryKey: ["admission-grades"], queryFn: async () => (await api.get<Page<any>>("/grades", { params: { page_size: 100 } })).data.items });
  const { data: years } = useQuery({ queryKey: ["admission-years"], queryFn: async () => (await api.get<Page<any>>("/academic-years", { params: { page_size: 100 } })).data.items });
  const { data: sections } = useQuery({ queryKey: ["admission-sections"], queryFn: async () => (await api.get<Page<any>>("/sections", { params: { page_size: 200 } })).data.items });
  const { data: admissionConfig } = useQuery({ queryKey: ["admission-config"], queryFn: async () => (await api.get<any>("/admissions/config")).data });
  const selected = applications.find((a) => a.id === selectedId) ?? null;
  const counts = useMemo(() => Object.fromEntries(COLUMNS.map((s) => [s, applications.filter((a) => a.status === s).length])), [applications]);

  const action = useMutation({
    mutationFn: async ({ url, body = {} }: { url: string; body?: Record<string, unknown> }) => api.post(url, body),
    onSuccess: async () => {
      setError("");
      await qc.invalidateQueries({ queryKey: ["admission-applications"] });
    },
    onError: (e) => setError(apiError(e)),
  });

  const publicUrl = `${location.origin}/apply/${admissionConfig?.tenant_code || "SUMAYA"}`;
  function updateCheck(check: Check, status: string) {
    action.mutate({ url: `/admissions/applications/${selected!.id}/checks/${check.id}`, body: { status } });
  }
  function updateDoc(doc: Doc, status: string) {
    action.mutate({ url: `/admissions/applications/${selected!.id}/documents/${doc.id}`, body: { status } });
  }
  async function viewDoc(doc: Doc) {
    try {
      const { data } = await api.get(`/admissions/applications/${selected!.id}/documents/${doc.id}/content`);
      if (!data.file_data) { setError("This document has no stored file content."); return; }
      const w = window.open();
      if (w) w.location.href = data.file_data;
    } catch (e) { setError(apiError(e)); }
  }
  function decide(decision: string) {
    const notes = prompt(`${decision === "approved" ? "Approval" : "Rejection"} notes (optional)`) ?? "";
    action.mutate({ url: `/admissions/applications/${selected!.id}/decision`, body: { decision, notes } });
  }
  function assignFee() {
    const raw = prompt("Admission fee amount");
    const amount = Number(raw);
    if (!amount) return;
    action.mutate({ url: `/admissions/applications/${selected!.id}/charges`, body: { amount, charge_type: "admission_fee" } });
  }
  function collect(charge: Charge) {
    const raw = prompt(`Amount received (balance ₹${Number(charge.amount) - Number(charge.paid_amount)})`);
    const amount = Number(raw);
    if (!amount) return;
    const method = prompt("Payment method: cash / upi / card / bank", "cash") || "cash";
    const reference = prompt("Payment reference (optional)") || null;
    action.mutate({ url: `/admissions/applications/${selected!.id}/charges/${charge.id}/pay`, body: { amount, method, reference } });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Admissions</h1>
          <p className="text-sm text-slate-400">Application → verification → approval → fee collection → class enrollment.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost border border-slate-200" onClick={() => navigator.clipboard.writeText(publicUrl)}>Copy public application link</button>
          <a className="btn-primary" href={publicUrl} target="_blank" rel="noreferrer">Open public form</a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {COLUMNS.map((s) => <div key={s} className="card p-4"><div className="text-2xl font-semibold">{counts[s]}</div><div className="text-xs capitalize text-slate-400">{s.replace(/_/g, " ")}</div></div>)}
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>}

      <div className="grid min-h-[560px] gap-4 lg:grid-cols-[360px_1fr]">
        <div className="card overflow-hidden">
          <div className="border-b px-4 py-3 text-sm font-semibold">Admission applications</div>
          <div className="max-h-[650px] divide-y overflow-y-auto">
            {applications.map((app) => (
              <button key={app.id} onClick={() => { setSelectedId(app.id); setError(""); }} className={`block w-full p-4 text-left hover:bg-slate-50 ${selectedId === app.id ? "bg-brand-50" : ""}`}>
                <div className="flex items-start justify-between gap-2"><div className="font-medium">{app.student_name}</div><Pill value={app.status} /></div>
                <div className="mt-1 text-xs text-slate-400">{app.application_no} · {app.application_type === "continuing" ? "Continuing student" : "New admission"}</div>
                <div className="mt-2 text-xs text-slate-500">{app.grade || "Class pending"} · {app.channel}</div>
              </button>
            ))}
            {!isLoading && applications.length === 0 && <div className="p-8 text-center text-sm text-slate-400">No submitted applications yet.</div>}
          </div>
        </div>

        <div className="card p-5">
          {!selected && <div className="flex h-full items-center justify-center text-sm text-slate-400">Select an application to verify and process it.</div>}
          {selected && (
            <div className="space-y-5">
              <div className="flex flex-wrap justify-between gap-3 border-b pb-4">
                <div><div className="text-xs uppercase tracking-wide text-slate-400">{selected.application_no}</div><h2 className="text-xl font-semibold">{selected.student_name}</h2><div className="text-sm text-slate-500">{selected.grade} · {selected.academic_year || "Academic year pending"}{selected.section ? ` · Section ${selected.section}` : ""}</div></div>
                <div className="flex items-start gap-2"><Pill value={selected.verification_status} /><Pill value={selected.fee_status} /><Pill value={selected.status} /></div>
              </div>

              <div className="grid gap-3 sm:grid-cols-4">
                <Info label="Admission type" value={selected.application_type} />
                <Info label="Source" value={selected.channel} />
                <Info label="Phone" value={selected.phone || "—"} />
                <Info label="Email" value={selected.email || "—"} />
              </div>

              <Panel title="Class and section allocation" subtitle="Confirm the academic year, class, and available section before final enrollment.">
                <div className="grid gap-3 md:grid-cols-3">
                  <select id="placement-year" className="input" defaultValue={selected.academic_year_id || ""}><option value="">Academic year</option>{years?.map((y: any) => <option key={y.id} value={y.id}>{y.name}</option>)}</select>
                  <select id="placement-grade" className="input" defaultValue={selected.target_grade_id || ""}><option value="">Class</option>{grades?.map((g: any) => <option key={g.id} value={g.id}>{g.name}</option>)}</select>
                  <select id="placement-section" className="input" defaultValue={selected.target_section_id || ""}><option value="">Section to allocate later</option>{sections?.map((s: any) => <option key={s.id} value={s.id}>{s.name} · capacity {s.capacity}</option>)}</select>
                </div>
                <button className="btn-ghost mt-3 border border-slate-200" onClick={() => {
                  const academic_year_id = (document.getElementById("placement-year") as HTMLSelectElement).value;
                  const grade_id = (document.getElementById("placement-grade") as HTMLSelectElement).value;
                  const section_id = (document.getElementById("placement-section") as HTMLSelectElement).value || null;
                  if (!academic_year_id || !grade_id) { setError("Academic year and class are required."); return; }
                  action.mutate({ url: `/admissions/applications/${selected.id}/placement`, body: { academic_year_id, grade_id, section_id } });
                }}>Save class allocation</button>
              </Panel>

              <Panel title="Eligibility and clearance checks" subtitle="Every check must be verified before the admission manager can approve.">
                <div className="divide-y">
                  {selected.checks.map((c) => <ReviewRow key={c.id} label={c.check_type} status={c.status} onVerify={() => updateCheck(c, "verified")} onReject={() => updateCheck(c, "rejected")} />)}
                </div>
              </Panel>

              <Panel title="Supporting documents" subtitle="Verify the applicant's uploaded evidence individually.">
                <div className="divide-y">
                  {selected.documents.map((d) => <ReviewRow key={d.id} label={`${d.document_type.replace(/_/g, " ")} · ${d.file_name}`} status={d.verification_status} onView={() => viewDoc(d)} onVerify={() => updateDoc(d, "verified")} onReject={() => updateDoc(d, "rejected")} />)}
                  {selected.documents.length === 0 && <div className="py-3 text-sm text-amber-600">No documents were attached. Use the documents clearance check to hold this application.</div>}
                </div>
              </Panel>

              <Panel title="Admission decision" subtitle="Approval is enabled by the API only after all checks and documents are verified.">
                <div className="flex flex-wrap gap-2">
                  {selected.status !== "approved" && selected.status !== "enrolled" && <button className="btn-primary" disabled={action.isPending} onClick={() => decide("approved")}>Approve admission</button>}
                  {selected.status !== "rejected" && selected.status !== "enrolled" && <button className="btn-danger" onClick={() => decide("rejected")}>Reject</button>}
                  {selected.decision_notes && <div className="w-full rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{selected.decision_notes}</div>}
                </div>
              </Panel>

              <Panel title="Admission fee and receipt" subtitle="Pre-enrollment collection is kept separate from the student's regular fee ledger.">
                {selected.charges.map((c) => <div key={c.id} className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm"><div><div className="font-medium capitalize">{c.charge_type.replace(/_/g, " ")}</div><div className="text-xs text-slate-400">₹{Number(c.paid_amount).toLocaleString("en-IN")} paid of ₹{Number(c.amount).toLocaleString("en-IN")}{c.receipt_no ? ` · ${c.receipt_no}` : ""}</div></div><div className="flex items-center gap-2"><Pill value={c.status} />{c.status !== "paid" && <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => collect(c)}>Collect payment</button>}</div></div>)}
                {selected.status === "approved" && selected.charges.length === 0 && <button className="btn-primary" onClick={assignFee}>Assign admission fee</button>}
                {selected.status !== "approved" && selected.status !== "enrolled" && <div className="text-sm text-slate-400">Approve the admission before assigning fees.</div>}
              </Panel>

              <div className="flex items-center justify-between rounded-xl bg-slate-900 p-4 text-white">
                <div><div className="font-medium">{selected.application_type === "continuing" ? "Promote and allocate class" : "Create student and allocate class"}</div><div className="text-xs text-slate-300">Requires approval and full admission-fee clearance.</div></div>
                <button className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 disabled:opacity-40" disabled={selected.status !== "approved" || !["paid", "waived"].includes(selected.fee_status) || action.isPending} onClick={() => action.mutate({ url: `/admissions/applications/${selected.id}/enroll` })}>
                  {selected.application_type === "continuing" ? "Complete promotion" : "Enroll student"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) { return <section className="rounded-xl border border-slate-200 p-4"><h3 className="font-semibold">{title}</h3><p className="mb-3 text-xs text-slate-400">{subtitle}</p>{children}</section>; }
function ReviewRow({ label, status, onView, onVerify, onReject }: { label: string; status: string; onView?: () => void; onVerify: () => void; onReject: () => void }) { return <div className="flex flex-wrap items-center justify-between gap-2 py-3"><div className="text-sm capitalize">{label.replace(/_/g, " ")}</div><div className="flex items-center gap-2"><Pill value={status} />{onView && <button className="btn-ghost px-2 py-1 text-xs" onClick={onView}>View</button>}{status !== "verified" && <button className="btn-ghost px-2 py-1 text-xs text-emerald-700" onClick={onVerify}>Verify</button>}{status !== "rejected" && <button className="btn-ghost px-2 py-1 text-xs text-red-600" onClick={onReject}>Flag issue</button>}</div></div>; }
function Info({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-slate-50 p-3"><div className="text-[11px] text-slate-400">{label}</div><div className="truncate text-sm font-medium capitalize">{value.replace(/_/g, " ")}</div></div>; }
function Pill({ value }: { value: string }) { const color = ["approved", "enrolled", "verified", "paid"].includes(value) ? "bg-emerald-50 text-emerald-700" : ["rejected", "issues"].includes(value) ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"; return <span className={`badge whitespace-nowrap capitalize ${color}`}>{value.replace(/_/g, " ")}</span>; }

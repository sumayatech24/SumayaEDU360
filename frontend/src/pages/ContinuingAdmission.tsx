import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";

type Config = {
  grades: { id: string; name: string }[];
  academic_years: { id: string; name: string; is_current: boolean }[];
};
type App = {
  id: string; application_no: string; grade: string; academic_year: string;
  status: string; verification_status: string; fee_status: string; decision_notes?: string;
};

export function ContinuingAdmission() {
  const qc = useQueryClient();
  const [grade, setGrade] = useState("");
  const [year, setYear] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: config } = useQuery({
    queryKey: ["internal-admission-config"],
    queryFn: async () => (await api.get<Config>("/admissions/config")).data,
  });
  const { data: apps = [] } = useQuery({
    queryKey: ["my-admission-applications"],
    queryFn: async () => (await api.get<App[]>("/admissions/my-applications")).data,
  });

  async function submit() {
    setBusy(true); setError("");
    try {
      await api.post("/admissions/internal/applications", {
        target_grade_id: grade, academic_year_id: year, notes: notes || null,
      });
      setGrade(""); setYear(""); setNotes("");
      await qc.invalidateQueries({ queryKey: ["my-admission-applications"] });
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }

  return <div className="space-y-5">
    <div><h1 className="text-2xl font-semibold">Continuation / Promotion</h1><p className="text-sm text-slate-400">Apply internally for your next class and track academic, fee, and discipline clearance.</p></div>
    <div className="card p-5">
      <h2 className="mb-4 font-semibold">New continuation application</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <label><span className="label">Target class</span><select className="input" value={grade} onChange={(e) => setGrade(e.target.value)}><option value="">— select —</option>{config?.grades.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
        <label><span className="label">Academic year</span><select className="input" value={year} onChange={(e) => setYear(e.target.value)}><option value="">— select —</option>{config?.academic_years.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}</select></label>
        <label><span className="label">Request / notes</span><input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" /></label>
      </div>
      {error && <div className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
      <div className="mt-4 flex justify-end"><button className="btn-primary" disabled={!grade || !year || busy} onClick={submit}>{busy ? "Submitting…" : "Submit for review"}</button></div>
    </div>
    <div className="card overflow-hidden">
      <div className="border-b px-4 py-3 font-semibold">My applications</div>
      <div className="divide-y">
        {apps.map((a) => <div key={a.id} className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-2"><div><div className="font-medium">{a.grade} · {a.academic_year}</div><div className="text-xs text-slate-400">{a.application_no}</div></div><span className="badge bg-brand-50 text-brand-700 capitalize">{a.status.replace(/_/g, " ")}</span></div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm"><div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-400">Clearances</div><div className="capitalize">{a.verification_status.replace(/_/g, " ")}</div></div><div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-400">Fee status</div><div className="capitalize">{a.fee_status.replace(/_/g, " ")}</div></div></div>
          {a.decision_notes && <div className="mt-3 text-sm text-slate-500">{a.decision_notes}</div>}
        </div>)}
        {apps.length === 0 && <div className="p-8 text-center text-sm text-slate-400">No continuation applications submitted.</div>}
      </div>
    </div>
  </div>;
}

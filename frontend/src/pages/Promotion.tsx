import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface Grade { id: string; name: string; sequence: number }
interface Exam { id: string; name: string; grade_id?: string }
interface Eligibility {
  exam: { id: string; name: string };
  review_status: string;
  reviewers: string[];
  subjects: string[];
  summary: { students: number; eligible: number; blocked: number };
  rows: { student_id: string; admission_no: string; roll_no?: string; student: string; section: string;
    percentage: number; eligible: boolean; reason: string }[];
}

export function Promotion() {
  const qc = useQueryClient();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [exam, setExam] = useState("");
  const [graduating, setGraduating] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: gradeData } = useQuery({
    queryKey: ["grades-all"],
    queryFn: async () => (await api.get<Page<Grade>>("/grades", { params: { page_size: 100 } })).data,
  });
  const { data: examData } = useQuery({
    queryKey: ["promotion-exams"],
    queryFn: async () => (await api.get<Page<Exam>>("/exams", { params: { page_size: 200 } })).data,
  });
  const grades = useMemo(() => [...(gradeData?.items ?? [])].sort((a, b) => a.sequence - b.sequence), [gradeData]);
  const exams = (examData?.items ?? []).filter((item) => !from || !item.grade_id || item.grade_id === from);
  const { data: eligibility, isFetching } = useQuery({
    queryKey: ["promotion-eligibility", from, exam],
    enabled: Boolean(from && exam),
    queryFn: async () => (await api.get<Eligibility>("/promotion/eligibility", {
      params: { from_grade_id: from, exam_id: exam },
    })).data,
  });
  const chosen = selected.length ? selected : eligibility?.rows.filter((r) => r.eligible).map((r) => r.student_id) ?? [];
  const run = useMutation({
    mutationFn: async () => (await api.post("/promotion/run", {
      from_grade_id: from, to_grade_id: to, exam_id: exam,
      student_ids: chosen, mark_graduating: graduating,
    })).data,
    onSuccess: (data) => {
      setMessage(`Promoted ${data.promoted} student(s) from ${data.from_grade} → ${data.to_grade}.`);
      setError(null);
      setSelected([]);
      qc.invalidateQueries({ queryKey: ["promotion-eligibility"] });
      qc.invalidateQueries({ queryKey: ["students"] });
    },
    onError: (e) => { setError(apiError(e)); setMessage(null); },
  });
  const toggle = (id: string) => setSelected((value) => value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Class Promotion</h1>
        <p className="text-sm text-slate-400">Promote only class-assigned students whose marks have been inspected and published.</p>
      </div>
      <div className="card grid gap-4 p-5 md:grid-cols-4">
        <div><label className="label">From class</label><select className="input" value={from}
          onChange={(e) => { setFrom(e.target.value); setExam(""); setSelected([]); }}>
          <option value="">Select class</option>{grades.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select></div>
        <div><label className="label">Final exam</label><select className="input" value={exam}
          onChange={(e) => { setExam(e.target.value); setSelected([]); }}>
          <option value="">Select exam</option>{exams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select></div>
        <div><label className="label">Promote to</label><select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
          <option value="">Select class</option>{grades.filter((g) => graduating || g.sequence > (grades.find((x) => x.id === from)?.sequence ?? -1))
            .map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select></div>
        <label className="mt-7 flex items-center gap-2 text-sm"><input type="checkbox" checked={graduating}
          onChange={(e) => setGraduating(e.target.checked)} /> Final class / graduate</label>
      </div>
      {isFetching && <div className="text-sm text-slate-400">Checking results and academic review…</div>}
      {eligibility && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ["Students", eligibility.summary.students, "text-slate-800"],
              ["Eligible", eligibility.summary.eligible, "text-emerald-600"],
              ["Blocked", eligibility.summary.blocked, "text-red-600"],
              ["Marks review", eligibility.review_status.replace(/_/g, " "), eligibility.review_status === "published" ? "text-emerald-600" : "text-amber-600"],
            ].map(([label, value, color]) => <div className="card p-4" key={String(label)}>
              <div className="text-xs uppercase text-slate-400">{label}</div><div className={`mt-1 text-xl font-semibold capitalize ${color}`}>{value}</div>
            </div>)}
          </div>
          <div className="card overflow-hidden">
            <div className="border-b px-4 py-3 text-sm text-slate-500">
              Subjects: {eligibility.subjects.join(", ") || "No submitted marks sheets"} · Reviewer: {eligibility.reviewers.join(", ") || "Not assigned"}
            </div>
            <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Select</th><th>Student</th><th>Class</th><th>Result</th><th>Status</th></tr>
            </thead><tbody className="divide-y">
              {eligibility.rows.map((row) => <tr key={row.student_id}>
                <td className="px-4 py-3"><input type="checkbox" disabled={!row.eligible}
                  checked={row.eligible && (selected.length ? selected.includes(row.student_id) : true)} onChange={() => toggle(row.student_id)} /></td>
                <td><div className="font-medium">{row.student}</div><div className="text-xs text-slate-400">{row.admission_no}</div></td>
                <td>{grades.find((g) => g.id === from)?.name} · {row.section}</td><td>{row.percentage}%</td>
                <td className={row.eligible ? "text-emerald-600" : "text-red-600"}>{row.reason}</td>
              </tr>)}
            </tbody></table></div>
          </div>
        </>
      )}
      {message && <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      <button className="btn-primary" disabled={!from || !to || !exam || !chosen.length || run.isPending}
        onClick={() => run.mutate()}>{run.isPending ? "Promoting…" : `Promote ${chosen.length || ""} eligible student(s)`}</button>
    </div>
  );
}

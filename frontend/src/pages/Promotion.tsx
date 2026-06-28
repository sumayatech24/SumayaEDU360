import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface Grade { id: string; name: string; sequence: number }
interface Section { id: string; name: string; grade_id: string }
interface Exam {
  id: string; name: string; grade_id?: string; is_final_exam: boolean;
  academic_year_id?: string; overall_pass_percentage: string; require_subject_pass: boolean;
}
interface ResultRow {
  student_id: string; admission_no: string; roll_no?: string; student: string; section: string;
  percentage: number; eligible: boolean; reason: string; result: "pending" | "passed" | "failed";
  grade: string; rank?: number | null; failed_subjects: string[];
  subject_results: { subject: string; percentage: number; pass_percentage: number; status: string }[];
}
interface Eligibility {
  exam: { id: string; name: string };
  board: string;
  review_status: string;
  reviewers: string[];
  subjects: string[];
  policy: { overall_pass_percentage: number; require_subject_pass: boolean; default_subject_pass_percentage: number };
  included_exams: { id: string; name: string; weightage_percent: number }[];
  summary: { students: number; eligible: number; blocked: number; pending: number; failed: number };
  rows: ResultRow[];
  leaders: ResultRow[];
  failed_students: ResultRow[];
}

export function Promotion() {
  const qc = useQueryClient();
  const [from, setFrom] = useState("");
  const [fromSection, setFromSection] = useState("");
  const [to, setTo] = useState("");
  const [toSection, setToSection] = useState("");
  const [exam, setExam] = useState("");
  const [graduating, setGraduating] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [view, setView] = useState<"all" | "leaders" | "failed">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: gradeData } = useQuery({
    queryKey: ["grades-all"],
    queryFn: async () => (await api.get<Page<Grade>>("/grades", { params: { page_size: 100 } })).data,
  });
  const { data: sectionData } = useQuery({
    queryKey: ["sections-all"],
    queryFn: async () => (await api.get<Page<Section>>("/sections", { params: { page_size: 200 } })).data,
  });
  const { data: examData } = useQuery({
    queryKey: ["promotion-exams"],
    queryFn: async () => (await api.get<Page<Exam>>("/exams", { params: { page_size: 200 } })).data,
  });

  const grades = useMemo(
    () => [...(gradeData?.items ?? [])].sort((a, b) => a.sequence - b.sequence),
    [gradeData],
  );
  const sections = sectionData?.items ?? [];
  const fromSections = sections.filter((section) => section.grade_id === from);
  const toSections = sections.filter((section) => section.grade_id === to);
  const finalExams = (examData?.items ?? []).filter(
    (item) => item.is_final_exam && (!from || !item.grade_id || item.grade_id === from),
  );

  const { data: eligibility, isFetching } = useQuery({
    queryKey: ["promotion-eligibility", from, fromSection, exam],
    enabled: Boolean(from && fromSection && exam),
    queryFn: async () => (await api.get<Eligibility>("/promotion/eligibility", {
      params: { from_grade_id: from, section_id: fromSection, exam_id: exam },
    })).data,
  });
  useEffect(() => {
    setSelected(eligibility?.rows.filter((row) => row.eligible).map((row) => row.student_id) ?? []);
  }, [eligibility]);

  const run = useMutation({
    mutationFn: async () => (await api.post("/promotion/run", {
      from_grade_id: from,
      from_section_id: fromSection,
      to_grade_id: to,
      to_section_id: toSection || null,
      exam_id: exam,
      student_ids: selected,
      mark_graduating: graduating,
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

  const toggle = (id: string) => setSelected((value) =>
    value.includes(id) ? value.filter((studentId) => studentId !== id) : [...value, id]
  );
  const shownRows = view === "leaders"
    ? eligibility?.leaders ?? []
    : view === "failed"
      ? eligibility?.failed_students ?? []
      : eligibility?.rows ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Annual Results & Promotion</h1>
        <p className="text-sm text-slate-400">Cumulative annual marks, subject pass rules, rankings, failed students and controlled class promotion.</p>
      </div>

      <div className="card grid gap-4 p-5 md:grid-cols-3 xl:grid-cols-6">
        <div><label className="label">From class</label><select className="input" value={from}
          onChange={(e) => { setFrom(e.target.value); setFromSection(""); setExam(""); setSelected([]); }}>
          <option value="">Select class</option>{grades.map((grade) => <option key={grade.id} value={grade.id}>{grade.name}</option>)}
        </select></div>
        <div><label className="label">Section</label><select className="input" value={fromSection}
          onChange={(e) => { setFromSection(e.target.value); setSelected([]); }}>
          <option value="">Select section</option>{fromSections.map((section) => <option key={section.id} value={section.id}>{section.name}</option>)}
        </select></div>
        <div><label className="label">Final examination</label><select className="input" value={exam}
          onChange={(e) => { setExam(e.target.value); setSelected([]); }}>
          <option value="">Select final exam</option>{finalExams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></div>
        <div><label className="label">Promote to</label><select className="input" value={to}
          onChange={(e) => { setTo(e.target.value); setToSection(""); }}>
          <option value="">Select class</option>{grades.filter((grade) =>
            graduating || grade.sequence > (grades.find((item) => item.id === from)?.sequence ?? -1)
          ).map((grade) => <option key={grade.id} value={grade.id}>{grade.name}</option>)}
        </select></div>
        <div><label className="label">Destination section</label><select className="input" value={toSection}
          disabled={graduating} onChange={(e) => setToSection(e.target.value)}>
          <option value="">Select section</option>{toSections.map((section) => <option key={section.id} value={section.id}>{section.name}</option>)}
        </select></div>
        <label className="mt-7 flex items-center gap-2 text-sm"><input type="checkbox" checked={graduating}
          onChange={(e) => setGraduating(e.target.checked)} /> Final class / graduate</label>
      </div>

      {isFetching && <div className="text-sm text-slate-400">Calculating cumulative annual results…</div>}
      {eligibility && (
        <>
          <div className="card p-4 text-sm">
            <div className="font-medium">{eligibility.board} result policy: {eligibility.policy.overall_pass_percentage}% overall
              {eligibility.policy.require_subject_pass ? ` and at least ${eligibility.policy.default_subject_pass_percentage}% in every subject` : ""}.
            </div>
            <div className="mt-1 text-slate-500">Annual weightage: {eligibility.included_exams.map((item) => `${item.name} ${item.weightage_percent}%`).join(" + ")}</div>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[
              ["Students", eligibility.summary.students, "text-slate-800"],
              ["Eligible", eligibility.summary.eligible, "text-emerald-600"],
              ["Failed", eligibility.summary.failed, "text-red-600"],
              ["Pending", eligibility.summary.pending, "text-amber-600"],
              ["Review", eligibility.review_status.replace(/_/g, " "), eligibility.review_status === "published" ? "text-emerald-600" : "text-amber-600"],
            ].map(([label, value, color]) => <div className="card p-4" key={String(label)}>
              <div className="text-xs uppercase text-slate-400">{label}</div><div className={`mt-1 text-xl font-semibold capitalize ${color}`}>{value}</div>
            </div>)}
          </div>

          <div className="flex gap-2">
            {(["all", "leaders", "failed"] as const).map((tab) => <button key={tab} className={view === tab ? "btn-primary" : "btn-ghost"} onClick={() => setView(tab)}>
              {tab === "all" ? `All students (${eligibility.rows.length})` : tab === "leaders" ? `Leader board (${eligibility.leaders.length})` : `Failed students (${eligibility.failed_students.length})`}
            </button>)}
          </div>

          <div className="card overflow-hidden">
            <div className="border-b px-4 py-3 text-sm text-slate-500">
              Subjects: {eligibility.subjects.join(", ") || "No subjects configured"} · HOD: {eligibility.reviewers.join(", ") || "Awaiting review"}
            </div>
            <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr><th className="px-4 py-3">Select</th><th>Rank</th><th>Student</th><th>Section</th><th>Cumulative</th><th>Grade</th><th>Subject result</th><th>Status</th></tr>
              </thead>
              <tbody className="divide-y">
                {shownRows.map((row) => <tr key={row.student_id}>
                  <td className="px-4 py-3"><input type="checkbox" disabled={!row.eligible}
                    checked={selected.includes(row.student_id)} onChange={() => toggle(row.student_id)} /></td>
                  <td>{row.rank ?? "—"}</td>
                  <td><div className="font-medium">{row.student}</div><div className="text-xs text-slate-400">{row.admission_no}</div></td>
                  <td>{row.section}</td><td className="font-semibold">{row.percentage}%</td><td>{row.grade}</td>
                  <td><div className="flex flex-wrap gap-1">{row.subject_results.map((subject) =>
                    <span key={subject.subject} className={`rounded px-1.5 py-0.5 text-xs ${subject.status === "passed" ? "bg-emerald-50 text-emerald-700" : subject.status === "failed" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
                      {subject.subject}: {subject.percentage}%
                    </span>)}</div></td>
                  <td className={row.eligible ? "text-emerald-600" : row.result === "failed" ? "text-red-600" : "text-amber-600"}>
                    <div className="font-medium capitalize">{row.result}</div><div className="max-w-xs text-xs">{row.reason}</div>
                  </td>
                </tr>)}
                {shownRows.length === 0 && <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">No students in this result group.</td></tr>}
              </tbody>
            </table></div>
          </div>
        </>
      )}

      {message && <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      <button className="btn-primary" disabled={!from || !fromSection || !to || (!graduating && !toSection) || !exam || !selected.length || run.isPending}
        onClick={() => run.mutate()}>{run.isPending ? "Promoting…" : `Promote ${selected.length || ""} eligible student(s)`}</button>
    </div>
  );
}

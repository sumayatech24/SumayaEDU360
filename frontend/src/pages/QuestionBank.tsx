import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import { useAuth } from "../lib/auth";

type Mapping = { id: string; grade_id?: string; section_id?: string; subject_id?: string; grade: string; section: string; subject: string };
type Question = { id: string; subject_id: string; grade_id: string; question_type: string; difficulty: string; marks: number; question_text: string; options: string[]; answer_text: string };
type Practice = { id: string; title: string; instructions?: string; due_date?: string; questions: Question[]; attempt?: { status: string; score?: number; max_score: number; feedback?: string } };
type TeacherAssignment = { id: string; title: string; status: string; due_date?: string; question_count: number };
type Attempt = { id: string; student: string; status: string; score?: number; max_score: number; feedback?: string };

export function QuestionBank() {
  const { portal } = useAuth();
  return portal?.portal === "student" || portal?.portal === "parent" ? <StudentPractice /> : <TeacherQuestionBank />;
}

export function TeacherQuestionBank() {
  const qc = useQueryClient();
  const [mappingId, setMappingId] = useState("");
  const [form, setForm] = useState({ question_type: "mcq", difficulty: "medium", marks: "1", question_text: "", answer_text: "", options: "" });
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState("");
  const [reviewAssignment, setReviewAssignment] = useState("");
  const { data: dashboard } = useQuery({ queryKey: ["qb-teacher-context"], queryFn: async () => (await api.get<{ assignments: Mapping[] }>("/portal/teacher/marks-entry-options")).data });
  const mappings = dashboard?.assignments ?? [];
  const mapping = mappings.find((m) => m.id === mappingId);
  const { data: questions = [] } = useQuery({ queryKey: ["teacher-question-bank"], queryFn: async () => (await api.get<Question[]>("/question-bank/questions")).data });
  const { data: assignments = [] } = useQuery({ queryKey: ["teacher-practice-assignments"], queryFn: async () => (await api.get<TeacherAssignment[]>("/question-bank/teacher/assignments")).data });
  const { data: attempts = [] } = useQuery({ enabled: !!reviewAssignment, queryKey: ["practice-attempts", reviewAssignment], queryFn: async () => (await api.get<Attempt[]>(`/question-bank/teacher/assignments/${reviewAssignment}/attempts`)).data });
  const scoped = useMemo(() => questions.filter((q) => !mapping || (q.grade_id === mapping.grade_id && q.subject_id === mapping.subject_id)), [questions, mapping]);
  const create = useMutation({
    mutationFn: async () => {
      if (!mapping?.grade_id || !mapping.subject_id) throw new Error("Choose an assigned class and subject");
      return api.post("/question-bank/questions", { ...form, marks: Number(form.marks), grade_id: mapping.grade_id, subject_id: mapping.subject_id, options: form.options.split("\n").map((x) => x.trim()).filter(Boolean) });
    },
    onSuccess: async () => { setForm({ question_type: "mcq", difficulty: "medium", marks: "1", question_text: "", answer_text: "", options: "" }); setError(""); await qc.invalidateQueries({ queryKey: ["teacher-question-bank"] }); },
    onError: (e) => setError(apiError(e)),
  });
  const assign = useMutation({
    mutationFn: async () => {
      if (!mapping?.grade_id || !mapping.subject_id) throw new Error("Choose an assigned class and subject");
      return api.post("/question-bank/assignments", { title, due_date: dueDate || null, grade_id: mapping.grade_id, section_id: mapping.section_id || null, subject_id: mapping.subject_id, question_ids: selected, publish: true });
    },
    onSuccess: async () => { setTitle(""); setDueDate(""); setSelected([]); setError(""); await qc.invalidateQueries({ queryKey: ["teacher-practice-assignments"] }); },
    onError: (e) => setError(apiError(e)),
  });
  const grade = useMutation({
    mutationFn: async (attempt: Attempt) => {
      const raw = window.prompt(`Score for ${attempt.student} (maximum ${attempt.max_score})`, String(attempt.score ?? 0));
      if (raw == null) return;
      const feedback = window.prompt("Feedback (optional)", attempt.feedback || "") || null;
      return api.post(`/question-bank/attempts/${attempt.id}/grade`, { score: Number(raw), feedback });
    },
    onSuccess: async () => qc.invalidateQueries({ queryKey: ["practice-attempts", reviewAssignment] }),
    onError: (e) => setError(apiError(e)),
  });
  return <div className="space-y-5">
    <div><h1 className="text-2xl font-semibold">Question Bank & Practice</h1><p className="text-sm text-slate-400">Create reusable questions from your teaching allocations, assemble a practice set, and publish it to the class.</p></div>
    <div className="card p-5">
      <label><span className="label">Assigned class and subject</span><select className="input max-w-xl" value={mappingId} onChange={(e) => { setMappingId(e.target.value); setSelected([]); }}><option value="">Select allocation</option>{mappings.map((m) => <option key={m.id} value={m.id}>{m.grade} · {m.section} · {m.subject}</option>)}</select></label>
    </div>
    {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
    <div className="grid gap-5 xl:grid-cols-2">
      <div className="card space-y-3 p-5"><h2 className="font-semibold">Add a question</h2>
        <div className="grid grid-cols-3 gap-3"><select className="input" value={form.question_type} onChange={(e) => setForm({ ...form, question_type: e.target.value })}><option value="mcq">MCQ</option><option value="true_false">True / False</option><option value="short">Short answer</option><option value="long">Long answer</option></select><select className="input" value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}><option>easy</option><option>medium</option><option>hard</option></select><input className="input" type="number" min="1" value={form.marks} onChange={(e) => setForm({ ...form, marks: e.target.value })} /></div>
        <textarea className="input min-h-24" placeholder="Question" value={form.question_text} onChange={(e) => setForm({ ...form, question_text: e.target.value })} />
        {(form.question_type === "mcq" || form.question_type === "true_false") && <textarea className="input min-h-20" placeholder="Options, one per line" value={form.options} onChange={(e) => setForm({ ...form, options: e.target.value })} />}
        <input className="input" placeholder="Correct / model answer" value={form.answer_text} onChange={(e) => setForm({ ...form, answer_text: e.target.value })} />
        <button className="btn-primary" disabled={!mapping || !form.question_text || !form.answer_text || create.isPending} onClick={() => create.mutate()}>Save question</button>
      </div>
      <div className="card space-y-3 p-5"><h2 className="font-semibold">Publish practice assignment</h2><input className="input" placeholder="Assignment title" value={title} onChange={(e) => setTitle(e.target.value)} /><input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        <div className="max-h-72 divide-y overflow-y-auto rounded-lg border">{scoped.map((q) => <label key={q.id} className="flex gap-3 p-3 text-sm"><input type="checkbox" checked={selected.includes(q.id)} onChange={(e) => setSelected(e.target.checked ? [...selected, q.id] : selected.filter((id) => id !== q.id))} /><span><span className="font-medium">{q.question_text}</span><span className="block text-xs text-slate-400">{q.question_type} · {q.difficulty} · {q.marks} mark(s)</span></span></label>)}{!scoped.length && <div className="p-5 text-sm text-slate-400">Add questions for the selected allocation first.</div>}</div>
        <button className="btn-primary" disabled={!title || !selected.length || assign.isPending} onClick={() => assign.mutate()}>Publish to students</button>
      </div>
    </div>
    <div className="card p-5"><h2 className="mb-3 font-semibold">Published assignments & submissions</h2><div className="grid gap-4 lg:grid-cols-[320px_1fr]"><div className="divide-y rounded-lg border">{assignments.map((a) => <button key={a.id} className={`block w-full p-3 text-left text-sm ${reviewAssignment === a.id ? "bg-brand-50" : ""}`} onClick={() => setReviewAssignment(a.id)}><span className="font-medium">{a.title}</span><span className="block text-xs text-slate-400">{a.question_count} questions · {a.status}</span></button>)}{!assignments.length && <div className="p-4 text-sm text-slate-400">No assignments published.</div>}</div><div className="divide-y">{attempts.map((a) => <div key={a.id} className="flex items-center justify-between gap-3 py-3 text-sm"><div><div className="font-medium">{a.student}</div><div className="text-xs text-slate-400">{a.status} · {a.score == null ? "manual grading needed" : `${a.score}/${a.max_score}`}</div></div><button className="btn-ghost border border-slate-200 px-3 py-1.5 text-xs" onClick={() => grade.mutate(a)}>Grade / feedback</button></div>)}{reviewAssignment && !attempts.length && <div className="p-4 text-sm text-slate-400">No student submissions yet.</div>}</div></div></div>
  </div>;
}

export function StudentPractice() {
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const { data = [] } = useQuery({ queryKey: ["student-practice"], queryFn: async () => (await api.get<Practice[]>("/question-bank/student/assignments")).data });
  const submit = useMutation({
    mutationFn: async (id: string) => api.post(`/question-bank/student/assignments/${id}/submit`, { answers }),
    onSuccess: async () => { setAnswers({}); setError(""); await qc.invalidateQueries({ queryKey: ["student-practice"] }); },
    onError: (e) => setError(apiError(e)),
  });
  return <div className="space-y-5"><div><h1 className="text-2xl font-semibold">Practice Assignments</h1><p className="text-sm text-slate-400">Solve question sets published for your class and review results.</p></div>{error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
    {data.map((a) => <div key={a.id} className="card p-5"><div className="mb-4 flex justify-between"><div><h2 className="font-semibold">{a.title}</h2><p className="text-xs text-slate-400">{a.due_date ? `Due ${a.due_date}` : "No due date"}</p></div>{a.attempt && <span className="badge bg-emerald-50 text-emerald-700">{a.attempt.status}{a.attempt.score != null ? ` · ${a.attempt.score}/${a.attempt.max_score}` : ""}</span>}</div>
      <div className="space-y-4">{a.questions.map((q, i) => <div key={q.id} className="rounded-lg border p-4"><div className="mb-2 text-sm font-medium">{i + 1}. {q.question_text} <span className="text-xs text-slate-400">({q.marks})</span></div>{!a.attempt && (q.options.length ? <div className="space-y-2">{q.options.map((option) => <label key={option} className="flex gap-2 text-sm"><input type="radio" name={q.id} checked={answers[q.id] === option} onChange={() => setAnswers({ ...answers, [q.id]: option })} />{option}</label>)}</div> : <textarea className="input" value={answers[q.id] || ""} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />)}</div>)}</div>
      {!a.attempt && <button className="btn-primary mt-4" disabled={submit.isPending} onClick={() => submit.mutate(a.id)}>Submit answers</button>}
    </div>)}{!data.length && <div className="card p-8 text-center text-sm text-slate-400">No practice assignments have been published for your class.</div>}
  </div>;
}

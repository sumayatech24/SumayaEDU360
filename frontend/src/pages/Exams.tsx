import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ResourcePage } from "../components/ResourcePage";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface Exam {
  id: string;
  name: string;
  code: string;
  exam_type: string;
  max_marks: string;
  pass_marks: string;
}

interface Student {
  id: string;
  first_name: string;
  last_name?: string;
  admission_no: string;
}

interface Subject {
  id: string;
  name: string;
  code: string;
}

interface Grade {
  id: string;
  name: string;
}

interface Section {
  id: string;
  name: string;
  grade_id: string;
}

interface MarkSheet {
  exam: { id: string; name: string; code: string };
  batch?: { id: string; status: string; reviewer_id?: string | null; review_note?: string | null } | null;
  rows: {
    student_id: string;
    admission_no: string;
    roll_no?: string | null;
    student_name: string;
    marks_obtained: string;
    max_marks: string;
    is_absent: boolean;
    remarks?: string | null;
    grade?: string | null;
  }[];
}

interface ReportCard {
  exam: { name: string; type: string };
  student: { name: string; admission_no: string };
  subjects: {
    subject_id: string;
    marks_obtained: string;
    max_marks: string;
    grade: string;
    is_absent: boolean;
  }[];
  total_obtained: number;
  total_max: number;
  percentage: number;
  overall_grade: string;
  result: string;
}

export function Exams() {
  const [tab, setTab] = useState<"setup" | "marks" | "report">("setup");
  const [examId, setExamId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [marks, setMarks] = useState("");
  const [maxMarks, setMaxMarks] = useState("100");
  const [sheetRows, setSheetRows] = useState<MarkSheet["rows"]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportCard | null>(null);

  const { data: exams } = useQuery({
    queryKey: ["exams-all"],
    queryFn: async () => (await api.get<Page<Exam>>("/exams", { params: { page_size: 200 } })).data,
  });
  const { data: students } = useQuery({
    queryKey: ["exam-students"],
    queryFn: async () => (await api.get<Page<Student>>("/students", { params: { page_size: 200 } })).data,
  });
  const { data: subjects } = useQuery({
    queryKey: ["exam-subjects"],
    queryFn: async () => (await api.get<Page<Subject>>("/subjects", { params: { page_size: 200 } })).data,
  });
  const { data: grades } = useQuery({
    queryKey: ["exam-grades"],
    queryFn: async () => (await api.get<Page<Grade>>("/grades", { params: { page_size: 200 } })).data,
  });
  const { data: sections } = useQuery({
    queryKey: ["exam-sections"],
    queryFn: async () => (await api.get<Page<Section>>("/sections", { params: { page_size: 200 } })).data,
  });

  const sheet = useQuery({
    queryKey: ["marks-sheet", examId, subjectId, gradeId, sectionId],
    enabled: tab === "marks" && !!examId && !!subjectId,
    queryFn: async () =>
      (
        await api.get<MarkSheet>(`/exams/${examId}/marks-sheet`, {
          params: {
            subject_id: subjectId,
            grade_id: gradeId || undefined,
            section_id: sectionId || undefined,
          },
        })
      ).data,
  });

  const enterMarks = useMutation({
    mutationFn: async () => {
      if (!window.confirm("Save this marksheet as draft? Please confirm the entered marks before saving.")) {
        throw new Error("Cancelled");
      }
      return api.post(`/exams/${examId}/marks-sheet`, {
        subject_id: subjectId,
        grade_id: gradeId || null,
        section_id: sectionId || null,
        entries: sheetRows.map((r) => ({
          student_id: r.student_id,
          subject_id: subjectId,
          marks_obtained: Number(r.marks_obtained || 0),
          max_marks: Number(r.max_marks || maxMarks || 100),
          is_absent: r.is_absent,
          remarks: r.remarks,
        })),
      });
    },
    onSuccess: (r) => {
      setMessage(`Saved ${r.data.count} marks as draft.`);
      setError(null);
      setReport(null);
      sheet.refetch();
    },
    onError: (e) => {
      setError(apiError(e));
      setMessage(null);
    },
  });

  const submitBatch = useMutation({
    mutationFn: async () => api.post(`/exams/marks-batches/${sheet.data?.batch?.id}/submit`),
    onSuccess: () => {
      setMessage("Marks sent to reviewer.");
      setError(null);
      sheet.refetch();
    },
    onError: (e) => setError(apiError(e)),
  });

  const reviewBatch = useMutation({
    mutationFn: async (decision: "approved" | "rejected" | "published") =>
      api.post(`/exams/marks-batches/${sheet.data?.batch?.id}/review`, { decision }),
    onSuccess: (r) => {
      setMessage(`Batch ${r.data.status}.`);
      setError(null);
      sheet.refetch();
    },
    onError: (e) => setError(apiError(e)),
  });

  const loadReport = useMutation({
    mutationFn: async () => (await api.get<ReportCard>(`/exams/${examId}/report-card/${studentId}`)).data,
    onSuccess: (data) => {
      setReport(data);
      setError(null);
      setMessage(null);
    },
    onError: (e) => {
      setError(apiError(e));
      setReport(null);
    },
  });

  const selectedExam = exams?.items.find((e) => e.id === examId);

  useEffect(() => {
    setSheetRows(sheet.data?.rows ?? []);
  }, [sheet.data]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Examinations</h1>
        <p className="text-sm text-slate-400">Exam setup, marks entry and student report cards.</p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
        {[
          ["setup", "Exam Setup"],
          ["marks", "Marks Entry"],
          ["report", "Report Card"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => {
              setTab(key as typeof tab);
              setMessage(null);
              setError(null);
            }}
            className={`rounded-t-lg px-3 py-2 text-sm ${
              tab === key
                ? "border-b-2 border-brand-600 font-medium text-brand-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "setup" && <ResourcePage entitySlug="exam" permPrefix="examination_management" title="Exam Setup" />}

      {tab !== "setup" && (
        <div className="card max-w-4xl space-y-4 p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="label">Exam</label>
              <select className="input" value={examId} onChange={(e) => setExamId(e.target.value)}>
                <option value="">-- select --</option>
                {exams?.items.map((exam) => (
                  <option key={exam.id} value={exam.id}>
                    {exam.name} - {exam.code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Student</label>
              <select className="input" value={studentId} onChange={(e) => setStudentId(e.target.value)}>
                <option value="">-- select --</option>
                {students?.items.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.first_name} {student.last_name ?? ""} - {student.admission_no}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {tab === "marks" && (
            <>
              <div className="grid gap-4 md:grid-cols-4">
                <div>
                  <label className="label">Subject</label>
                  <select className="input" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
                    <option value="">-- select --</option>
                    {subjects?.items.map((subject) => (
                      <option key={subject.id} value={subject.id}>
                        {subject.name} - {subject.code}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Grade</label>
                  <select className="input" value={gradeId} onChange={(e) => { setGradeId(e.target.value); setSheetRows([]); }}>
                    <option value="">All</option>
                    {grades?.items.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Section</label>
                  <select className="input" value={sectionId} onChange={(e) => { setSectionId(e.target.value); setSheetRows([]); }}>
                    <option value="">All</option>
                    {sections?.items
                      .filter((s) => !gradeId || s.grade_id === gradeId)
                      .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Default Max Marks</label>
                  <input type="number" className="input" value={maxMarks} onChange={(e) => setMaxMarks(e.target.value)} />
                </div>
              </div>
              {sheet.data?.batch && (
                <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  Batch status: <span className="font-semibold capitalize">{sheet.data.batch.status}</span>
                </div>
              )}
              <div className="overflow-hidden rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Roll</th>
                      <th className="px-3 py-2">Student</th>
                      <th className="px-3 py-2">Marks</th>
                      <th className="px-3 py-2">Max</th>
                      <th className="px-3 py-2">Absent</th>
                      <th className="px-3 py-2">Remarks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sheetRows.map((row, idx) => (
                      <tr key={row.student_id}>
                        <td className="px-3 py-2 text-slate-500">{row.roll_no || row.admission_no}</td>
                        <td className="px-3 py-2 font-medium">{row.student_name}</td>
                        <td className="px-3 py-2">
                          <input className="input h-9 w-24" type="number" value={row.marks_obtained}
                            onChange={(e) => setSheetRows((rows) => rows.map((r, i) => i === idx ? { ...r, marks_obtained: e.target.value } : r))} />
                        </td>
                        <td className="px-3 py-2">
                          <input className="input h-9 w-24" type="number" value={row.max_marks || maxMarks}
                            onChange={(e) => setSheetRows((rows) => rows.map((r, i) => i === idx ? { ...r, max_marks: e.target.value } : r))} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="checkbox" checked={row.is_absent}
                            onChange={(e) => setSheetRows((rows) => rows.map((r, i) => i === idx ? { ...r, is_absent: e.target.checked } : r))} />
                        </td>
                        <td className="px-3 py-2">
                          <input className="input h-9" value={row.remarks || ""}
                            onChange={(e) => setSheetRows((rows) => rows.map((r, i) => i === idx ? { ...r, remarks: e.target.value } : r))} />
                        </td>
                      </tr>
                    ))}
                    {!sheet.isLoading && sheetRows.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Select exam and subject to load students.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-primary" disabled={!examId || !subjectId || sheetRows.length === 0 || enterMarks.isPending} onClick={() => enterMarks.mutate()}>
                  {enterMarks.isPending ? "Saving..." : "Confirm & Save Draft"}
                </button>
                <button className="btn-ghost" disabled={!sheet.data?.batch?.id || submitBatch.isPending} onClick={() => submitBatch.mutate()}>
                  Send to Review
                </button>
                <button className="btn-ghost" disabled={sheet.data?.batch?.status !== "submitted"} onClick={() => reviewBatch.mutate("approved")}>
                  Approve
                </button>
                <button className="btn-ghost" disabled={sheet.data?.batch?.status !== "approved"} onClick={() => reviewBatch.mutate("published")}>
                  Publish to Students
                </button>
              </div>
            </>
          )}

          {tab === "report" && (
            <button
              className="btn-primary"
              disabled={!examId || !studentId || loadReport.isPending}
              onClick={() => loadReport.mutate()}
            >
              {loadReport.isPending ? "Loading..." : "View Report Card"}
            </button>
          )}

          {message && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</div>}
          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

          {report && (
            <div className="rounded-lg border border-slate-200">
              <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
                <div className="font-semibold">{report.student.name}</div>
                <div className="text-xs text-slate-500">
                  {report.student.admission_no} - {selectedExam?.name ?? report.exam.name}
                </div>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-white text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Marks</th>
                    <th className="px-4 py-3">Grade</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {report.subjects.map((row) => {
                    const subject = subjects?.items.find((s) => s.id === row.subject_id);
                    return (
                      <tr key={row.subject_id}>
                        <td className="px-4 py-3">{subject?.name ?? row.subject_id.slice(0, 8)}</td>
                        <td className="px-4 py-3">
                          {row.marks_obtained}/{row.max_marks}
                        </td>
                        <td className="px-4 py-3">{row.grade}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="grid gap-3 border-t border-slate-200 p-4 text-sm md:grid-cols-4">
                <Metric label="Total" value={`${report.total_obtained}/${report.total_max}`} />
                <Metric label="Percentage" value={`${report.percentage}%`} />
                <Metric label="Grade" value={report.overall_grade} />
                <Metric label="Result" value={report.result} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-lg font-semibold text-slate-800">{value}</div>
    </div>
  );
}

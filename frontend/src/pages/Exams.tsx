import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
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
  const [marks, setMarks] = useState("");
  const [maxMarks, setMaxMarks] = useState("100");
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

  const enterMarks = useMutation({
    mutationFn: async () =>
      api.post(`/exams/${examId}/marks`, {
        entries: [
          {
            student_id: studentId,
            subject_id: subjectId,
            marks_obtained: Number(marks),
            max_marks: Number(maxMarks),
          },
        ],
      }),
    onSuccess: (r) => {
      setMessage(`Recorded ${r.data.count} mark entry.`);
      setError(null);
      setReport(null);
    },
    onError: (e) => {
      setError(apiError(e));
      setMessage(null);
    },
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
              <div className="grid gap-4 md:grid-cols-3">
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
                  <label className="label">Marks Obtained</label>
                  <input
                    type="number"
                    className="input"
                    value={marks}
                    onChange={(e) => setMarks(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label">Max Marks</label>
                  <input
                    type="number"
                    className="input"
                    value={maxMarks}
                    onChange={(e) => setMaxMarks(e.target.value)}
                  />
                </div>
              </div>
              <button
                className="btn-primary"
                disabled={!examId || !studentId || !subjectId || !marks || enterMarks.isPending}
                onClick={() => enterMarks.mutate()}
              >
                {enterMarks.isPending ? "Saving..." : "Save Marks"}
              </button>
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

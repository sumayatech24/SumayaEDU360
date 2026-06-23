import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";
import type { Page } from "../lib/types";

interface Student360 {
  student: Record<string, any>;
  guardians: { name: string; relation: string; phone?: string; email?: string }[];
  fees: { billed: string; paid: string; balance: string; invoices: number };
  attendance: Record<string, number>;
  marks: { exam: string; subject: string; marks: string; max: string; grade?: string }[];
}

export function ParentPortal() {
  const [studentId, setStudentId] = useState("");

  const { data: students } = useQuery({
    queryKey: ["students-360-pick"],
    queryFn: async () => (await api.get<Page<any>>("/students", { params: { page_size: 200 } })).data,
  });

  const active = studentId || students?.items?.[0]?.id || "";

  const { data } = useQuery({
    enabled: !!active,
    queryKey: ["student-360", active],
    queryFn: async () => (await api.get<Student360>(`/reports/student-360/${active}`)).data,
  });

  const inr = (v?: string) => "₹" + Number(v ?? 0).toLocaleString("en-IN");
  const attTotal = data ? Object.values(data.attendance).reduce((a, b) => a + b, 0) : 0;
  const present = data?.attendance?.present ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Parent Portal — Student 360</h1>
          <p className="text-sm text-slate-400">Consolidated view: profile, guardians, fees, attendance and results.</p>
        </div>
        <select className="input w-64" value={active} onChange={(e) => setStudentId(e.target.value)}>
          {students?.items?.map((s: any) => (
            <option key={s.id} value={s.id}>
              {s.first_name} {s.last_name} · {s.admission_no}
            </option>
          ))}
        </select>
      </div>

      {data && (
        <>
          <div className="card flex flex-wrap items-center gap-6 p-5">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-2xl font-bold text-brand-700">
              {data.student.name?.[0]}
            </div>
            <div>
              <div className="text-lg font-semibold">{data.student.name}</div>
              <div className="text-sm text-slate-400">
                {data.student.admission_no} · Grade {data.student.grade} · Section {data.student.section}
              </div>
            </div>
            <div className="ml-auto flex gap-6 text-sm">
              <Info label="Status" value={data.student.status} />
              <Info label="Phone" value={data.student.phone || "—"} />
              <Info label="Email" value={data.student.email || "—"} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">Fees</h3>
              <Row label="Billed" value={inr(data.fees.billed)} />
              <Row label="Paid" value={inr(data.fees.paid)} tone="green" />
              <Row label="Balance" value={inr(data.fees.balance)} tone="amber" />
              <div className="mt-1 text-xs text-slate-400">{data.fees.invoices} invoice(s)</div>
            </div>
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">Attendance</h3>
              <div className="text-3xl font-semibold">
                {attTotal ? Math.round((present / attTotal) * 100) : 0}%
              </div>
              <div className="text-xs text-slate-400">present rate ({present}/{attTotal} days)</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(data.attendance).map(([state, n]) => (
                  <span key={state} className="badge bg-slate-100 text-slate-600">
                    {state}: {n}
                  </span>
                ))}
              </div>
            </div>
            <div className="card p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">Guardians</h3>
              {data.guardians.length === 0 && <p className="text-sm text-slate-400">None on record.</p>}
              {data.guardians.map((g, i) => (
                <div key={i} className="mb-2 text-sm">
                  <span className="font-medium">{g.name}</span>
                  <span className="ml-2 text-xs capitalize text-slate-400">{g.relation}</span>
                  <div className="text-xs text-slate-400">{g.phone || g.email || "—"}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-600">
              Exam Results
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Exam</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Marks</th>
                  <th className="px-4 py-3">Grade</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.marks.map((m, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">{m.exam}</td>
                    <td className="px-4 py-2.5">{m.subject}</td>
                    <td className="px-4 py-2.5">
                      {m.marks} / {m.max}
                    </td>
                    <td className="px-4 py-2.5">{m.grade || "—"}</td>
                  </tr>
                ))}
                {data.marks.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                      No marks recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="font-medium capitalize">{value}</div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  const tones: Record<string, string> = { green: "text-emerald-600", amber: "text-amber-600" };
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className={`font-medium ${tone ? tones[tone] : ""}`}>{value}</span>
    </div>
  );
}

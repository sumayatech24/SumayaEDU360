import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface Student {
  id: string;
  first_name: string;
  last_name?: string;
  admission_no: string;
  section_id?: string;
}

const STATES = ["present", "absent", "late", "leave"];

export function Attendance() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["students-att"],
    queryFn: async () => (await api.get<Page<Student>>("/students", { params: { page_size: 100 } })).data,
  });
  const students = data?.items ?? [];

  const submit = useMutation({
    mutationFn: async () =>
      api.post("/attendance/bulk", {
        att_date: date,
        method: "manual",
        entries: students.map((s) => ({ student_id: s.id, state: marks[s.id] ?? "present" })),
      }),
    onSuccess: (r: any) => {
      setMsg(`Recorded attendance for ${r.data.count} students on ${r.data.date}.`);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Attendance</h1>
          <p className="text-sm text-slate-400">Mark daily attendance (manual / QR / RFID / biometric capable).</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="label">Date</label>
            <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <button className="btn-primary" disabled={submit.isPending} onClick={() => submit.mutate()}>
            {submit.isPending ? "Saving…" : "Save Attendance"}
          </button>
        </div>
      </div>

      {msg && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

      <div className="card divide-y divide-slate-100">
        {students.map((s) => (
          <div key={s.id} className="flex items-center justify-between px-4 py-3">
            <div className="text-sm">
              <span className="font-medium">
                {s.first_name} {s.last_name}
              </span>
              <span className="ml-2 text-xs text-slate-400">{s.admission_no}</span>
            </div>
            <div className="flex gap-1">
              {STATES.map((st) => {
                const active = (marks[s.id] ?? "present") === st;
                return (
                  <button
                    key={st}
                    onClick={() => setMarks((m) => ({ ...m, [s.id]: st }))}
                    className={`rounded-lg px-3 py-1 text-xs capitalize ${
                      active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                  >
                    {st}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        {students.length === 0 && <p className="px-4 py-6 text-sm text-slate-400">No students.</p>}
      </div>
    </div>
  );
}

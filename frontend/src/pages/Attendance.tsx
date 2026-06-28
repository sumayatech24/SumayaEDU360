import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

type PersonType = "student" | "employee";
interface MasterValue { code: string; label: string }
interface Person { id: string; name: string; sub: string }

function useMaster(code: string) {
  return useQuery({
    queryKey: ["master-values", code],
    queryFn: async () => (await api.get<MasterValue[]>(`/master-types/${code}/values`)).data,
  });
}

export function Attendance() {
  const today = new Date().toISOString().slice(0, 10);
  const [tab, setTab] = useState<PersonType>("student");
  const [date, setDate] = useState(today);
  const [method, setMethod] = useState("manual");
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const states = useMaster("attendance_state");
  const methods = useMaster("attendance_method");

  // Roster for the active tab.
  const studentsQ = useQuery({
    enabled: tab === "student",
    queryKey: ["att-students"],
    queryFn: async () => (await api.get<Page<any>>("/students", { params: { page_size: 200 } })).data,
  });
  const staffQ = useQuery({
    enabled: tab === "employee",
    queryKey: ["att-staff"],
    queryFn: async () => (await api.get<Page<any>>("/employees", { params: { page_size: 200 } })).data,
  });

  const people: Person[] = useMemo(() => {
    if (tab === "student") {
      return (studentsQ.data?.items ?? []).map((s: any) => ({
        id: s.id, name: `${s.first_name} ${s.last_name ?? ""}`.trim(), sub: s.admission_no,
      }));
    }
    return (staffQ.data?.items ?? []).map((e: any) => ({
      id: e.id, name: `${e.first_name} ${e.last_name ?? ""}`.trim(), sub: e.employee_no,
    }));
  }, [tab, studentsQ.data, staffQ.data]);

  // Existing marks for the chosen date prefill the grid.
  const dayQ = useQuery({
    queryKey: ["att-day", tab, date],
    queryFn: async () =>
      (await api.get<{ marks: Record<string, { state: string }> }>(
        `/attendance/day`, { params: { person_type: tab, att_date: date } })).data,
  });
  useEffect(() => {
    const m: Record<string, string> = {};
    Object.entries(dayQ.data?.marks ?? {}).forEach(([pid, v]) => (m[pid] = v.state));
    setMarks(m);
  }, [dayQ.data]);

  // Default the method dropdown to the first master value once loaded.
  useEffect(() => {
    if (methods.data?.length && !methods.data.some((m) => m.code === method)) {
      setMethod(methods.data[0].code);
    }
  }, [methods.data]);

  const stateOptions = states.data ?? [{ code: "present", label: "Present" }];

  async function save() {
    setSaving(true); setError(null); setMsg(null);
    try {
      const r = await api.post("/attendance/bulk", {
        person_type: tab,
        att_date: date,
        method,
        entries: people.map((p) => ({ person_id: p.id, state: marks[p.id] ?? "present" })),
      });
      setMsg(`Recorded attendance for ${r.data.count} ${tab === "student" ? "students" : "staff"} on ${r.data.date}.`);
    } catch (e) { setError(apiError(e)); } finally { setSaving(false); }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Attendance</h1>
          <p className="text-sm text-slate-400">Daily attendance for students and staff — states & methods are master-driven.</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="label">Method</label>
            <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              {(methods.data ?? [{ code: "manual", label: "Manual" }]).map((m) => (
                <option key={m.code} value={m.code}>{m.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Date</label>
            <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <button className="btn-primary" disabled={saving} onClick={() => void save()}>
            {saving ? "Saving…" : "Save Attendance"}
          </button>
        </div>
      </div>

      <div className="flex gap-2 border-b border-slate-200">
        {([["student", "Students"], ["employee", "Staff"]] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px rounded-t-lg px-4 py-2 text-sm ${
              tab === key ? "border-b-2 border-brand-600 font-medium text-brand-700" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {msg && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
      {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

      <div className="card divide-y divide-slate-100">
        {people.map((p) => (
          <div key={p.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="text-sm">
              <span className="font-medium">{p.name}</span>
              <span className="ml-2 text-xs text-slate-400">{p.sub}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {stateOptions.map((st) => {
                const active = (marks[p.id] ?? "present") === st.code;
                return (
                  <button
                    key={st.code}
                    onClick={() => setMarks((m) => ({ ...m, [p.id]: st.code }))}
                    className={`rounded-lg px-3 py-1 text-xs ${
                      active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                  >
                    {st.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        {people.length === 0 && (
          <p className="px-4 py-6 text-sm text-slate-400">
            No {tab === "student" ? "students" : "staff"} found.
          </p>
        )}
      </div>
    </div>
  );
}

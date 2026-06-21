import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface Grade {
  id: string;
  name: string;
  sequence: number;
}

export function Promotion() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [graduating, setGraduating] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["grades-all"],
    queryFn: async () => (await api.get<Page<Grade>>("/grades", { params: { page_size: 100 } })).data,
  });
  const grades = (data?.items ?? []).sort((a, b) => a.sequence - b.sequence);

  const run = useMutation({
    mutationFn: async () =>
      (
        await api.post("/promotion/run", {
          from_grade_id: from,
          to_grade_id: to,
          mark_graduating: graduating,
        })
      ).data,
    onSuccess: (d: any) => {
      setResult(`Promoted ${d.promoted} student(s) from ${d.from_grade} → ${d.to_grade} (${d.status_set}).`);
      setError(null);
    },
    onError: (e) => {
      setError(apiError(e));
      setResult(null);
    },
  });

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Student Promotion</h1>
        <p className="text-sm text-slate-400">
          Move a cohort to the next class. Enrolled students are updated transactionally with an audit entry.
        </p>
      </div>

      <div className="card space-y-4 p-6">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">From Grade</label>
            <select className="input" value={from} onChange={(e) => setFrom(e.target.value)}>
              <option value="">— select —</option>
              {grades.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">To Grade</label>
            <select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
              <option value="">— select —</option>
              {grades.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={graduating} onChange={(e) => setGraduating(e.target.checked)} />
          Mark as graduated (final class)
        </label>

        {result && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{result}</div>}
        {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

        <button
          className="btn-primary"
          disabled={!from || !to || from === to || run.isPending}
          onClick={() => run.mutate()}
        >
          {run.isPending ? "Promoting…" : "Run Promotion"}
        </button>
      </div>
    </div>
  );
}

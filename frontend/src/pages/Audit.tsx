import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

interface AuditRow {
  id: string;
  action: string;
  entity: string;
  entity_id?: string;
  actor_email?: string;
  method?: string;
  path?: string;
  created_at?: string;
}

const ACTION_TONE: Record<string, string> = {
  create: "bg-emerald-50 text-emerald-600",
  update: "bg-amber-50 text-amber-600",
  delete: "bg-red-50 text-red-600",
  login: "bg-brand-50 text-brand-700",
};

export function Audit() {
  const { data = [] } = useQuery({
    queryKey: ["audit-log"],
    queryFn: async () => (await api.get<AuditRow[]>("/reports/audit-log", { params: { limit: 200 } })).data,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Audit Log</h1>
        <p className="text-sm text-slate-400">Immutable trail of every mutation across the system.</p>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Actor</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Entity</th>
              <th className="px-4 py-3">Path</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3">{r.actor_email ?? "system"}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${ACTION_TONE[r.action] ?? "bg-slate-100 text-slate-600"}`}>
                    {r.action}
                  </span>
                </td>
                <td className="px-4 py-3">{r.entity}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">
                  {r.method} {r.path}
                </td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  No audit entries yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

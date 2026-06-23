import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../lib/api";

interface ReportFilter {
  key: string;
  label: string;
  type: "date" | "bool" | "text";
}
interface ReportMeta {
  key: string;
  name: string;
  module: string;
  filters: ReportFilter[];
}
interface ReportResult {
  key: string;
  name: string;
  columns: { key: string; label: string }[];
  rows: Record<string, any>[];
  total: number;
}

export function Reports() {
  const [selected, setSelected] = useState<ReportMeta | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const { data: catalog = [] } = useQuery({
    queryKey: ["report-catalog"],
    queryFn: async () => (await api.get<ReportMeta[]>("/reports/catalog")).data,
  });

  const active = selected ?? catalog[0] ?? null;

  const { data: result, isFetching } = useQuery({
    enabled: !!active,
    queryKey: ["report-run", active?.key, filters],
    queryFn: async () =>
      (await api.get<ReportResult>(`/reports/run/${active!.key}`, { params: filters })).data,
  });

  const grouped = useMemo(() => {
    const g: Record<string, ReportMeta[]> = {};
    catalog.forEach((r) => (g[r.module] = [...(g[r.module] ?? []), r]));
    return g;
  }, [catalog]);

  function exportCsv() {
    if (!result) return;
    const head = result.columns.map((c) => `"${c.label}"`).join(",");
    const body = result.rows
      .map((row) => result.columns.map((c) => `"${String(row[c.key] ?? "").replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([head + "\n" + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.key}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="text-sm text-slate-400">{catalog.length} reports across every module — filter and export to CSV.</p>
      </div>

      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-3 card max-h-[72vh] overflow-y-auto p-2">
          {Object.entries(grouped).map(([module, reports]) => (
            <div key={module} className="mb-2">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {module}
              </div>
              {reports.map((r) => (
                <button
                  key={r.key}
                  onClick={() => {
                    setSelected(r);
                    setFilters({});
                  }}
                  className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm ${
                    active?.key === r.key ? "bg-brand-50 font-medium text-brand-700" : "hover:bg-slate-100"
                  }`}
                >
                  {r.name}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="col-span-9 space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap items-end gap-3">
              {active?.filters.map((f) => (
                <div key={f.key}>
                  <label className="label">{f.label}</label>
                  {f.type === "bool" ? (
                    <select
                      className="input w-40"
                      value={filters[f.key] ?? ""}
                      onChange={(e) => setFilters((v) => ({ ...v, [f.key]: e.target.value }))}
                    >
                      <option value="">No</option>
                      <option value="true">Yes</option>
                    </select>
                  ) : (
                    <input
                      type={f.type === "date" ? "date" : "text"}
                      className="input w-44"
                      value={filters[f.key] ?? ""}
                      onChange={(e) => setFilters((v) => ({ ...v, [f.key]: e.target.value }))}
                    />
                  )}
                </div>
              ))}
            </div>
            <button className="btn-primary" disabled={!result?.rows.length} onClick={exportCsv}>
              Export CSV
            </button>
          </div>

          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h3 className="text-sm font-semibold text-slate-600">{result?.name ?? "—"}</h3>
              <span className="text-xs text-slate-400">{result?.total ?? 0} rows</span>
            </div>
            <div className="max-h-[60vh] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    {result?.columns.map((c) => (
                      <th key={c.key} className="px-4 py-3 font-medium">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {isFetching && (
                    <tr>
                      <td colSpan={result?.columns.length ?? 1} className="px-4 py-8 text-center text-slate-400">
                        Loading…
                      </td>
                    </tr>
                  )}
                  {!isFetching &&
                    result?.rows.map((row, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        {result.columns.map((c) => (
                          <td key={c.key} className="px-4 py-2.5">
                            {renderCell(row[c.key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  {!isFetching && (result?.rows.length ?? 0) === 0 && (
                    <tr>
                      <td colSpan={result?.columns.length ?? 1} className="px-4 py-8 text-center text-slate-400">
                        No data for this report.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function renderCell(v: any) {
  if (v === "LOW" || v === "overdue")
    return <span className="badge bg-red-50 text-red-600">{v}</span>;
  if (v === "OK" || v === "paid" || v === "approved")
    return <span className="badge bg-emerald-50 text-emerald-600">{v}</span>;
  return v === null || v === undefined || v === "" ? <span className="text-slate-300">—</span> : String(v);
}

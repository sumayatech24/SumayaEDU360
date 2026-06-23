import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import type { EntityDef } from "../lib/types";

export function FieldCustomizer() {
  const qc = useQueryClient();
  const [slug, setSlug] = useState("");
  const [drafts, setDrafts] = useState<Record<string, { label: string; is_required: boolean; is_list_visible: boolean }>>({});
  const [savedField, setSavedField] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: entities = [] } = useQuery({
    queryKey: ["entities-all"],
    queryFn: async () => (await api.get<EntityDef[]>("/entities")).data,
  });
  const active = slug || entities[0]?.slug || "";

  const { data: entity } = useQuery({
    enabled: !!active,
    queryKey: ["entity-fields", active],
    queryFn: async () => (await api.get<EntityDef>(`/entities/${active}`)).data,
  });

  const fields = useMemo(() => entity?.fields ?? [], [entity]);

  function draftFor(name: string, fallback: any) {
    return drafts[name] ?? fallback;
  }

  const save = useMutation({
    mutationFn: async ({ name, body }: { name: string; body: any }) =>
      api.put(`/entities/${active}/fields/${name}`, body),
    onSuccess: (_d, vars) => {
      setSavedField(vars.name);
      setError(null);
      qc.invalidateQueries({ queryKey: ["entity-fields", active] });
      qc.invalidateQueries({ queryKey: ["entity", active] });
      setTimeout(() => setSavedField(null), 1500);
    },
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Customize Fields</h1>
          <p className="text-sm text-slate-400">
            Rename any field label and control whether it's required or shown in lists. Changes apply across forms and tables.
          </p>
        </div>
        <div>
          <label className="label">Entity</label>
          <select className="input w-64" value={active} onChange={(e) => { setSlug(e.target.value); setDrafts({}); }}>
            {entities.map((e) => (
              <option key={e.slug} value={e.slug}>
                {e.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Field</th>
              <th className="px-4 py-3">Label (rename)</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3 text-center">Required</th>
              <th className="px-4 py-3 text-center">In List</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fields.map((f) => {
              const d = drafts[f.name] ?? {
                label: f.label,
                is_required: f.is_required,
                is_list_visible: f.is_list_visible,
              };
              const setD = (patch: Partial<typeof d>) =>
                setDrafts((prev) => ({ ...prev, [f.name]: { ...d, ...patch } }));
              return (
                <tr key={f.name} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-400">{f.name}</td>
                  <td className="px-4 py-2.5">
                    <input className="input" value={d.label} onChange={(e) => setD({ label: e.target.value })} />
                  </td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {f.data_type}
                    {f.options_master ? ` · ${f.options_master}` : ""}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <input type="checkbox" checked={d.is_required} onChange={(e) => setD({ is_required: e.target.checked })} />
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <input type="checkbox" checked={d.is_list_visible} onChange={(e) => setD({ is_list_visible: e.target.checked })} />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      className="btn-primary px-2.5 py-1 text-xs"
                      disabled={save.isPending}
                      onClick={() => save.mutate({ name: f.name, body: d })}
                    >
                      {savedField === f.name ? "Saved ✓" : "Save"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {fields.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  This entity has no editable fields.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

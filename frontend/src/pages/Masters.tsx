import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";

interface MasterType {
  id: string;
  code: string;
  name: string;
  description?: string;
}
interface MasterValue {
  id: string;
  code: string;
  label: string;
  sort_order: number;
  is_active: boolean;
}

export function Masters() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: types = [] } = useQuery({
    queryKey: ["master-types"],
    queryFn: async () => (await api.get<MasterType[]>("/master-types")).data,
  });

  const active = selected ?? types[0]?.code ?? null;

  const { data: values = [] } = useQuery({
    enabled: !!active,
    queryKey: ["master-values-admin", active],
    queryFn: async () => (await api.get<MasterValue[]>(`/master-types/${active}/values`)).data,
  });

  const addValue = useMutation({
    mutationFn: async () =>
      api.post(`/master-types/${active}/values`, {
        code: newLabel.toLowerCase().replace(/\s+/g, "_"),
        label: newLabel,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["master-values-admin", active] });
      setNewLabel("");
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const delValue = useMutation({
    mutationFn: async (id: string) => api.delete(`/master-values/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["master-values-admin", active] }),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Masters & Configuration</h1>
        <p className="text-sm text-slate-400">
          Every lookup list is configurable here and stored in the database.
        </p>
      </div>

      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-4 card max-h-[70vh] overflow-y-auto p-2">
          {types.map((t) => (
            <button
              key={t.code}
              onClick={() => setSelected(t.code)}
              className={`flex w-full flex-col rounded-lg px-3 py-2 text-left text-sm ${
                active === t.code ? "bg-brand-50 text-brand-700" : "hover:bg-slate-100"
              }`}
            >
              <span className="font-medium">{t.name}</span>
              <span className="text-[11px] text-slate-400">{t.code}</span>
            </button>
          ))}
        </div>

        <div className="col-span-8 card p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-600">
            Values · <span className="text-slate-400">{active}</span>
          </h3>

          <div className="mb-4 flex gap-2">
            <input
              className="input"
              placeholder="Add a new value…"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && newLabel && addValue.mutate()}
            />
            <button className="btn-primary" disabled={!newLabel} onClick={() => addValue.mutate()}>
              Add
            </button>
          </div>
          {error && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

          <div className="divide-y divide-slate-100">
            {values.map((v) => (
              <div key={v.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <span className="font-medium">{v.label}</span>
                  <span className="ml-2 text-[11px] text-slate-400">{v.code}</span>
                </div>
                <button
                  className="btn-danger px-2 py-1 text-xs"
                  onClick={() => delValue.mutate(v.id)}
                >
                  Remove
                </button>
              </div>
            ))}
            {values.length === 0 && <p className="py-4 text-sm text-slate-400">No values.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

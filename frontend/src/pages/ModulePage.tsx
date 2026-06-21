import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { ResourcePage } from "../components/ResourcePage";
import type { EntityDef, ModuleDef } from "../lib/types";

export function ModulePage() {
  const { slug = "" } = useParams();
  const [active, setActive] = useState<string | null>(null);

  const { data: modules = [] } = useQuery({
    queryKey: ["modules"],
    queryFn: async () => (await api.get<ModuleDef[]>("/modules")).data,
  });
  const mod = modules.find((m) => m.slug === slug);

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ["module-entities", slug],
    queryFn: async () =>
      (await api.get<EntityDef[]>("/entities", { params: { module_slug: slug } })).data,
  });

  const selected = active ?? entities[0]?.slug ?? null;

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="badge bg-brand-50 text-brand-700">{mod?.code ?? "Module"}</span>
          {mod?.release_bucket && (
            <span className="badge bg-slate-100 text-slate-500">{mod.release_bucket}</span>
          )}
        </div>
        <h1 className="mt-2 text-2xl font-semibold">{mod?.name ?? slug}</h1>
        {mod?.description && <p className="max-w-3xl text-sm text-slate-400">{mod.description}</p>}
      </div>

      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}

      {entities.length > 1 && (
        <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
          {entities.map((e) => (
            <button
              key={e.slug}
              onClick={() => setActive(e.slug)}
              className={`rounded-t-lg px-3 py-2 text-sm ${
                selected === e.slug
                  ? "border-b-2 border-brand-600 font-medium text-brand-700"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {e.name}
              <span className="ml-1.5 text-[10px] uppercase text-slate-400">
                {e.is_typed ? "typed" : e.kind}
              </span>
            </button>
          ))}
        </div>
      )}

      {selected && <ResourcePage key={selected} entitySlug={selected} permPrefix={slug} />}
      {!isLoading && entities.length === 0 && (
        <p className="text-sm text-slate-400">No entities configured for this module yet.</p>
      )}
    </div>
  );
}

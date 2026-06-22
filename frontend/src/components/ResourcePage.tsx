import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { endpointFor } from "../lib/resources";
import type { EntityDef, Page } from "../lib/types";
import { EntityForm } from "./EntityForm";
import { Modal } from "./Modal";

interface Props {
  entitySlug: string;
  permPrefix?: string; // module slug for RBAC gating of buttons
  title?: string;
}

export function ResourcePage({ entitySlug, permPrefix, title }: Props) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<Record<string, any> | null>(null);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: entity } = useQuery({
    queryKey: ["entity", entitySlug],
    queryFn: async () => (await api.get<EntityDef>(`/entities/${entitySlug}`)).data,
  });

  const ep = entity ? endpointFor(entity) : null;

  const { data: pageData, isLoading } = useQuery({
    enabled: !!ep,
    queryKey: ["resource", entitySlug, page, q],
    queryFn: async () => {
      const { data } = await api.get<Page<any>>(ep!.base, {
        params: { page, page_size: 10, q: q || undefined },
      });
      return data;
    },
  });

  const fields = entity?.fields ?? [];
  const listFields = useMemo(() => fields.filter((f) => f.is_list_visible), [fields]);

  function rowData(row: any): Record<string, any> {
    return ep?.generic ? row.data ?? {} : row;
  }

  const saveMutation = useMutation({
    mutationFn: async (values: Record<string, any>) => {
      const id = editing?.__id;
      if (ep!.generic) {
        const body = { data: values };
        if (id) return api.put(`${ep!.base}/${id}`, body);
        return api.post(ep!.base, body);
      }
      if (id) return api.put(`${ep!.base}/${id}`, values);
      return api.post(ep!.base, values);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resource", entitySlug] });
      setCreating(false);
      setEditing(null);
      setFormError(null);
    },
    onError: (e) => setFormError(apiError(e)),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => api.delete(`${ep!.base}/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["resource", entitySlug] }),
  });

  const canCreate = !permPrefix || can(`${permPrefix}:create`);
  const canDelete = !permPrefix || can(`${permPrefix}:delete`);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{title || entity?.name || "Records"}</h1>
          {entity?.purpose && <p className="text-sm text-slate-400">{entity.purpose}</p>}
        </div>
        <div className="flex items-center gap-2">
          <input
            className="input w-56"
            placeholder="Search…"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
          />
          {canCreate && (
            <button
              className="btn-primary"
              onClick={() => {
                setFormError(null);
                setCreating(true);
              }}
            >
              + New
            </button>
          )}
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              {listFields.map((f) => (
                <th key={f.name} className="px-4 py-3 font-medium">
                  {f.label}
                </th>
              ))}
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={listFields.length + 1} className="px-4 py-8 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && (pageData?.items?.length ?? 0) === 0 && (
              <tr>
                <td colSpan={listFields.length + 1} className="px-4 py-8 text-center text-slate-400">
                  No records yet.
                </td>
              </tr>
            )}
            {pageData?.items?.map((row: any) => {
              const d = rowData(row);
              return (
                <tr key={row.id} className="hover:bg-slate-50">
                  {listFields.map((f) => (
                    <td key={f.name} className="px-4 py-3">
                      {formatCell(d[f.name])}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right">
                    <button
                      className="btn-ghost px-2 py-1 text-xs"
                      onClick={() => {
                        setFormError(null);
                        setEditing({ ...d, __id: row.id });
                      }}
                    >
                      Edit
                    </button>
                    {canDelete && (
                      <button
                        className="btn-danger px-2 py-1 text-xs"
                        onClick={() => {
                          if (confirm("Delete this record?")) deleteMutation.mutate(row.id);
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500">
          <span>{pageData?.total ?? 0} total</span>
          <div className="flex items-center gap-2">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Prev
            </button>
            <span>
              Page {pageData?.page ?? 1} / {pageData?.pages ?? 1}
            </span>
            <button
              className="btn-ghost"
              disabled={(pageData?.page ?? 1) >= (pageData?.pages ?? 1)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {(creating || editing) && (
        <Modal
          wide
          title={editing ? `Edit ${entity?.name}` : `New ${entity?.name}`}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
        >
          <EntityForm
            fields={fields}
            initial={editing ?? undefined}
            error={formError}
            submitting={saveMutation.isPending}
            onCancel={() => {
              setCreating(false);
              setEditing(null);
            }}
            onSubmit={async (values) => {
              await saveMutation.mutateAsync(values);
            }}
          />
        </Modal>
      )}
    </div>
  );
}

function formatCell(v: any) {
  if (v === null || v === undefined || v === "") return <span className="text-slate-300">—</span>;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

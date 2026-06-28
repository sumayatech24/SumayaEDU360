import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useBranding } from "../lib/branding";
import { endpointFor, rowLabel } from "../lib/resources";
import { exportCsv, exportExcel, exportPdf, type ExportColumn, type ExportRow } from "../lib/export";
import type { EntityDef, FieldDef, Page } from "../lib/types";
import { EntityForm } from "./EntityForm";
import { Modal } from "./Modal";

/** Build id→label and code→label lookups so list cells render real names
 *  instead of the raw UUIDs / codes stored on each record. */
function useDisplayMaps(listFields: FieldDef[]) {
  const refSlugs = useMemo(
    () => [...new Set(listFields.filter((f) => f.reference_entity).map((f) => f.reference_entity!))],
    [listFields],
  );
  const masterTypes = useMemo(
    () => [...new Set(listFields.filter((f) => f.options_master).map((f) => f.options_master!))],
    [listFields],
  );

  // Definitions of the referenced entities (needed to label their rows + find their endpoint).
  const refEntities = useQueries({
    queries: refSlugs.map((slug) => ({
      queryKey: ["entity", slug],
      queryFn: async () => (await api.get<EntityDef>(`/entities/${slug}`)).data,
      staleTime: 5 * 60_000,
    })),
  });
  // The referenced collections themselves.
  const refCollections = useQueries({
    queries: refSlugs.map((slug, i) => {
      const ent = refEntities[i].data;
      const ep = ent ? endpointFor(ent) : null;
      return {
        queryKey: ["ref-options", slug],
        enabled: !!ep,
        staleTime: 5 * 60_000,
        queryFn: async () => (await api.get<Page<any>>(ep!.base, { params: { page_size: 500 } })).data,
      };
    }),
  });
  const masterValues = useQueries({
    queries: masterTypes.map((type) => ({
      queryKey: ["master-values", type],
      queryFn: async () =>
        (await api.get<{ code: string; label: string }[]>(`/master-types/${type}/values`)).data,
      staleTime: 5 * 60_000,
    })),
  });

  return useMemo(() => {
    const refs: Record<string, Record<string, string>> = {};
    refSlugs.forEach((slug, i) => {
      const ent = refEntities[i].data;
      const map: Record<string, string> = {};
      (refCollections[i].data?.items ?? []).forEach((row: any) => {
        map[row.id] = rowLabel(ent, row);
      });
      refs[slug] = map;
    });
    const masters: Record<string, Record<string, string>> = {};
    masterTypes.forEach((type, i) => {
      masters[type] = Object.fromEntries((masterValues[i].data ?? []).map((v) => [v.code, v.label]));
    });
    return { refs, masters };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refSlugs, masterTypes, refEntities.map((q) => q.data), refCollections.map((q) => q.data), masterValues.map((q) => q.data)]);
}

export interface RowAction {
  label: string;
  tone?: "primary" | "danger" | "ghost";
  /** Only show the button when this returns true for the row's data. */
  show?: (row: Record<string, any>) => boolean;
  /** Perform the workflow action; throw to surface an error. */
  run: (row: Record<string, any>, id: string) => Promise<void>;
}

interface Props {
  entitySlug: string;
  permPrefix?: string; // module slug for RBAC gating of buttons
  title?: string;
  hideCreate?: boolean;
  rowActions?: RowAction[];
  /** Render a "View" link per row to this path. */
  viewPath?: (id: string) => string;
}

export function ResourcePage({ entitySlug, permPrefix, title, hideCreate, rowActions, viewPath }: Props) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const brand = useBranding();
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
  const displayMaps = useDisplayMaps(listFields);

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

  const actionMutation = useMutation({
    mutationFn: async ({ action, row, id }: { action: RowAction; row: Record<string, any>; id: string }) =>
      action.run(row, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resource", entitySlug] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => alert(apiError(e)),
  });

  const canCreate = !hideCreate && (!permPrefix || can(`${permPrefix}:create`));
  const canDelete = !permPrefix || can(`${permPrefix}:delete`);

  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function runExport(kind: "csv" | "excel" | "pdf") {
    if (!ep) return;
    setExportOpen(false);
    setExporting(true);
    try {
      // Pull the full (filtered) result set, not just the visible page.
      const { data } = await api.get<Page<any>>(ep.base, { params: { page_size: 1000, q: q || undefined } });
      const items = data.items ?? [];
      const columns: ExportColumn[] = listFields.map((f) => ({ key: f.name, label: f.label }));
      const rows: ExportRow[] = items.map((it: any) => {
        const d = rowData(it);
        const out: ExportRow = {};
        listFields.forEach((f) => {
          out[f.name] = resolveCellText(d[f.name], f, displayMaps);
        });
        return out;
      });
      const name = title || entity?.name || "Records";
      if (kind === "csv") exportCsv(name, columns, rows);
      else if (kind === "excel") exportExcel(name, columns, rows);
      else exportPdf(name, columns, rows, brand);
    } catch (e) {
      alert(apiError(e));
    } finally {
      setExporting(false);
    }
  }

  const hasRows = (pageData?.total ?? 0) > 0;

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
          <div className="relative">
            <button
              className="btn-ghost border border-slate-200"
              disabled={!hasRows || exporting}
              onClick={() => setExportOpen((o) => !o)}
            >
              {exporting ? "Exporting…" : "Export ▾"}
            </button>
            {exportOpen && (
              <>
                <button
                  type="button"
                  className="fixed inset-0 z-10 cursor-default"
                  aria-label="Close export menu"
                  onClick={() => setExportOpen(false)}
                />
                <div className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
                  <button className="block w-full px-4 py-2 text-left text-sm hover:bg-slate-50" onClick={() => void runExport("csv")}>CSV (.csv)</button>
                  <button className="block w-full px-4 py-2 text-left text-sm hover:bg-slate-50" onClick={() => void runExport("excel")}>Excel (.xls)</button>
                  <button className="block w-full px-4 py-2 text-left text-sm hover:bg-slate-50" onClick={() => void runExport("pdf")}>PDF (print)</button>
                </div>
              </>
            )}
          </div>
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
                      {formatCell(d[f.name], f, displayMaps)}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right">
                    {viewPath && (
                      <Link to={viewPath(row.id)} className="btn-ghost px-2 py-1 text-xs text-brand-600">
                        Profile
                      </Link>
                    )}
                    {rowActions
                      ?.filter((a) => !a.show || a.show(d))
                      .map((a) => (
                        <button
                          key={a.label}
                          className={`${
                            a.tone === "danger"
                              ? "btn-danger"
                              : a.tone === "ghost"
                              ? "btn-ghost"
                              : "btn-primary"
                          } px-2 py-1 text-xs`}
                          disabled={actionMutation.isPending}
                          onClick={() => actionMutation.mutate({ action: a, row: d, id: row.id })}
                        >
                          {a.label}
                        </button>
                      ))}
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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type DisplayMaps = { refs: Record<string, Record<string, string>>; masters: Record<string, Record<string, string>> };

/** Resolve a stored value to its human-readable text (FK→name, code→label). */
function resolveCellText(v: any, field?: FieldDef, maps?: DisplayMaps): string {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (field?.reference_entity && maps?.refs[field.reference_entity]?.[String(v)]) {
    return maps.refs[field.reference_entity][String(v)];
  }
  if (field?.options_master && maps?.masters[field.options_master]?.[String(v)]) {
    return maps.masters[field.options_master][String(v)];
  }
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function formatCell(v: any, field?: FieldDef, maps?: DisplayMaps) {
  if (v === null || v === undefined || v === "") return <span className="text-slate-300">—</span>;
  const text = resolveCellText(v, field, maps);
  // Last resort: never show a bare UUID — shorten it.
  if (typeof v === "string" && UUID_RE.test(v) && text === v) {
    return <span className="font-mono text-xs text-slate-400">{v.slice(0, 8)}…</span>;
  }
  return text;
}

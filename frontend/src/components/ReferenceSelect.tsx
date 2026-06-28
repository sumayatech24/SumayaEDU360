import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { endpointFor, rowLabel } from "../lib/resources";
import type { EntityDef, Page } from "../lib/types";

/** A dropdown that loads its options from a referenced entity's collection. */
export function ReferenceSelect({
  entitySlug,
  value,
  onChange,
}: {
  entitySlug: string;
  value: any;
  onChange: (v: any) => void;
}) {
  const { data: entity } = useQuery({
    queryKey: ["entity", entitySlug],
    queryFn: async () => (await api.get<EntityDef>(`/entities/${entitySlug}`)).data,
  });

  const ep = entity ? endpointFor(entity) : null;

  const { data } = useQuery({
    enabled: !!ep,
    queryKey: ["ref-options", entitySlug],
    queryFn: async () => (await api.get<Page<any>>(ep!.base, { params: { page_size: 200 } })).data,
  });

  return (
    <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">— select —</option>
      {data?.items?.map((row: any) => (
        <option key={row.id} value={row.id}>
          {rowLabel(entity, row)}
        </option>
      ))}
    </select>
  );
}

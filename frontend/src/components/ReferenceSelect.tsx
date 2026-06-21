import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { endpointFor } from "../lib/resources";
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

  const labelField =
    entity?.fields.find((f) => ["title", "name", "full_name", "first_name"].includes(f.name))?.name ??
    entity?.fields[0]?.name;

  function labelFor(row: any): string {
    const d = ep?.generic ? row.data ?? {} : row;
    const base = labelField ? d[labelField] : null;
    const extra = d.admission_no || d.code || d.room_no || d.registration_no;
    return [base, extra].filter(Boolean).join(" · ") || row.id.slice(0, 8);
  }

  return (
    <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">— select —</option>
      {data?.items?.map((row: any) => (
        <option key={row.id} value={row.id}>
          {labelFor(row)}
        </option>
      ))}
    </select>
  );
}

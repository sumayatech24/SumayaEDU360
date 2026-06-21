import { useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";
import type { FieldDef } from "../lib/types";
import { ReferenceSelect } from "./ReferenceSelect";

interface Props {
  fields: FieldDef[];
  initial?: Record<string, any>;
  onSubmit: (values: Record<string, any>) => Promise<void>;
  onCancel: () => void;
  submitting?: boolean;
  error?: string | null;
}

export function EntityForm({ fields, initial, onSubmit, onCancel, submitting, error }: Props) {
  const [values, setValues] = useState<Record<string, any>>(initial ?? {});

  // Fetch option lists for any select field bound to a master type.
  const masterFields = fields.filter((f) => f.data_type === "select" && f.options_master);
  const masterQueries = useQueries({
    queries: masterFields.map((f) => ({
      queryKey: ["master-values", f.options_master],
      queryFn: async () =>
        (await api.get(`/master-types/${f.options_master}/values`)).data as {
          code: string;
          label: string;
        }[],
    })),
  });
  const optionsByMaster: Record<string, { code: string; label: string }[]> = {};
  masterFields.forEach((f, i) => {
    optionsByMaster[f.options_master!] = masterQueries[i].data ?? [];
  });

  function set(name: string, value: any) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        await onSubmit(values);
      }}
      className="space-y-4"
    >
      <div className="grid grid-cols-2 gap-4">
        {fields.map((f) => (
          <div key={f.name} className={f.data_type === "text" ? "col-span-2" : ""}>
            <label className="label">
              {f.label}
              {f.is_required && <span className="text-red-500"> *</span>}
            </label>
            {f.data_type === "reference" && f.reference_entity ? (
              <ReferenceSelect
                entitySlug={f.reference_entity}
                value={values[f.name]}
                onChange={(val) => set(f.name, val)}
              />
            ) : (
              renderField(f, values[f.name], (val) => set(f.name, val), optionsByMaster)
            )}
            {f.help_text && <p className="mt-1 text-[11px] text-slate-400">{f.help_text}</p>}
          </div>
        ))}
      </div>

      {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

      <div className="flex justify-end gap-2 pt-2">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

function renderField(
  f: FieldDef,
  value: any,
  onChange: (v: any) => void,
  options: Record<string, { code: string; label: string }[]>
) {
  switch (f.data_type) {
    case "text":
      return (
        <textarea className="input" rows={3} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      );
    case "bool":
      return (
        <select className="input" value={String(value ?? false)} onChange={(e) => onChange(e.target.value === "true")}>
          <option value="false">No</option>
          <option value="true">Yes</option>
        </select>
      );
    case "select": {
      const opts = f.options_master ? options[f.options_master] ?? [] : [];
      return (
        <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">— select —</option>
          {opts.map((o) => (
            <option key={o.code} value={o.code}>
              {o.label}
            </option>
          ))}
        </select>
      );
    }
    case "number":
    case "decimal":
      return (
        <input
          type="number"
          className="input"
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      );
    case "date":
      return <input type="date" className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
    case "email":
      return <input type="email" className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
    default:
      return <input className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

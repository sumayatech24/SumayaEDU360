import type { EntityDef } from "./types";

// Map a typed entity's backing table to its dedicated REST collection path.
const TYPED_PATHS: Record<string, string> = {
  institution: "/institutions",
  academic_year: "/academic-years",
  program: "/programs",
  grade: "/grades",
  section: "/sections",
  subject: "/subjects",
  student: "/students",
  guardian: "/guardians",
  employee: "/employees",
  admission_lead: "/admission-leads",
  fee_plan: "/fee-plans",
  invoice: "/invoices",
  exam: "/exams",
};

export interface ResourceEndpoint {
  /** Collection URL for list/create. */
  base: string;
  /** Whether records are stored via the generic JSON engine. */
  generic: boolean;
}

export function endpointFor(entity: EntityDef): ResourceEndpoint {
  if (entity.is_typed) {
    // Core entities keep their pluralised REST path; registry-driven typed
    // entities expose a collection at `/{slug}` (matching the dynamic router).
    if (entity.typed_table && TYPED_PATHS[entity.typed_table]) {
      return { base: TYPED_PATHS[entity.typed_table], generic: false };
    }
    return { base: `/${entity.slug}`, generic: false };
  }
  return { base: `/records/${entity.slug}`, generic: true };
}

/** Human-friendly label for a row of `entity` — used wherever a referenced
 *  record would otherwise surface as a raw UUID. */
export function rowLabel(entity: EntityDef | undefined, row: any): string {
  const generic = entity ? endpointFor(entity).generic : false;
  const d = generic ? row?.data ?? {} : row ?? {};
  // People (employees, guardians, students…): show the full name.
  if (d.first_name || d.last_name) {
    const full = [d.first_name, d.last_name].filter(Boolean).join(" ");
    const extra = d.admission_no || d.employee_code || d.code;
    return [full, extra].filter(Boolean).join(" · ") || full;
  }
  const labelField =
    entity?.fields.find((f) => ["title", "name", "full_name"].includes(f.name))?.name ??
    entity?.fields[0]?.name;
  const base = labelField ? d[labelField] : null;
  const extra = d.admission_no || d.code || d.room_no || d.registration_no;
  return [base, extra].filter(Boolean).join(" · ") || String(row?.id ?? "").slice(0, 8);
}

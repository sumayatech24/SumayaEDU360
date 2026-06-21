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

import { useState } from "react";
import { ResourcePage } from "../components/ResourcePage";

const TABS = [
  { slug: "academic-year", label: "Academic Years" },
  { slug: "program", label: "Programs" },
  { slug: "grade", label: "Grades / Classes" },
  { slug: "section", label: "Sections" },
  { slug: "subject", label: "Subjects" },
];

export function Academic() {
  const [tab, setTab] = useState(TABS[2].slug);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Academic Setup</h1>
        <p className="text-sm text-slate-400">Configure the academic structure that drives the whole SIS.</p>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
        {TABS.map((t) => (
          <button
            key={t.slug}
            onClick={() => setTab(t.slug)}
            className={`rounded-t-lg px-3 py-2 text-sm ${
              tab === t.slug
                ? "border-b-2 border-brand-600 font-medium text-brand-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <ResourcePage key={tab} entitySlug={tab} permPrefix="academic_configuration" title="" />
    </div>
  );
}

import { useState } from "react";
import { ResourcePage, type RowAction } from "./ResourcePage";

export interface WorkbenchTab {
  slug: string;
  label: string;
  permPrefix?: string;
  rowActions?: RowAction[];
  hideCreate?: boolean;
}

/** A module screen with tabs, each backed by a typed/generic ResourcePage. */
export function Workbench({
  title,
  description,
  tabs,
}: {
  title: string;
  description?: string;
  tabs: WorkbenchTab[];
}) {
  const [active, setActive] = useState(tabs[0]?.slug);
  const tab = tabs.find((t) => t.slug === active) ?? tabs[0];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {description && <p className="text-sm text-slate-400">{description}</p>}
      </div>

      {tabs.length > 1 && (
        <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
          {tabs.map((t) => (
            <button
              key={t.slug}
              onClick={() => setActive(t.slug)}
              className={`rounded-t-lg px-3 py-2 text-sm ${
                tab.slug === t.slug
                  ? "border-b-2 border-brand-600 font-medium text-brand-700"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {tab && (
        <ResourcePage
          key={tab.slug}
          entitySlug={tab.slug}
          permPrefix={tab.permPrefix}
          rowActions={tab.rowActions}
          hideCreate={tab.hideCreate}
          title=""
        />
      )}
    </div>
  );
}

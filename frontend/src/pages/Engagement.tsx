import { useState } from "react";
import { ComplaintsPanel, MeetingsPanel } from "../components/EngagementPanels";

/** Admin / principal view of family engagement: oversee all meetings and complaints. */
export function Engagement() {
  const [tab, setTab] = useState<"complaints" | "meetings">("complaints");
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Family Engagement</h1>
        <p className="text-sm text-slate-400">
          Oversee parent-teacher meetings and the complaints / service-request desk across the school.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
        {([["complaints", "Complaints & Requests"], ["meetings", "Parent-Teacher Meetings"]] as const).map(([slug, label]) => (
          <button
            key={slug}
            onClick={() => setTab(slug)}
            className={`rounded-t-lg px-3 py-2 text-sm ${
              tab === slug ? "border-b-2 border-brand-600 font-medium text-brand-700" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "complaints" ? <ComplaintsPanel canManage /> : <MeetingsPanel canSchedule />}
    </div>
  );
}

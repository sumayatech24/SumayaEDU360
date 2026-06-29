import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";

interface TopicRow { name: string; weeks?: string; hours?: number; status: string }
interface Plan {
  id: string; title: string; term: string; grade: string; section: string; subject: string;
  teacher: string; reviewer?: string | null; objectives?: string; resources?: string;
  topics: TopicRow[]; completion_percent: number; status: string; review_note?: string | null;
  submitted_at?: string | null; reviewed_at?: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600", submitted: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700", rejected: "bg-rose-50 text-rose-700",
  in_progress: "bg-indigo-50 text-indigo-700", completed: "bg-emerald-50 text-emerald-700",
};

export function Curriculum() {
  const [tab, setTab] = useState<"by-class" | "review">("by-class");
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Curriculum Planning</h1>
        <p className="text-sm text-slate-400">
          Class-wise curriculum for the academic session, and the review queue for teacher-submitted plans.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-1">
        {([["by-class", "By Class (Session)"], ["review", "Review Queue"]] as const).map(([slug, label]) => (
          <button key={slug} onClick={() => setTab(slug)}
            className={`rounded-t-lg px-3 py-2 text-sm ${tab === slug ? "border-b-2 border-brand-600 font-medium text-brand-700" : "text-slate-500 hover:text-slate-700"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "by-class" ? <ByClassView /> : <ReviewQueue />}
    </div>
  );
}

// ---------------------------------------------------------------- Class-wise view
interface ClassPlan { id: string; term: string; title: string; status: string; completion_percent: number; topics: TopicRow[] }
interface ClassSubject { subject: string; teacher: string; plans: ClassPlan[] }
interface ClassRow { grade: string; section: string; subjects: ClassSubject[]; plan_count: number; approved: number; avg_completion: number }
interface ByClass {
  academic_years: { id: string; name: string; is_current: boolean }[];
  selected_year: string | null;
  classes: ClassRow[];
}

function ByClassView() {
  const [year, setYear] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["curriculum-by-class", year],
    queryFn: async () => (await api.get<ByClass>(`/curriculum/by-class${year ? `?academic_year_id=${year}` : ""}`)).data,
  });

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <label className="text-sm font-medium text-slate-600">Academic Session</label>
        <select className="input w-64" value={year || data?.selected_year || ""} onChange={(e) => setYear(e.target.value)}>
          {data?.academic_years.map((y) => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " (current)" : ""}</option>)}
        </select>
      </div>

      {isLoading && <div className="card p-5 text-sm text-slate-400">Loading…</div>}
      {!isLoading && data && data.classes.length === 0 && (
        <div className="card p-5 text-sm text-slate-400">No curriculum plans for this session yet.</div>
      )}

      <div className="space-y-4">
        {data?.classes.map((c) => (
          <div key={`${c.grade}-${c.section}`} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <div className="text-base font-semibold">{c.grade} · Section {c.section}</div>
                <div className="text-xs text-slate-400">{c.subjects.length} subjects · {c.plan_count} plans · {c.approved} approved</div>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${c.avg_completion}%` }} />
                </div>
                <span className="text-xs text-slate-500">{c.avg_completion}%</span>
              </div>
            </div>
            <div className="mt-3 space-y-3">
              {c.subjects.map((s) => (
                <div key={s.subject} className="rounded-lg border border-slate-100">
                  <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
                    <span className="text-sm font-medium">{s.subject}</span>
                    <span className="text-xs text-slate-400">{s.teacher}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 p-3">
                    {s.plans.sort((a, b) => a.term.localeCompare(b.term)).map((p) => (
                      <div key={p.id} className="min-w-[160px] flex-1 rounded-lg bg-slate-50 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-slate-600">{p.term}</span>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${STATUS_BADGE[p.status] ?? "bg-slate-100 text-slate-600"}`}>{p.status.replace("_", " ")}</span>
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">{p.topics.length} topics · {p.completion_percent}% done</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Review queue (flat)
const FILTERS = ["submitted", "approved", "rejected", "draft", "all"] as const;

function ReviewQueue() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<(typeof FILTERS)[number]>("submitted");
  const { data, isLoading } = useQuery({
    queryKey: ["curriculum-plans", status],
    queryFn: async () =>
      (await api.get<Plan[]>(`/curriculum/plans${status === "all" ? "" : `?status=${status}`}`)).data,
  });

  async function review(p: Plan, decision: "approved" | "rejected") {
    const review_note =
      decision === "rejected" ? prompt("Reason for returning the plan to the teacher:") ?? "" : prompt("Approval note (optional):") ?? "";
    try {
      await api.post(`/curriculum/plans/${p.id}/review`, { decision, review_note });
      qc.invalidateQueries({ queryKey: ["curriculum-plans"] });
    } catch (e) { alert(apiError(e)); }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setStatus(f)}
            className={`rounded-full px-3 py-1.5 text-sm capitalize ${status === f ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {f}
          </button>
        ))}
      </div>
      <div className="space-y-3">
        {isLoading && <div className="card p-5 text-sm text-slate-400">Loading…</div>}
        {data?.map((p) => (
          <div key={p.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold">{p.title}</div>
                <div className="text-xs text-slate-400">
                  {p.term} · {p.grade}/{p.section} · {p.subject} · by {p.teacher}{p.reviewer ? ` · reviewer ${p.reviewer}` : ""}
                </div>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STATUS_BADGE[p.status] ?? "bg-slate-100 text-slate-600"}`}>
                {p.status.replace("_", " ")}
              </span>
            </div>
            {p.objectives && <p className="mt-2 text-sm text-slate-500">{p.objectives}</p>}
            {p.topics.length > 0 && (
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-100">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-left uppercase tracking-wide text-slate-400">
                    <tr><th className="px-3 py-2">Topic</th><th className="px-3 py-2">Weeks</th><th className="px-3 py-2">Hours</th><th className="px-3 py-2">Status</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {p.topics.map((t, i) => (
                      <tr key={i}>
                        <td className="px-3 py-1.5">{t.name}</td>
                        <td className="px-3 py-1.5 text-slate-400">{t.weeks || "—"}</td>
                        <td className="px-3 py-1.5 text-slate-400">{t.hours ? `${t.hours}h` : "—"}</td>
                        <td className="px-3 py-1.5 capitalize text-slate-500">{(t.status || "pending").replace("_", " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-2 text-xs text-slate-400">{p.completion_percent}% complete</div>
            {p.review_note && <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">Note: {p.review_note}</div>}
            {p.status === "submitted" && (
              <div className="mt-3 flex gap-2">
                <button className="btn-primary px-2.5 py-1 text-xs" onClick={() => void review(p, "approved")}>Approve</button>
                <button className="btn-ghost border border-slate-200 px-2.5 py-1 text-xs text-rose-600" onClick={() => void review(p, "rejected")}>Return</button>
              </div>
            )}
          </div>
        ))}
        {!isLoading && (!data || data.length === 0) && (
          <div className="card p-5 text-sm text-slate-400">No {status === "all" ? "" : status} plans.</div>
        )}
      </div>
    </div>
  );
}

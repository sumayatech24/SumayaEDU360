import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ComplaintsPanel, MeetingsPanel } from "../components/EngagementPanels";
import { Icon } from "../components/Icon";
import { PortalShell } from "../components/PortalShell";
import { api, apiError } from "../lib/api";

interface Card { key: string; label: string; value: number; icon: string }
interface Dash {
  principal: { name: string; designation?: string; department?: string } | null;
  cards: Card[];
  announcements: { title: string; body?: string; date?: string }[];
}

function PrincipalHome() {
  const { data } = useQuery({
    queryKey: ["principal-dash"],
    queryFn: async () => (await api.get<Dash>("/portal/principal/dashboard")).data,
  });
  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="text-[11px] uppercase tracking-wide text-slate-400">Principal</div>
        <div className="text-xl font-semibold">{data?.principal?.name ?? "Principal"}</div>
        <div className="text-sm text-slate-400">{data?.principal?.designation}{data?.principal?.department ? ` · ${data.principal.department}` : ""}</div>
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {data?.cards.map((c) => (
          <div key={c.key} className="card flex items-center gap-4 p-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Icon name={c.icon} />
            </div>
            <div>
              <div className="text-2xl font-semibold">{c.value}</div>
              <div className="text-xs text-slate-400">{c.label}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-slate-600">Announcements</h3>
        {(!data?.announcements || data.announcements.length === 0) && <p className="text-sm text-slate-400">Nothing new.</p>}
        <div className="space-y-3">
          {data?.announcements.map((a, i) => (
            <div key={i} className="border-l-2 border-indigo-400 pl-3">
              <div className="text-sm font-medium">{a.title}</div>
              {a.body && <div className="text-xs text-slate-500">{a.body}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface MarksBatchRow {
  id: string; exam: string; subject: string; grade: string; section: string; teacher: string; status: string;
}
interface MarksSheet {
  id: string; status: string; review_note?: string | null;
  rows: { student_id: string; roll_no?: string | null; admission_no: string; student_name: string; marks_obtained: string; max_marks: string; is_absent: boolean; grade?: string | null }[];
}

function MarksApprovals() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { data: list } = useQuery({
    queryKey: ["principal-marks"],
    queryFn: async () => (await api.get<MarksBatchRow[]>("/portal/principal/marks-approvals")).data,
  });
  const sheet = useQuery({
    queryKey: ["principal-marks-sheet", selected],
    enabled: !!selected,
    queryFn: async () => (await api.get<MarksSheet>(`/portal/principal/marks-approvals/${selected}`)).data,
  });

  async function review(decision: "approved" | "rejected") {
    if (decision === "rejected" && !note.trim()) { setError("Add a note when returning marks."); return; }
    setBusy(true); setError("");
    try {
      await api.post(`/portal/principal/marks-approvals/${selected}`, { decision, review_note: note.trim() || null });
      setSelected(""); setNote("");
      await qc.invalidateQueries({ queryKey: ["principal-marks"] });
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3">
          <h2 className="font-semibold">Marksheets awaiting approval</h2>
          <p className="text-xs text-slate-400">Submitted by teachers/HODs across the school. Approving publishes & locks the marksheet.</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Exam</th><th className="px-4 py-3">Subject</th><th className="px-4 py-3">Class</th><th className="px-4 py-3">Teacher</th><th className="px-4 py-3" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list?.map((b) => (
              <tr key={b.id} className={selected === b.id ? "bg-indigo-50" : ""}>
                <td className="px-4 py-2.5">{b.exam}</td><td className="px-4 py-2.5">{b.subject}</td>
                <td className="px-4 py-2.5">{b.grade}/{b.section}</td><td className="px-4 py-2.5">{b.teacher}</td>
                <td className="px-4 py-2.5 text-right"><button className="btn-ghost" onClick={() => { setSelected(b.id); setNote(""); setError(""); }}>Review</button></td>
              </tr>
            ))}
            {(!list || list.length === 0) && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No marksheets pending approval.</td></tr>}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="card overflow-hidden">
          <div className="border-b border-slate-100 px-4 py-3 font-semibold">Class marksheet</div>
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-4 py-3">Roll</th><th className="px-4 py-3">Student</th><th className="px-4 py-3">Marks</th><th className="px-4 py-3">Grade</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sheet.data?.rows.map((r) => (
                  <tr key={r.student_id}><td className="px-4 py-2.5">{r.roll_no || r.admission_no}</td><td className="px-4 py-2.5 font-medium">{r.student_name}</td><td className="px-4 py-2.5">{r.is_absent ? "Absent" : `${r.marks_obtained} / ${r.max_marks}`}</td><td className="px-4 py-2.5">{r.grade || "--"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="space-y-3 border-t border-slate-100 p-4">
            <textarea className="input min-h-16" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional for approval, required to return)" />
            {error && <div className="text-sm text-rose-600">{error}</div>}
            <div className="flex gap-2">
              <button className="btn-primary" disabled={busy} onClick={() => void review("approved")}>Approve, publish & lock</button>
              <button className="btn-ghost border border-rose-200 text-rose-600" disabled={busy} onClick={() => void review("rejected")}>Return to teacher</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface PlanRow {
  id: string; title: string; term: string; grade: string; section: string; subject: string;
  teacher: string; objectives?: string | null; topics: { name?: string; weeks?: string }[]; status: string; review_note?: string | null;
}

function CurriculumApprovals() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const { data: list } = useQuery({
    queryKey: ["principal-curriculum"],
    queryFn: async () => (await api.get<PlanRow[]>("/portal/principal/curriculum-approvals")).data,
  });
  async function review(p: PlanRow, decision: "approved" | "rejected") {
    const review_note = decision === "rejected" ? (prompt("Reason for returning the plan:") ?? "") : (prompt("Approval note (optional):") ?? "");
    if (decision === "rejected" && !review_note.trim()) return;
    setBusy(true);
    try {
      await api.post(`/portal/principal/curriculum-approvals/${p.id}`, { decision, review_note: review_note || null });
      await qc.invalidateQueries({ queryKey: ["principal-curriculum"] });
    } catch (e) { alert(apiError(e)); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-3">
      {list?.map((p) => (
        <div key={p.id} className="card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">{p.title}</div>
              <div className="text-xs text-slate-400">{p.term} · {p.grade}/{p.section} · {p.subject} · by {p.teacher}</div>
            </div>
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium capitalize text-amber-700">{p.status}</span>
          </div>
          {p.objectives && <p className="mt-2 text-sm text-slate-500">{p.objectives}</p>}
          {p.topics.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-xs text-slate-500">
              {p.topics.map((t, i) => <li key={i}>{t.name}{t.weeks ? ` (${t.weeks})` : ""}</li>)}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <button className="btn-primary px-2.5 py-1 text-xs" disabled={busy} onClick={() => void review(p, "approved")}>Approve</button>
            <button className="btn-ghost border border-rose-200 px-2.5 py-1 text-xs text-rose-600" disabled={busy} onClick={() => void review(p, "rejected")}>Return</button>
          </div>
        </div>
      ))}
      {(!list || list.length === 0) && <div className="card p-5 text-sm text-slate-400">No curriculum plans awaiting approval.</div>}
    </div>
  );
}

export function PrincipalPortal() {
  return (
    <PortalShell
      portal="principal"
      nav={[
        { label: "Dashboard", icon: "grid", to: "" },
        { label: "Marksheet Approvals", icon: "check-square", to: "marks" },
        { label: "Curriculum Approvals", icon: "book", to: "curriculum" },
        { label: "Complaints", icon: "shield", to: "complaints" },
        { label: "Meetings", icon: "calendar", to: "meetings" },
      ]}
    >
      <Routes>
        <Route index element={<PrincipalHome />} />
        <Route path="marks" element={<MarksApprovals />} />
        <Route path="curriculum" element={<CurriculumApprovals />} />
        <Route path="complaints" element={<ComplaintsPanel canManage />} />
        <Route path="meetings" element={<MeetingsPanel canSchedule />} />
        <Route path="*" element={<Navigate to="" replace />} />
      </Routes>
    </PortalShell>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";

// ----------------------------------------------------------------- shared types
interface TrailEntry {
  id: string;
  author: string;
  role?: string;
  note?: string | null;
  status_from?: string | null;
  status_to?: string | null;
  at?: string | null;
  is_internal?: boolean;
}
interface Complaint {
  id: string;
  ticket_no: string;
  subject: string;
  category: string;
  description?: string | null;
  priority: string;
  status: string;
  raised_by?: string | null;
  raised_by_role?: string | null;
  student?: string | null;
  assigned_to?: string | null;
  assigned_role?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
  updates: TrailEntry[];
}
interface ComplaintOptions {
  categories: string[];
  priorities: string[];
  role: string;
  staff: { id: string; name: string; designation?: string }[];
}
interface Meeting {
  id: string;
  title: string;
  student?: string | null;
  teacher?: string | null;
  meeting_date?: string | null;
  slot_time?: string | null;
  mode: string;
  location?: string | null;
  status: string;
  agenda?: string | null;
  notes?: string | null;
  teacher_feedback?: string | null;
  parent_feedback?: string | null;
  action_items: { text?: string; owner?: string; done?: boolean }[];
  follow_up_date?: string | null;
  parent_ack: boolean;
}

const STATUS_BADGE: Record<string, string> = {
  open: "bg-slate-100 text-slate-600",
  assigned: "bg-amber-50 text-amber-700",
  in_progress: "bg-indigo-50 text-indigo-700",
  resolved: "bg-emerald-50 text-emerald-700",
  closed: "bg-slate-200 text-slate-600",
  reopened: "bg-rose-50 text-rose-700",
  scheduled: "bg-amber-50 text-amber-700",
  completed: "bg-emerald-50 text-emerald-700",
  cancelled: "bg-slate-200 text-slate-500",
  no_show: "bg-rose-50 text-rose-700",
};
const PRIORITY_BADGE: Record<string, string> = {
  low: "bg-slate-100 text-slate-500",
  normal: "bg-sky-50 text-sky-700",
  high: "bg-amber-50 text-amber-700",
  urgent: "bg-rose-50 text-rose-700",
};
const cap = (s?: string | null) => (s ? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "");
const when = (s?: string | null) => (s ? new Date(s).toLocaleString() : "—");

// ============================================================ Complaints
export function ComplaintsPanel({ canRaise = false, canManage = false }: { canRaise?: boolean; canManage?: boolean }) {
  const qc = useQueryClient();
  const { data: options } = useQuery({
    queryKey: ["complaint-options"],
    queryFn: async () => (await api.get<ComplaintOptions>("/engagement/complaint-options")).data,
  });
  const { data: list, isLoading } = useQuery({
    queryKey: ["complaints"],
    queryFn: async () => (await api.get<Complaint[]>("/engagement/complaints")).data,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["complaints"] });

  const empty = { subject: "", category: "general", priority: "normal", description: "" };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function raise() {
    if (!form.subject.trim()) { setError("Enter a subject."); return; }
    setBusy(true); setError("");
    try {
      await api.post("/engagement/complaints", { ...form, subject: form.subject.trim() });
      setForm(empty);
      refresh();
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      {canRaise && (
        <div className="card p-5">
          <h2 className="font-semibold">Raise a complaint / service request</h2>
          <p className="mb-3 text-sm text-slate-400">It is automatically routed to the class teacher (or the HOD), and you can follow every update below.</p>
          {error && <div className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          <div className="grid gap-3 md:grid-cols-3">
            <label className="md:col-span-3"><span className="label">Subject</span>
              <input className="input" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Short summary of the issue" /></label>
            <label><span className="label">Category</span>
              <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {(options?.categories ?? ["general"]).map((c) => <option key={c} value={c}>{cap(c)}</option>)}
              </select></label>
            <label><span className="label">Priority</span>
              <select className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                {(options?.priorities ?? ["normal"]).map((p) => <option key={p} value={p}>{cap(p)}</option>)}
              </select></label>
            <label className="md:col-span-3"><span className="label">Details</span>
              <textarea className="input min-h-20" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Describe the issue, when it happened, and what you would like done." /></label>
          </div>
          <button className="btn-primary mt-4" disabled={busy} onClick={() => void raise()}>{busy ? "Submitting…" : "Submit request"}</button>
        </div>
      )}

      <div className="space-y-3">
        {list?.map((c) => (
          <ComplaintCard key={c.id} c={c} options={options} canManage={canManage} canRaise={canRaise} onChanged={refresh} />
        ))}
        {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
        {!isLoading && (!list || list.length === 0) && (
          <div className="card p-5 text-sm text-slate-400">No requests yet.</div>
        )}
      </div>
    </div>
  );
}

function ComplaintCard({ c, options, canManage, canRaise, onChanged }: {
  c: Complaint; options?: ComplaintOptions; canManage: boolean; canRaise: boolean; onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [internal, setInternal] = useState(false);
  const [busy, setBusy] = useState(false);

  const update = useMutation({
    mutationFn: async (body: Record<string, unknown>) => api.post(`/engagement/complaints/${c.id}/updates`, body),
    onSuccess: () => { setNote(""); setInternal(false); onChanged(); },
    onError: (e) => alert(apiError(e)),
  });

  async function send(body: Record<string, unknown>) {
    setBusy(true);
    try { await update.mutateAsync(body); } finally { setBusy(false); }
  }

  const familyCanReopen = canRaise && (c.status === "resolved" || c.status === "closed");

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{c.subject}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_BADGE[c.priority] ?? "bg-slate-100"}`}>{cap(c.priority)}</span>
          </div>
          <div className="mt-0.5 text-xs text-slate-400">
            {c.ticket_no} · {cap(c.category)}
            {c.student ? ` · ${c.student}` : ""}
            {c.raised_by ? ` · by ${c.raised_by}` : ""}
          </div>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_BADGE[c.status] ?? "bg-slate-100"}`}>{cap(c.status)}</span>
      </div>
      {c.description && <p className="mt-2 text-sm text-slate-600">{c.description}</p>}
      <div className="mt-2 text-xs text-slate-400">
        Assigned to: <span className="font-medium text-slate-600">{c.assigned_to || "Unassigned"}</span>
        {c.assigned_role ? ` (${cap(c.assigned_role)})` : ""} · Raised {when(c.created_at)}
      </div>

      <button className="btn-ghost mt-2 px-0 text-xs text-brand-600" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "View"} trail ({c.updates.length})
      </button>

      {open && (
        <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
          <div className="space-y-2">
            {c.updates.map((u) => (
              <div key={u.id} className="rounded-lg bg-slate-50 px-3 py-2">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span className="font-medium text-slate-600">{u.author}{u.role ? ` · ${cap(u.role)}` : ""}{u.is_internal ? " · internal" : ""}</span>
                  <span>{when(u.at)}</span>
                </div>
                {u.status_to && <div className="text-xs text-indigo-600">Status → {cap(u.status_to)}</div>}
                {u.note && <div className="text-sm text-slate-600">{u.note}</div>}
              </div>
            ))}
            {c.updates.length === 0 && <div className="text-xs text-slate-400">No updates yet.</div>}
          </div>

          <div className="space-y-2">
            <textarea className="input min-h-16" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a comment…" />
            {canManage && (
              <label className="flex items-center gap-2 text-xs text-slate-500">
                <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal note (hidden from student/parent)
              </label>
            )}
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost border border-slate-200 text-xs" disabled={busy || !note.trim()} onClick={() => void send({ note: note.trim(), is_internal: internal })}>Add comment</button>
              {canManage && c.status !== "in_progress" && OPEN(c.status) && (
                <button className="btn-ghost border border-slate-200 text-xs" disabled={busy} onClick={() => void send({ note: note.trim() || null, status: "in_progress" })}>Mark in progress</button>
              )}
              {canManage && OPEN(c.status) && (
                <button className="btn-primary text-xs" disabled={busy} onClick={() => void send({ note: note.trim() || null, status: "resolved" })}>Resolve</button>
              )}
              {canManage && c.status !== "closed" && (
                <button className="btn-ghost border border-slate-200 text-xs" disabled={busy} onClick={() => void send({ note: note.trim() || null, status: "closed" })}>Close</button>
              )}
              {familyCanReopen && (
                <button className="btn-ghost border border-rose-200 text-xs text-rose-600" disabled={busy} onClick={() => void send({ note: note.trim() || "Reopened by requester", status: "reopened" })}>Reopen</button>
              )}
            </div>
            {canManage && options && options.staff.length > 0 && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-xs text-slate-400">Reassign to:</span>
                <select className="input h-9 max-w-xs text-sm" defaultValue="" disabled={busy}
                  onChange={(e) => { if (e.target.value) void send({ assigned_to_id: e.target.value, note: note.trim() || null }); }}>
                  <option value="">— choose staff —</option>
                  {options.staff.map((s) => <option key={s.id} value={s.id}>{s.name}{s.designation ? ` (${s.designation})` : ""}</option>)}
                </select>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
const OPEN = (s: string) => ["open", "assigned", "in_progress", "reopened"].includes(s);

// ============================================================ Meetings
export function MeetingsPanel({ canSchedule = false, isFamily = false }: { canSchedule?: boolean; isFamily?: boolean }) {
  const qc = useQueryClient();
  const { data: options } = useQuery({
    enabled: canSchedule,
    queryKey: ["meeting-options"],
    queryFn: async () => (await api.get<{ students: { id: string; label: string }[]; modes: string[] }>("/engagement/meeting-options")).data,
  });
  const { data: list, isLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: async () => (await api.get<Meeting[]>("/engagement/meetings")).data,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["meetings"] });

  const empty = { student_id: "", title: "", meeting_date: "", slot_time: "", mode: "in_person", location: "", agenda: "" };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function schedule() {
    if (!form.student_id) { setError("Select a student."); return; }
    if (!form.title.trim()) { setError("Enter a title."); return; }
    setBusy(true); setError("");
    try {
      await api.post("/engagement/meetings", {
        student_id: form.student_id,
        title: form.title.trim(),
        meeting_date: form.meeting_date || null,
        slot_time: form.slot_time || null,
        mode: form.mode,
        location: form.location || null,
        agenda: form.agenda || null,
      });
      setForm(empty);
      refresh();
    } catch (e) { setError(apiError(e)); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      {canSchedule && (
        <div className="card p-5">
          <h2 className="font-semibold">Schedule a parent-teacher meeting</h2>
          {error && <div className="my-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <label className="md:col-span-2"><span className="label">Student</span>
              <select className="input" value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })}>
                <option value="">— select student —</option>
                {options?.students.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select></label>
            <label><span className="label">Mode</span>
              <select className="input" value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
                {(options?.modes ?? ["in_person", "online", "phone"]).map((m) => <option key={m} value={m}>{cap(m)}</option>)}
              </select></label>
            <label className="md:col-span-3"><span className="label">Title / Purpose</span>
              <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Term 1 progress discussion" /></label>
            <label><span className="label">Date</span>
              <input className="input" type="date" value={form.meeting_date} onChange={(e) => setForm({ ...form, meeting_date: e.target.value })} /></label>
            <label><span className="label">Time</span>
              <input className="input" type="time" value={form.slot_time} onChange={(e) => setForm({ ...form, slot_time: e.target.value })} /></label>
            <label><span className="label">Room / Meeting link</span>
              <input className="input" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></label>
            <label className="md:col-span-3"><span className="label">Agenda</span>
              <textarea className="input min-h-16" value={form.agenda} onChange={(e) => setForm({ ...form, agenda: e.target.value })} /></label>
          </div>
          <button className="btn-primary mt-4" disabled={busy} onClick={() => void schedule()}>{busy ? "Scheduling…" : "Schedule meeting"}</button>
        </div>
      )}

      <div className="space-y-3">
        {list?.map((m) => (
          <MeetingCard key={m.id} m={m} canSchedule={canSchedule} isFamily={isFamily} onChanged={refresh} />
        ))}
        {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
        {!isLoading && (!list || list.length === 0) && (
          <div className="card p-5 text-sm text-slate-400">No meetings yet.</div>
        )}
      </div>
    </div>
  );
}

function MeetingCard({ m, canSchedule, isFamily, onChanged }: {
  m: Meeting; canSchedule: boolean; isFamily: boolean; onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [teacherFeedback, setTeacherFeedback] = useState(m.teacher_feedback ?? "");
  const [followUp, setFollowUp] = useState(m.follow_up_date ?? "");
  const [parentFeedback, setParentFeedback] = useState(m.parent_feedback ?? "");
  const [busy, setBusy] = useState(false);

  async function post(body: Record<string, unknown>) {
    setBusy(true);
    try {
      await api.post(`/engagement/meetings/${m.id}/feedback`, body);
      onChanged();
    } catch (e) { alert(apiError(e)); } finally { setBusy(false); }
  }

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">{m.title}</div>
          <div className="mt-0.5 text-xs text-slate-400">
            {m.student ? `${m.student} · ` : ""}{m.teacher ? `with ${m.teacher} · ` : ""}{cap(m.mode)}
            {m.meeting_date ? ` · ${m.meeting_date}${m.slot_time ? ` ${m.slot_time}` : ""}` : ""}
            {m.location ? ` · ${m.location}` : ""}
          </div>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_BADGE[m.status] ?? "bg-slate-100"}`}>{cap(m.status)}</span>
      </div>
      {m.agenda && <p className="mt-2 text-sm text-slate-600"><span className="text-slate-400">Agenda:</span> {m.agenda}</p>}

      <button className="btn-ghost mt-2 px-0 text-xs text-brand-600" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "Details & feedback"}
      </button>

      {open && (
        <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 text-sm">
          {m.teacher_feedback && <div><span className="text-xs font-semibold text-slate-500">Teacher feedback</span><p className="text-slate-600">{m.teacher_feedback}</p></div>}
          {m.parent_feedback && <div><span className="text-xs font-semibold text-slate-500">Parent feedback</span><p className="text-slate-600">{m.parent_feedback}</p></div>}
          {m.action_items.length > 0 && (
            <div>
              <span className="text-xs font-semibold text-slate-500">Action items</span>
              <ul className="list-disc pl-5 text-slate-600">
                {m.action_items.map((a, i) => <li key={i}>{a.text}{a.owner ? ` (${a.owner})` : ""}</li>)}
              </ul>
            </div>
          )}
          {m.follow_up_date && <div className="text-xs text-slate-500">Follow-up: <span className="font-medium">{m.follow_up_date}</span></div>}

          {canSchedule && (
            <div className="space-y-2 rounded-lg bg-slate-50 p-3">
              <span className="text-xs font-semibold text-slate-500">Record outcome (teacher)</span>
              <textarea className="input min-h-16" value={teacherFeedback} onChange={(e) => setTeacherFeedback(e.target.value)} placeholder="What was discussed, observations, next steps…" />
              <label className="block text-xs text-slate-500">Follow-up date
                <input className="input mt-1 h-9" type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} /></label>
              <div className="flex flex-wrap gap-2">
                <button className="btn-ghost border border-slate-200 text-xs" disabled={busy} onClick={() => void post({ teacher_feedback: teacherFeedback, follow_up_date: followUp || null })}>Save feedback</button>
                <button className="btn-primary text-xs" disabled={busy} onClick={() => void post({ teacher_feedback: teacherFeedback, follow_up_date: followUp || null, status: "completed" })}>Save & mark completed</button>
                <button className="btn-ghost border border-rose-200 text-xs text-rose-600" disabled={busy} onClick={() => void post({ status: "cancelled" })}>Cancel meeting</button>
              </div>
            </div>
          )}

          {isFamily && (
            <div className="space-y-2 rounded-lg bg-slate-50 p-3">
              <span className="text-xs font-semibold text-slate-500">Your feedback (parent)</span>
              <textarea className="input min-h-16" value={parentFeedback} onChange={(e) => setParentFeedback(e.target.value)} placeholder="Share your notes or concerns…" />
              <div className="flex flex-wrap gap-2">
                <button className="btn-ghost border border-slate-200 text-xs" disabled={busy} onClick={() => void post({ parent_feedback: parentFeedback })}>Save feedback</button>
                {!m.parent_ack && <button className="btn-primary text-xs" disabled={busy} onClick={() => void post({ parent_feedback: parentFeedback || null, parent_ack: true })}>Acknowledge</button>}
                {m.parent_ack && <span className="self-center text-xs text-emerald-600">✓ Acknowledged</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

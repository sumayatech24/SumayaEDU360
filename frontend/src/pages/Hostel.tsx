import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../components/Modal";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

type Tab = "allocations" | "attendance" | "visitors" | "incidents";
interface Allocation { id: string; student_id: string; student: string; admission_no: string; grade: string; section: string;
  block: string; room: string; room_id: string; bed?: string; allocation_date: string; status: string }

export function Hostel() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("allocations");
  const [modal, setModal] = useState<"allocate" | "attendance" | "visitor" | "incident" | null>(null);
  const [gradeId, setGradeId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [roomId, setRoomId] = useState("");
  const [status, setStatus] = useState("present");
  const [name, setName] = useState("");
  const [details, setDetails] = useState("");
  const [severity, setSeverity] = useState("low");
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => {
    ["hostel-dashboard", "hostel-allocs", "hostel-rooms", "hostel-attendance", "hostel-visitors", "hostel-incidents"].forEach((key) =>
      qc.invalidateQueries({ queryKey: [key] }));
  };
  const { data: summary } = useQuery({ queryKey: ["hostel-dashboard"], queryFn: async () => (await api.get("/hostel/dashboard")).data });
  const { data: rooms } = useQuery({ queryKey: ["hostel-rooms"], queryFn: async () => (await api.get<Page<any>>("/hostel-room", { params: { page_size: 200 } })).data });
  const { data: grades } = useQuery({ queryKey: ["hostel-grades"], queryFn: async () => (await api.get<Page<any>>("/grades", { params: { page_size: 100 } })).data });
  const { data: sections } = useQuery({ queryKey: ["hostel-sections"], queryFn: async () => (await api.get<Page<any>>("/sections", { params: { page_size: 200 } })).data });
  const { data: students = [] } = useQuery({ queryKey: ["hostel-students", gradeId, sectionId], enabled: Boolean(gradeId),
    queryFn: async () => (await api.get("/hostel/eligible-students", { params: { grade_id: gradeId, section_id: sectionId || undefined } })).data });
  const { data: allocations = [] } = useQuery({ queryKey: ["hostel-allocs"], queryFn: async () => (await api.get<Allocation[]>("/hostel/allocations")).data });
  const { data: attendance = [] } = useQuery({ queryKey: ["hostel-attendance"], queryFn: async () => (await api.get("/hostel/attendance")).data });
  const { data: visitors = [] } = useQuery({ queryKey: ["hostel-visitors"], queryFn: async () => (await api.get("/hostel/visitors")).data });
  const { data: incidents = [] } = useQuery({ queryKey: ["hostel-incidents"], queryFn: async () => (await api.get("/hostel/incidents")).data });
  const active = allocations.filter((a) => a.status === "allocated");
  const action = useMutation({
    mutationFn: async () => {
      if (modal === "allocate") return api.post("/hostel/allocations", { student_id: studentId, room_id: roomId });
      if (modal === "attendance") return api.post("/hostel/attendance", { student_id: studentId, attendance_status: status });
      if (modal === "visitor") return api.post("/hostel/visitors", { student_id: studentId, visitor_name: name, purpose: details });
      return api.post("/hostel/incidents", { student_id: studentId || null, room_id: roomId || null,
        incident_type: name, severity, description: details });
    },
    onSuccess: () => { invalidate(); setModal(null); setStudentId(""); setRoomId(""); setName(""); setDetails(""); setError(null); },
    onError: (e) => setError(apiError(e)),
  });
  const quick = useMutation({
    mutationFn: async ({ url, body }: { url: string; body?: any }) => api.post(url, body),
    onSuccess: invalidate, onError: (e) => setError(apiError(e)),
  });
  const classSections = (sections?.items ?? []).filter((s: any) => !gradeId || s.grade_id === gradeId);
  const availableRooms = (rooms?.items ?? []).filter((r: any) => r.occupied < r.capacity);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><div>
        <h1 className="text-2xl font-semibold">Hostel Management</h1>
        <p className="text-sm text-slate-400">Class-linked residence, daily safeguarding and parent-visible allocation.</p>
      </div><button className="btn-primary" onClick={() => setModal("allocate")}>+ Allocate student</button></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {[["Blocks", summary?.blocks], ["Rooms", summary?.rooms], ["Capacity", summary?.capacity], ["Occupied", summary?.occupied],
          ["Available", summary?.available], ["Present today", summary?.today_present]].map(([label, value]) =>
          <div className="card p-4" key={String(label)}><div className="text-xs uppercase text-slate-400">{label}</div>
            <div className="text-2xl font-semibold">{value ?? 0}</div></div>)}
      </div>
      <div className="flex gap-2 border-b">
        {(["allocations", "attendance", "visitors", "incidents"] as Tab[]).map((item) =>
          <button key={item} onClick={() => setTab(item)} className={`px-4 py-2 text-sm capitalize ${tab === item ? "border-b-2 border-brand-500 font-semibold text-brand-700" : "text-slate-500"}`}>{item}</button>)}
      </div>
      <div className="flex justify-end">
        {tab !== "allocations" && <button className="btn-primary" onClick={() => setModal(tab === "attendance" ? "attendance" : tab === "visitors" ? "visitor" : "incident")}>
          + {tab === "attendance" ? "Mark attendance" : tab === "visitors" ? "Visitor check-in" : "Report incident"}</button>}
      </div>
      {tab === "allocations" && <DataTable headers={["Student / class", "Block", "Room / bed", "Since", "Status", "Action"]} rows={allocations.map((a) => [
        <div><div className="font-medium">{a.student}</div><div className="text-xs text-slate-400">{a.admission_no} · {a.grade}-{a.section}</div></div>,
        a.block, `${a.room} / ${a.bed ?? "—"}`, a.allocation_date, <span className="badge">{a.status}</span>,
        a.status === "allocated" ? <button className="btn-danger px-2 py-1 text-xs" onClick={() => quick.mutate({ url: `/hostel/allocations/${a.id}/vacate` })}>Vacate</button> : "—",
      ])} empty="No hostel allocations." />}
      {tab === "attendance" && <DataTable headers={["Student", "Date", "Status", "Remarks"]} rows={attendance.map((a: any) => [a.student, a.date, a.status, a.remarks ?? "—"])} empty="No hostel attendance recorded." />}
      {tab === "visitors" && <DataTable headers={["Student", "Visitor", "Purpose", "Check in", "Status", "Action"]} rows={visitors.map((v: any) => [
        v.student, `${v.visitor_name}${v.relation ? ` (${v.relation})` : ""}`, v.purpose ?? "—", new Date(v.check_in_at).toLocaleString(), v.status,
        v.status === "checked_in" ? <button className="btn-ghost text-xs" onClick={() => quick.mutate({ url: `/hostel/visitors/${v.id}/checkout` })}>Check out</button> : "—",
      ])} empty="No visitor entries." />}
      {tab === "incidents" && <DataTable headers={["Date", "Type", "Severity", "Description", "Status", "Action"]} rows={incidents.map((i: any) => [
        i.date, i.type, i.severity, i.description, i.status,
        i.status !== "resolved" ? <button className="btn-ghost text-xs" onClick={() => quick.mutate({ url: `/hostel/incidents/${i.id}/resolve`, body: { status: "resolved", action_taken: "Reviewed and closed by hostel manager" } })}>Resolve</button> : "—",
      ])} empty="No incidents reported." />}
      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {modal && <Modal title={modal === "allocate" ? "Allocate hostel bed" : modal === "attendance" ? "Hostel attendance" : modal === "visitor" ? "Visitor check-in" : "Report incident"} onClose={() => setModal(null)}>
        <div className="space-y-4">
          {(modal === "allocate") && <><div><label className="label">1. Class</label><select className="input" value={gradeId} onChange={(e) => { setGradeId(e.target.value); setSectionId(""); setStudentId(""); }}>
            <option value="">Select class</option>{grades?.items.map((g: any) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
            <div><label className="label">2. Section</label><select className="input" value={sectionId} onChange={(e) => { setSectionId(e.target.value); setStudentId(""); }}>
              <option value="">All sections</option>{classSections.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div></>}
          <div><label className="label">{modal === "allocate" ? "3. Student" : "Resident student"}</label><select className="input" value={studentId} onChange={(e) => setStudentId(e.target.value)}>
            <option value="">Select student</option>{(modal === "allocate" ? students.filter((s: any) => !s.already_allocated) : active).map((s: any) =>
              <option key={s.id} value={modal === "allocate" ? s.id : s.student_id}>{modal === "allocate" ? `${s.name} · ${s.admission_no} · ${s.grade}-${s.section}` : `${s.student} · ${s.grade}-${s.section}`}</option>)}</select></div>
          {(modal === "allocate" || modal === "incident") && <div><label className="label">{modal === "allocate" ? "4. Available room" : "Room (optional)"}</label>
            <select className="input" value={roomId} onChange={(e) => setRoomId(e.target.value)}><option value="">Select room</option>{availableRooms.map((r: any) =>
              <option key={r.id} value={r.id}>Room {r.room_no} · {r.occupied}/{r.capacity}</option>)}</select></div>}
          {modal === "attendance" && <div><label className="label">Status</label><select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="present">Present</option><option value="leave">Approved leave</option><option value="absent">Absent</option></select></div>}
          {(modal === "visitor" || modal === "incident") && <div><label className="label">{modal === "visitor" ? "Visitor name" : "Incident type"}</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>}
          {modal === "incident" && <div><label className="label">Severity</label><select className="input" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></div>}
          {(modal === "visitor" || modal === "incident") && <div><label className="label">{modal === "visitor" ? "Purpose" : "Description"}</label>
            <textarea className="input min-h-20" value={details} onChange={(e) => setDetails(e.target.value)} /></div>}
          <button className="btn-primary w-full" disabled={action.isPending || (modal !== "incident" && !studentId) || (modal === "allocate" && (!gradeId || !roomId)) || ((modal === "visitor" || modal === "incident") && (!name || !details))}
            onClick={() => action.mutate()}>{action.isPending ? "Saving…" : "Save"}</button>
        </div>
      </Modal>}
    </div>
  );
}

function DataTable({ headers, rows, empty }: { headers: string[]; rows: any[][]; empty: string }) {
  return <div className="card overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr>
    {headers.map((h) => <th className="px-4 py-3" key={h}>{h}</th>)}</tr></thead><tbody className="divide-y">
    {rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td className="px-4 py-3" key={j}>{cell}</td>)}</tr>)}
    {!rows.length && <tr><td colSpan={headers.length} className="px-4 py-8 text-center text-slate-400">{empty}</td></tr>}
  </tbody></table></div>;
}

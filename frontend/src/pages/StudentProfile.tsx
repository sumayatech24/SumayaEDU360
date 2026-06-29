import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiError } from "../lib/api";
import { DocumentUpload } from "../components/DocumentUpload";
import { useBranding } from "../lib/branding";
import { printMarksheet } from "../lib/print";

const inr = (v?: string | number) => "₹" + Number(v ?? 0).toLocaleString("en-IN");

function Section({ title, children, count }: { title: string; children: React.ReactNode; count?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
        {count !== undefined && <span className="text-xs text-slate-400">{count}</span>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: any }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-sm font-medium capitalize">{value || "—"}</div>
    </div>
  );
}

function Table({ cols, rows }: { cols: [string, string][]; rows: Record<string, any>[] }) {
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
        <tr>
          {cols.map(([, label]) => (
            <th key={label} className="pb-2 pr-4 font-medium">
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map(([key]) => (
              <td key={key} className="py-2 pr-4">
                {r[key] ?? "—"}
              </td>
            ))}
          </tr>
        ))}
        {rows.length === 0 && (
          <tr>
            <td colSpan={cols.length} className="py-3 text-center text-slate-400">
              None on record.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function StudentLifecycle({ studentId, studentStatus }: { studentId: string; studentStatus: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    request_type: studentStatus === "enrolled" ? "transfer" : "reenrollment",
    effective_date: new Date().toISOString().slice(0, 10),
    reason: "",
    destination_school: "",
    target_grade_id: "",
    target_section_id: "",
  });
  const { data: cases = [] } = useQuery({
    queryKey: ["student-lifecycle", studentId],
    queryFn: async () => (await api.get<any[]>("/student-lifecycle", { params: { student_id: studentId } })).data,
  });
  const { data: grades } = useQuery({
    queryKey: ["grades", "lifecycle"],
    queryFn: async () => (await api.get<any>("/grades", { params: { page_size: 100 } })).data,
  });
  const { data: sections } = useQuery({
    queryKey: ["sections", "lifecycle"],
    queryFn: async () => (await api.get<any>("/sections", { params: { page_size: 100 } })).data,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["student-lifecycle", studentId] });
    qc.invalidateQueries({ queryKey: ["student-profile", studentId] });
  };
  const create = useMutation({
    mutationFn: async () => (await api.post("/student-lifecycle", {
      ...form,
      student_id: studentId,
      destination_school: form.destination_school || null,
      target_grade_id: form.target_grade_id || null,
      target_section_id: form.target_section_id || null,
    })).data,
    onSuccess: () => { setOpen(false); setError(""); refresh(); },
    onError: (e) => setError(apiError(e)),
  });
  const transition = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: string }) =>
      (await api.post(`/student-lifecycle/${id}/${action}`, action === "approve" ? { override_clearance: false } : {})).data,
    onSuccess: refresh,
    onError: (e) => setError(apiError(e)),
  });
  const availableSections = (sections?.items ?? []).filter((s: any) =>
    !form.target_grade_id || s.grade_id === form.target_grade_id
  );

  return (
    <Section title="Transfer, Withdrawal & TC" count={cases.length}>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-slate-500">Clearance-gated lifecycle with approval and certificate history.</p>
        <button className="btn-primary text-xs" onClick={() => setOpen(true)}>New request</button>
      </div>
      {error && <div className="mb-3 rounded-lg bg-rose-50 p-2 text-xs text-rose-600">{error}</div>}
      <div className="space-y-3">
        {cases.map((c: any) => (
          <div key={c.id} className="rounded-xl border border-slate-100 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold">{c.request_no} · <span className="capitalize">{c.request_type}</span></div>
                <div className="text-xs text-slate-500">{c.reason} · effective {c.effective_date}</div>
              </div>
              <span className="badge bg-slate-100 capitalize text-slate-600">{c.status}</span>
            </div>
            {c.clearance && (
              <div className={`mt-2 rounded-lg p-2 text-xs ${c.clearance.clear ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                {c.clearance.clear ? "All clearance checks passed." : c.clearance.blockers.join(" · ")}
              </div>
            )}
            {c.certificate && (
              <div className="mt-2 rounded-lg bg-indigo-50 p-2 text-xs text-indigo-700">
                Transfer certificate {c.certificate_no} · Last class {c.certificate.last_class || "—"} · Issued {c.certificate.issued_on}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              {c.status === "draft" && <button className="btn-ghost text-xs" onClick={() => transition.mutate({ id: c.id, action: "submit" })}>Submit for clearance</button>}
              {c.status === "submitted" && <button className="btn-primary text-xs" onClick={() => transition.mutate({ id: c.id, action: "approve" })}>Approve</button>}
              {c.status === "approved" && <button className="btn-primary text-xs" onClick={() => transition.mutate({ id: c.id, action: "complete" })}>Complete & issue TC</button>}
              {["draft", "submitted"].includes(c.status) && <button className="btn-ghost text-xs text-rose-600" onClick={() => transition.mutate({ id: c.id, action: "cancel" })}>Cancel</button>}
            </div>
          </div>
        ))}
        {!cases.length && <p className="text-sm text-slate-400">No lifecycle requests.</p>}
      </div>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="card w-full max-w-lg p-5">
            <div className="mb-4 flex items-center justify-between"><h3 className="font-semibold">New student lifecycle request</h3><button onClick={() => setOpen(false)}>✕</button></div>
            <div className="space-y-3">
              <label><span className="label">Request type</span><select className="input" value={form.request_type} onChange={(e) => setForm({ ...form, request_type: e.target.value })}>
                {studentStatus === "enrolled" ? <><option value="transfer">Transfer with TC</option><option value="withdrawal">Withdrawal with TC</option></> : <option value="reenrollment">Re-enrollment</option>}
              </select></label>
              <label><span className="label">Effective date</span><input className="input" type="date" value={form.effective_date} onChange={(e) => setForm({ ...form, effective_date: e.target.value })} /></label>
              <label><span className="label">Reason</span><textarea className="input min-h-20" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></label>
              {form.request_type === "transfer" && <label><span className="label">Destination school</span><input className="input" value={form.destination_school} onChange={(e) => setForm({ ...form, destination_school: e.target.value })} /></label>}
              {form.request_type === "reenrollment" && <div className="grid grid-cols-2 gap-3">
                <label><span className="label">Target class</span><select className="input" value={form.target_grade_id} onChange={(e) => setForm({ ...form, target_grade_id: e.target.value, target_section_id: "" })}><option value="">Select</option>{(grades?.items ?? []).map((g: any) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
                <label><span className="label">Target section</span><select className="input" value={form.target_section_id} onChange={(e) => setForm({ ...form, target_section_id: e.target.value })}><option value="">Select</option>{availableSections.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
              </div>}
            </div>
            <div className="mt-5 flex justify-end gap-2"><button className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={create.isPending || form.reason.trim().length < 3 || (form.request_type === "reenrollment" && (!form.target_grade_id || !form.target_section_id))} onClick={() => create.mutate()}>{create.isPending ? "Creating…" : "Create draft"}</button></div>
          </div>
        </div>
      )}
    </Section>
  );
}

function HealthAndConsent({ studentId }: { studentId: string }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [medical, setMedical] = useState({ record_type: "medical", condition: "", details: "" });
  const [consent, setConsent] = useState({ consent_type: "photo_media", policy_version: "1.0" });
  const records = useQuery({
    queryKey: ["student-medical", studentId],
    queryFn: async () => (await api.get<any[]>(`/student-lifecycle/students/${studentId}/medical-records`)).data,
  });
  const consents = useQuery({
    queryKey: ["student-consents", studentId],
    queryFn: async () => (await api.get<any[]>(`/student-lifecycle/students/${studentId}/consents`)).data,
  });
  const addMedical = useMutation({
    mutationFn: async () => api.post(`/student-lifecycle/students/${studentId}/medical-records`, {
      ...medical, recorded_on: new Date().toISOString().slice(0, 10), visible_to_parent: true,
    }),
    onSuccess: () => {
      setMedical({ record_type: "medical", condition: "", details: "" });
      qc.invalidateQueries({ queryKey: ["student-medical", studentId] });
    },
    onError: (e) => setError(apiError(e)),
  });
  const requestConsent = useMutation({
    mutationFn: async () => api.post(`/student-lifecycle/students/${studentId}/consents`, consent),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student-consents", studentId] }),
    onError: (e) => setError(apiError(e)),
  });
  const respond = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: string }) => {
      const guardian_name = window.prompt("Guardian name confirming this decision");
      if (!guardian_name) throw new Error("Guardian name is required");
      return api.post(`/student-lifecycle/consents/${id}/respond`, { decision, guardian_name });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student-consents", studentId] }),
    onError: (e) => setError(apiError(e)),
  });
  return (
    <Section title="Medical & Consent Vault">
      {error && <div className="mb-3 rounded-lg bg-rose-50 p-2 text-xs text-rose-600">{error}</div>}
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Restricted health records</div>
          <div className="grid gap-2">
            <select className="input" value={medical.record_type} onChange={(e) => setMedical({ ...medical, record_type: e.target.value })}>
              <option value="medical">Medical condition</option><option value="allergy">Allergy</option>
              <option value="immunization">Immunization</option><option value="emergency">Emergency instruction</option>
            </select>
            <input className="input" placeholder="Condition / record title" value={medical.condition} onChange={(e) => setMedical({ ...medical, condition: e.target.value })} />
            <input className="input" placeholder="Details" value={medical.details} onChange={(e) => setMedical({ ...medical, details: e.target.value })} />
            <button className="btn-primary text-xs" disabled={medical.condition.trim().length < 2 || addMedical.isPending} onClick={() => addMedical.mutate()}>Add health record</button>
          </div>
          <div className="mt-3 space-y-2">
            {(records.data ?? []).map((r: any) => <div key={r.id} className="rounded-lg bg-slate-50 p-2 text-xs"><span className="font-semibold capitalize">{r.record_type}</span> · {r.condition}<div className="text-slate-500">{r.details || "No additional details"} · {r.recorded_on}</div></div>)}
            {!records.data?.length && <p className="text-xs text-slate-400">No health records.</p>}
          </div>
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Versioned guardian consent</div>
          <div className="flex gap-2">
            <select className="input" value={consent.consent_type} onChange={(e) => setConsent({ ...consent, consent_type: e.target.value })}>
              <option value="photo_media">Photo & media</option><option value="field_trip">Field trip</option>
              <option value="medical_treatment">Emergency medical treatment</option><option value="data_processing">Data processing</option>
            </select>
            <input className="input w-24" value={consent.policy_version} onChange={(e) => setConsent({ ...consent, policy_version: e.target.value })} />
            <button className="btn-primary whitespace-nowrap text-xs" onClick={() => requestConsent.mutate()}>Request</button>
          </div>
          <div className="mt-3 space-y-2">
            {(consents.data ?? []).map((c: any) => <div key={c.id} className="rounded-lg border border-slate-100 p-2 text-xs">
              <div className="flex justify-between"><span className="font-semibold capitalize">{c.consent_type.replace(/_/g, " ")}</span><span className="badge bg-slate-100 capitalize">{c.status}</span></div>
              <div className="text-slate-500">Policy {c.policy_version} · requested {c.requested_on}</div>
              {c.status === "pending" && <div className="mt-2 flex gap-2"><button className="btn-primary text-xs" onClick={() => respond.mutate({ id: c.id, decision: "granted" })}>Grant</button><button className="btn-ghost text-xs" onClick={() => respond.mutate({ id: c.id, decision: "declined" })}>Decline</button></div>}
              {c.status === "granted" && <button className="btn-ghost mt-2 text-xs text-rose-600" onClick={() => respond.mutate({ id: c.id, decision: "revoked" })}>Revoke</button>}
            </div>)}
            {!consents.data?.length && <p className="text-xs text-slate-400">No consent requests.</p>}
          </div>
        </div>
      </div>
    </Section>
  );
}

export function StudentProfile() {
  const { id = "" } = useParams();
  const branding = useBranding();
  const { data, isLoading } = useQuery({
    queryKey: ["student-profile", id],
    queryFn: async () => (await api.get<any>(`/reports/student-360/${id}`)).data,
  });

  if (isLoading) return <div className="text-slate-400">Loading…</div>;
  if (!data) return <div className="text-slate-400">Student not found.</div>;
  const s = data.student;
  const attTotal = Object.values(data.attendance).reduce((a: number, b: any) => a + b, 0) as number;
  const present = data.attendance.present ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Link to="/students" className="btn-ghost text-sm">
          ← All students
        </Link>
        <button
          className="btn-primary text-sm"
          onClick={() => printMarksheet(branding, s, data.marks)}
        >
          Download Marksheet
        </button>
      </div>

      {/* Header */}
      <div className="card flex flex-wrap items-center gap-5 p-5">
        {s.photo_url ? (
          <img src={s.photo_url} alt="" className="h-20 w-20 rounded-full object-cover" />
        ) : (
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-100 text-3xl font-bold text-brand-700">
            {s.name?.[0]}
          </div>
        )}
        <div>
          <div className="text-2xl font-semibold">{s.name}</div>
          <div className="text-sm text-slate-400">
            {s.admission_no} · Roll {s.roll_no || "—"} · Grade {s.grade} · Section {s.section}
          </div>
          <span className="badge mt-1 bg-emerald-50 capitalize text-emerald-600">{s.status}</span>
        </div>
        <div className="ml-auto grid grid-cols-3 gap-4">
          <Field label="Class Teacher" value={s.class_teacher} />
          <Field label="House" value={s.house} />
          <Field label="Blood Group" value={s.blood_group} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Section title="Personal Details">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <Field label="Date of Birth" value={s.date_of_birth} />
            <Field label="Gender" value={s.gender} />
            <Field label="Admission Date" value={s.admission_date} />
            <Field label="Category" value={s.category} />
            <Field label="Religion" value={s.religion} />
            <Field label="Nationality" value={s.nationality} />
            <Field label="Mother Tongue" value={s.mother_tongue} />
            <Field label={`${s.government_id_type?.toUpperCase() || "Govt ID"} (masked)`} value={s.government_id_masked} />
            <Field label="Phone" value={s.phone} />
            <Field label="Email" value={s.email} />
            <Field label="Emergency Contact" value={s.emergency_contact_name && `${s.emergency_contact_name} · ${s.emergency_contact_phone || ""}`} />
            <Field label="Previous School" value={s.previous_school} />
          </div>
          <div className="mt-3 border-t border-slate-100 pt-3">
            <Field label="Address" value={[s.address, s.city, s.state, s.pincode].filter(Boolean).join(", ")} />
          </div>
        </Section>

        <Section title="Guardians" count={data.guardians.length}>
          <Table
            cols={[["name", "Name"], ["relation", "Relation"], ["phone", "Phone"], ["occupation", "Occupation"]]}
            rows={data.guardians}
          />
        </Section>

        <Section title="Teachers" count={data.teachers?.length ?? 0}>
          <div className="mb-2 text-xs text-slate-500">
            Class Teacher: <span className="font-medium">{s.class_teacher || "—"}</span>
          </div>
          <Table
            cols={[["name", "Teacher"], ["subject", "Subject"], ["designation", "Designation"]]}
            rows={data.teachers ?? []}
          />
        </Section>

        <Section title="Academic History" count={data.academic_history.length}>
          <Table
            cols={[["year", "Year"], ["grade", "Class"], ["result", "Result"], ["percentage", "%"], ["rank", "Rank"]]}
            rows={data.academic_history}
          />
        </Section>

        <Section title="Exam Results" count={data.marks.length}>
          <Table
            cols={[["exam", "Exam"], ["subject", "Subject"], ["marks", "Marks"], ["grade", "Grade"]]}
            rows={data.marks}
          />
        </Section>

        <Section title="Achievements" count={data.achievements.length}>
          <Table
            cols={[["title", "Title"], ["category", "Category"], ["level", "Level"], ["date", "Date"]]}
            rows={data.achievements}
          />
        </Section>

        <Section title="Activities" count={data.activities.length}>
          <Table cols={[["name", "Activity"], ["status", "Status"], ["date", "Since"]]} rows={data.activities} />
        </Section>

        <Section title="Assets Held (Library & Inventory)" count={data.assets?.length ?? 0}>
          <Table
            cols={[["type", "Type"], ["name", "Item"], ["quantity", "Qty"], ["status", "Status"], ["due_date", "Due"]]}
            rows={data.assets ?? []}
          />
        </Section>

        <Section title="Documents">
          <DocumentUpload ownerType="student" ownerId={id} />
        </Section>

        <StudentLifecycle studentId={id} studentStatus={s.status} />

        <HealthAndConsent studentId={id} />

        <Section title="Disciplinary Actions" count={data.discipline.length}>
          <Table
            cols={[["date", "Date"], ["incident", "Incident"], ["severity", "Severity"], ["action", "Action"], ["status", "Status"]]}
            rows={data.discipline}
          />
        </Section>

        <Section title="Remarks" count={data.remarks.length}>
          <div className="space-y-2">
            {data.remarks.map((r: any, i: number) => (
              <div key={i} className="rounded-lg bg-slate-50 px-3 py-2">
                <div className="text-sm">{r.remark}</div>
                <div className="text-[11px] text-slate-400">
                  {r.type} · {r.by || "—"} · {r.date || "—"}
                </div>
              </div>
            ))}
            {data.remarks.length === 0 && <p className="text-sm text-slate-400">None.</p>}
          </div>
        </Section>

        <Section title="Attendance">
          <div className="mb-2 text-3xl font-semibold text-indigo-600">
            {attTotal ? Math.round((present / attTotal) * 100) : 0}%
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.attendance).map(([state, n]) => (
              <span key={state} className="badge bg-slate-100 capitalize text-slate-600">
                {state}: {n as number}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Fees">
          <div className="mb-3 grid grid-cols-3 gap-3">
            <Field label="Billed" value={inr(data.fees.billed)} />
            <Field label="Paid" value={inr(data.fees.paid)} />
            <Field label="Balance" value={inr(data.fees.balance)} />
          </div>
          <Table
            cols={[["invoice_no", "Invoice"], ["net", "Net"], ["paid", "Paid"], ["status", "Status"], ["due_date", "Due"]]}
            rows={data.invoices}
          />
        </Section>
      </div>
    </div>
  );
}

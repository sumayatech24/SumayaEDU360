import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Modal } from "../components/Modal";
import type { Page } from "../lib/types";

interface Lead {
  id: string;
  lead_no: string;
  student_name: string;
  phone?: string;
  stage: string;
  source?: string;
  converted_student_id?: string | null;
}

const STAGES = [
  "inquiry",
  "counseling",
  "entrance_test",
  "document_collection",
  "approved",
  "enrolled",
  "rejected",
];
const NEXT: Record<string, string> = {
  inquiry: "counseling",
  counseling: "entrance_test",
  entrance_test: "document_collection",
  document_collection: "approved",
  approved: "enrolled",
};

const EMPTY_APP = {
  student_name: "", phone: "", email: "", source: "website", grade_applied_id: "",
  date_of_birth: "", gender: "", category: "", religion: "", previous_school: "",
  address: "", city: "", state: "", pincode: "",
  father_name: "", father_phone: "", mother_name: "", mother_phone: "",
};

export function Admissions() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_APP });
  const [documents, setDocuments] = useState<{ name: string; data: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["admission-leads-board"],
    queryFn: async () =>
      (await api.get<Page<Lead>>("/admission-leads", { params: { page_size: 200 } })).data,
  });
  const { data: grades } = useQuery({
    queryKey: ["grades-pick"],
    queryFn: async () => (await api.get<Page<any>>("/grades", { params: { page_size: 100 } })).data,
  });
  const leads = data?.items ?? [];

  function onDocFile(file?: File) {
    if (!file) return;
    if (file.size > 500_000) {
      setError("Each document must be under 500 KB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setDocuments((d) => [...d, { name: file.name, data: String(reader.result) }]);
    reader.readAsDataURL(file);
  }

  const advance = useMutation({
    mutationFn: async ({ id, stage }: { id: string; stage: string }) =>
      api.post(`/admissions/leads/${id}/advance`, { stage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admission-leads-board"] }),
  });

  const convert = useMutation({
    mutationFn: async (id: string) => api.post(`/admissions/leads/${id}/convert`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admission-leads-board"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => alert(apiError(e)),
  });

  const create = useMutation({
    mutationFn: async () => {
      const count = leads.length + 1;
      return api.post("/admission-leads", {
        lead_no: `LEAD-${String(count).padStart(4, "0")}-${Date.now() % 1000}`,
        stage: "inquiry",
        ...form,
        grade_applied_id: form.grade_applied_id || null,
        date_of_birth: form.date_of_birth || null,
        documents,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admission-leads-board"] });
      setCreating(false);
      setForm({ ...EMPTY_APP });
      setDocuments([]);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Admissions Pipeline</h1>
          <p className="text-sm text-slate-400">
            Move leads through the lifecycle — inquiry → counseling → test → docs → approved → enrolled.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setCreating(true)}>
          + New Inquiry
        </button>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-4">
        {STAGES.map((stage) => {
          const col = leads.filter((l) => l.stage === stage);
          return (
            <div key={stage} className="w-64 shrink-0">
              <div className="mb-2 flex items-center justify-between px-1">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {stage.replace(/_/g, " ")}
                </span>
                <span className="badge bg-slate-100 text-slate-500">{col.length}</span>
              </div>
              <div className="space-y-2">
                {col.map((l) => (
                  <div key={l.id} className="card p-3">
                    <div className="text-sm font-medium">{l.student_name}</div>
                    <div className="text-[11px] text-slate-400">
                      {l.lead_no} · {l.phone || "—"}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {NEXT[stage] && (
                        <button
                          className="btn-ghost px-2 py-1 text-[11px]"
                          onClick={() => advance.mutate({ id: l.id, stage: NEXT[stage] })}
                        >
                          → {NEXT[stage].replace(/_/g, " ")}
                        </button>
                      )}
                      {stage === "approved" && !l.converted_student_id && (
                        <button
                          className="btn-primary px-2 py-1 text-[11px]"
                          onClick={() => convert.mutate(l.id)}
                        >
                          Enroll
                        </button>
                      )}
                      {stage !== "rejected" && stage !== "enrolled" && (
                        <button
                          className="btn-danger px-2 py-1 text-[11px]"
                          onClick={() => advance.mutate({ id: l.id, stage: "rejected" })}
                        >
                          Reject
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {col.length === 0 && (
                  <div className="rounded-lg border border-dashed border-slate-200 py-4 text-center text-[11px] text-slate-300">
                    empty
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {creating && (
        <Modal wide title="New Admission Application" onClose={() => setCreating(false)}>
          <div className="space-y-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Applicant</div>
            <div className="grid grid-cols-3 gap-3">
              <F label="Student Name *" v={form.student_name} set={(v) => setForm({ ...form, student_name: v })} />
              <div>
                <label className="label">Class Applied</label>
                <select className="input" value={form.grade_applied_id} onChange={(e) => setForm({ ...form, grade_applied_id: e.target.value })}>
                  <option value="">— select —</option>
                  {grades?.items?.map((g: any) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Gender</label>
                <select className="input" value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
                  <option value="">—</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="label">Date of Birth</label>
                <input type="date" className="input" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} />
              </div>
              <F label="Category" v={form.category} set={(v) => setForm({ ...form, category: v })} />
              <F label="Religion" v={form.religion} set={(v) => setForm({ ...form, religion: v })} />
              <F label="Phone" v={form.phone} set={(v) => setForm({ ...form, phone: v })} />
              <F label="Email" v={form.email} set={(v) => setForm({ ...form, email: v })} />
              <F label="Previous School" v={form.previous_school} set={(v) => setForm({ ...form, previous_school: v })} />
            </div>

            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Address</div>
            <div className="grid grid-cols-4 gap-3">
              <div className="col-span-2"><F label="Address" v={form.address} set={(v) => setForm({ ...form, address: v })} /></div>
              <F label="City" v={form.city} set={(v) => setForm({ ...form, city: v })} />
              <F label="Pincode" v={form.pincode} set={(v) => setForm({ ...form, pincode: v })} />
            </div>

            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Parents / Guardians</div>
            <div className="grid grid-cols-4 gap-3">
              <F label="Father Name" v={form.father_name} set={(v) => setForm({ ...form, father_name: v })} />
              <F label="Father Phone" v={form.father_phone} set={(v) => setForm({ ...form, father_phone: v })} />
              <F label="Mother Name" v={form.mother_name} set={(v) => setForm({ ...form, mother_name: v })} />
              <F label="Mother Phone" v={form.mother_phone} set={(v) => setForm({ ...form, mother_phone: v })} />
            </div>

            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Documents</div>
            <div>
              <input type="file" accept="image/*,application/pdf" className="text-sm" onChange={(e) => onDocFile(e.target.files?.[0])} />
              <div className="mt-2 flex flex-wrap gap-2">
                {documents.map((d, i) => (
                  <span key={i} className="badge bg-slate-100 text-slate-600">
                    {d.name}
                    <button className="ml-1 text-red-500" onClick={() => setDocuments(documents.filter((_, j) => j !== i))}>✕</button>
                  </span>
                ))}
              </div>
            </div>

            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setCreating(false)}>Cancel</button>
              <button className="btn-primary" disabled={!form.student_name || create.isPending} onClick={() => create.mutate()}>
                Submit Application
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function F({ label, v, set }: { label: string; v: string; set: (v: string) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input className="input" value={v} onChange={(e) => set(e.target.value)} />
    </div>
  );
}

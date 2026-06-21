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

export function Admissions() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ student_name: "", phone: "", source: "website" });
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["admission-leads-board"],
    queryFn: async () =>
      (await api.get<Page<Lead>>("/admission-leads", { params: { page_size: 200 } })).data,
  });
  const leads = data?.items ?? [];

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
        student_name: form.student_name,
        phone: form.phone,
        source: form.source,
        stage: "inquiry",
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admission-leads-board"] });
      setCreating(false);
      setForm({ student_name: "", phone: "", source: "website" });
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
        <Modal title="New Admission Inquiry" onClose={() => setCreating(false)}>
          <div className="space-y-4">
            <div>
              <label className="label">Student Name *</label>
              <input
                className="input"
                value={form.student_name}
                onChange={(e) => setForm({ ...form, student_name: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Phone</label>
              <input
                className="input"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setCreating(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!form.student_name || create.isPending}
                onClick={() => create.mutate()}
              >
                Create
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../components/Modal";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface Asset {
  id: string;
  item: string;
  assignee_type: string;
  assignee: string;
  quantity: number;
  issue_date?: string;
  due_date?: string;
  status: string;
}

export function AssetTracking() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    item_id: "",
    assignee_type: "student",
    student_id: "",
    employee_id: "",
    quantity: 1,
    due_date: "",
  });

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: async () => (await api.get<Asset[]>("/inventory/assets")).data,
  });
  const { data: items } = useQuery({
    queryKey: ["inv-items"],
    queryFn: async () => (await api.get<Page<any>>("/inventory-item", { params: { page_size: 200 } })).data,
  });
  const { data: students } = useQuery({
    queryKey: ["students-pick"],
    queryFn: async () => (await api.get<Page<any>>("/students", { params: { page_size: 300 } })).data,
  });
  const { data: employees } = useQuery({
    queryKey: ["employees-pick"],
    queryFn: async () => (await api.get<Page<any>>("/employees", { params: { page_size: 200 } })).data,
  });

  const issue = useMutation({
    mutationFn: async () =>
      api.post("/inventory/assets/issue", {
        item_id: form.item_id,
        assignee_type: form.assignee_type,
        student_id: form.assignee_type === "student" ? form.student_id : null,
        employee_id: form.assignee_type === "employee" ? form.employee_id : null,
        quantity: Number(form.quantity),
        due_date: form.due_date || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["inv-items"] });
      setOpen(false);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const ret = useMutation({
    mutationFn: async (assetId: string) => api.post(`/inventory/assets/${assetId}/return`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["inv-items"] });
    },
    onError: (e) => alert(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Asset Tracking</h1>
          <p className="text-sm text-slate-400">
            Issue inventory (sports kit, instruments, devices…) to students or staff and track returns. Issuing
            reduces stock; returning restores it. Issued items appear on the student's profile.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          + Issue Asset
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3">Issued To</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">Issued</th>
              <th className="px-4 py-3">Due</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {assets.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-4 py-2.5 font-medium">{a.item}</td>
                <td className="px-4 py-2.5">{a.assignee}</td>
                <td className="px-4 py-2.5 capitalize">{a.assignee_type}</td>
                <td className="px-4 py-2.5">{a.quantity}</td>
                <td className="px-4 py-2.5">{a.issue_date || "—"}</td>
                <td className="px-4 py-2.5">{a.due_date || "—"}</td>
                <td className="px-4 py-2.5">
                  <span className={`badge ${a.status === "returned" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}>
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  {a.status !== "returned" && (
                    <button className="btn-primary px-2.5 py-1 text-xs" onClick={() => ret.mutate(a.id)}>
                      Return
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {assets.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                  No assets issued yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal title="Issue Asset" onClose={() => setOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="label">Item</label>
              <select className="input" value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}>
                <option value="">— select —</option>
                {items?.items?.map((i: any) => (
                  <option key={i.id} value={i.id}>
                    {i.name} ({i.quantity_on_hand} in stock)
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Issue To</label>
                <select className="input" value={form.assignee_type} onChange={(e) => setForm({ ...form, assignee_type: e.target.value })}>
                  <option value="student">Student</option>
                  <option value="employee">Employee</option>
                </select>
              </div>
              <div>
                <label className="label">Quantity</label>
                <input type="number" min={1} className="input" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
              </div>
            </div>
            {form.assignee_type === "student" ? (
              <div>
                <label className="label">Student</label>
                <select className="input" value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })}>
                  <option value="">— select —</option>
                  {students?.items?.map((s: any) => (
                    <option key={s.id} value={s.id}>
                      {s.first_name} {s.last_name} · {s.admission_no}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div>
                <label className="label">Employee</label>
                <select className="input" value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
                  <option value="">— select —</option>
                  {employees?.items?.map((e: any) => (
                    <option key={e.id} value={e.id}>
                      {e.first_name} {e.last_name} · {e.employee_no}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="label">Due Date (optional)</label>
              <input type="date" className="input" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!form.item_id || (form.assignee_type === "student" ? !form.student_id : !form.employee_id) || issue.isPending}
                onClick={() => issue.mutate()}
              >
                Issue
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

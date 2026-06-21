import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Modal } from "../components/Modal";
import type { Page } from "../lib/types";

interface Leave {
  id: string;
  employee_id: string;
  leave_type?: string;
  from_date: string;
  to_date: string;
  days: number;
  reason?: string;
  request_status: string;
}
interface PayrollRow {
  id: string;
  employee: string;
  month: number;
  year: number;
  basic: string;
  net_pay: string;
  status: string;
}

export function HR() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"leave" | "payroll">("leave");
  const [applyOpen, setApplyOpen] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leaveForm, setLeaveForm] = useState({ employee_id: "", from_date: "", to_date: "", reason: "" });
  const [payForm, setPayForm] = useState({ employee_id: "", month: 6, year: 2026, allowances: 0, deductions: 0 });

  const { data: employees } = useQuery({
    queryKey: ["employees-pick"],
    queryFn: async () => (await api.get<Page<any>>("/employees", { params: { page_size: 200 } })).data,
  });
  const { data: leaves } = useQuery({
    queryKey: ["leave-requests"],
    queryFn: async () => (await api.get<Page<Leave>>("/leave-request", { params: { page_size: 100 } })).data,
  });
  const { data: payroll = [] } = useQuery({
    queryKey: ["payroll"],
    queryFn: async () => (await api.get<PayrollRow[]>("/hr/payroll")).data,
  });

  const empName = (id: string) => {
    const e = employees?.items?.find((x: any) => x.id === id);
    return e ? `${e.first_name} ${e.last_name ?? ""}`.trim() : id.slice(0, 8);
  };

  const apply = useMutation({
    mutationFn: async () => api.post("/hr/leave-requests", leaveForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leave-requests"] });
      setApplyOpen(false);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });
  const decide = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: string }) =>
      api.post(`/hr/leave-requests/${id}/decide`, { decision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leave-requests"] }),
    onError: (e) => alert(apiError(e)),
  });
  const genPay = useMutation({
    mutationFn: async () => api.post("/hr/payroll/generate", payForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payroll"] });
      setPayOpen(false);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">HR Operations</h1>
          <p className="text-sm text-slate-400">Leave management and payroll.</p>
        </div>
        {tab === "leave" ? (
          <button className="btn-primary" onClick={() => setApplyOpen(true)}>
            + Apply Leave
          </button>
        ) : (
          <button className="btn-primary" onClick={() => setPayOpen(true)}>
            + Generate Payroll
          </button>
        )}
      </div>

      <div className="flex gap-2 border-b border-slate-200 pb-1">
        {(["leave", "payroll"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-t-lg px-3 py-2 text-sm capitalize ${
              tab === t ? "border-b-2 border-brand-600 font-medium text-brand-700" : "text-slate-500"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "leave" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Employee</th>
                <th className="px-4 py-3">From</th>
                <th className="px-4 py-3">To</th>
                <th className="px-4 py-3">Days</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {leaves?.items.map((l) => (
                <tr key={l.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{empName(l.employee_id)}</td>
                  <td className="px-4 py-3">{l.from_date}</td>
                  <td className="px-4 py-3">{l.to_date}</td>
                  <td className="px-4 py-3">{l.days}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`badge ${
                        l.request_status === "approved"
                          ? "bg-emerald-50 text-emerald-600"
                          : l.request_status === "rejected"
                          ? "bg-red-50 text-red-600"
                          : "bg-amber-50 text-amber-600"
                      }`}
                    >
                      {l.request_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {l.request_status === "applied" && (
                      <>
                        <button
                          className="btn-ghost px-2 py-1 text-xs text-emerald-600"
                          onClick={() => decide.mutate({ id: l.id, decision: "approved" })}
                        >
                          Approve
                        </button>
                        <button
                          className="btn-danger px-2 py-1 text-xs"
                          onClick={() => decide.mutate({ id: l.id, decision: "rejected" })}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {(leaves?.items.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                    No leave requests.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "payroll" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Employee</th>
                <th className="px-4 py-3">Period</th>
                <th className="px-4 py-3">Basic</th>
                <th className="px-4 py-3">Net Pay</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {payroll.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{p.employee}</td>
                  <td className="px-4 py-3">
                    {p.month}/{p.year}
                  </td>
                  <td className="px-4 py-3">₹{Number(p.basic).toLocaleString("en-IN")}</td>
                  <td className="px-4 py-3 font-medium">₹{Number(p.net_pay).toLocaleString("en-IN")}</td>
                  <td className="px-4 py-3">
                    <span className="badge bg-emerald-50 text-emerald-600">{p.status}</span>
                  </td>
                </tr>
              ))}
              {payroll.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                    No payroll generated.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {applyOpen && (
        <Modal title="Apply Leave" onClose={() => setApplyOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="label">Employee</label>
              <select
                className="input"
                value={leaveForm.employee_id}
                onChange={(e) => setLeaveForm({ ...leaveForm, employee_id: e.target.value })}
              >
                <option value="">— select —</option>
                {employees?.items?.map((e: any) => (
                  <option key={e.id} value={e.id}>
                    {e.first_name} {e.last_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">From</label>
                <input
                  type="date"
                  className="input"
                  value={leaveForm.from_date}
                  onChange={(e) => setLeaveForm({ ...leaveForm, from_date: e.target.value })}
                />
              </div>
              <div>
                <label className="label">To</label>
                <input
                  type="date"
                  className="input"
                  value={leaveForm.to_date}
                  onChange={(e) => setLeaveForm({ ...leaveForm, to_date: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="label">Reason</label>
              <input
                className="input"
                value={leaveForm.reason}
                onChange={(e) => setLeaveForm({ ...leaveForm, reason: e.target.value })}
              />
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setApplyOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!leaveForm.employee_id || !leaveForm.from_date || !leaveForm.to_date || apply.isPending}
                onClick={() => apply.mutate()}
              >
                Apply
              </button>
            </div>
          </div>
        </Modal>
      )}

      {payOpen && (
        <Modal title="Generate Payroll" onClose={() => setPayOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="label">Employee</label>
              <select
                className="input"
                value={payForm.employee_id}
                onChange={(e) => setPayForm({ ...payForm, employee_id: e.target.value })}
              >
                <option value="">— select —</option>
                {employees?.items?.map((e: any) => (
                  <option key={e.id} value={e.id}>
                    {e.first_name} {e.last_name} · ₹{Number(e.salary ?? 0).toLocaleString("en-IN")}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Month</label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  className="input"
                  value={payForm.month}
                  onChange={(e) => setPayForm({ ...payForm, month: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="label">Year</label>
                <input
                  type="number"
                  className="input"
                  value={payForm.year}
                  onChange={(e) => setPayForm({ ...payForm, year: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="label">Allowances</label>
                <input
                  type="number"
                  className="input"
                  value={payForm.allowances}
                  onChange={(e) => setPayForm({ ...payForm, allowances: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="label">Deductions</label>
                <input
                  type="number"
                  className="input"
                  value={payForm.deductions}
                  onChange={(e) => setPayForm({ ...payForm, deductions: Number(e.target.value) })}
                />
              </div>
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setPayOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!payForm.employee_id || genPay.isPending}
                onClick={() => genPay.mutate()}
              >
                Generate
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

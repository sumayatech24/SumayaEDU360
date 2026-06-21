import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Modal } from "../components/Modal";
import type { Page } from "../lib/types";

interface Invoice {
  id: string;
  invoice_no: string;
  student_id: string;
  net_amount: string;
  paid_amount: string;
  payment_status: string;
  due_date?: string;
}

const STATUS_TONE: Record<string, string> = {
  paid: "bg-emerald-50 text-emerald-600",
  partial: "bg-amber-50 text-amber-600",
  unpaid: "bg-slate-100 text-slate-500",
  overdue: "bg-red-50 text-red-600",
  cancelled: "bg-slate-100 text-slate-400",
};

export function Fees() {
  const qc = useQueryClient();
  const [paying, setPaying] = useState<Invoice | null>(null);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["invoices"],
    queryFn: async () => (await api.get<Page<Invoice>>("/invoices", { params: { page_size: 50 } })).data,
  });

  const { data: methods = [] } = useQuery({
    queryKey: ["payment-methods"],
    queryFn: async () =>
      (await api.get<{ code: string; label: string }[]>("/master-types/payment_method/values")).data,
  });

  const pay = useMutation({
    mutationFn: async () =>
      api.post("/fees/payments", {
        invoice_id: paying!.id,
        amount: Number(amount),
        method,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setPaying(null);
      setAmount("");
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const inr = (v: string) => "₹" + Number(v).toLocaleString("en-IN");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Fees & Billing</h1>
        <p className="text-sm text-slate-400">Invoices and collections.</p>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Invoice</th>
              <th className="px-4 py-3">Net</th>
              <th className="px-4 py-3">Paid</th>
              <th className="px-4 py-3">Balance</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.items.map((i) => {
              const balance = Number(i.net_amount) - Number(i.paid_amount);
              return (
                <tr key={i.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{i.invoice_no}</td>
                  <td className="px-4 py-3">{inr(i.net_amount)}</td>
                  <td className="px-4 py-3">{inr(i.paid_amount)}</td>
                  <td className="px-4 py-3">{inr(String(balance))}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${STATUS_TONE[i.payment_status] ?? "bg-slate-100"}`}>
                      {i.payment_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {balance > 0 && (
                      <button
                        className="btn-primary px-2.5 py-1 text-xs"
                        onClick={() => {
                          setError(null);
                          setAmount(String(balance));
                          setPaying(i);
                        }}
                      >
                        Collect
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {paying && (
        <Modal title={`Collect — ${paying.invoice_no}`} onClose={() => setPaying(null)}>
          <div className="space-y-4">
            <div>
              <label className="label">Amount</label>
              <input
                type="number"
                className="input"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div>
              <label className="label">Method</label>
              <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
                {methods.map((m) => (
                  <option key={m.code} value={m.code}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setPaying(null)}>
                Cancel
              </button>
              <button className="btn-primary" disabled={pay.isPending} onClick={() => pay.mutate()}>
                {pay.isPending ? "Saving…" : "Record Payment"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

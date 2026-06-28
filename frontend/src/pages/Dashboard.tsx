import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Icon } from "../components/Icon";
import { useAuth } from "../lib/auth";

interface DashboardData {
  cards: { key: string; label: string; value: number; icon: string }[];
  finance: { total_billed: string; total_collected: string; outstanding: string };
}

/** Compact self check-in for staff who land on the admin shell (non-teaching staff). */
function SelfCheckInCard() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["me-attendance"],
    queryFn: async () => (await api.get<{ today: string; today_state: string | null }>("/portal/me/attendance")).data,
  });
  const states = useQuery({
    queryKey: ["master-values", "attendance_state"],
    queryFn: async () => (await api.get<{ code: string; label: string }[]>("/master-types/attendance_state/values")).data,
  });
  const [state, setState] = useState("present");
  const [busy, setBusy] = useState(false);
  async function checkIn() {
    setBusy(true);
    try {
      await api.post("/portal/me/attendance/check-in", { state });
      qc.invalidateQueries({ queryKey: ["me-attendance"] });
    } catch (e) { alert(apiError(e)); } finally { setBusy(false); }
  }
  const marked = !!data?.today_state;
  return (
    <div className="card flex flex-wrap items-center justify-between gap-3 p-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-600">My Attendance · {data?.today}</h3>
        {marked ? (
          <div className="text-lg font-semibold capitalize text-emerald-600">Marked: {data?.today_state?.replace("_", " ")}</div>
        ) : (
          <div className="text-lg font-semibold text-slate-500">Not marked yet</div>
        )}
      </div>
      <div className="flex items-end gap-2">
        <select className="input" value={state} onChange={(e) => setState(e.target.value)}>
          {(states.data ?? [{ code: "present", label: "Present" }]).map((s) => (
            <option key={s.code} value={s.code}>{s.label}</option>
          ))}
        </select>
        <button className="btn-primary" disabled={busy} onClick={() => void checkIn()}>
          {busy ? "Saving…" : marked ? "Update" : "Check in"}
        </button>
      </div>
    </div>
  );
}

export function Dashboard() {
  const { portal } = useAuth();
  const { data } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardData>("/reports/dashboard")).data,
  });

  const { data: feeBreakdown = [] } = useQuery({
    queryKey: ["fees-collection"],
    queryFn: async () =>
      (await api.get<{ status: string; count: number; amount: string }[]>("/reports/fees-collection")).data,
  });

  const inr = (v?: string) =>
    "₹" + Number(v ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-400">Live metrics — everything sourced from the database.</p>
      </div>

      {portal?.person_type === "employee" && <SelfCheckInCard />}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {data?.cards.map((c) => (
          <div key={c.key} className="card flex items-center gap-4 p-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
              <Icon name={c.icon} />
            </div>
            <div>
              <div className="text-2xl font-semibold">{c.value}</div>
              <div className="text-xs text-slate-400">{c.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <FinanceCard label="Total Billed" value={inr(data?.finance.total_billed)} tone="slate" />
        <FinanceCard label="Collected" value={inr(data?.finance.total_collected)} tone="green" />
        <FinanceCard label="Outstanding" value={inr(data?.finance.outstanding)} tone="amber" />
      </div>

      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-slate-600">Fee Collection by Status</h3>
        {feeBreakdown.length === 0 && <p className="text-sm text-slate-400">No invoices yet.</p>}
        <div className="space-y-3">
          {feeBreakdown.map((f) => {
            const max = Math.max(...feeBreakdown.map((x) => x.count), 1);
            return (
              <div key={f.status} className="flex items-center gap-3">
                <span className="w-20 text-xs capitalize text-slate-500">{f.status}</span>
                <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-brand-500"
                    style={{ width: `${(f.count / max) * 100}%` }}
                  />
                </div>
                <span className="w-28 text-right text-xs text-slate-500">
                  {f.count} · {inr(f.amount)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function FinanceCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  const tones: Record<string, string> = {
    slate: "text-slate-700",
    green: "text-emerald-600",
    amber: "text-amber-600",
  };
  return (
    <div className="card p-5">
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${tones[tone]}`}>{value}</div>
    </div>
  );
}

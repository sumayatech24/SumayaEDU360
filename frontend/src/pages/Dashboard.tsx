import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Icon } from "../components/Icon";

interface DashboardData {
  cards: { key: string; label: string; value: number; icon: string }[];
  finance: { total_billed: string; total_collected: string; outstanding: string };
}

export function Dashboard() {
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

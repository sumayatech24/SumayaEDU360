import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Modal } from "../components/Modal";
import { api, apiError } from "../lib/api";
import type { Page } from "../lib/types";

interface AcademicYear { id: string; name: string; is_current: boolean }
interface Grade { id: string; name: string }
interface Section { id: string; name: string; grade_id: string }
interface Plan {
  id: string; name: string; code: string; academic_year_id: string; grade_id?: string;
  frequency: string; amount: string; allow_partial_payment: boolean;
  components: { id: string; head: string; amount: string; aid_eligible: boolean }[];
  installments: { id: string; name: string; due_date: string; percentage: string }[];
}
interface DueRow {
  id: string; invoice_no: string; student: string; admission_no: string; academic_year: string;
  grade: string; section: string; class_teacher: string; installment: string; installment_id?: string;
  due_date?: string; gross_amount: string; government_aid_amount: string; discount_amount: string;
  net_amount: string; paid_amount: string; balance: string; payment_status: string; fee_category: string;
  components: { head: string; gross_amount: string; aid_amount: string; net_amount: string }[];
}
interface DuesResponse {
  rows: DueRow[];
  summary: { invoices: number; billed: string; paid: string; pending: string; overdue: number };
}
interface FeePayment { id: string; receipt_no: string; student: string; amount: string; method: string; paid_at?: string }
interface FeeRefund { id: string; refund_no: string; amount: string; reason: string; status: string }
interface CashierSession { id: string; business_date: string; opening_float: string; system_cash: string; counted_cash?: string; variance?: string; status: string }
interface Reconciliation { id: string; provider: string; provider_reference: string; expected_amount: string; settled_amount: string; status: string }

const STATUS_TONE: Record<string, string> = {
  paid: "bg-emerald-50 text-emerald-600", partial: "bg-amber-50 text-amber-600",
  unpaid: "bg-slate-100 text-slate-500", overdue: "bg-red-50 text-red-600",
};
const money = (value?: string | number) => "₹" + Number(value ?? 0).toLocaleString("en-IN");
const emptyComponents = () => [
  { head: "Tuition Fee", amount: "36000", aid_eligible: true },
  { head: "Transport Fee", amount: "12000", aid_eligible: false },
  { head: "Development Fee", amount: "6000", aid_eligible: false },
  { head: "Meals / Mess Fee", amount: "6000", aid_eligible: false },
];

export function Fees() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"dues" | "plans" | "operations">("dues");
  const [year, setYear] = useState("");
  const [grade, setGrade] = useState("");
  const [section, setSection] = useState("");
  const [installment, setInstallment] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [paying, setPaying] = useState<DueRow | null>(null);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [planForm, setPlanForm] = useState({
    name: "Standard School Fee", code: `FEE-${new Date().getFullYear()}`,
    academic_year_id: "", grade_id: "", frequency: "quarterly", first_due_date: "",
    allow_partial_payment: true, description: "",
  });
  const [components, setComponents] = useState(emptyComponents());
  const [assignPlan, setAssignPlan] = useState("");
  const [assignGrade, setAssignGrade] = useState("");
  const [assignSection, setAssignSection] = useState("");
  const [aidPercent, setAidPercent] = useState("");
  const [refundForm, setRefundForm] = useState({ payment_id: "", amount: "", reason: "" });
  const [openingFloat, setOpeningFloat] = useState("0");
  const [reconForm, setReconForm] = useState({ provider: "razorpay", provider_reference: "", payment_id: "", expected_amount: "", settled_amount: "" });

  const years = useQuery({
    queryKey: ["fee-years"],
    queryFn: async () => (await api.get<Page<AcademicYear>>("/academic-years", { params: { page_size: 100 } })).data,
  });
  const grades = useQuery({
    queryKey: ["fee-grades"],
    queryFn: async () => (await api.get<Page<Grade>>("/grades", { params: { page_size: 100 } })).data,
  });
  const sections = useQuery({
    queryKey: ["fee-sections"],
    queryFn: async () => (await api.get<Page<Section>>("/sections", { params: { page_size: 200 } })).data,
  });
  const plans = useQuery({
    queryKey: ["fee-plans", year],
    queryFn: async () => (await api.get<Plan[]>("/fees/plans", { params: { academic_year_id: year || undefined } })).data,
  });
  const dues = useQuery({
    queryKey: ["fee-dues", year, grade, section, installment, status],
    queryFn: async () => (await api.get<DuesResponse>("/fees/dues", {
      params: {
        academic_year_id: year || undefined, grade_id: grade || undefined,
        section_id: section || undefined, installment_id: installment || undefined,
        payment_status: status || undefined,
      },
    })).data,
  });
  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: async () => (await api.get<{ code: string; label: string }[]>("/master-types/payment_method/values")).data,
  });
  const payments = useQuery({
    queryKey: ["fee-payments"],
    queryFn: async () => (await api.get<FeePayment[]>("/fees/payments")).data,
  });
  const refunds = useQuery({
    queryKey: ["fee-refunds"],
    queryFn: async () => (await api.get<FeeRefund[]>("/fees/refunds")).data,
  });
  const cashier = useQuery({
    queryKey: ["cashier-sessions"],
    queryFn: async () => (await api.get<CashierSession[]>("/fees/cashier-sessions")).data,
  });
  const reconciliations = useQuery({
    queryKey: ["payment-reconciliations"],
    queryFn: async () => (await api.get<Reconciliation[]>("/fees/reconciliations")).data,
  });
  const allInstallments = useMemo(
    () => (plans.data ?? []).flatMap((plan) => plan.installments),
    [plans.data],
  );

  const createPlan = useMutation({
    mutationFn: async () => api.post("/fees/plans", {
      ...planForm,
      grade_id: planForm.grade_id || null,
      components: components.map((component) => ({
        ...component, amount: Number(component.amount), is_optional: false,
      })),
    }),
    onSuccess: () => {
      setNotice("Fee plan and installment schedule created.");
      setError("");
      qc.invalidateQueries({ queryKey: ["fee-plans"] });
    },
    onError: (e) => setError(apiError(e)),
  });
  const assign = useMutation({
    mutationFn: async () => api.post("/fees/assign", {
      fee_plan_id: assignPlan, grade_id: assignGrade || null, section_id: assignSection || null,
      government_aid_percent: aidPercent === "" ? null : Number(aidPercent),
    }),
    onSuccess: (response) => {
      setNotice(`Assigned fees to ${response.data.students} students; generated ${response.data.invoices_generated} installments.`);
      setError("");
      qc.invalidateQueries({ queryKey: ["fee-dues"] });
    },
    onError: (e) => setError(apiError(e)),
  });
  const pay = useMutation({
    mutationFn: async () => api.post("/fees/payments", {
      invoice_id: paying!.id, amount: Number(amount), method,
    }),
    onSuccess: () => {
      setPaying(null); setAmount(""); setNotice("Payment recorded and balance updated.");
      qc.invalidateQueries({ queryKey: ["fee-dues"] });
    },
    onError: (e) => setError(apiError(e)),
  });
  const remind = useMutation({
    mutationFn: async () => api.post("/fees/reminders", {
      invoice_ids: selected, channels: ["in_app", "email", "whatsapp"],
    }),
    onSuccess: (response) => {
      setNotice(`${response.data.deliveries_created} reminder deliveries created. In-app sent; email/WhatsApp queued.`);
      setSelected([]);
    },
    onError: (e) => setError(apiError(e)),
  });
  const requestRefund = useMutation({
    mutationFn: async () => api.post("/fees/refunds", { ...refundForm, amount: Number(refundForm.amount) }),
    onSuccess: () => {
      setRefundForm({ payment_id: "", amount: "", reason: "" });
      setNotice("Refund submitted for independent approval.");
      qc.invalidateQueries({ queryKey: ["fee-refunds"] });
    },
    onError: (e) => setError(apiError(e)),
  });
  const refundDecision = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: string }) =>
      api.post(`/fees/refunds/${id}/decision`, { decision, reference: decision === "processed" ? `MANUAL-${Date.now()}` : null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fee-refunds"] });
      qc.invalidateQueries({ queryKey: ["fee-dues"] });
    },
    onError: (e) => setError(apiError(e)),
  });
  const openCashier = useMutation({
    mutationFn: async () => api.post("/fees/cashier-sessions/open", { opening_float: Number(openingFloat) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cashier-sessions"] }),
    onError: (e) => setError(apiError(e)),
  });
  const closeCashier = useMutation({
    mutationFn: async (session: CashierSession) => {
      const counted = window.prompt("Counted cash at close", String(Number(session.opening_float) + Number(session.system_cash)));
      if (counted === null) throw new Error("Close cancelled");
      return api.post(`/fees/cashier-sessions/${session.id}/close`, { counted_cash: Number(counted) });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cashier-sessions"] }),
    onError: (e) => setError(apiError(e)),
  });
  const reconcile = useMutation({
    mutationFn: async () => api.post("/fees/reconciliations", {
      ...reconForm, payment_id: reconForm.payment_id || null,
      expected_amount: Number(reconForm.expected_amount), settled_amount: Number(reconForm.settled_amount),
    }),
    onSuccess: () => {
      setReconForm({ provider: "razorpay", provider_reference: "", payment_id: "", expected_amount: "", settled_amount: "" });
      qc.invalidateQueries({ queryKey: ["payment-reconciliations"] });
    },
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div><h1 className="text-2xl font-semibold">Fees & Billing</h1>
        <p className="text-sm text-slate-400">Academic-year plans, installments, fee components, government aid, collections and parent reminders.</p></div>
      <div className="flex gap-2 border-b">
        <button className={tab === "dues" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("dues")}>Student-wise Dues</button>
        <button className={tab === "plans" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("plans")}>Fee Plans & Assignment</button>
        <button className={tab === "operations" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("operations")}>Refunds & Cashier Close</button>
      </div>
      {notice && <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {tab === "dues" && <>
        <div className="card grid gap-3 p-4 md:grid-cols-5">
          <label><span className="label">Academic session</span><select className="input" value={year} onChange={(e) => setYear(e.target.value)}>
            <option value="">All sessions</option>{years.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label><span className="label">Class</span><select className="input" value={grade} onChange={(e) => { setGrade(e.target.value); setSection(""); }}>
            <option value="">All classes</option>{grades.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label><span className="label">Section</span><select className="input" value={section} onChange={(e) => setSection(e.target.value)}>
            <option value="">All sections</option>{sections.data?.items.filter((item) => !grade || item.grade_id === grade).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label><span className="label">Installment</span><select className="input" value={installment} onChange={(e) => setInstallment(e.target.value)}>
            <option value="">All installments</option>{allInstallments.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.due_date}</option>)}
          </select></label>
          <label><span className="label">Status</span><select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>{["unpaid", "partial", "overdue", "paid"].map((item) => <option key={item}>{item}</option>)}
          </select></label>
        </div>
        {dues.data && <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[["Invoices", dues.data.summary.invoices], ["Billed", money(dues.data.summary.billed)], ["Collected", money(dues.data.summary.paid)], ["Pending", money(dues.data.summary.pending)], ["Overdue", dues.data.summary.overdue]].map(([label, value]) =>
            <div className="card p-4" key={String(label)}><div className="text-xs uppercase text-slate-400">{label}</div><div className="mt-1 text-xl font-semibold">{value}</div></div>)}
        </div>}
        <div className="flex gap-2"><button className="btn-primary" disabled={!selected.length || remind.isPending} onClick={() => remind.mutate()}>Send parent reminders ({selected.length})</button>
          <span className="self-center text-xs text-slate-400">Creates in-app notification and queues email + WhatsApp delivery.</span></div>
        <div className="card overflow-hidden"><div className="overflow-x-auto"><table className="w-full min-w-[1250px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr>
            <th className="px-4 py-3">Select</th><th>Student</th><th>Class / Teacher</th><th>Session / Installment</th><th>Components</th><th>Gross</th><th>Govt. Aid</th><th>Paid</th><th>Balance</th><th>Due</th><th>Status</th><th></th>
          </tr></thead><tbody className="divide-y">{dues.data?.rows.map((row) => <tr key={row.id}>
            <td className="px-4 py-3"><input type="checkbox" disabled={Number(row.balance) <= 0} checked={selected.includes(row.id)} onChange={() => setSelected((value) => value.includes(row.id) ? value.filter((id) => id !== row.id) : [...value, row.id])} /></td>
            <td><div className="font-medium">{row.student}</div><div className="text-xs text-slate-400">{row.admission_no} · {row.fee_category}</div></td>
            <td>{row.grade}/{row.section}<div className="text-xs text-slate-400">{row.class_teacher}</div></td>
            <td>{row.academic_year}<div className="text-xs text-slate-400">{row.installment}</div></td>
            <td><div className="max-w-52 text-xs">{row.components.map((item) => `${item.head}: ${money(item.net_amount)}`).join(" · ")}</div></td>
            <td>{money(row.gross_amount)}</td><td className="text-emerald-600">{money(row.government_aid_amount)}</td>
            <td>{money(row.paid_amount)}</td><td className="font-semibold">{money(row.balance)}</td><td>{row.due_date}</td>
            <td><span className={`badge ${STATUS_TONE[row.payment_status]}`}>{row.payment_status}</span></td>
            <td>{Number(row.balance) > 0 && <button className="btn-primary px-2 py-1 text-xs" onClick={() => { setPaying(row); setAmount(row.balance); }}>Collect</button>}</td>
          </tr>)}</tbody>
        </table></div></div>
      </>}

      {tab === "plans" && <div className="grid gap-5 xl:grid-cols-2">
        <div className="card space-y-4 p-5"><h2 className="font-semibold">Create Academic-Year Fee Plan</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <label><span className="label">Plan name</span><input className="input" value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} /></label>
            <label><span className="label">Code</span><input className="input" value={planForm.code} onChange={(e) => setPlanForm({ ...planForm, code: e.target.value })} /></label>
            <label><span className="label">Academic year</span><select className="input" value={planForm.academic_year_id} onChange={(e) => setPlanForm({ ...planForm, academic_year_id: e.target.value })}><option value="">Select</option>{years.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label><span className="label">Class</span><select className="input" value={planForm.grade_id} onChange={(e) => setPlanForm({ ...planForm, grade_id: e.target.value })}><option value="">All classes</option>{grades.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label><span className="label">Frequency</span><select className="input" value={planForm.frequency} onChange={(e) => setPlanForm({ ...planForm, frequency: e.target.value })}><option value="annual">Yearly</option><option value="half_yearly">Half-yearly</option><option value="quarterly">Quarterly</option></select></label>
            <label><span className="label">First due date</span><input type="date" className="input" value={planForm.first_due_date} onChange={(e) => setPlanForm({ ...planForm, first_due_date: e.target.value })} /></label>
          </div>
          <div><div className="label">Fee components</div>{components.map((component, index) => <div className="mb-2 grid grid-cols-[1fr_120px_auto] gap-2" key={index}>
            <input className="input" value={component.head} onChange={(e) => setComponents((items) => items.map((item, i) => i === index ? { ...item, head: e.target.value } : item))} />
            <input className="input" type="number" value={component.amount} onChange={(e) => setComponents((items) => items.map((item, i) => i === index ? { ...item, amount: e.target.value } : item))} />
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={component.aid_eligible} onChange={(e) => setComponents((items) => items.map((item, i) => i === index ? { ...item, aid_eligible: e.target.checked } : item))} /> Aid eligible</label>
          </div>)}</div>
          <button className="btn-primary" disabled={!planForm.name || !planForm.code || !planForm.academic_year_id || !planForm.first_due_date || createPlan.isPending} onClick={() => createPlan.mutate()}>Create plan & installments</button>
        </div>
        <div className="space-y-5">
          <div className="card space-y-3 p-5"><h2 className="font-semibold">Assign Plan to Class / Students</h2>
            <label><span className="label">Fee plan</span><select className="input" value={assignPlan} onChange={(e) => setAssignPlan(e.target.value)}><option value="">Select plan</option>{plans.data?.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.frequency} · {money(item.amount)}</option>)}</select></label>
            <div className="grid gap-3 md:grid-cols-2"><label><span className="label">Class</span><select className="input" value={assignGrade} onChange={(e) => { setAssignGrade(e.target.value); setAssignSection(""); }}><option value="">Plan default</option>{grades.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label><span className="label">Section</span><select className="input" value={assignSection} onChange={(e) => setAssignSection(e.target.value)}><option value="">All sections</option>{sections.data?.items.filter((item) => !assignGrade || item.grade_id === assignGrade).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
            <label><span className="label">Aid override % (blank uses each student category)</span><input className="input" type="number" min="0" max="100" value={aidPercent} onChange={(e) => setAidPercent(e.target.value)} /></label>
            <button className="btn-primary" disabled={!assignPlan || assign.isPending} onClick={() => assign.mutate()}>Generate student installments</button>
          </div>
          {plans.data?.map((plan) => <div className="card p-4" key={plan.id}><div className="font-semibold">{plan.name}</div><div className="text-xs text-slate-400">{plan.frequency} · {money(plan.amount)} · {plan.installments.length} installment(s)</div><div className="mt-2 flex flex-wrap gap-1">{plan.components.map((component) => <span className="badge bg-slate-100" key={component.id}>{component.head}: {money(component.amount)}{component.aid_eligible ? " · aid" : ""}</span>)}</div></div>)}
        </div>
      </div>}

      {tab === "operations" && <div className="grid gap-5 xl:grid-cols-2">
        <div className="card space-y-4 p-5">
          <div><h2 className="font-semibold">Refund control</h2><p className="text-xs text-slate-400">Requests require approval before processing and automatically reopen the invoice balance.</p></div>
          <select className="input" value={refundForm.payment_id} onChange={(e) => {
            const selectedPayment = payments.data?.find((p) => p.id === e.target.value);
            setRefundForm({ ...refundForm, payment_id: e.target.value, amount: selectedPayment?.amount || "" });
          }}><option value="">Select receipt</option>{payments.data?.map((p) => <option key={p.id} value={p.id}>{p.receipt_no} · {p.student} · {money(p.amount)}</option>)}</select>
          <div className="grid grid-cols-2 gap-2"><input className="input" type="number" placeholder="Refund amount" value={refundForm.amount} onChange={(e) => setRefundForm({ ...refundForm, amount: e.target.value })} /><input className="input" placeholder="Reason" value={refundForm.reason} onChange={(e) => setRefundForm({ ...refundForm, reason: e.target.value })} /></div>
          <button className="btn-primary" disabled={!refundForm.payment_id || Number(refundForm.amount) <= 0 || refundForm.reason.length < 3} onClick={() => requestRefund.mutate()}>Request refund</button>
          <div className="space-y-2">{refunds.data?.map((r) => <div key={r.id} className="rounded-lg border p-3 text-sm"><div className="flex justify-between"><span className="font-semibold">{r.refund_no} · {money(r.amount)}</span><span className="badge bg-slate-100 capitalize">{r.status}</span></div><div className="text-xs text-slate-500">{r.reason}</div><div className="mt-2 flex gap-2">{r.status === "requested" && <><button className="btn-primary text-xs" onClick={() => refundDecision.mutate({ id: r.id, decision: "approved" })}>Approve</button><button className="btn-ghost text-xs" onClick={() => refundDecision.mutate({ id: r.id, decision: "rejected" })}>Reject</button></>}{r.status === "approved" && <button className="btn-primary text-xs" onClick={() => refundDecision.mutate({ id: r.id, decision: "processed" })}>Process refund</button>}</div></div>)}</div>
        </div>
        <div className="card space-y-4 p-5">
          <div><h2 className="font-semibold">Cashier session & daily close</h2><p className="text-xs text-slate-400">Reconciles recorded cash against the physical count and records variance.</p></div>
          {!cashier.data?.some((s) => s.status === "open") && <div className="flex gap-2"><input className="input" type="number" value={openingFloat} onChange={(e) => setOpeningFloat(e.target.value)} /><button className="btn-primary whitespace-nowrap" onClick={() => openCashier.mutate()}>Open till</button></div>}
          <div className="space-y-2">{cashier.data?.map((s) => <div key={s.id} className="rounded-lg border p-3 text-sm"><div className="flex justify-between"><span className="font-semibold">{s.business_date}</span><span className="badge bg-slate-100 capitalize">{s.status}</span></div><div className="text-xs text-slate-500">Opening {money(s.opening_float)} · System {money(s.system_cash)}{s.variance !== undefined && ` · Variance ${money(s.variance)}`}</div>{s.status === "open" && <button className="btn-primary mt-2 text-xs" onClick={() => closeCashier.mutate(s)}>Count & close</button>}</div>)}</div>
          <div className="border-t pt-4"><h3 className="mb-2 text-sm font-semibold">Gateway reconciliation</h3>
            <div className="grid gap-2">
              <select className="input" value={reconForm.payment_id} onChange={(e) => { const p = payments.data?.find((item) => item.id === e.target.value); setReconForm({ ...reconForm, payment_id: e.target.value, expected_amount: p?.amount || "", settled_amount: p?.amount || "" }); }}><option value="">Unmatched settlement</option>{payments.data?.filter((p) => p.method !== "cash").map((p) => <option key={p.id} value={p.id}>{p.receipt_no} · {money(p.amount)}</option>)}</select>
              <div className="grid grid-cols-2 gap-2"><input className="input" placeholder="Provider" value={reconForm.provider} onChange={(e) => setReconForm({ ...reconForm, provider: e.target.value })} /><input className="input" placeholder="Provider reference" value={reconForm.provider_reference} onChange={(e) => setReconForm({ ...reconForm, provider_reference: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-2"><input className="input" type="number" placeholder="Expected" value={reconForm.expected_amount} onChange={(e) => setReconForm({ ...reconForm, expected_amount: e.target.value })} /><input className="input" type="number" placeholder="Settled" value={reconForm.settled_amount} onChange={(e) => setReconForm({ ...reconForm, settled_amount: e.target.value })} /></div>
              <button className="btn-primary text-xs" disabled={!reconForm.provider_reference || !reconForm.expected_amount} onClick={() => reconcile.mutate()}>Reconcile settlement</button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">{reconciliations.data?.slice(0, 8).map((r) => <span key={r.id} className="badge bg-slate-100">{r.provider_reference} · {r.status}</span>)}</div>
          </div>
        </div>
      </div>}

      {paying && <Modal title={`Collect — ${paying.invoice_no}`} onClose={() => setPaying(null)}>
        <div className="space-y-4"><label><span className="label">Amount</span><input type="number" className="input" max={paying.balance} value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
          <label><span className="label">Method</span><select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>{methods.data?.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}</select></label>
          <div className="flex justify-end gap-2"><button className="btn-ghost" onClick={() => setPaying(null)}>Cancel</button><button className="btn-primary" disabled={pay.isPending || Number(amount) <= 0 || Number(amount) > Number(paying.balance)} onClick={() => pay.mutate()}>Record Payment</button></div>
        </div></Modal>}
    </div>
  );
}

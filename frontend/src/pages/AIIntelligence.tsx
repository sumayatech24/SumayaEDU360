import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";

type Tab = "assistant" | "insights" | "automations";
type AssistantType = "teacher" | "parent" | "student" | "operations";
type Task = "chat" | "lesson_plan" | "question_paper" | "student_tutor" | "parent_summary" |
  "teacher_remark" | "message_draft" | "workflow_plan";

interface AIResponse {
  session: { id: string; title: string };
  message: { id: string; content: string; confidence: number; provider: string; model_name: string };
}
interface Insight {
  id: string; insight_type: string; title: string; summary: string; score: number;
  risk_band: "low" | "medium" | "high"; factors: Record<string, unknown>[];
  recommendations: string[]; review_status: string; model_version: string;
}
interface Automation {
  id: string; workflow_type: string; objective: string; status: string;
  proposed_actions: { step: number; tool: string; mode: string; approval_required?: boolean }[];
  output?: Record<string, unknown>;
}

const taskOptions: { value: Task; label: string }[] = [
  { value: "chat", label: "General assistant" },
  { value: "lesson_plan", label: "Lesson plan" },
  { value: "question_paper", label: "Question paper" },
  { value: "teacher_remark", label: "Teacher remark" },
  { value: "message_draft", label: "Message draft" },
  { value: "student_tutor", label: "Student tutor" },
  { value: "parent_summary", label: "Parent summary" },
  { value: "workflow_plan", label: "Workflow plan" },
];
const riskStyle = {
  high: "bg-red-50 text-red-700", medium: "bg-amber-50 text-amber-700", low: "bg-emerald-50 text-emerald-700",
};

export function AIIntelligence() {
  const [tab, setTab] = useState<Tab>("assistant");
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">AI Intelligence</h1>
          <p className="text-sm text-slate-500">
            Governed copilots, explainable predictions and approval-gated agentic workflows.
          </p>
        </div>
        <span className="badge bg-emerald-50 text-emerald-700">Human review enforced</span>
      </div>
      <div className="flex gap-2 border-b border-slate-200">
        {(["assistant", "insights", "automations"] as Tab[]).map((value) => (
          <button key={value} onClick={() => setTab(value)}
            className={`px-4 py-2 text-sm font-medium capitalize ${tab === value ? "border-b-2 border-brand-600 text-brand-700" : "text-slate-500"}`}>
            {value}
          </button>
        ))}
      </div>
      {tab === "assistant" && <AssistantPanel />}
      {tab === "insights" && <InsightsPanel />}
      {tab === "automations" && <AutomationPanel />}
    </div>
  );
}

function AssistantPanel() {
  const [assistantType, setAssistantType] = useState<AssistantType>("teacher");
  const [task, setTask] = useState<Task>("lesson_plan");
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [messages, setMessages] = useState<{ role: string; content: string; meta?: string }[]>([]);
  const generate = useMutation({
    mutationFn: async () => (await api.post<AIResponse>("/ai/assistant", {
      assistant_type: assistantType, task, prompt, session_id: sessionId,
    })).data,
    onSuccess: (data) => {
      setSessionId(data.session.id);
      setMessages((rows) => [
        ...rows, { role: "You", content: prompt },
        { role: "AI draft", content: data.message.content,
          meta: `${data.message.provider} / ${data.message.model_name} · ${Math.round(data.message.confidence * 100)}% confidence` },
      ]);
      setPrompt("");
    },
  });
  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <div className="card space-y-4 p-5">
        <div><label className="label">Assistant</label>
          <select className="input" value={assistantType} onChange={(e) => setAssistantType(e.target.value as AssistantType)}>
            <option value="teacher">Teacher assistant</option><option value="operations">Operations copilot</option>
            <option value="parent">Parent chatbot</option><option value="student">Student tutor</option>
          </select>
        </div>
        <div><label className="label">Task</label>
          <select className="input" value={task} onChange={(e) => setTask(e.target.value as Task)}>
            {taskOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>
        <div><label className="label">Instruction and verified context</label>
          <textarea className="input min-h-36" value={prompt} onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe grade, subject, objective, constraints and evidence…" />
        </div>
        {generate.isError && <p className="text-sm text-red-600">{apiError(generate.error)}</p>}
        <button className="btn-primary w-full" disabled={prompt.trim().length < 3 || generate.isPending}
          onClick={() => generate.mutate()}>{generate.isPending ? "Generating…" : "Generate governed draft"}</button>
        <p className="text-xs text-slate-500">
          Generated content is versioned and audited. Restricted credentials and unmasked government IDs are blocked.
        </p>
      </div>
      <div className="card min-h-[460px] p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">Working session</h2>
          {sessionId && <span className="text-xs text-slate-400">Session {sessionId.slice(0, 8)}</span>}
        </div>
        {!messages.length && <div className="rounded-lg border border-dashed p-10 text-center text-sm text-slate-400">
          Choose a task and generate the first reviewed draft.
        </div>}
        <div className="space-y-4">
          {messages.map((message, index) => <div key={index}
            className={`rounded-xl p-4 ${message.role === "You" ? "ml-12 bg-slate-100" : "mr-8 border border-brand-100 bg-brand-50"}`}>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{message.role}</div>
            <div className="whitespace-pre-wrap text-sm leading-6">{message.content}</div>
            {message.meta && <div className="mt-3 text-xs text-slate-400">{message.meta}</div>}
          </div>)}
        </div>
      </div>
    </div>
  );
}

function InsightsPanel() {
  const qc = useQueryClient();
  const [type, setType] = useState("absence_risk");
  const { data, isLoading } = useQuery({
    queryKey: ["ai-insights"],
    queryFn: async () => (await api.get<{ items: Insight[]; total: number }>("/ai/insights", { params: { page_size: 100 } })).data,
  });
  const analyze = useMutation({
    mutationFn: async () => api.post("/ai/insights/analyze", { analysis_type: type, refresh: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-insights"] }),
  });
  const review = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "accepted" | "dismissed" }) =>
      api.post(`/ai/insights/${id}/review`, { decision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-insights"] }),
  });
  const items = data?.items ?? [];
  return <div className="space-y-4">
    <div className="card flex flex-wrap items-end gap-3 p-4">
      <div className="min-w-56"><label className="label">Analysis model</label>
        <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="admission_lead">Admission lead scoring</option>
          <option value="absence_risk">Absence prediction</option>
          <option value="fee_default">Fee default prediction</option>
        </select>
      </div>
      <button className="btn-primary" disabled={analyze.isPending} onClick={() => analyze.mutate()}>
        {analyze.isPending ? "Analyzing…" : "Refresh explainable insights"}
      </button>
      <div className="ml-auto text-sm text-slate-500">{data?.total ?? 0} governed insights</div>
    </div>
    {isLoading && <p className="text-sm text-slate-400">Loading insights…</p>}
    <div className="grid gap-4 lg:grid-cols-2">
      {items.map((row) => <div className="card space-y-3 p-5" key={row.id}>
        <div className="flex items-start justify-between gap-3"><div>
          <div className="text-xs uppercase tracking-wide text-slate-400">{row.insight_type.replace(/_/g, " ")}</div>
          <h3 className="font-semibold">{row.title}</h3></div>
          <span className={`badge ${riskStyle[row.risk_band]}`}>{row.risk_band} · {Math.round(row.score)}</span>
        </div>
        <p className="text-sm text-slate-600">{row.summary}</p>
        <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          {row.factors.map((factor, i) => <div key={i}>{Object.entries(factor).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div>)}
        </div>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          {row.recommendations.map((item) => <li key={item}>{item}</li>)}
        </ul>
        <div className="flex items-center justify-between border-t pt-3">
          <span className="text-xs text-slate-400">{row.model_version} · {row.review_status}</span>
          {row.review_status === "pending" && <div className="flex gap-2">
            <button className="btn-ghost" onClick={() => review.mutate({ id: row.id, decision: "dismissed" })}>Dismiss</button>
            <button className="btn-primary" onClick={() => review.mutate({ id: row.id, decision: "accepted" })}>Accept</button>
          </div>}
        </div>
      </div>)}
    </div>
  </div>;
}

function AutomationPanel() {
  const qc = useQueryClient();
  const [workflow, setWorkflow] = useState("fee_reminder_campaign");
  const [objective, setObjective] = useState("");
  const { data = [] } = useQuery({
    queryKey: ["ai-automations"],
    queryFn: async () => (await api.get<Automation[]>("/ai/automations")).data,
  });
  const propose = useMutation({
    mutationFn: async () => api.post("/ai/automations", {
      workflow_type: workflow, objective, parameters: {}, idempotency_key: `${workflow}-${Date.now()}`,
    }),
    onSuccess: () => { setObjective(""); qc.invalidateQueries({ queryKey: ["ai-automations"] }); },
  });
  const decide = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: string }) =>
      api.post(`/ai/automations/${id}/decision`, { decision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-automations"] }),
  });
  return <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
    <div className="card space-y-4 p-5">
      <div><label className="label">Workflow</label><select className="input" value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
        <option value="fee_reminder_campaign">Fee reminder campaign</option>
        <option value="attendance_intervention">Attendance intervention</option>
        <option value="admission_follow_up">Admission follow-up</option>
        <option value="report_distribution">Report distribution</option>
        <option value="timetable_repair">Timetable repair</option>
      </select></div>
      <div><label className="label">Objective</label><textarea className="input min-h-28" value={objective}
        onChange={(e) => setObjective(e.target.value)} placeholder="Define scope, safeguards and expected outcome…" /></div>
      <button className="btn-primary w-full" disabled={objective.trim().length < 5 || propose.isPending}
        onClick={() => propose.mutate()}>Create dry-run proposal</button>
      <p className="text-xs text-slate-500">Write tools cannot execute until an authorized human approves the proposal.</p>
    </div>
    <div className="space-y-4">
      {data.map((run) => <div key={run.id} className="card p-5">
        <div className="flex items-start justify-between"><div>
          <div className="text-xs uppercase text-slate-400">{run.workflow_type.replace(/_/g, " ")}</div>
          <h3 className="font-semibold">{run.objective}</h3></div>
          <span className="badge bg-slate-100 text-slate-700">{run.status}</span>
        </div>
        <div className="my-4 space-y-2">{run.proposed_actions.map((action) =>
          <div key={action.step} className="flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs">{action.step}</span>
            <span className="font-mono text-xs">{action.tool}</span><span className="badge bg-white">{action.mode}</span>
            {action.approval_required && <span className="ml-auto text-xs text-amber-600">approval required</span>}
          </div>)}</div>
        {run.status === "proposed" && <div className="flex justify-end gap-2 border-t pt-3">
          <button className="btn-ghost" onClick={() => decide.mutate({ id: run.id, decision: "reject" })}>Reject</button>
          <button className="btn-primary" onClick={() => decide.mutate({ id: run.id, decision: "approve" })}>Approve proposal</button>
        </div>}
      </div>)}
      {!data.length && <div className="card p-10 text-center text-sm text-slate-400">No agentic workflow proposals yet.</div>}
    </div>
  </div>;
}

import {
  Check,
  ChevronDown,
  CirclePause,
  CirclePlay,
  FileSearch,
  Plus,
  RotateCcw,
  Send,
  ShieldAlert,
  Square,
} from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { Link } from "react-router";

import type {
  ResearchTaskDetail,
  ResearchTaskInput,
  ResearchTaskSummary,
} from "../api/research";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";
import {
  useCancelResearchTaskMutation,
  useCompleteResearchTaskMutation,
  useCreateResearchTaskMutation,
  useDecideResearchActionMutation,
  usePauseResearchTaskMutation,
  useResearchTaskQuery,
  useResearchTasksQuery,
  useRerunResearchTaskMutation,
  useResumeResearchTaskMutation,
} from "../features/research/hooks/use-research-queries";
import { errorMessage } from "../lib/utils";

const statusLabels: Record<ResearchTaskSummary["status"], string> = {
  Draft: "草稿",
  Planning: "规划中",
  Researching: "研究中",
  WaitingCrawl: "等待采集",
  WaitingLogin: "等待登录",
  Summarizing: "汇总中",
  AwaitingReview: "待审核",
  Done: "已完成",
  BudgetExceeded: "预算触发",
  Failed: "失败",
  Cancelled: "已取消",
};

const statusVariant: Record<ResearchTaskSummary["status"], "neutral" | "info" | "success" | "warning" | "danger"> = {
  Draft: "neutral",
  Planning: "info",
  Researching: "info",
  WaitingCrawl: "warning",
  WaitingLogin: "warning",
  Summarizing: "info",
  AwaitingReview: "warning",
  Done: "success",
  BudgetExceeded: "warning",
  Failed: "danger",
  Cancelled: "neutral",
};

const initialForm: ResearchTaskInput = {
  objective: "",
  platforms: ["bili"],
  budget: {
    crawl_limit: 2,
    content_limit: 100,
    duration_seconds: 3_600,
    token_limit: 50_000,
    cost_limit: null,
    cost_currency: null,
  },
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`;
}

function formatCost(cost: string | null, currency: string | null): string {
  return cost === null ? "未配置" : `${cost} ${currency ?? ""}`.trim();
}

export function ResearchTasksPage() {
  const tasks = useResearchTasksQuery();
  const [selectedId, setSelectedId] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const effectiveSelectedId = selectedId && tasks.data?.some((task) => task.id === selectedId)
    ? selectedId
    : tasks.data?.[0]?.id || "";
  const detail = useResearchTaskQuery(effectiveSelectedId);
  const create = useCreateResearchTaskMutation();

  function submit(input: ResearchTaskInput) {
    create.mutate(input, {
      onSuccess: (task) => {
        setSelectedId(task.id);
        setShowCreate(false);
      },
    });
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="AI Runtime · Phase 8B"
        title="AI 研究任务"
        description="围绕一个目标创建可中断、可恢复、证据可追溯的研究任务。采集、模型调用和每次状态流转都保留在任务轨迹中。"
        action={
          <Button onClick={() => setShowCreate((value) => !value)}>
            <Plus className="size-4" /> 新建研究任务
          </Button>
        }
      />

      {showCreate ? <ResearchCreateForm pending={create.isPending} error={create.error} onSubmit={submit} onCancel={() => setShowCreate(false)} /> : null}

      {tasks.isError ? <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} /> : null}
      {!tasks.isError ? (
        <section className="grid gap-5 xl:grid-cols-[330px_minmax(0,1fr)]">
          <TaskList tasks={tasks.data ?? []} selectedId={effectiveSelectedId} loading={tasks.isPending} onSelect={setSelectedId} />
          {detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} /> : detail.data ? <TaskDetail task={detail.data} /> : <EmptyDetail />}
        </section>
      ) : null}
    </div>
  );
}

function ResearchCreateForm({
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  pending: boolean;
  error: unknown;
  onSubmit: (input: ResearchTaskInput) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<ResearchTaskInput>(initialForm);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({ ...form, objective: form.objective.trim() });
  }
  function setBudget(key: keyof ResearchTaskInput["budget"], value: string) {
    if (key === "cost_limit" || key === "cost_currency") {
      setForm((current) => ({ ...current, budget: { ...current.budget, [key]: value || null } }));
      return;
    }
    const number = Number(value);
    if (Number.isFinite(number)) setForm((current) => ({ ...current, budget: { ...current.budget, [key]: number } }));
  }
  return (
    <Card>
      <CardHeader>
        <p className="section-kicker">New research task</p>
        <h2 className="mt-1 font-display text-xl font-semibold">输入研究目标与边界</h2>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-5">
          <label className="block text-sm font-semibold">
            研究目标
            <textarea
              className="mt-2 min-h-28 w-full rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15"
              value={form.objective}
              onChange={(event) => {
                const objective = event.currentTarget.value;
                setForm((current) => ({ ...current, objective }));
              }}
              placeholder="例如：寻找当前值得关注的个人 AI 工作台产品，分析其需求、产品形态与机会。"
              required
              minLength={5}
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <BudgetField label="采集次数上限" value={form.budget.crawl_limit} onChange={(value) => setBudget("crawl_limit", value)} />
            <BudgetField label="新增内容上限" value={form.budget.content_limit} onChange={(value) => setBudget("content_limit", value)} />
            <BudgetField label="运行时长（秒）" value={form.budget.duration_seconds} onChange={(value) => setBudget("duration_seconds", value)} />
            <BudgetField label="Token 上限" value={form.budget.token_limit} onChange={(value) => setBudget("token_limit", value)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-semibold">金额上限（可选）<Input className="mt-2" value={form.budget.cost_limit ?? ""} onChange={(event) => setBudget("cost_limit", event.currentTarget.value)} placeholder="价格未配置时不会生效" /></label>
            <label className="text-sm font-semibold">币种（可选）<Input className="mt-2" value={form.budget.cost_currency ?? ""} onChange={(event) => setBudget("cost_currency", event.currentTarget.value)} placeholder="例如 USD" /></label>
          </div>
          <p className="text-xs leading-5 text-muted">当前平台范围：Bilibili（bili）。每轮会先查已有资料，采集由单 Worker 串行执行。</p>
          {error ? <p className="text-sm text-danger">{errorMessage(error)}</p> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>取消</Button>
            <Button disabled={pending || form.objective.trim().length < 5}><Send className="size-4" />{pending ? "创建中…" : "创建并开始"}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function BudgetField({ label, value, onChange }: { label: string; value: number; onChange: (value: string) => void }) {
  return <label className="text-sm font-semibold">{label}<Input className="mt-2" type="number" min={1} value={value} onChange={(event) => onChange(event.currentTarget.value)} /></label>;
}

function TaskList({ tasks, selectedId, loading, onSelect }: { tasks: ResearchTaskSummary[]; selectedId: string; loading: boolean; onSelect: (id: string) => void }) {
  return (
    <Card className="h-fit overflow-hidden">
      <CardHeader className="border-b border-line pb-4"><p className="section-kicker">Task queue</p><h2 className="mt-1 font-display text-xl font-semibold">研究任务</h2></CardHeader>
      <CardContent className="space-y-2 p-3">
        {loading ? Array.from({ length: 3 }, (_, index) => <div key={index} className="h-20 animate-pulse rounded-xl bg-paper" />) : null}
        {!loading && tasks.length === 0 ? <p className="rounded-xl bg-paper p-5 text-sm text-muted">还没有研究任务，先创建一个目标。</p> : null}
        {tasks.map((task) => <button key={task.id} type="button" onClick={() => onSelect(task.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedId === task.id ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}>
          <div className="flex items-start justify-between gap-2"><span className="line-clamp-2 text-sm font-semibold">{task.objective}</span><Badge variant={statusVariant[task.status]}>{statusLabels[task.status]}</Badge></div>
          <div className="mt-3 flex items-center justify-between text-xs text-muted"><span>第 {task.current_round} 轮 · {task.current_step ?? "等待调度"}</span><span>{(task.consumption.input_tokens + task.consumption.output_tokens).toLocaleString()} tok</span></div>
        </button>)}
      </CardContent>
    </Card>
  );
}

function TaskDetail({ task }: { task: ResearchTaskDetail }) {
  const pause = usePauseResearchTaskMutation();
  const resume = useResumeResearchTaskMutation();
  const cancel = useCancelResearchTaskMutation();
  const rerun = useRerunResearchTaskMutation();
  const complete = useCompleteResearchTaskMutation();
  const decide = useDecideResearchActionMutation();
  const busy = pause.isPending || resume.isPending || cancel.isPending || rerun.isPending || complete.isPending || decide.isPending;
  const isTerminal = ["Done", "Failed", "Cancelled"].includes(task.status);
  const route = useMemo(() => task.route_snapshot.primary as { provider?: string; model?: string } | undefined, [task.route_snapshot.primary]);
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="border-b border-line pb-5"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><p className="section-kicker">Research dossier</p><h2 className="mt-1 break-words font-display text-2xl font-semibold">{task.objective}</h2><p className="mt-2 font-mono text-xs text-muted">{task.id}</p></div><Badge variant={statusVariant[task.status]}>{statusLabels[task.status]}</Badge></div><div className="mt-5 flex flex-wrap gap-2">{!isTerminal && !task.paused ? <Button variant="secondary" size="sm" disabled={busy} onClick={() => pause.mutate(task.id)}><CirclePause className="size-4" />暂停</Button> : null}{!isTerminal && task.paused ? <Button variant="secondary" size="sm" disabled={busy} onClick={() => resume.mutate(task.id)}><CirclePlay className="size-4" />继续</Button> : null}{task.status === "AwaitingReview" ? <><Button size="sm" disabled={busy} onClick={() => complete.mutate(task.id)}><Check className="size-4" />确认完成</Button><Button variant="secondary" size="sm" disabled={busy} onClick={() => rerun.mutate(task.id)}><RotateCcw className="size-4" />再跑一轮</Button></> : null}{!isTerminal ? <Button variant="danger" size="sm" disabled={busy} onClick={() => cancel.mutate(task.id)}><Square className="size-3.5" />取消任务</Button> : null}</div></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Metric label="阶段" value={task.current_step ?? "等待调度"} /><Metric label="研究轮次" value={`第 ${task.current_round} 轮`} /><Metric label="采集 / 内容" value={`${task.consumption.crawl_count} / ${task.consumption.content_count}`} /><Metric label="运行时长" value={formatDuration(task.consumption.duration_seconds)} /><Metric label="Token" value={`${(task.consumption.input_tokens + task.consumption.output_tokens).toLocaleString()} / ${task.budget.token_limit.toLocaleString()}`} /><Metric label="估算成本" value={formatCost(task.consumption.estimated_cost, task.consumption.cost_currency)} /><Metric label="主路由" value={route?.model ?? "尚未快照"} /><Metric label="来源平台" value={task.platforms.join("、")} /></CardContent>
      </Card>

      {task.failure_reason ? <div className="flex gap-3 rounded-2xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger"><ShieldAlert className="size-5 shrink-0" /><span>{task.failure_reason}</span></div> : null}
      {task.result ? <Card><CardHeader><p className="section-kicker">Result</p><h3 className="mt-1 font-display text-xl font-semibold">研究结果</h3></CardHeader><CardContent><p className="whitespace-pre-wrap text-sm leading-7">{typeof task.result.summary === "string" ? task.result.summary : "暂无摘要"}</p><div className="mt-4 flex gap-2 text-xs text-muted"><span>{task.findings.length} 条结论</span><span>·</span><span>{Number(task.result.evidence_count ?? 0)} 条证据引用</span></div></CardContent></Card> : null}

      <div className="grid gap-5 lg:grid-cols-2"><FindingsCard task={task} /><ActionsCard taskId={task.id} actions={task.actions} busy={busy} onDecide={(actionId, decision) => decide.mutate({ taskId: task.id, actionId, decision })} /></div>
      <TraceCard trace={task.trace} />
      <Card><CardHeader><p className="section-kicker">Plan & context</p><h3 className="mt-1 font-display text-xl font-semibold">执行上下文</h3></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2"><pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(task.plan, null, 2)}</pre><pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(task.context, null, 2)}</pre></CardContent></Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 break-words text-sm font-semibold">{value}</p></div>; }

function FindingsCard({ task }: { task: ResearchTaskDetail }) {
  return <Card><CardHeader><div className="flex items-center justify-between"><div><p className="section-kicker">Evidence</p><h3 className="mt-1 font-display text-xl font-semibold">结论与证据</h3></div><FileSearch className="size-5 text-signal" /></div></CardHeader><CardContent className="space-y-4">{task.findings.length === 0 ? <p className="text-sm text-muted">尚无证据绑定结论。</p> : task.findings.map((finding) => <article key={finding.id} className="rounded-xl border border-line p-4"><div className="flex items-center gap-2"><Badge variant={finding.kind === "fact" ? "info" : "warning"}>{finding.kind === "fact" ? "事实" : "推测"}</Badge><span className="text-xs text-muted">第 {finding.round_number} 轮</span></div><p className="mt-3 text-sm leading-6">{finding.statement}</p>{finding.derivation ? <p className="mt-2 text-xs leading-5 text-muted">推导：{finding.derivation}</p> : null}<div className="mt-3 space-y-2">{finding.evidence.map((evidence) => <Link key={evidence.content_id} to={`/library/contents/${encodeURIComponent(evidence.content_id)}`} className="block rounded-lg bg-paper px-3 py-2 text-xs hover:bg-signal/7"><span className="font-semibold">{evidence.title ?? evidence.content_id}</span><span className="mt-1 block text-muted">{evidence.platform ?? "未知平台"} · {evidence.author_name ?? "未知作者"} · 采集 {evidence.collected_at ?? "未知"}</span></Link>)}</div></article>)}</CardContent></Card>;
}

function ActionsCard({ actions, busy, onDecide }: { taskId: string; actions: ResearchTaskDetail["actions"]; busy: boolean; onDecide: (actionId: string, decision: "approve" | "reject") => void }) {
  return <Card><CardHeader><p className="section-kicker">Owner approval</p><h3 className="mt-1 font-display text-xl font-semibold">待确认动作</h3></CardHeader><CardContent className="space-y-3">{actions.length === 0 ? <p className="text-sm text-muted">暂无待确认动作。</p> : actions.map((action) => <div key={action.id} className="rounded-xl border border-line p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold">{action.action}</p><p className="mt-1 text-xs leading-5 text-muted">{action.reason}</p></div><Badge variant={action.status === "pending" ? "warning" : action.status === "approved" ? "success" : "neutral"}>{action.status}</Badge></div>{action.status === "pending" ? <div className="mt-3 flex gap-2"><Button size="sm" disabled={busy} onClick={() => onDecide(action.id, "approve")}>批准</Button><Button variant="secondary" size="sm" disabled={busy} onClick={() => onDecide(action.id, "reject")}>拒绝</Button></div> : null}</div>)}</CardContent></Card>;
}

function TraceCard({ trace }: { trace: ResearchTaskDetail["trace"] }) {
  return <Card><CardHeader><p className="section-kicker">Execution trace</p><h3 className="mt-1 font-display text-xl font-semibold">执行轨迹（{trace.length} 步）</h3></CardHeader><CardContent className="space-y-2">{trace.length === 0 ? <p className="text-sm text-muted">暂无轨迹。</p> : trace.map((entry) => <details key={entry.sequence} className="group rounded-xl border border-line"><summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm"><ChevronDown className="size-4 transition group-open:rotate-180" /><span className="font-mono text-xs text-muted">#{entry.sequence}</span><span className="font-semibold">{entry.event}</span><span className="ml-auto text-xs text-muted">{entry.step ?? entry.status ?? ""}</span></summary><div className="grid gap-3 border-t border-line bg-paper/50 p-4 text-xs sm:grid-cols-2"><div><p className="text-muted">原因</p><p className="mt-1">{entry.reason ?? "—"}</p><p className="mt-3 text-muted">模型</p><p className="mt-1">{entry.provider ?? "—"} / {entry.model ?? "—"}</p></div><div><p className="text-muted">Token / 耗时</p><p className="mt-1">{entry.input_tokens ?? "—"} / {entry.output_tokens ?? "—"} · {entry.elapsed_ms ?? "—"} ms</p>{entry.tool_arguments ? <><p className="mt-3 text-muted">实际工具参数</p><pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{JSON.stringify(entry.tool_arguments, null, 2)}</pre></> : null}</div></div></details>)}</CardContent></Card>;
}

function EmptyDetail() { return <Card className="grid min-h-80 place-items-center"><div className="text-center"><FileSearch className="mx-auto size-8 text-muted" /><p className="mt-3 text-sm text-muted">选择一个任务查看真实执行状态与证据。</p></div></Card>; }

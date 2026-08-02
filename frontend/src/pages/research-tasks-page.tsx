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
import DOMPurify from "dompurify";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";

import type { CrawlerPlatformCapability } from "../api/crawler";
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
import { useCrawlerCapabilitiesQuery } from "../features/crawler/hooks/use-crawler-queries";
import { modeCapabilityStatusLabel } from "../features/crawler/lib/task";
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

const defaultBudget: ResearchTaskInput["budget"] = {
    crawl_limit: 6,
    content_limit: 100,
    duration_seconds: 3_600,
    token_limit: 50_000,
    cost_limit: null,
    cost_currency: null,
};

function createInitialForm(platforms: string[]): ResearchTaskInput {
  return {
    objective: "",
    platforms,
    budget: { ...defaultBudget },
    coverage: {
      target_platform_count: Math.min(3, platforms.length || 3),
      target_entity_count: 3,
      target_negative_evidence_count: 1,
      max_single_entity_evidence_ratio: 0.6,
      target_independent_evidence_count: 5,
      target_new_content_count: 5,
    },
  };
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`;
}

function formatCost(cost: string | null, currency: string | null): string {
  return cost === null ? "未配置" : `${cost} ${currency ?? ""}`.trim();
}

function searchMode(capability: CrawlerPlatformCapability) {
  return capability.modes.find((mode) => mode.mode === "search");
}

const SAFE_RESEARCH_HTML_TAGS = [
  "a",
  "blockquote",
  "br",
  "code",
  "del",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "hr",
  "li",
  "ol",
  "p",
  "pre",
  "strong",
  "table",
  "tbody",
  "td",
  "th",
  "thead",
  "tr",
  "ul",
];

const SAFE_RESEARCH_HTML_ATTRIBUTES = ["href", "title"];

function sanitizeResearchHtml(value: string): string {
  return DOMPurify.sanitize(value, {
    ALLOWED_TAGS: SAFE_RESEARCH_HTML_TAGS,
    ALLOWED_ATTR: SAFE_RESEARCH_HTML_ATTRIBUTES,
    ALLOWED_URI_REGEXP: /^(?:https?:\/\/|#)/i,
  });
}

function resultString(result: ResearchTaskDetail["result"], key: string): string | null {
  const value = result?.[key];
  return typeof value === "string" ? value : null;
}

export function ResearchTasksPage() {
  const tasks = useResearchTasksQuery();
  const capabilities = useCrawlerCapabilitiesQuery();
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
        eyebrow="AI Runtime · Phase 8C"
        title="AI 研究任务"
        description="围绕一个目标创建可中断、可恢复、证据可追溯的研究任务。采集、模型调用和每次状态流转都保留在任务轨迹中。"
        action={
          <Button onClick={() => setShowCreate((value) => !value)}>
            <Plus className="size-4" /> 新建研究任务
          </Button>
        }
      />

      {showCreate ? (
        <ResearchCreateForm
          capabilities={capabilities.data?.platforms ?? []}
          capabilitiesPending={capabilities.isPending}
          capabilitiesError={capabilities.error}
          pending={create.isPending}
          error={create.error}
          onSubmit={submit}
          onCancel={() => setShowCreate(false)}
        />
      ) : null}

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
  capabilities,
  capabilitiesPending,
  capabilitiesError,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  capabilities: CrawlerPlatformCapability[];
  capabilitiesPending: boolean;
  capabilitiesError: unknown;
  pending: boolean;
  error: unknown;
  onSubmit: (input: ResearchTaskInput) => void;
  onCancel: () => void;
}) {
  const selectablePlatforms = useMemo(
    () => capabilities.filter((capability) => searchMode(capability)?.enabled),
    [capabilities],
  );
  const [form, setForm] = useState<ResearchTaskInput>(() => createInitialForm([]));
  const initializedPlatforms = useRef(false);

  useEffect(() => {
    if (initializedPlatforms.current || selectablePlatforms.length === 0) return;
    initializedPlatforms.current = true;
    setForm((current) => ({
      ...current,
      platforms: selectablePlatforms.map((capability) => capability.platform),
    }));
  }, [selectablePlatforms]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.platforms.length === 0 || capabilitiesPending || capabilitiesError) return;
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
          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold">研究平台范围</legend>
            <p className="text-xs leading-5 text-muted">
              展示全部已注册平台；只有搜索模式已启用的平台可以执行研究采集。
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {capabilities.map((capability) => {
                const mode = searchMode(capability);
                const selectable = mode?.enabled === true;
                return (
                  <label
                    key={capability.platform}
                    className={`rounded-xl border p-3 text-sm ${selectable ? "border-line" : "border-line/60 bg-paper/60 text-muted"}`}
                  >
                    <span className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        className="mt-0.5 size-4 accent-signal"
                        checked={form.platforms.includes(capability.platform)}
                        disabled={!selectable || pending || capabilitiesPending}
                        onChange={(event) => {
                          const checked = event.currentTarget.checked;
                          setForm((current) => ({
                            ...current,
                            platforms: checked
                              ? [...current.platforms, capability.platform]
                              : current.platforms.filter((item) => item !== capability.platform),
                          }));
                        }}
                      />
                      <span className="min-w-0">
                        <span className="block font-semibold">
                          {capability.display_name} <span className="font-mono text-xs text-muted">{capability.platform}</span>
                        </span>
                        <span className="mt-1 block text-xs leading-5 text-muted">
                          {mode ? modeCapabilityStatusLabel(mode) : "（没有搜索模式）"}
                          {mode?.reason ? ` · ${mode.reason}` : null}
                        </span>
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
            {capabilitiesPending ? <p className="text-xs text-muted">正在加载平台能力…</p> : null}
            {capabilitiesError ? <p className="text-sm text-danger" role="alert">平台能力加载失败，无法创建研究任务。</p> : null}
            {!capabilitiesPending && !capabilitiesError && capabilities.length === 0 ? <p className="text-sm text-danger" role="alert">没有可用的平台能力。</p> : null}
            {!capabilitiesPending && !capabilitiesError && capabilities.length > 0 && form.platforms.length === 0 ? <p className="text-sm text-danger" role="alert">至少选择一个已启用搜索模式的平台。</p> : null}
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-semibold">金额上限（可选）<Input className="mt-2" value={form.budget.cost_limit ?? ""} onChange={(event) => setBudget("cost_limit", event.currentTarget.value)} placeholder="价格未配置时不会生效" /></label>
            <label className="text-sm font-semibold">币种（可选）<Input className="mt-2" value={form.budget.cost_currency ?? ""} onChange={(event) => setBudget("cost_currency", event.currentTarget.value)} placeholder="例如 USD" /></label>
          </div>
          <p className="text-xs leading-5 text-muted">每轮会先查已有资料；跨平台采集仍由单 Worker 串行执行。</p>
          {error ? <p className="text-sm text-danger">{errorMessage(error)}</p> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>取消</Button>
            <Button disabled={pending || capabilitiesPending || Boolean(capabilitiesError) || form.platforms.length === 0 || form.objective.trim().length < 5}><Send className="size-4" />{pending ? "创建中…" : "创建并开始"}</Button>
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
      {task.result ? <ResearchResultCard task={task} /> : null}
      <QueryTrajectoryCard queries={task.queries ?? []} />
      <CoverageCard task={task} />
      <EvidencePoolCard task={task} />
      <BudgetTraceCard task={task} />

      <div className="grid gap-5 lg:grid-cols-2"><FindingsCard task={task} /><ActionsCard taskId={task.id} actions={task.actions} busy={busy} onDecide={(actionId, decision) => decide.mutate({ taskId: task.id, actionId, decision })} /></div>
      <TraceCard trace={task.trace} />
      <Card><CardHeader><p className="section-kicker">Plan & context</p><h3 className="mt-1 font-display text-xl font-semibold">执行上下文</h3></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2"><pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(task.plan, null, 2)}</pre><pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(task.context, null, 2)}</pre></CardContent></Card>
    </div>
  );
}

function CoverageCard({ task }: { task: ResearchTaskDetail }) {
  const coverage = task.coverage;
  const platforms = task.platform_coverage ?? [];
  const entities = task.entity_coverage ?? [];
  const targetPlatforms = coverage?.target_platform_count ?? task.platforms.length;
  const targetEntities = coverage?.target_entity_count ?? 3;
  const targetNegative = coverage?.target_negative_evidence_count ?? 1;
  const targetIndependent = coverage?.target_independent_evidence_count ?? 5;
  const targetNew = coverage?.target_new_content_count ?? 5;
  const actualPlatforms = platforms.filter((item) => item.status === "completed" && item.result_count > 0).length;
  const negativeEvidence = task.result?.negative_evidence_count ?? platforms.reduce((sum, item) => sum + item.negative_evidence_count, 0);
  const independentEvidence = task.result?.independent_evidence_count ?? 0;
  const newContent = task.result?.new_content_count ?? 0;
  const target = (actual: number, expected: number) => `${actual} / ${expected} ${actual >= expected ? "✓" : "·"}`;
  return (
    <Card>
      <CardHeader>
        <p className="section-kicker">Coverage plan</p>
        <h3 className="mt-1 font-display text-xl font-semibold">平台计划与实体覆盖</h3>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 grid-cols-2 sm:grid-cols-5">
          <Metric label="平台" value={target(actualPlatforms, targetPlatforms)} />
          <Metric label="实体" value={target(entities.length, targetEntities)} />
          <Metric label="反向证据" value={target(negativeEvidence, targetNegative)} />
          <Metric label="独立来源" value={target(independentEvidence, targetIndependent)} />
          <Metric label="新增内容" value={target(newContent, targetNew)} />
        </div>
        <div className="space-y-2">
          {platforms.length === 0 ? <p className="text-sm text-muted">尚无平台回归记录。</p> : platforms.map((platform) => (
            <div key={platform.id ?? platform.platform} className="rounded-xl border border-line p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{platform.platform}</span>
                <Badge variant={platform.status === "completed" ? "success" : platform.status === "failed" ? "danger" : "warning"}>{platform.status}</Badge>
              </div>
              <p className="mt-2 text-muted">查询 {platform.actual_query_count} · 结果 {platform.result_count} · 新增 {platform.new_content_count} · 独立证据 {platform.independent_evidence_count}</p>
              {platform.failure_reason ? <p className="mt-1 text-danger">失败原因：{platform.failure_reason}</p> : null}
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">已发现实体</p>
          {entities.length === 0 ? <p className="text-sm text-muted">尚未发现明确实体。</p> : entities.map((entity) => (
            <div key={`${entity.entity_type}-${entity.canonical_name}`} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-paper p-3 text-xs">
              <span className="min-w-0 break-words font-semibold">{entity.canonical_name} <span className="font-normal text-muted">· {entity.entity_type}</span></span>
              <span className="text-muted">证据 {entity.entity_evidence_count} · 平台 {entity.entity_platform_count} · 占比 {(entity.entity_coverage_ratio * 100).toFixed(0)}%{entity.saturated ? " · 饱和" : ""}</span>
            </div>
          ))}
        </div>
        <p className="text-xs leading-5 text-muted">停止原因：{task.stop_reason ?? coverage?.stop_reason ?? "尚未停止"} · 单一实体上限 {(coverage?.max_single_entity_evidence_ratio ?? 0.6) * 100}%</p>
      </CardContent>
    </Card>
  );
}

function EvidencePoolCard({ task }: { task: ResearchTaskDetail }) {
  const decisions = task.content_decisions ?? [];
  const adopted = decisions.filter((item) => item.decision === "adopted");
  const notAdopted = decisions.filter((item) => item.decision === "not_adopted");
  const reposts = decisions.filter((item) => item.is_repost);
  return (
    <Card>
      <CardHeader>
        <p className="section-kicker">Evidence pool</p>
        <h3 className="mt-1 font-display text-xl font-semibold">证据池与未采用内容</h3>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="采集结果" value={String(decisions.length)} />
          <Metric label="最终采用" value={String(adopted.length)} />
          <Metric label="未采用" value={String(notAdopted.length)} />
          <Metric label="转载标记" value={String(reposts.length)} />
        </div>
        {decisions.length === 0 ? <p className="text-sm text-muted">暂无内容决策记录。</p> : (
          <div className="space-y-2">
            {decisions.map((item) => (
              <div key={item.content_id} className="rounded-xl border border-line p-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link to={`/library/contents/${encodeURIComponent(item.content_id)}`} className="font-semibold hover:text-signal">{item.content_id}</Link>
                  <span className="text-muted">{item.decision}{item.is_repost ? " · 转载" : ""}</span>
                </div>
                <p className="mt-1 text-muted">来源独立性：{item.source_independence} · 完整度：{item.content_completeness} · 质量：{item.evidence_quality}</p>
                {item.not_adopted_reason ? <p className="mt-1 text-danger">未采用原因：{item.not_adopted_reason}</p> : null}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BudgetTraceCard({ task }: { task: ResearchTaskDetail }) {
  const usage = task.step_usage ?? [];
  const consumption = task.consumption;
  const modeLabel: Record<string, string> = {
    subscription_fixed: "年度套餐",
    pay_as_you_go: "按量",
    relay: "中转",
    prepaid_balance: "预付余额",
    quota_bundle: "额度包",
    unknown: "未知价格",
  };
  return (
    <Card>
      <CardHeader>
        <p className="section-kicker">Resource budget</p>
        <h3 className="mt-1 font-display text-xl font-semibold">预算分类与模型轨迹</h3>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="总 Token" value={`${(consumption.input_tokens + consumption.output_tokens).toLocaleString()} / ${task.budget.token_limit.toLocaleString()}`} />
          <Metric label="模型调用" value={`${consumption.model_call_count ?? usage.length} / ${task.budget.max_model_calls ?? "—"}`} />
          <Metric label="采集任务" value={`${consumption.crawl_count} / ${task.budget.crawl_limit}`} />
          <Metric label="按量金额" value={formatCost(consumption.estimated_cost, consumption.cost_currency)} />
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl bg-paper p-3 text-xs"><p className="font-semibold">MiniMax / GLM 套餐</p><p className="mt-1 text-muted">{(consumption.subscription_calls ?? 0).toLocaleString()} 次 · {(consumption.subscription_tokens ?? 0).toLocaleString()} Token · 单次金额不适用</p></div>
          <div className="rounded-xl bg-paper p-3 text-xs"><p className="font-semibold">DeepSeek / 按量</p><p className="mt-1 text-muted">{(consumption.payg_calls ?? 0).toLocaleString()} 次 · {(consumption.payg_tokens ?? 0).toLocaleString()} Token · {formatCost(consumption.estimated_cost, consumption.cost_currency)}</p></div>
          <div className="rounded-xl bg-paper p-3 text-xs"><p className="font-semibold">中转 / 未知</p><p className="mt-1 text-muted">{(consumption.relay_calls ?? 0).toLocaleString()} 次中转 · {(consumption.uncosted_call_count ?? 0).toLocaleString()} 次不可计算</p></div>
        </div>
        {usage.length === 0 ? <p className="text-sm text-muted">尚无步骤级模型用量。</p> : <div className="space-y-2">{usage.map((item) => <div key={`${item.sequence}-${item.step}`} className="rounded-xl border border-line p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">#{item.sequence} · {item.step}</span><span className="text-muted">{item.vendor ?? "未知厂商"} / {item.model ?? "未知模型"}</span></div><p className="mt-1 text-muted">{modeLabel[item.billing_mode ?? "unknown"]} · 输入 {item.input_tokens ?? 0} · 输出 {item.output_tokens ?? 0} · {item.latency_ms ?? "—"} ms · 费用 {item.estimated_cost === null || item.estimated_cost === undefined ? "不适用/不可计算" : `${item.estimated_cost} ${item.currency ?? ""}`.trim()}{item.fallback_reason ? ` · Fallback：${item.fallback_reason}` : ""}</p></div>)}</div>}
        <p className="text-xs leading-5 text-muted">Context Compactor：{typeof task.context.compaction_stats === "object" && task.context.compaction_stats !== null ? JSON.stringify(task.context.compaction_stats) : "尚未运行"}</p>
      </CardContent>
    </Card>
  );
}

function ResearchResultCard({ task }: { task: ResearchTaskDetail }) {
  const [showMarkdown, setShowMarkdown] = useState(false);
  const summaryMarkdown = resultString(task.result, "summary_markdown") ?? resultString(task.result, "summary");
  const summaryHtml = resultString(task.result, "summary_html");
  const safeHtml = summaryHtml ? sanitizeResearchHtml(summaryHtml) : null;
  const evidenceCount = task.result?.evidence_count;
  const qualityCounts = [
    ["新增", task.result?.new_content_count],
    ["已存在", task.result?.existing_content_count],
    ["已更新", task.result?.updated_content_count],
    ["重复证据", task.result?.duplicate_evidence_count],
    ["独立证据", task.result?.independent_evidence_count ?? evidenceCount],
    ["发现次数", task.result?.discovery_count],
  ] as const;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="section-kicker">Result · HTML</p>
            <h3 className="mt-1 font-display text-xl font-semibold">研究结果</h3>
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={() => setShowMarkdown((current) => !current)}>
            {showMarkdown ? "查看渲染结果" : "查看 Markdown"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {showMarkdown ? (
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-4 text-sm leading-7 text-slate-100">
            {summaryMarkdown ?? "暂无摘要"}
          </pre>
        ) : safeHtml ? (
          <div
            className="research-result space-y-3 text-sm leading-7 [&_a]:text-signal [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-line [&_blockquote]:pl-4 [&_code]:rounded [&_code]:bg-paper [&_code]:px-1 [&_h1]:font-display [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:font-display [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:font-display [&_h3]:text-lg [&_h3]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_pre]:overflow-auto [&_pre]:rounded-xl [&_pre]:bg-slate-950 [&_pre]:p-4 [&_pre]:text-slate-100 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-line [&_td]:p-2 [&_th]:border [&_th]:border-line [&_th]:bg-paper [&_th]:p-2"
            // The API sanitizes this model-controlled HTML; DOMPurify is a second browser-boundary check.
            dangerouslySetInnerHTML={{ __html: safeHtml }}
          />
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-7">{summaryMarkdown ?? "暂无摘要"}</p>
        )}
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {qualityCounts.map(([label, value]) => <Metric key={label} label={label} value={typeof value === "number" ? value.toLocaleString() : "—"} />)}
          <div className="col-span-2 text-xs text-muted sm:col-span-3 lg:col-span-6">{task.findings.length} 条结论 · 独立证据按标准化 content_id 合并，发现次数单独累计。</div>
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 break-words text-sm font-semibold">{value}</p></div>; }

function QueryTrajectoryCard({ queries }: { queries: NonNullable<ResearchTaskDetail["queries"]> }) {
  const lifecycle = (query: (typeof queries)[number]) => query.lifecycle_status ?? query.status;
  const rejected = queries.filter((query) => lifecycle(query).startsWith("rejected"));
  const executed = queries.filter((query) => !lifecycle(query).startsWith("rejected"));
  const sourceLabel = (query: (typeof queries)[number]) => {
    if (query.parent_query_id) {
      const parent = queries.find((candidate) => candidate.id === query.parent_query_id);
      return parent ? `父查询：${parent.query}` : `父查询：${query.parent_query_id}`;
    }
    if (query.source_content_id) return `来源内容：${query.source_content_id}`;
    return query.source_type === "user_goal" ? "用户目标" : query.source_type;
  };
  const row = (query: (typeof queries)[number]) => {
    const currentLifecycle = lifecycle(query);
    const isUnexecuted = !query.crawler_task_id && !["completed", "failed", "cancelled"].includes(currentLifecycle);
    return <article key={query.id} className="rounded-xl border border-line p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="break-words text-sm font-semibold">{query.query}</p><p className="mt-1 text-xs text-muted">{query.query_type} · {sourceLabel(query)} · {query.platform}</p></div><Badge variant={currentLifecycle.startsWith("rejected") ? "danger" : currentLifecycle === "completed" ? "success" : currentLifecycle.startsWith("skipped") ? "warning" : "info"}>{currentLifecycle}</Badge></div>
    <p className="mt-2 text-xs leading-5 text-muted">生成理由：{query.generation_reason}</p>
    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5"><Metric label="相关性" value={query.relevance_score === null ? "—" : query.relevance_score.toFixed(2)} /><Metric label="具体性" value={query.specificity_score.toFixed(2)} /><Metric label="新颖性" value={query.novelty_score.toFixed(2)} /><Metric label="新增率" value={query.new_content_rate === null || query.new_content_rate === undefined ? "—" : `${(query.new_content_rate * 100).toFixed(0)}%`} /><Metric label="边际价值" value={query.marginal_value_score === null || query.marginal_value_score === undefined ? "—" : query.marginal_value_score.toFixed(2)} /></div>
    {query.rejection_reason ? <p className="mt-3 rounded-lg bg-danger/5 px-3 py-2 text-xs leading-5 text-danger">拒绝原因：{query.rejection_reason}</p> : null}
    {isUnexecuted && query.unexecuted_reason ? <p className="mt-3 rounded-lg bg-paper px-3 py-2 text-xs leading-5 text-muted">未执行原因：{query.unexecuted_reason}</p> : null}
    <p className="mt-3 text-xs text-muted">结果 {query.result_count} · 新增 {query.new_content_count} · 已存在 {query.existing_content_count} · 已更新 {query.updated_content_count} · 重复证据 {query.duplicate_evidence_count}</p>
  </article>;
  };
  return <Card><CardHeader><p className="section-kicker">Query quality gate</p><h3 className="mt-1 font-display text-xl font-semibold">查询轨迹与质量闸门</h3></CardHeader><CardContent className="space-y-4">{queries.length === 0 ? <p className="text-sm text-muted">暂无查询轨迹（历史任务兼容）。</p> : <><div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted">已执行 / 通过</p><div className="space-y-2">{executed.map(row)}</div></div>{rejected.length > 0 ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-danger">已拒绝（全部保留）</p><div className="space-y-2">{rejected.map(row)}</div></div> : null}</>}</CardContent></Card>;
}

function FindingsCard({ task }: { task: ResearchTaskDetail }) {
  const supportLabel = (value: string | undefined) => ({ direct: "直接支持", contextual: "上下文", contradictory: "反证", background: "背景" }[value ?? "background"] ?? "背景");
  const strengthLabel = (value: string | undefined) => ({ strong: "强", medium: "中", weak: "弱" }[value ?? "weak"] ?? "弱");
  return <Card><CardHeader><div className="flex items-center justify-between"><div><p className="section-kicker">Evidence</p><h3 className="mt-1 font-display text-xl font-semibold">结论与证据</h3></div><FileSearch className="size-5 text-signal" /></div></CardHeader><CardContent className="space-y-4">{task.findings.length === 0 ? <p className="text-sm text-muted">尚无证据绑定结论。</p> : task.findings.map((finding) => <article key={finding.id} className="rounded-xl border border-line p-4"><div className="flex flex-wrap items-center gap-2"><Badge variant={finding.kind === "fact" ? "info" : "warning"}>{finding.kind === "fact" ? "事实" : "推测 / inference"}</Badge><span className="text-xs text-muted">第 {finding.round_number} 轮</span></div><p className="mt-3 text-sm leading-6">{finding.statement}</p>{finding.derivation ? <p className="mt-2 text-xs leading-5 text-muted">推导：{finding.derivation}</p> : null}{finding.kind === "inference" ? <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-xs leading-5 text-muted">反证：{finding.counterevidence_explanation ?? "历史任务未记录反证状态。"}</p> : null}<div className="mt-3 space-y-2">{finding.evidence.map((evidence) => <details key={evidence.content_id} className="rounded-lg bg-paper px-3 py-2 text-xs"><summary className="cursor-pointer list-none"><Link to={`/library/contents/${encodeURIComponent(evidence.content_id)}`} className="font-semibold hover:text-signal">{evidence.title ?? evidence.content_id}</Link><span className="ml-2 inline-flex gap-1"><Badge variant={evidence.support_type === "contradictory" ? "danger" : evidence.support_type === "direct" ? "info" : "neutral"}>{supportLabel(evidence.support_type)} · {strengthLabel(evidence.support_strength)}</Badge></span></summary><p className="mt-2 leading-5 text-muted">支持说明：{evidence.support_explanation ?? "历史任务未记录支持说明。"}</p><p className="mt-1 text-muted">{evidence.platform ?? "未知平台"} · {evidence.author_name ?? "未知作者"} · 采集 {evidence.collected_at ?? "未知"}</p>{evidence.occurrences && evidence.occurrences.length > 0 ? <div className="mt-2 space-y-1 text-muted"><p>发现 {evidence.occurrences.reduce((total, occurrence) => total + occurrence.occurrence_count, 0)} 次 · 涉及 {evidence.occurrences.length} 条发现记录</p>{evidence.occurrences.map((occurrence) => <p key={occurrence.id}>查询：{occurrence.source_query_ids?.join("、") || occurrence.research_query_id || "—"} · 采集：{occurrence.source_crawler_task_ids?.join("、") || occurrence.crawler_task_id || "—"}</p>)}</div> : null}</details>)}</div></article>)}</CardContent></Card>;
}

function ActionsCard({ actions, busy, onDecide }: { taskId: string; actions: ResearchTaskDetail["actions"]; busy: boolean; onDecide: (actionId: string, decision: "approve" | "reject") => void }) {
  return <Card><CardHeader><p className="section-kicker">Owner approval</p><h3 className="mt-1 font-display text-xl font-semibold">待确认动作</h3></CardHeader><CardContent className="space-y-3">{actions.length === 0 ? <p className="text-sm text-muted">暂无待确认动作。</p> : actions.map((action) => <div key={action.id} className="rounded-xl border border-line p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold">{action.action}</p><p className="mt-1 text-xs leading-5 text-muted">{action.reason}</p></div><Badge variant={action.status === "pending" ? "warning" : action.status === "approved" ? "success" : "neutral"}>{action.status}</Badge></div>{action.status === "pending" ? <div className="mt-3 flex gap-2"><Button size="sm" disabled={busy} onClick={() => onDecide(action.id, "approve")}>批准</Button><Button variant="secondary" size="sm" disabled={busy} onClick={() => onDecide(action.id, "reject")}>拒绝</Button></div> : null}</div>)}</CardContent></Card>;
}

function TraceCard({ trace }: { trace: ResearchTaskDetail["trace"] }) {
  return <Card><CardHeader><p className="section-kicker">Execution trace</p><h3 className="mt-1 font-display text-xl font-semibold">执行轨迹（{trace.length} 步）</h3></CardHeader><CardContent className="space-y-2">{trace.length === 0 ? <p className="text-sm text-muted">暂无轨迹。</p> : trace.map((entry) => <details key={entry.sequence} className="group rounded-xl border border-line"><summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm"><ChevronDown className="size-4 transition group-open:rotate-180" /><span className="font-mono text-xs text-muted">#{entry.sequence}</span><span className="font-semibold">{entry.event}</span><span className="ml-auto text-xs text-muted">{entry.step ?? entry.status ?? ""}</span></summary><div className="grid gap-3 border-t border-line bg-paper/50 p-4 text-xs sm:grid-cols-2"><div><p className="text-muted">原因</p><p className="mt-1">{entry.reason ?? "—"}</p><p className="mt-3 text-muted">模型</p><p className="mt-1">{entry.provider ?? "—"} / {entry.model ?? "—"}</p></div><div><p className="text-muted">Token / 耗时</p><p className="mt-1">{entry.input_tokens ?? "—"} / {entry.output_tokens ?? "—"} · {entry.elapsed_ms ?? "—"} ms</p>{entry.tool_arguments ? <><p className="mt-3 text-muted">实际工具参数</p><pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{JSON.stringify(entry.tool_arguments, null, 2)}</pre></> : null}</div></div></details>)}</CardContent></Card>;
}

function EmptyDetail() { return <Card className="grid min-h-80 place-items-center"><div className="text-center"><FileSearch className="mx-auto size-8 text-muted" /><p className="mt-3 text-sm text-muted">选择一个任务查看真实执行状态与证据。</p></div></Card>; }

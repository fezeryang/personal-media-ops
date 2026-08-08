import {
  ArrowRight,
  Check,
  ChevronDown,
  CirclePause,
  CirclePlay,
  FileSearch,
  Plus,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  Square,
} from "lucide-react";
import DOMPurify from "dompurify";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";

import type { CrawlerPlatformCapability } from "../api/crawler";
import type { OpportunitySummary } from "../api/opportunity";
import type {
  DiscoveryInboxItem,
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
import { useOpportunitiesQuery } from "../features/opportunity/hooks/use-opportunity-queries";
import {
  useCancelResearchTaskMutation,
  useCompleteResearchTaskMutation,
  useCreateResearchTaskMutation,
  useDecideResearchActionMutation,
  usePauseResearchTaskMutation,
  useResearchTaskQuery,
  useResearchTasksQuery,
  useRerunResearchTaskMutation,
  useReviseResearchIntentMutation,
  useResumeResearchTaskMutation,
} from "../features/research/hooks/use-research-queries";
import { useDiscoveriesQuery } from "../features/research/hooks/use-discovery-queries";
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

const researchStepLabels: Record<string, string> = {
  awaiting_review: "等待确认",
  budget_review: "预算检查",
  coverage_review: "覆盖度检查",
  discovery: "发现候选",
  evidence_selection: "整理证据",
  final_report: "生成报告",
  intent_interpretation: "理解研究目标",
  plan_generation: "制定研究计划",
  search_library: "检索已有资料",
  tool_call: "调用研究工具",
};

const queryTypeLabels: Record<string, string> = {
  comparison: "对比方向",
  generic_topic: "泛化主题",
  product: "产品方向",
  scenario: "使用场景",
  topic: "主题方向",
};

const querySourceLabels: Record<string, string> = {
  finding: "来自结论",
  user_goal: "来自用户目标",
  model: "来自研究规划",
};

const queryDecisionLabels: Record<string, string> = {
  allow: "允许执行",
  hold: "等待判断",
  reject: "拒绝执行",
  transform: "已转换",
};

const queryGateLabels: Record<string, string> = {
  not_applicable: "不适用",
  passed: "通过闸门",
  rejected: "未通过闸门",
};

const discoveryTypeLabels: Record<string, string> = {
  entity: "实体",
  creator: "创作者",
  topic: "主题",
  event: "事件",
  query: "查询方向",
  pain_point: "痛点",
  need: "需求",
  product_opportunity_signal: "产品机会",
  content_opportunity_signal: "内容机会",
};

const discoveryStateLabels: Record<string, string> = {
  generated: "已生成",
  scored: "已评分",
  queued: "待处理",
  accepted: "已采纳",
  ignored: "已忽略",
  deferred: "已延后",
  converted_to_research: "已转为研究",
  added_to_space: "已加入空间",
  dismissed_duplicate: "已标记重复",
  expired: "已过期",
};

const entityTypeLabels: Record<string, string> = {
  product: "产品",
  creator: "创作者",
  topic: "主题",
  company: "公司",
  person: "人物",
  event: "事件",
  technology: "技术",
};

const entityCandidateStatusLabels: Record<string, string> = {
  candidate_discovery: "待验证",
  accepted: "已采纳",
  dismissed: "已忽略",
};

const eventTypeLabels: Record<string, string> = {
  new_version: "版本更新",
  launch: "发布",
  funding: "融资",
  policy_change: "政策变化",
  trend_shift: "趋势变化",
};

const eventStatusLabels: Record<string, string> = {
  candidate: "待确认",
  accepted: "已确认",
  dismissed: "已忽略",
};

const memoryTypeLabels: Record<string, string> = {
  fact: "事实",
  inference: "推测",
  entity: "实体",
  change: "变化",
};

const actionStatusLabels: Record<string, string> = {
  pending: "待确认",
  approved: "已批准",
  rejected: "已拒绝",
};

function researchStepLabel(value: string | null | undefined): string {
  if (!value) return "等待调度";
  return researchStepLabels[value] ?? "研究进行中";
}

const traceEventLabels: Record<string, string> = {
  task_created: "创建任务",
  intent_interpreted: "理解意图",
  plan_generated: "制定计划",
  memory_searched: "检索记忆",
  query_generated: "生成查询",
  crawler_task_created: "平台采集",
  content_evaluated: "评估信息",
  evidence_organized: "组织证据",
  alignment_reviewed: "对齐检查",
  tool_call: "调用研究工具",
};

function traceEventLabel(value: string): string {
  return traceEventLabels[value] ?? "研究步骤";
}

function queryLifecycleLabel(value: string | null | undefined): string {
  if (!value) return "历史状态";
  if (value === "completed") return "已执行";
  if (value === "running") return "执行中";
  if (value === "pending") return "等待执行";
  if (value === "rejected") return "已拒绝";
  if (value === "skipped_low_marginal_value") return "因边际价值低跳过";
  if (value === "skipped_budget") return "因预算跳过";
  if (value === "skipped_duplicate") return "因重复跳过";
  if (value.startsWith("rejected")) return "已拒绝";
  if (value.startsWith("skipped")) return "因质量闸门跳过";
  return "已记录";
}

function queryTypeLabel(value: string): string {
  return queryTypeLabels[value] ?? "研究方向";
}

function querySourceLabel(value: string): string {
  return querySourceLabels[value] ?? "研究来源";
}

function queryDecisionLabel(value: string | null | undefined): string {
  return value ? queryDecisionLabels[value] ?? "已记录" : "历史记录";
}

function queryGateLabel(value: string | null | undefined): string {
  return value ? queryGateLabels[value] ?? "已检查" : "历史记录";
}

function discoveryTypeLabel(value: string): string {
  return discoveryTypeLabels[value] ?? "发现项";
}

function discoveryStateLabel(value: string): string {
  return discoveryStateLabels[value] ?? "已记录";
}

function entityTypeLabel(value: string): string {
  return entityTypeLabels[value] ?? "实体";
}

function entityCandidateStatusLabel(value: string): string {
  return entityCandidateStatusLabels[value] ?? "已记录";
}

function eventTypeLabel(value: string): string {
  return eventTypeLabels[value] ?? "事件信号";
}

function eventStatusLabel(value: string): string {
  return eventStatusLabels[value] ?? "已记录";
}

function memoryTypeLabel(value: string): string {
  return memoryTypeLabels[value] ?? "研究记忆";
}

function actionStatusLabel(value: string): string {
  return actionStatusLabels[value] ?? "已记录";
}

function platformCoverageLabel(value: string): string {
  return {
    completed: "已完成",
    failed: "失败",
    pending: "等待执行",
    running: "执行中",
  }[value] ?? "已记录";
}

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

function crawlerTaskIds(task: ResearchTaskDetail): string[] {
  return Array.from(
    new Set(
      (task.queries ?? [])
        .map((query) => query.crawler_task_id)
        .filter((id): id is string => Boolean(id)),
    ),
  );
}

export function ResearchTasksPage() {
  const tasks = useResearchTasksQuery();
  const discoveries = useDiscoveriesQuery();
  const capabilities = useCrawlerCapabilitiesQuery();
  const opportunities = useOpportunitiesQuery();
  const [selectedId, setSelectedId] = useState("");
  const [showCreate, setShowCreate] = useState(true);
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
        eyebrow="AI Research Workbench · 8D"
        title="AI 研究工作台"
        description="从一个问题开始：AI 先说明它理解了什么，再在预算和来源边界内研究，把证据、发现、反馈和长期记忆连成可继续推进的上下文。"
        action={
          <Button variant="secondary" onClick={() => setShowCreate((value) => !value)}>
            <Plus className="size-4" /> {showCreate ? "收起目标输入" : "开始新的研究"}
          </Button>
        }
      />

      <ResearchFlow />

      <WorkbenchOpportunityPulse opportunities={opportunities.data ?? []} pending={opportunities.isPending} error={opportunities.error} />

      <ResearchHomePulse
        tasks={tasks.data ?? []}
        discoveries={discoveries.data ?? []}
        discoveriesPending={discoveries.isPending}
        discoveriesError={discoveries.error}
        onRetryDiscoveries={() => void discoveries.refetch()}
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

function WorkbenchOpportunityPulse({ opportunities, pending, error }: { opportunities: OpportunitySummary[]; pending: boolean; error: unknown }) {
  const top = opportunities.slice(0, 3);
  return (
    <section aria-label="行动中枢摘要" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="section-kicker">Action Assistant · 8F</p><h2 className="mt-1 font-display text-2xl font-semibold">值得行动的机会</h2><p className="mt-1 text-sm text-muted">从有证据的信号开始，先判断，再验证。</p></div><Button asChild variant="secondary"><Link to="/opportunities">查看全部机会 <ArrowRight className="size-4" /></Link></Button></div>
      {error ? <p className="rounded-xl border border-warning/20 bg-warning/5 p-3 text-sm text-muted">机会摘要暂时不可用；研究流程仍可继续。</p> : pending ? <div className="grid gap-3 md:grid-cols-3">{Array.from({ length: 3 }, (_, index) => <div key={index} className="h-32 animate-pulse rounded-2xl bg-paper" />)}</div> : top.length ? <div className="grid gap-3 md:grid-cols-3">{top.map((opportunity) => <Link key={opportunity.id} to={`/opportunities/${encodeURIComponent(opportunity.id)}`} className="rounded-2xl border border-line bg-white p-4 transition hover:border-signal/35 hover:shadow-sm"><div className="flex items-center justify-between gap-2"><Badge variant="info">{opportunityTypeLabel(opportunity.opportunity_type)}</Badge><span className="text-xs text-muted">{readinessLabel(opportunity.readiness)}</span></div><p className="mt-3 line-clamp-2 text-sm font-semibold">{opportunity.title}</p><p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">{opportunity.next_step}</p></Link>)}</div> : <Card><CardContent className="flex flex-wrap items-center gap-3 p-4 text-sm text-muted"><Sparkles className="size-4 text-signal" />目前还没有足够证据形成机会。先完成研究或处理发现，AI会保留“没有机会”的结果。</CardContent></Card>}
    </section>
  );
}

function opportunityTypeLabel(value: OpportunitySummary["opportunity_type"]): string {
  return { product_opportunity: "产品机会", business_opportunity: "商业机会", content_opportunity: "内容机会", research_opportunity: "研究机会" }[value];
}

function readinessLabel(value: OpportunitySummary["readiness"]): string {
  return { insufficient_evidence: "证据不足", needs_more_evidence: "需更多证据", review_ready: "待判断", validation_ready: "可验证", validated: "已验证" }[value];
}

function ResearchHomePulse({
  tasks,
  discoveries,
  discoveriesPending,
  discoveriesError,
  onRetryDiscoveries,
}: {
  tasks: ResearchTaskSummary[];
  discoveries: DiscoveryInboxItem[];
  discoveriesPending: boolean;
  discoveriesError: unknown;
  onRetryDiscoveries: () => void;
}) {
  const recentTasks = tasks.slice(0, 3);
  const reviewTasks = tasks.filter(
    (task) => task.status === "AwaitingReview" || task.action_count > 0,
  ).slice(0, 3);
  const pendingDiscoveries = discoveries.slice(0, 3);
  return (
    <section className="grid gap-4 lg:grid-cols-3" aria-label="研究首页摘要">
      <Card>
        <CardHeader>
          <p className="section-kicker">Recent research</p>
          <h2 className="mt-1 font-display text-xl font-semibold">最近研究</h2>
        </CardHeader>
        <CardContent className="space-y-2">
          {recentTasks.length === 0 ? <p className="text-sm text-muted">暂无最近研究</p> : recentTasks.map((task) => (
            <div key={task.id} className="rounded-xl bg-paper p-3">
              <p className="line-clamp-2 text-sm font-semibold">{task.objective}</p>
              <p className="mt-1 text-xs text-muted">{statusLabels[task.status]} · {researchStepLabel(task.current_step)}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="section-kicker">Discovery inbox</p>
          <h2 className="mt-1 font-display text-xl font-semibold">待处理发现</h2>
        </CardHeader>
        <CardContent className="space-y-2">
          {discoveriesError ? <ErrorState title="待处理发现加载失败" error={discoveriesError} onRetry={onRetryDiscoveries} /> : discoveriesPending ? <p className="text-sm text-muted">正在加载待处理发现…</p> : pendingDiscoveries.length === 0 ? <p className="text-sm text-muted">暂无待处理发现</p> : pendingDiscoveries.map((candidate) => (
            <Link key={candidate.id} to={candidate.source_type === "monitoring" && candidate.mission_id ? `/monitoring/${encodeURIComponent(candidate.mission_id)}` : `/discoveries/${encodeURIComponent(candidate.id)}`} className="block rounded-xl bg-paper p-3 hover:bg-signal/5">
              <p className="line-clamp-2 text-sm font-semibold">{candidate.title}</p>
              <p className="mt-1 text-xs text-muted">{candidate.source_type === "monitoring" ? "监控变化" : discoveryTypeLabel(candidate.candidate_type)} · {Math.round(candidate.final_score * 100)} 分</p>
            </Link>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="section-kicker">Owner decisions</p>
          <h2 className="mt-1 font-display text-xl font-semibold">需要用户确认</h2>
        </CardHeader>
        <CardContent className="space-y-2">
          {reviewTasks.length === 0 ? <p className="text-sm text-muted">暂无待确认事项</p> : reviewTasks.map((task) => (
            <div key={task.id} className="rounded-xl border border-warning/20 bg-warning/5 p-3">
              <p className="line-clamp-2 text-sm font-semibold">{task.objective}</p>
              <p className="mt-1 text-xs text-muted">{task.action_count > 0 ? `${task.action_count} 项动作待确认` : "研究结果待确认"}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}

function ResearchFlow() {
  const stages = [
    ["01", "研究目标", "用自然语言表达你真正想知道什么"],
    ["02", "研究理解", "检查 AI 的假设、未知项和成功标准"],
    ["03", "有边界地研究", "按来源、预算和边际价值推进"],
    ["04", "发现与记忆", "把证据变成候选、反馈和长期上下文"],
  ];
  return <section className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" aria-label="AI 研究流程">{stages.map(([number, title, description]) => <Card key={number} className="p-4"><p className="font-mono text-xs text-signal">{number}</p><p className="mt-3 text-sm font-semibold">{title}</p><p className="mt-1 text-xs leading-5 text-muted">{description}</p></Card>)}</section>;
}

function previewIntent(objective: string): {
  primary: string;
  secondary: string[];
  unknowns: string[];
  timeScope: string;
  evidence: string[];
  counterevidence: string[];
  exclusions: string[];
  output: string;
} {
  const normalized = objective.toLowerCase();
  if (normalized.includes("痛点") || normalized.includes("问题") || normalized.includes("抱怨")) {
    return {
      primary: "痛点研究",
      secondary: ["来源独立性与转载识别", "可复现性与替代方案"],
      unknowns: ["哪些负向体验来自直接用户证据", "问题是否跨平台、跨作者重复出现"],
      timeScope: "未指定；按可用时间范围与预算边界检索",
      evidence: ["直接用户负向表达", "不同作者或平台的独立复核"],
      counterevidence: ["官方或正向使用体验", "仅个体问题或疑似转载"],
      exclusions: ["纯营销内容", "无正文、重复或无法复核的记录"],
      output: "直接负向证据、反例、来源独立性与可验证的改进机会",
    };
  }
  if (normalized.includes("机会") || normalized.includes("产品") || normalized.includes("工具")) {
    return {
      primary: "产品机会探索",
      secondary: ["用户需求与使用场景", "跨平台变化验证"],
      unknowns: ["真实需求是否重复出现", "现有工具的限制与替代方案"],
      timeScope: "未指定；优先近期且可比较的使用记录",
      evidence: ["真实使用场景", "跨作者或平台的独立来源"],
      counterevidence: ["纯营销陈述", "用户已知或饱和的候选"],
      exclusions: ["无正文内容", "疑似同稿转载和未通过平台门禁的来源"],
      output: "产品/工具候选、需求信号、证据强度和下一步验证建议",
    };
  }
  return {
    primary: "探索发现",
    secondary: ["实体、主题与事件扩展", "证据缺口与反向验证"],
    unknowns: ["哪些实体、主题或事件值得继续验证", "哪些来源具备独立且可复核的证据价值"],
    timeScope: "未指定；按可用时间范围与预算边界检索",
    evidence: ["与目标直接相关的正文", "独立来源和可追溯来源链"],
    counterevidence: ["反向观点、失败记录和未知项"],
    exclusions: ["纯营销、重复、噪音和无正文内容"],
    output: "有限候选、来源链、反向证据和可继续推进的研究方向",
  };
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
  const [reviewing, setReviewing] = useState(false);
  const [supplement, setSupplement] = useState("");
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
    if (!reviewing) {
      setReviewing(true);
      return;
    }
    const objective = form.objective.trim();
    const additionalRequirements = supplement.trim();
    onSubmit({
      ...form,
      objective: additionalRequirements ? `${objective}\n\n补充要求：${additionalRequirements}` : objective,
    });
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
        <p className="section-kicker">Natural language research</p>
        <h2 className="mt-1 font-display text-xl font-semibold">先说你想知道什么</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">不需要先填写产品名、关键词或竞争对象。提交后会先生成研究理解卡，你可以检查 AI 的假设，再观察执行查询和信息价值。</p>
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
          <details className="rounded-2xl border border-line bg-paper/40 p-4">
            <summary className="cursor-pointer text-sm font-semibold">高级边界（可选）</summary>
            <div className="mt-4 space-y-5">
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
            </div>
          </details>
          <p className="text-xs leading-5 text-muted">每轮会先查已有资料；跨平台采集仍由单 Worker 串行执行。</p>
          {reviewing ? <ResearchIntentPreview objective={form.objective} platforms={form.platforms} budget={form.budget} supplement={supplement} onSupplementChange={setSupplement} /> : null}
          {error ? <p className="text-sm text-danger">{errorMessage(error)}</p> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>取消</Button>
            {reviewing ? <Button type="button" variant="secondary" disabled={pending} onClick={() => setReviewing(false)}>修改理解</Button> : null}
            <Button disabled={pending || capabilitiesPending || Boolean(capabilitiesError) || form.platforms.length === 0 || form.objective.trim().length < 5}><Send className="size-4" />{pending ? "创建中…" : reviewing ? "确认理解并开始" : "查看研究理解"}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function ResearchIntentPreview({ objective, platforms, budget, supplement, onSupplementChange }: { objective: string; platforms: string[]; budget: ResearchTaskInput["budget"]; supplement: string; onSupplementChange: (value: string) => void }) {
  const intent = previewIntent(objective);
  return <div role="region" className="rounded-2xl border border-signal/25 bg-signal/[0.04] p-4" aria-label="研究理解预览">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="section-kicker">Step 02 · Intent preview</p><h3 className="mt-1 font-display text-lg font-semibold">先确认研究理解</h3></div>
      <Badge variant="info">{intent.primary}</Badge>
    </div>
    <p className="mt-3 text-sm leading-6">“{objective.trim()}”</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <PreviewItem label="次要意图" value={intent.secondary.join("；")} />
      <PreviewItem label="需要发现的内容" value={intent.unknowns.join("；")} />
      <PreviewItem label="时间范围" value={intent.timeScope} />
      <PreviewItem label="计划平台" value={platforms.join("、")} />
      <PreviewItem label="需要的证据" value={intent.evidence.join("；")} />
      <PreviewItem label="反向证据" value={intent.counterevidence.join("；")} />
      <PreviewItem label="排除项" value={intent.exclusions.join("；")} />
      <PreviewItem label="预期输出" value={intent.output} />
    </div>
    <label className="mt-4 block text-sm font-semibold">
      补充要求
      <textarea
        aria-label="补充要求"
        className="mt-2 min-h-24 w-full rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15"
        value={supplement}
        onChange={(event) => onSupplementChange(event.currentTarget.value)}
        placeholder="可补充必须回答的问题、排除项或输出格式。"
      />
    </label>
    <p className="mt-3 text-xs leading-5 text-muted">预算边界：{budget.crawl_limit} 次采集 · {budget.content_limit} 条新增内容 · {budget.token_limit.toLocaleString()} Token。创建后仍可在草稿阶段修改理解。</p>
  </div>;
}

function PreviewItem({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-white p-3 text-xs"><p className="font-semibold">{label}</p><p className="mt-1 leading-5 text-muted">{value || "未指定"}</p></div>;
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
          <div className="mt-3 flex items-center justify-between text-xs text-muted"><span>第 {task.current_round} 轮 · {researchStepLabel(task.current_step)}</span><span>{task.finding_count} 条结论 · {task.action_count} 项待确认</span></div>
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
  const reviseIntent = useReviseResearchIntentMutation();
  const busy = pause.isPending || resume.isPending || cancel.isPending || rerun.isPending || complete.isPending || decide.isPending || reviseIntent.isPending;
  const isTerminal = ["Done", "Failed", "Cancelled"].includes(task.status);
  const [activeTab, setActiveTab] = useState<"overview" | "process" | "discovery" | "evidence" | "queries" | "budget" | "technical">("overview");
  const tabs = [
    ["overview", "总览"],
    ["process", "研究过程"],
    ["discovery", "发现"],
    ["evidence", "证据"],
    ["queries", "查询"],
    ["budget", "预算"],
    ["technical", "技术详情"],
  ] as const;
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="border-b border-line pb-5"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><p className="section-kicker">Research dossier</p><h2 className="mt-1 break-words font-display text-2xl font-semibold">{task.objective}</h2></div><Badge variant={statusVariant[task.status]}>{statusLabels[task.status]}</Badge></div><div className="mt-5 flex flex-wrap gap-2">{!isTerminal && !task.paused ? <Button variant="secondary" size="sm" disabled={busy} onClick={() => pause.mutate(task.id)}><CirclePause className="size-4" />暂停</Button> : null}{!isTerminal && task.paused ? <Button variant="secondary" size="sm" disabled={busy} onClick={() => resume.mutate(task.id)}><CirclePlay className="size-4" />继续</Button> : null}{task.status === "AwaitingReview" ? <><Button size="sm" disabled={busy} onClick={() => complete.mutate(task.id)}><Check className="size-4" />确认完成</Button><Button variant="secondary" size="sm" disabled={busy} onClick={() => rerun.mutate(task.id)}><RotateCcw className="size-4" />重新研究</Button></> : null}{!isTerminal ? <Button variant="danger" size="sm" disabled={busy} onClick={() => cancel.mutate(task.id)}><Square className="size-3.5" />取消任务</Button> : null}</div></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Metric label="阶段" value={researchStepLabel(task.current_step)} /><Metric label="研究轮次" value={`第 ${task.current_round} 轮`} /><Metric label="采集 / 内容" value={`${task.consumption.crawl_count} / ${task.consumption.content_count}`} /><Metric label="运行时长" value={formatDuration(task.consumption.duration_seconds)} /><Metric label="关键结论" value={`${task.findings.length} 条`} /><Metric label="待确认动作" value={`${task.action_count} 项`} /><Metric label="发现候选" value={`${task.discovery_candidates?.length ?? 0} 条`} /><Metric label="来源平台" value={task.platforms.join("、")} /></CardContent>
      </Card>

      <ResearchSummaryStrip task={task} />
      <div className="flex gap-1 overflow-x-auto border-b border-line pb-px" role="tablist" aria-label="研究详情分区">
        {tabs.map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={activeTab === value} onClick={() => setActiveTab(value)} className={`shrink-0 border-b-2 px-3 py-2 text-sm font-semibold transition ${activeTab === value ? "border-signal text-signal-strong" : "border-transparent text-muted hover:text-ink"}`}>{label}</button>)}
      </div>
      {activeTab === "overview" ? <div className="space-y-5">
        <CrawlerAccessCard task={task} />
        <IntentUnderstandingCard task={task} canRevise={task.status === "Draft"} revisePending={reviseIntent.isPending} reviseError={reviseIntent.error} onRevise={(request) => reviseIntent.mutate({ taskId: task.id, request })} />
        <div className="grid gap-5 lg:grid-cols-2"><AlignmentReviewCard task={task} /><CoverageCard task={task} /></div>
        {task.result ? <ResearchResultCard task={task} /> : null}
      </div> : null}
      {activeTab === "process" ? <TraceCard trace={task.trace} /> : null}
      {activeTab === "discovery" ? <div className="space-y-5">
        <div className="grid gap-5 lg:grid-cols-2"><DiscoveryCandidatesCard task={task} /><EventCandidatesCard task={task} /></div>
        <MemoryCard task={task} />
      </div> : null}
      {activeTab === "evidence" ? <div className="space-y-5">
        <InformationUtilityCard task={task} />
        <EvidencePoolCard task={task} />
        <div className="grid gap-5 lg:grid-cols-2"><FindingsCard task={task} /><ActionsCard taskId={task.id} actions={task.actions} busy={busy} onDecide={(actionId, decision) => decide.mutate({ taskId: task.id, actionId, decision })} /></div>
      </div> : null}
      {activeTab === "queries" ? <QueryTrajectoryCard queries={task.queries ?? []} /> : null}
      {activeTab === "budget" ? <BudgetTraceCard task={task} /> : null}
      {activeTab === "technical" ? <TechnicalDetailsCard task={task} /> : null}
    </div>
  );
}

function CrawlerAccessCard({ task }: { task: ResearchTaskDetail }) {
  const ids = crawlerTaskIds(task);
  if (ids.length === 0) return null;

  const waitingLogin = task.status === "WaitingLogin";
  const waitingCrawl = task.status === "WaitingCrawl";
  const title = waitingLogin
    ? "平台采集需要登录"
    : waitingCrawl
      ? "平台采集准备中"
      : "平台采集任务";
  const description = waitingLogin
    ? "请在采集详情页查看二维码，并在你的 Windows Chrome 中完成对应平台扫码或验证。完成后服务器 Worker 会继续执行。"
    : waitingCrawl
      ? "采集任务已创建；如果平台需要登录，扫码入口会在采集详情页出现。"
      : "本研究已记录平台采集任务。若二维码已失效，请重新研究以创建新的登录窗口；不要在 AI 研究页寻找 Owner 登录。";

  return (
    <Card className={waitingLogin ? "border-warning/30 bg-warning/[0.04]" : "border-signal/20 bg-signal/[0.025]"}>
      <CardHeader>
        <p className="section-kicker">Platform authentication</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h3 className="font-display text-xl font-semibold">{title}</h3>
          <Badge variant={waitingLogin || waitingCrawl ? "warning" : "neutral"}>
            {waitingLogin ? "现在需要操作" : waitingCrawl ? "等待 Worker" : "已记录"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-6">
          <span className="font-semibold">这不是 Owner Workbench 登录。</span> {description}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {ids.map((id, index) => (
            <Button key={id} asChild variant="secondary" size="sm">
              <Link to={`/tools/crawls/${encodeURIComponent(id)}`}>
                {ids.length === 1 ? "打开平台采集详情" : `打开第 ${index + 1} 个采集详情`}
              </Link>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ResearchSummaryStrip({ task }: { task: ResearchTaskDetail }) {
  const alignment = task.alignment_review;
  const newContent = task.result?.new_content_count;
  const discoveries = task.discovery_candidates?.length ?? 0;
  return <Card className="border-signal/15 bg-signal/[0.025]"><CardContent className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6"><div className="sm:col-span-2 lg:col-span-2"><p className="text-xs font-semibold text-muted">研究目标</p><p className="mt-1 line-clamp-2 text-sm font-semibold">{task.objective}</p></div><Metric label="研究目标覆盖度" value={alignment ? `${Math.round(alignment.alignment_score * 100)}%` : "进行中"} /><Metric label="结论" value={`${task.findings.length} 条`} /><Metric label="新增内容" value={typeof newContent === "number" ? String(newContent) : "—"} /><Metric label="发现候选" value={String(discoveries)} /><Metric label="关键状态" value={task.status === "AwaitingReview" ? "等待确认" : task.status === "Done" ? "已完成" : "持续研究"} /></CardContent></Card>;
}

const intentLabels: Record<string, string> = {
  discovery: "探索发现",
  verification: "事实验证",
  comparison: "对比研究",
  trend_tracking: "趋势追踪",
  pain_point_research: "痛点研究",
  competitor_scan: "竞品扫描",
  creator_scan: "创作者扫描",
  content_opportunity: "内容机会",
  market_mapping: "市场地图",
  product_opportunity: "产品机会",
  monitoring: "持续监控",
};

const utilityLabels: Record<string, string> = {
  core_evidence: "核心证据",
  discovery_seed: "发现种子",
  background_context: "背景材料",
  event_signal: "事件信号",
  counterevidence: "反向证据",
  memory_update: "长期记忆",
  action_trigger: "行动触发",
  noise: "噪音",
  duplicate: "重复",
};

const intentSourceLabels: Record<string, string> = {
  model: "AI 解析",
  fallback_default: "默认假设",
  legacy_migrated: "历史任务迁移",
  owner_revised: "用户修改",
};

const timeScopeLabels: Record<string, string> = {
  recent: "近期",
  year: "年度",
  ongoing: "持续范围",
  custom: "自定义范围",
};

const contentDecisionLabels: Record<string, string> = {
  adopted: "已采用",
  not_adopted: "未采用",
};

const sourceIndependenceLabels: Record<string, string> = {
  independent: "独立来源",
  repost: "转载来源",
  unknown: "来源未确认",
};

const contentCompletenessLabels: Record<string, string> = {
  complete: "完整",
  partial: "部分完整",
  missing: "缺失",
  unknown: "未确认",
};

const evidenceQualityLabels: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
  unknown: "未确认",
};

function intentValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value) ?? "—";
}

function objectStringField(value: unknown, key: string): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "string" ? field : null;
}

function IntentUnderstandingCard({
  task,
  canRevise,
  revisePending,
  reviseError,
  onRevise,
}: {
  task: ResearchTaskDetail;
  canRevise: boolean;
  revisePending: boolean;
  reviseError: unknown;
  onRevise: (request: string) => void;
}) {
  const intent = task.intent_contract;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(intent?.original_request ?? task.objective);

  if (!intent) {
    return (
      <Card>
        <CardHeader><p className="section-kicker">Intent understanding</p><h3 className="mt-1 font-display text-xl font-semibold">研究理解卡</h3></CardHeader>
        <CardContent><p className="text-sm leading-6 text-muted">这是阶段 8D-0 之前创建的历史任务。系统保留原始目标和执行轨迹，不会重新解释或重新执行它。</p></CardContent>
      </Card>
    );
  }

  const confidence = Math.round(intent.confidence * 100);
  const confidenceLabel = confidence >= 75 ? "高置信度" : confidence >= 45 ? "使用默认假设" : "需要澄清";
  const timeScope = intent.time_scope;
  const defaultDays = typeof timeScope.default_days === "number" ? timeScope.default_days : null;
  const scopeYear = typeof timeScope.year === "number" ? timeScope.year : null;
  const knownEntities = intent.known_entities
    .map((entity) => (typeof entity === "object" && entity !== null && "name" in entity ? String(entity.name) : intentValue(entity)))
    .filter(Boolean);
  return (
    <Card className="border-signal/20 bg-signal/[0.03]">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="section-kicker">Intent understanding · v{intent.version}</p>
            <h3 className="mt-1 font-display text-xl font-semibold">研究理解卡</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={confidence >= 75 ? "success" : confidence >= 45 ? "warning" : "danger"}>{confidenceLabel} · {confidence}%</Badge>
            {canRevise ? <Button type="button" variant="secondary" size="sm" onClick={() => setEditing((value) => !value)}>{editing ? "收起修改" : "修改理解"}</Button> : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {editing ? (
          <form
            className="space-y-3 rounded-xl border border-line bg-white p-4"
            onSubmit={(event) => {
              event.preventDefault();
              const request = draft.trim();
              if (request.length >= 5) {
                onRevise(request);
                setEditing(false);
              }
            }}
          >
            <label className="block text-sm font-semibold" htmlFor={`intent-revision-${task.id}`}>补充或改写研究目标</label>
            <textarea id={`intent-revision-${task.id}`} className="min-h-24 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15" value={draft} onChange={(event) => setDraft(event.currentTarget.value)} minLength={5} />
            <p className="text-xs leading-5 text-muted">仅允许在任务开始前修改；原始目标会保留，新的理解会作为版本记录。</p>
            {reviseError ? <p className="text-sm text-danger">{errorMessage(reviseError)}</p> : null}
            <div className="flex justify-end gap-2"><Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>取消</Button><Button type="submit" size="sm" disabled={revisePending || draft.trim().length < 5}>{revisePending ? "保存中…" : "保存理解"}</Button></div>
          </form>
        ) : null}
        <div className="rounded-xl bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">我理解你想研究什么</p>
          <p className="mt-2 text-sm leading-6">{intent.interpreted_goal}</p>
          <div className="mt-3 flex flex-wrap gap-2"><Badge variant="info">主要：{intentLabels[intent.primary_intent] ?? intent.primary_intent}</Badge>{intent.secondary_intents.map((value) => <Badge key={value} variant="neutral">次要：{intentLabels[value] ?? value}</Badge>)}</div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <InfoList title="需要发现的未知项" values={intent.unknowns_to_discover} empty="未记录未知项" />
          <div className="rounded-xl border border-line p-4 text-sm"><p className="font-semibold">默认范围与计划平台</p><p className="mt-2 text-muted">{timeScopeLabels[String(timeScope.type)] ?? "自定义范围"}{defaultDays !== null ? ` · ${defaultDays} 天` : ""}{scopeYear !== null ? ` · ${scopeYear} 年` : ""}</p><p className="mt-2 break-words text-muted">{intent.platform_preferences.length > 0 ? intent.platform_preferences.join("、") : task.platforms.join("、")}</p>{intent.target_audience ? <p className="mt-2 text-muted">目标人群：{intent.target_audience}</p> : null}</div>
        </div>
        {knownEntities.length > 0 ? <InfoList title="用户已知实体" values={knownEntities} empty="无" /> : null}
        <div className="grid gap-4 md:grid-cols-2">
          <InfoList title="需要的正向证据" values={intent.evidence_requirements} empty="未指定" />
          <InfoList title="需要寻找的反向证据" values={intent.negative_evidence_requirements} empty="未指定" danger />
        </div>
        <div className="grid gap-4 md:grid-cols-2"><InfoList title="排除内容" values={intent.exclusions} empty="未指定" /><InfoList title="预期输出" values={intent.desired_output} empty="未指定" /></div>
        {intent.assumptions.length > 0 ? <InfoList title="默认假设" values={intent.assumptions} empty="无" /> : null}
        {intent.ambiguities.length > 0 ? <div className="rounded-xl border border-warning/30 bg-warning/5 p-4 text-sm"><p className="font-semibold text-warning">待确认的歧义</p><ul className="mt-2 space-y-1 text-muted">{intent.ambiguities.map((value) => <li key={value}>· {value}</li>)}</ul>{intent.clarification_question ? <p className="mt-3 font-semibold">澄清问题：{intent.clarification_question}</p> : null}</div> : null}
        <p className="text-xs leading-5 text-muted">理解来源：{intentSourceLabels[intent.intent_source] ?? "研究理解"} · 当前研究假设：{intent.current_research_hypothesis} · 未静默覆盖原始目标。</p>
      </CardContent>
    </Card>
  );
}

function InfoList({ title, values, empty, danger = false }: { title: string; values: string[]; empty: string; danger?: boolean }) {
  return <div className={`rounded-xl border p-4 ${danger ? "border-danger/20 bg-danger/[0.03]" : "border-line"}`}><p className="text-sm font-semibold">{title}</p>{values.length === 0 ? <p className="mt-2 text-sm text-muted">{empty}</p> : <ul className="mt-2 space-y-1 text-sm leading-6 text-muted">{values.map((value) => <li key={value}>· {value}</li>)}</ul>}</div>;
}

function InformationUtilityCard({ task }: { task: ResearchTaskDetail }) {
  const utilities = task.information_utilities ?? [];
  const order = ["core_evidence", "discovery_seed", "background_context", "event_signal", "counterevidence", "memory_update", "action_trigger", "noise", "duplicate"];
  const counts = order.map((type) => [type, utilities.filter((item) => item.utility_type === type).length] as const);
  return <Card><CardHeader><p className="section-kicker">Information utility</p><h3 className="mt-1 font-display text-xl font-semibold">信息价值分布</h3><p className="mt-2 text-sm text-muted">同一条内容可以拥有多个用途；分类理由来自真实内容决策和证据绑定。</p></CardHeader><CardContent className="space-y-4"><div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{counts.map(([type, count]) => <Metric key={type} label={utilityLabels[type] ?? type} value={String(count)} />)}</div>{utilities.length === 0 ? <p className="text-sm text-muted">尚未完成内容价值评估。</p> : <div className="space-y-2">{utilities.slice(0, 12).map((item) => <article key={item.id} className="rounded-xl border border-line p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><Link to={`/memory/contents/${encodeURIComponent(item.content_id)}`} className="font-semibold hover:text-signal">{item.content_id}</Link><Badge variant={item.utility_type === "noise" || item.utility_type === "duplicate" ? "neutral" : item.utility_type === "counterevidence" ? "danger" : "info"}>{utilityLabels[item.utility_type] ?? item.utility_type}</Badge></div><p className="mt-2 leading-5 text-muted">{item.rationale}</p></article>)}</div>}</CardContent></Card>;
}

function DiscoveryCandidatesCard({ task }: { task: ResearchTaskDetail }) {
  const candidates = task.entity_candidates ?? [];
  const discoveries = task.discovery_candidates ?? [];
  return <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="section-kicker">Bounded discovery</p><h3 className="mt-1 font-display text-xl font-semibold">新发现与下一步</h3></div><Link className="text-xs font-semibold text-signal hover:underline" to="/discoveries">打开收件箱 →</Link></div></CardHeader><CardContent className="space-y-3">
    {discoveries.length > 0 ? discoveries.slice(0, 8).map((candidate) => <article key={candidate.id} className="rounded-xl border border-signal/15 bg-signal/[0.025] p-3 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><Link to={`/discoveries/${encodeURIComponent(candidate.id)}`} className="font-semibold hover:text-signal">{candidate.title}</Link><Badge variant={candidate.state === "accepted" || candidate.state === "converted_to_research" ? "success" : candidate.state === "ignored" ? "neutral" : "info"}>{discoveryStateLabel(candidate.state)}</Badge></div><p className="mt-1 text-xs leading-5 text-muted">{discoveryTypeLabel(candidate.candidate_type)} · 排序 {(candidate.final_score * 100).toFixed(0)}% · {candidate.platform_count} 个平台 · {candidate.independent_source_count} 个独立来源</p><p className="mt-2 text-xs leading-5 text-muted">{candidate.summary}</p></article>) : null}
    {candidates.length > 0 ? <><p className="text-xs font-semibold text-muted">阶段 8D-0 实体候选</p>{candidates.map((candidate) => <article key={candidate.id} className="rounded-xl border border-line p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{candidate.normalized_name}</span><Badge variant="info">{entityCandidateStatusLabel(candidate.status)}</Badge></div><p className="mt-1 text-xs text-muted">{entityTypeLabel(candidate.entity_type)} · 新颖性 {(candidate.novelty * 100).toFixed(0)}% · 相关性 {(candidate.relevance_to_intent * 100).toFixed(0)}% · 置信度 {(candidate.confidence * 100).toFixed(0)}%</p>{candidate.suggested_next_action ? <p className="mt-2 text-xs leading-5 text-muted">建议：{candidate.suggested_next_action}</p> : null}{candidate.source_content_id ? <Link className="mt-2 inline-block text-xs text-signal hover:underline" to={`/memory/contents/${encodeURIComponent(candidate.source_content_id)}`}>查看来源内容</Link> : null}</article>)}</> : null}
    {discoveries.length === 0 && candidates.length === 0 ? <p className="text-sm text-muted">尚未产生有来源约束的发现。</p> : null}
  </CardContent></Card>;
}

function EventCandidatesCard({ task }: { task: ResearchTaskDetail }) {
  const events = task.event_candidates ?? [];
  return <Card><CardHeader><p className="section-kicker">Event candidates</p><h3 className="mt-1 font-display text-xl font-semibold">事件与变化信号</h3></CardHeader><CardContent className="space-y-3">{events.length === 0 ? <p className="text-sm text-muted">尚未记录事件候选。</p> : events.map((event) => <article key={event.id} className="rounded-xl border border-line p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{event.title}</span><Badge variant="warning">{eventTypeLabel(event.event_type)}</Badge></div><p className="mt-2 text-xs leading-5 text-muted">{event.summary}</p><p className="mt-2 text-xs text-muted">置信度 {(event.confidence * 100).toFixed(0)}% · 状态 {eventStatusLabel(event.status)}{event.source_content_id ? ` · 来源 ${event.source_content_id}` : ""}</p></article>)}</CardContent></Card>;
}

function MemoryCard({ task }: { task: ResearchTaskDetail }) {
  const memories = task.memory_items ?? [];
  return <Card><CardHeader><p className="section-kicker">Long-term research memory</p><h3 className="mt-1 font-display text-xl font-semibold">长期研究记忆</h3><p className="mt-2 text-sm text-muted">已确认事实、推测和实体变化会保留来源，下一次研究可区分已知与新变化。</p></CardHeader><CardContent className="space-y-2">{memories.length === 0 ? <p className="text-sm text-muted">尚未写入长期记忆。</p> : memories.map((memory) => <article key={memory.id} className="rounded-xl border border-line p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold break-words">{memory.memory_key}</span><Badge variant={memory.is_current ? "info" : "neutral"}>{memory.is_current ? "当前" : "历史"}</Badge></div><p className="mt-1 text-xs text-muted">{memoryTypeLabel(memory.memory_type)} · 置信度 {(memory.confidence * 100).toFixed(0)}% · {intentValue(memory.value)}</p><p className="mt-1 text-xs text-muted">来源：{memory.source_content_id ?? memory.source_query_id ?? memory.source_finding_id ?? "—"}</p></article>)}</CardContent></Card>;
}

function AlignmentReviewCard({ task }: { task: ResearchTaskDetail }) {
  const review = task.alignment_review;
  if (!review) return <Card><CardHeader><p className="section-kicker">Intent alignment review</p><h3 className="mt-1 font-display text-xl font-semibold">研究对齐审查</h3></CardHeader><CardContent><p className="text-sm text-muted">研究完成前才会生成对齐审查；当前仍在积累证据。</p></CardContent></Card>;
  const reviewLabel = review.review_status === "passed" ? "已通过" : review.review_status === "partial_completion" ? "部分完成" : "仍需研究";
  return <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="section-kicker">Intent alignment review</p><h3 className="mt-1 font-display text-xl font-semibold">研究对齐审查</h3></div><Badge variant={review.review_status === "passed" ? "success" : review.review_status === "partial_completion" ? "warning" : "danger"}>{reviewLabel} · {(review.alignment_score * 100).toFixed(0)}%</Badge></div></CardHeader><CardContent className="space-y-3">{review.review_status === "partial_completion" ? <p className="rounded-xl border border-warning/25 bg-warning/5 p-3 text-sm leading-6 text-muted">当前结果已经形成部分可用结论，但仍有关键要求没有覆盖。系统保留缺口和建议，不会把部分完成包装成完整答案。</p> : null}<InfoList title="已覆盖要求" values={review.covered_requirements} empty="尚无" /><InfoList title="仍缺少" values={review.missing_requirements} empty="无" danger={review.missing_requirements.length > 0} />{review.scope_drift && Object.keys(review.scope_drift).length > 0 ? <div className="rounded-xl bg-paper p-3 text-xs leading-5 text-muted">范围漂移：{JSON.stringify(review.scope_drift)}</div> : null}<p className="text-xs leading-5 text-muted">建议下一步：{review.recommended_next_step ?? "无"}</p></CardContent></Card>;
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
                <Badge variant={platform.status === "completed" ? "success" : platform.status === "failed" ? "danger" : "warning"}>{platformCoverageLabel(platform.status)}</Badge>
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
              <span className="min-w-0 break-words font-semibold">{entity.canonical_name} <span className="font-normal text-muted">· {entityTypeLabel(entity.entity_type)}</span></span>
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
  const reasonLabel = (reason: string | null) => ({
    not_used_as_evidence_but_seed: "未作为证据采用，但保留为发现种子",
    not_used_as_evidence_but_background: "未作为证据采用，但保留为背景材料",
    not_used_as_evidence_but_memory_update: "未作为证据采用，但已更新长期记忆",
    not_used_low_relevance: "相关性较低",
    not_used_no_factual_increment: "没有事实增量",
    not_used_duplicate: "重复内容",
    not_used_marketing: "营销内容",
    not_used_incomplete: "内容不完整",
    not_used_out_of_scope: "超出研究范围",
  }[reason ?? ""] ?? reason);
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
                  <Link to={`/memory/contents/${encodeURIComponent(item.content_id)}`} className="font-semibold hover:text-signal">{item.content_id}</Link>
                  <span className="text-muted">{contentDecisionLabels[item.decision] ?? "已记录"}{item.is_repost ? " · 转载" : ""}</span>
                </div>
                <p className="mt-1 text-muted">来源独立性：{sourceIndependenceLabels[item.source_independence] ?? "未确认"} · 完整度：{contentCompletenessLabels[item.content_completeness] ?? "未确认"} · 质量：{evidenceQualityLabels[item.evidence_quality] ?? "未确认"}</p>
                {item.not_adopted_reason ? <p className="mt-1 text-danger">未采用原因：{reasonLabel(item.not_adopted_reason)}</p> : null}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BudgetTraceCard({ task }: { task: ResearchTaskDetail }) {
  const consumption = task.consumption;
  return (
    <Card>
      <CardHeader>
        <p className="section-kicker">Resource budget</p>
        <h3 className="mt-1 font-display text-xl font-semibold">预算与资源使用</h3>
        <p className="mt-2 text-sm text-muted">查看本次研究的资源边界和套餐归属；模型调用轨迹与原始参数位于技术详情。</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="总 Token" value={`${(consumption.input_tokens + consumption.output_tokens).toLocaleString()} / ${task.budget.token_limit.toLocaleString()}`} />
          <Metric label="模型调用" value={`${consumption.model_call_count ?? task.step_usage?.length ?? 0} / ${task.budget.max_model_calls ?? "—"}`} />
          <Metric label="采集任务" value={`${consumption.crawl_count} / ${task.budget.crawl_limit}`} />
          <Metric label="按量金额" value={formatCost(consumption.estimated_cost, consumption.cost_currency)} />
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl bg-paper p-3 text-xs"><p className="font-semibold">MiniMax / GLM 套餐</p><p className="mt-1 text-muted">{(consumption.subscription_calls ?? 0).toLocaleString()} 次 · {(consumption.subscription_tokens ?? 0).toLocaleString()} Token · 单次金额不适用</p></div>
          <div className="rounded-xl bg-paper p-3 text-xs"><p className="font-semibold">DeepSeek / 按量</p><p className="mt-1 text-muted">{(consumption.payg_calls ?? 0).toLocaleString()} 次 · {(consumption.payg_tokens ?? 0).toLocaleString()} Token · {formatCost(consumption.estimated_cost, consumption.cost_currency)}</p></div>
          <div className="rounded-xl bg-paper p-3 text-xs"><p className="font-semibold">中转 / 未知</p><p className="mt-1 text-muted">{(consumption.relay_calls ?? 0).toLocaleString()} 次中转 · {(consumption.uncosted_call_count ?? 0).toLocaleString()} 次不可计算</p></div>
        </div>
      </CardContent>
    </Card>
  );
}

function TechnicalDetailsCard({ task }: { task: ResearchTaskDetail }) {
  const [showContext, setShowContext] = useState(false);
  const usage = task.step_usage ?? [];
  const modeLabel: Record<string, string> = {
    subscription_fixed: "年度套餐",
    pay_as_you_go: "按量",
    relay: "中转",
    prepaid_balance: "预付余额",
    quota_bundle: "额度包",
    unknown: "未知价格",
  };
  const provider = objectStringField(task.route_snapshot.primary, "provider");
  const model = objectStringField(task.route_snapshot.primary, "model");
  const crawlerIds = crawlerTaskIds(task);
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader><p className="section-kicker">Internal diagnostics</p><h3 className="mt-1 font-display text-xl font-semibold">技术详情</h3><p className="mt-2 text-sm text-muted">仅在这里查看任务标识、模型路由、Token 明细和原始执行上下文。</p></CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Metric label="任务 UUID" value={task.id} />
          <Metric label="Provider" value={provider ?? "尚未快照"} />
          <Metric label="模型" value={model ?? "尚未快照"} />
          <Metric label="Token 明细" value={`${task.consumption.input_tokens.toLocaleString()} 输入 · ${task.consumption.output_tokens.toLocaleString()} 输出 · ${task.consumption.cached_tokens.toLocaleString()} 缓存`} />
          <Metric label="Fallback" value={task.step_usage?.some((item) => Boolean(item.fallback_reason)) ? "发生过" : "未记录"} />
          <Metric label="采集任务数" value={String(task.consumption.crawl_count)} />
          <Metric label="内部状态" value={`${task.status} · ${task.current_step ?? "—"}`} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader><p className="section-kicker">Crawler references</p><h3 className="mt-1 font-display text-xl font-semibold">Crawler Task ID</h3></CardHeader>
        <CardContent>
          {crawlerIds.length === 0 ? <p className="text-sm text-muted">尚未生成 Crawler Task ID。</p> : <ul className="space-y-2 text-xs text-muted">{crawlerIds.map((id) => <li key={id} className="rounded-lg bg-paper p-3"><Link to={`/tools/crawls/${encodeURIComponent(id)}`} className="flex flex-wrap items-center justify-between gap-2 hover:text-signal"><span className="break-all font-mono">{id}</span><span className="shrink-0 font-semibold">打开采集详情 →</span></Link></li>)}</ul>}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><p className="section-kicker">Model calls</p><h3 className="mt-1 font-display text-xl font-semibold">模型调用轨迹</h3></CardHeader>
        <CardContent>
          <details className="rounded-xl border border-line">
            <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold">展开全部模型调用（{usage.length} 条）</summary>
            <div className="space-y-2 border-t border-line p-3">
              {usage.length === 0 ? <p className="text-sm text-muted">尚无步骤级模型用量。</p> : usage.map((item) => <div key={`${item.sequence}-${item.step}`} className="rounded-xl border border-line p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">#{item.sequence} · {item.step}</span><span className="text-muted">{item.vendor ?? "未知厂商"} / {item.model ?? "未知模型"}</span></div><p className="mt-1 text-muted">{modeLabel[item.billing_mode ?? "unknown"]} · 输入 {item.input_tokens ?? 0} · 输出 {item.output_tokens ?? 0} · {item.latency_ms ?? "—"} ms · 费用 {item.estimated_cost === null || item.estimated_cost === undefined ? "不适用/不可计算" : `${item.estimated_cost} ${item.currency ?? ""}`.trim()}{item.fallback_reason ? ` · Fallback：${item.fallback_reason}` : ""}</p></div>)}
            </div>
          </details>
        </CardContent>
      </Card>
      <details className="rounded-2xl border border-danger/20 bg-danger/[0.03]">
        <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold text-danger">原始错误{task.failure_reason ? "（有记录）" : "（无记录）"}</summary>
        <div className="border-t border-danger/20 p-5 text-sm leading-6 text-danger">{task.failure_reason ?? "当前任务没有原始错误记录。"}</div>
      </details>
      <Card>
        <CardHeader><button type="button" className="flex w-full items-center justify-between gap-3 text-left" aria-expanded={showContext} onClick={() => setShowContext((value) => !value)}><span><span className="section-kicker">Raw runtime context</span><span className="mt-1 block font-display text-xl font-semibold">研究执行上下文</span></span><span className="text-xs text-muted">{showContext ? "收起" : "展开"}</span></button></CardHeader>
        {showContext ? <CardContent className="grid gap-4 sm:grid-cols-2"><div><p className="mb-2 text-sm font-semibold">研究计划</p><pre className="max-h-80 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(task.research_plan ?? task.plan, null, 2)}</pre></div><div><p className="mb-2 text-sm font-semibold">运行上下文</p><pre className="max-h-80 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{JSON.stringify(task.context, null, 2)}</pre></div></CardContent> : null}
      </Card>
    </div>
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
  const [showExecuted, setShowExecuted] = useState(false);
  const [showRejected, setShowRejected] = useState(false);
  const lifecycle = (query: (typeof queries)[number]) => query.lifecycle_status ?? query.status;
  const userGoals = queries.filter((query) => query.record_type === "user_goal");
  const executionQueries = queries.filter((query) => query.record_type !== "user_goal");
  const rejectedExecution = executionQueries.filter((query) => lifecycle(query).startsWith("rejected"));
  const executed = executionQueries.filter((query) => !lifecycle(query).startsWith("rejected")).sort((left, right) => (right.expected_value_score ?? -1) - (left.expected_value_score ?? -1));
  const sourceLabel = (query: (typeof queries)[number]) => {
    if (query.parent_query_id) {
      const parent = queries.find((candidate) => candidate.id === query.parent_query_id);
      return parent ? `父查询：${parent.query}` : `父查询：${query.parent_query_id}`;
    }
    if (query.source_content_id) return `来源内容：${query.source_content_id}`;
    if (query.record_type === "user_goal" || query.source_type === "user_goal") return "用户目标（不进入执行闸门）";
    return querySourceLabel(query.source_type);
  };
  const roleLabel = (query: (typeof queries)[number]) => query.query_role ? ({ seed_discovery: "发现种子", entity_expansion: "实体扩展", cross_platform_validation: "跨平台验证", counterevidence: "反向证据", competitor_scan: "竞品扫描", trend_probe: "趋势探测", creator_scan: "创作者扫描", pain_point_probe: "痛点探测" }[query.query_role] ?? "研究扩展") : "历史查询";
  const row = (query: (typeof queries)[number]) => {
    const currentLifecycle = lifecycle(query);
    const isUnexecuted = !query.crawler_task_id && !["completed", "failed", "cancelled"].includes(currentLifecycle);
    return <article key={query.id} className="rounded-xl border border-line p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="break-words text-sm font-semibold">{query.query}</p><p className="mt-1 text-xs text-muted">{queryTypeLabel(query.query_type)} · {roleLabel(query)} · {sourceLabel(query)} · {query.platform}</p></div><Badge variant={currentLifecycle.startsWith("rejected") ? "danger" : currentLifecycle === "completed" ? "success" : currentLifecycle.startsWith("skipped") ? "warning" : "info"}>{queryLifecycleLabel(currentLifecycle)}</Badge></div>
    <p className="mt-2 text-xs leading-5 text-muted">生成理由：{query.generation_reason}</p>
    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5"><Metric label="相关性" value={query.relevance_score === null ? "—" : query.relevance_score.toFixed(2)} /><Metric label="具体性" value={query.specificity_score.toFixed(2)} /><Metric label="新颖性" value={query.novelty_score.toFixed(2)} /><Metric label="新增率" value={query.new_content_rate === null || query.new_content_rate === undefined ? "—" : `${(query.new_content_rate * 100).toFixed(0)}%`} /><Metric label="边际价值" value={query.marginal_value_score === null || query.marginal_value_score === undefined ? "—" : query.marginal_value_score.toFixed(2)} /></div>
    {query.rejection_reason ? <p className="mt-3 rounded-lg bg-danger/5 px-3 py-2 text-xs leading-5 text-danger">拒绝原因：{query.rejection_reason}</p> : null}
    {isUnexecuted && query.unexecuted_reason ? <p className="mt-3 rounded-lg bg-paper px-3 py-2 text-xs leading-5 text-muted">未执行原因：{query.unexecuted_reason}</p> : null}
    <p className="mt-3 text-xs text-muted">决策 {queryDecisionLabel(query.decision)} · 闸门 {queryGateLabel(query.gate_status)} · 结果 {query.result_count} · 新增 {query.new_content_count} · 已存在 {query.existing_content_count} · 已更新 {query.updated_content_count} · 重复证据 {query.duplicate_evidence_count}</p>
  </article>;
  };
  return <Card><CardHeader><p className="section-kicker">Query quality gate</p><h3 className="mt-1 font-display text-xl font-semibold">查询轨迹与质量闸门</h3><p className="mt-2 text-sm text-muted">平台查询按预期价值排序；已执行和拒绝分组默认收起，避免执行细节遮住研究结论。</p></CardHeader><CardContent className="space-y-4">{queries.length === 0 ? <p className="text-sm text-muted">暂无查询轨迹（历史任务兼容）。</p> : <>{userGoals.length > 0 ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted">用户目标（仅作意图来源，不进入平台闸门）</p><div className="space-y-2">{userGoals.map(row)}</div></div> : null}<div className="rounded-xl border border-line"><button type="button" className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold" aria-expanded={showExecuted} onClick={() => setShowExecuted((value) => !value)}><span>平台执行查询 · 已执行 / 通过</span><span className="text-xs font-normal text-muted">{executed.length} 条 · {showExecuted ? "收起" : "展开"}</span></button>{showExecuted ? <div className="space-y-2 border-t border-line p-3">{executed.length > 0 ? executed.map(row) : <p className="text-sm text-muted">暂无已执行查询。</p>}</div> : null}</div>{rejectedExecution.length > 0 ? <div className="rounded-xl border border-danger/20"><button type="button" className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-danger" aria-expanded={showRejected} onClick={() => setShowRejected((value) => !value)}><span>平台执行查询 · 已拒绝（全部保留）</span><span className="text-xs font-normal">{rejectedExecution.length} 条 · {showRejected ? "收起" : "展开"}</span></button>{showRejected ? <div className="space-y-2 border-t border-danger/20 p-3">{rejectedExecution.map(row)}</div> : null}</div> : null}</>}</CardContent></Card>;
}

function FindingsCard({ task }: { task: ResearchTaskDetail }) {
  const supportLabel = (value: string | undefined) => ({ direct: "直接支持", contextual: "上下文", contradictory: "反证", background: "背景" }[value ?? "background"] ?? "背景");
  const strengthLabel = (value: string | undefined) => ({ strong: "强", medium: "中", weak: "弱" }[value ?? "weak"] ?? "弱");
  return <Card><CardHeader><div className="flex items-center justify-between"><div><p className="section-kicker">Evidence</p><h3 className="mt-1 font-display text-xl font-semibold">结论与证据</h3></div><FileSearch className="size-5 text-signal" /></div></CardHeader><CardContent className="space-y-4">{task.findings.length === 0 ? <p className="text-sm text-muted">尚无证据绑定结论。</p> : task.findings.map((finding) => <article key={finding.id} className="rounded-xl border border-line p-4"><div className="flex flex-wrap items-center gap-2"><Badge variant={finding.kind === "fact" ? "info" : "warning"}>{finding.kind === "fact" ? "事实" : "推测 / inference"}</Badge><span className="text-xs text-muted">第 {finding.round_number} 轮</span></div><p className="mt-3 text-sm leading-6">{finding.statement}</p>{finding.derivation ? <p className="mt-2 text-xs leading-5 text-muted">推导：{finding.derivation}</p> : null}{finding.kind === "inference" ? <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-xs leading-5 text-muted">反证：{finding.counterevidence_explanation ?? "历史任务未记录反证状态。"}</p> : null}<div className="mt-3 space-y-2">{finding.evidence.map((evidence) => <details key={evidence.content_id} className="rounded-lg bg-paper px-3 py-2 text-xs"><summary className="cursor-pointer list-none"><Link to={`/memory/contents/${encodeURIComponent(evidence.content_id)}`} className="font-semibold hover:text-signal">{evidence.title ?? evidence.content_id}</Link><span className="ml-2 inline-flex gap-1"><Badge variant={evidence.support_type === "contradictory" ? "danger" : evidence.support_type === "direct" ? "info" : "neutral"}>{supportLabel(evidence.support_type)} · {strengthLabel(evidence.support_strength)}</Badge></span></summary><p className="mt-2 leading-5 text-muted">支持说明：{evidence.support_explanation ?? "历史任务未记录支持说明。"}</p><p className="mt-1 text-muted">{evidence.platform ?? "未知平台"} · {evidence.author_name ?? "未知作者"} · 采集 {evidence.collected_at ?? "未知"}</p>{evidence.occurrences && evidence.occurrences.length > 0 ? <div className="mt-2 space-y-1 text-muted"><p>发现 {evidence.occurrences.reduce((total, occurrence) => total + occurrence.occurrence_count, 0)} 次 · 涉及 {evidence.occurrences.length} 条发现记录</p>{evidence.occurrences.map((occurrence) => <p key={occurrence.id}>查询：{occurrence.source_query_ids?.join("、") || occurrence.research_query_id || "—"} · 采集：{occurrence.source_crawler_task_ids?.join("、") || occurrence.crawler_task_id || "—"}</p>)}</div> : null}</details>)}</div></article>)}</CardContent></Card>;
}

function ActionsCard({ actions, busy, onDecide }: { taskId: string; actions: ResearchTaskDetail["actions"]; busy: boolean; onDecide: (actionId: string, decision: "approve" | "reject") => void }) {
  return <Card><CardHeader><p className="section-kicker">Owner approval</p><h3 className="mt-1 font-display text-xl font-semibold">待确认动作</h3></CardHeader><CardContent className="space-y-3">{actions.length === 0 ? <p className="text-sm text-muted">暂无待确认动作。</p> : actions.map((action) => <div key={action.id} className="rounded-xl border border-line p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold">{action.action}</p><p className="mt-1 text-xs leading-5 text-muted">{action.reason}</p></div><Badge variant={action.status === "pending" ? "warning" : action.status === "approved" ? "success" : "neutral"}>{actionStatusLabel(action.status)}</Badge></div>{action.status === "pending" ? <div className="mt-3 flex gap-2"><Button size="sm" disabled={busy} onClick={() => onDecide(action.id, "approve")}>批准</Button><Button variant="secondary" size="sm" disabled={busy} onClick={() => onDecide(action.id, "reject")}>拒绝</Button></div> : null}</div>)}</CardContent></Card>;
}

function TraceCard({ trace }: { trace: ResearchTaskDetail["trace"] }) {
  const [search, setSearch] = useState("");
  const filtered = trace.filter((entry) => {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return `${entry.event} ${entry.step ?? ""} ${entry.status ?? ""} ${entry.reason ?? ""}`.toLowerCase().includes(query);
  });
  const groups = new Map<string, typeof trace>();
  filtered.forEach((entry) => {
    const key = entry.step ? researchStepLabel(entry.step) : "其他步骤";
    const current = groups.get(key) ?? [];
    current.push(entry);
    groups.set(key, current);
  });
  return <Card><CardHeader><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="section-kicker">Execution trace</p><h3 className="mt-1 font-display text-xl font-semibold">执行轨迹（{trace.length} 步）</h3><p className="mt-2 text-sm text-muted">按研究步骤分组；空的 tool、reason、token 字段不会占据详情区域。</p></div><div className="relative w-full sm:w-64"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.currentTarget.value)} placeholder="搜索轨迹" aria-label="搜索执行轨迹" /></div></div></CardHeader><CardContent className="space-y-2">{trace.length === 0 ? <p className="text-sm text-muted">暂无轨迹。</p> : filtered.length === 0 ? <p className="text-sm text-muted">没有匹配的轨迹。</p> : Array.from(groups.entries()).map(([group, entries]) => { const elapsed = entries.reduce((total, entry) => total + (entry.elapsed_ms ?? 0), 0); return <details key={group} className="group rounded-xl border border-line"><summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm"><ChevronDown className="size-4 transition group-open:rotate-180" /><span className="font-semibold">{group}</span><span className="text-xs text-muted">{entries.length} 步</span><span className="ml-auto text-xs text-muted">{elapsed > 0 ? `${elapsed} ms` : "耗时未记录"}</span></summary><div className="space-y-2 border-t border-line p-3">{entries.map((entry) => <details key={entry.sequence} className="rounded-xl border border-line"><summary className="flex cursor-pointer list-none items-center gap-3 px-3 py-2 text-sm"><span className="font-mono text-xs text-muted">#{entry.sequence}</span><span className="font-semibold">{traceEventLabel(entry.event)}</span><span className="ml-auto text-xs text-muted">{entry.status ? statusLabels[entry.status] : ""}</span></summary><div className="grid gap-3 border-t border-line bg-paper/50 p-3 text-xs sm:grid-cols-2"><div>{entry.reason ? <><p className="text-muted">原因</p><p className="mt-1">{entry.reason}</p></> : null}{entry.provider || entry.model ? <><p className="mt-3 text-muted">模型</p><p className="mt-1">{entry.provider ?? "—"} / {entry.model ?? "—"}</p></> : null}</div><div>{entry.input_tokens !== null || entry.output_tokens !== null || entry.elapsed_ms !== null ? <><p className="text-muted">Token / 耗时</p><p className="mt-1">{entry.input_tokens ?? "—"} / {entry.output_tokens ?? "—"} · {entry.elapsed_ms ?? "—"} ms</p></> : null}{entry.tool_arguments ? <><p className="mt-3 text-muted">实际工具参数</p><pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{JSON.stringify(entry.tool_arguments, null, 2)}</pre></> : null}</div></div></details>)}</div></details>; })}</CardContent></Card>;
}

function EmptyDetail() { return <Card className="grid min-h-80 place-items-center"><div className="text-center"><FileSearch className="mx-auto size-8 text-muted" /><p className="mt-3 text-sm text-muted">选择一个任务查看真实执行状态与证据。</p></div></Card>; }

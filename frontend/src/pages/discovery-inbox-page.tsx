import {
  ArrowDown,
  ArrowRight,
  Check,
  Clock3,
  ExternalLink,
  FolderPlus,
  RotateCcw,
  Radar,
  Search,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  VolumeX,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import type {
  DiscoveryCandidateDetail,
  DiscoveryCandidateSummary,
  DiscoveryFeedbackType,
  DiscoveryInboxItem,
  ResearchSpaceSummary,
} from "../api/research";
import { useAnalyzeOpportunityMutation } from "../features/opportunity/hooks/use-opportunity-queries";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { ActionMenu } from "../components/ui/action-menu";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { CollapsibleSection } from "../components/ui/collapsible-section";
import { FilterBar } from "../components/ui/filter-bar";
import { MasterDetailLayout } from "../components/ui/master-detail-layout";
import { SegmentedTabs } from "../components/ui/segmented-tabs";
import {
  useAddDiscoveryToSpaceMutation,
  useContinueDiscoveryMutation,
  useDiscoveryFeedbackMutation,
  useDiscoveryQuery,
  useDiscoveriesQuery,
  useResearchSpacesQuery,
} from "../features/research/hooks/use-discovery-queries";
import { errorMessage } from "../lib/utils";

const stateLabels: Record<string, string> = {
  generated: "待排序",
  scored: "已排序",
  queued: "已排队",
  accepted: "已采纳",
  ignored: "已忽略",
  deferred: "稍后跟进",
  converted_to_research: "已转研究",
  added_to_space: "已入空间",
  dismissed_duplicate: "已标记重复",
  expired: "已过期",
};

const candidateTypeLabels: Record<string, string> = {
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

const stateVariants: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  generated: "neutral",
  scored: "info",
  queued: "info",
  accepted: "success",
  ignored: "neutral",
  deferred: "warning",
  converted_to_research: "success",
  added_to_space: "success",
  dismissed_duplicate: "danger",
  expired: "neutral",
};

const attentionLabels: Record<string, string> = {
  immediate_attention: "立即关注",
  daily_digest: "今日摘要",
  normal_record: "普通记录",
};

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function candidateMatches(candidate: DiscoveryInboxItem, query: string): boolean {
  if (!query) return true;
  const haystack = `${candidate.title} ${candidate.summary} ${candidate.candidate_type} ${candidate.source_platform ?? ""}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function asCount(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "未记录";
}

function explanationText(
  candidate: Pick<DiscoveryCandidateSummary, "score_explanation">,
  key: string,
): string | null {
  const value = candidate.score_explanation[key];
  return typeof value === "string" && value.trim() ? value : null;
}

export function DiscoveryInboxPage() {
  const navigate = useNavigate();
  const { candidateId } = useParams<{ candidateId: string }>();
  const [state, setState] = useState("");
  const [search, setSearch] = useState("");
  const [candidateType, setCandidateType] = useState("all");
  const [platform, setPlatform] = useState("all");
  const [source, setSource] = useState("all");
  const [importance, setImportance] = useState("all");
  const [sort, setSort] = useState("recommended");
  const [selectedId, setSelectedId] = useState("");
  const discoveries = useDiscoveriesQuery({ state: state || undefined });
  const effectiveItems = useMemo(() => {
    const items = (discoveries.data ?? []).filter((item) => {
      const matchesType = candidateType === "all" || item.candidate_type === candidateType;
      const matchesPlatform = platform === "all" || item.source_platform === platform;
      const matchesSource = source === "all" || (item.source_type ?? "discovery") === source;
      const matchesImportance = importance === "all" || (importance === "high" ? item.final_score >= 0.75 : item.final_score >= 0.5 && item.final_score < 0.75);
      return candidateMatches(item, search.trim()) && matchesType && matchesPlatform && matchesSource && matchesImportance;
    });
    return items.sort((left, right) => {
      if (sort === "latest") return right.updated_at.localeCompare(left.updated_at);
      if (sort === "evidence") return right.evidence_strength_score - left.evidence_strength_score;
      if (sort === "independent") return right.independent_source_count - left.independent_source_count;
      return right.final_score - left.final_score;
    });
  }, [candidateType, discoveries.data, importance, platform, search, sort, source]);
  const platforms = useMemo(() => Array.from(new Set((discoveries.data ?? []).map((item) => item.source_platform).filter((value): value is string => Boolean(value)))).sort(), [discoveries.data]);
  const effectiveId = candidateId ?? selectedId ?? effectiveItems[0]?.id ?? "";
  const selectedItem = effectiveItems.find((item) => item.id === effectiveId);
  const detail = useDiscoveryQuery(effectiveId, selectedItem?.source_type !== "monitoring");
  const spaces = useResearchSpacesQuery();
  const feedback = useDiscoveryFeedbackMutation();
  const continueResearch = useContinueDiscoveryMutation();
  const addToSpace = useAddDiscoveryToSpaceMutation();
  const analyzeOpportunity = useAnalyzeOpportunityMutation();
  const [spaceId, setSpaceId] = useState("");
  const [followUpRequest, setFollowUpRequest] = useState("");
  const effectiveSpaceId = spaceId || spaces.data?.[0]?.id || "";

  function selectCandidate(item: DiscoveryInboxItem) {
    setSelectedId(item.id);
    if (item.source_type === "monitoring" && item.mission_id) {
      void navigate(`/monitoring/${encodeURIComponent(item.mission_id)}`);
      return;
    }
    void navigate(`/discoveries/${encodeURIComponent(item.id)}`);
  }

  function giveFeedback(feedbackType: DiscoveryFeedbackType) {
    if (!effectiveId) return;
    const topicFeedback = new Set<DiscoveryFeedbackType>([
      "follow",
      "mute_topic",
      "deprioritize_similar",
    ]);
    const feedbackInput = topicFeedback.has(feedbackType) && detail.data
      ? {
          feedback_type: feedbackType,
          scope: "topic" as const,
          scope_key: detail.data.normalized_key,
        }
      : { feedback_type: feedbackType };
    feedback.mutate({ candidateId: effectiveId, feedback: feedbackInput });
  }

  const activeFeedback = detail.data?.feedback.filter((item) => !item.undone_at) ?? [];
  // The API returns feedback newest-first; undo must target the actual most
  // recent action rather than the oldest item in the list.
  const lastFeedback = activeFeedback[0];

  function analyzeSelectedOpportunity() {
    if (!effectiveId) return;
    analyzeOpportunity.mutate(
      { source_type: "discovery_candidate", source_id: effectiveId, opportunity_type: "product_opportunity" },
      { onSuccess: (result) => { const first = result.opportunities[0]; if (first) void navigate(`/opportunities/${encodeURIComponent(first.id)}`); } },
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="发现收件箱"
        description="把值得判断的新实体、主题、痛点和机会集中在一个可筛选的收件箱里。"
        action={
          <Button asChild variant="secondary">
            <Link to="/research">回到 AI 研究</Link>
          </Button>
        }
      />

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="搜索标题、摘要或平台"
        resultCount={effectiveItems.length}
        filters={<>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">状态</span><select className="h-10 max-w-full rounded-lg border border-line bg-white px-3 text-sm" value={state} onChange={(event) => setState(event.currentTarget.value)} aria-label="发现状态"><option value="">全部</option>{Object.entries(stateLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">类型</span><select className="h-10 max-w-full rounded-lg border border-line bg-white px-3 text-sm" value={candidateType} onChange={(event) => setCandidateType(event.currentTarget.value)} aria-label="发现类型"><option value="all">全部</option>{Object.entries(candidateTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">平台</span><select className="h-10 max-w-full rounded-lg border border-line bg-white px-3 text-sm" value={platform} onChange={(event) => setPlatform(event.currentTarget.value)} aria-label="发现平台"><option value="all">全部</option>{platforms.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">来源</span><select className="h-10 max-w-full rounded-lg border border-line bg-white px-3 text-sm" value={source} onChange={(event) => setSource(event.currentTarget.value)} aria-label="发现来源"><option value="all">全部</option><option value="discovery">研究</option><option value="monitoring">监控</option></select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">重要度</span><select className="h-10 max-w-full rounded-lg border border-line bg-white px-3 text-sm" value={importance} onChange={(event) => setImportance(event.currentTarget.value)} aria-label="发现重要度"><option value="all">全部</option><option value="high">高</option><option value="medium">中</option></select></label>
        </>}
        sort={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">排序</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={sort} onChange={(event) => setSort(event.currentTarget.value)} aria-label="发现排序"><option value="recommended">推荐</option><option value="latest">最新</option><option value="evidence">证据强度</option><option value="independent">独立来源</option></select></label>}
        chips={[
          ...(state ? [{ label: `状态：${stateLabels[state] ?? state}`, onRemove: () => setState("") }] : []),
          ...(candidateType !== "all" ? [{ label: `类型：${candidateTypeLabels[candidateType] ?? candidateType}`, onRemove: () => setCandidateType("all") }] : []),
          ...(platform !== "all" ? [{ label: `平台：${platform}`, onRemove: () => setPlatform("all") }] : []),
          ...(source !== "all" ? [{ label: `来源：${source === "monitoring" ? "监控" : "研究"}`, onRemove: () => setSource("all") }] : []),
          ...(importance !== "all" ? [{ label: `重要度：${importance === "high" ? "高" : "中"}`, onRemove: () => setImportance("all") }] : []),
          ...(sort !== "recommended" ? [{ label: `排序：${sort === "latest" ? "最新" : sort === "evidence" ? "证据强度" : "独立来源"}`, onRemove: () => setSort("recommended") }] : []),
        ]}
        onClear={() => { setSearch(""); setState(""); setCandidateType("all"); setPlatform("all"); setSource("all"); setImportance("all"); setSort("recommended"); }}
      />

      {discoveries.isError ? (
        <ErrorState title="发现收件箱加载失败" error={discoveries.error} onRetry={() => void discoveries.refetch()} />
      ) : (
        <MasterDetailLayout
          listLabel="发现列表"
          storageKey="mediaops.master-detail.discoveries.collapsed"
          list={<Card className="overflow-hidden"><CardHeader className="border-b border-line pb-4"><p className="section-kicker">当前收件箱</p><h2 className="mt-1 font-display text-xl font-semibold">候选列表</h2></CardHeader><CardContent className="space-y-2 p-3">
            {discoveries.isPending ? Array.from({ length: 4 }, (_, index) => <div key={index} className="h-24 animate-pulse rounded-xl bg-paper" />) : null}
            {!discoveries.isPending && effectiveItems.length === 0 ? <div className="rounded-xl bg-paper p-5 text-sm text-muted">暂时没有符合筛选条件的发现。调整筛选条件，或完成一轮真实研究。</div> : null}
            {effectiveItems.map((candidate) => (
              <button key={candidate.id} type="button" onClick={() => selectCandidate(candidate)} className={`w-full rounded-xl border p-3 text-left transition ${effectiveId === candidate.id ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}>
                <div className="flex items-start justify-between gap-2"><span className="line-clamp-2 text-sm font-semibold">{candidate.title}</span><Badge variant={candidate.source_type === "monitoring" ? "info" : stateVariants[candidate.state] ?? "neutral"}>{candidate.source_type === "monitoring" ? attentionLabels[candidate.attention_level ?? ""] ?? "监控变化" : stateLabels[candidate.state] ?? candidate.state}</Badge></div>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">{candidate.summary}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted"><span>{candidateTypeLabels[candidate.candidate_type] ?? candidate.candidate_type}</span><span>·</span><span>{candidate.source_type === "monitoring" ? "监控" : candidate.source_platform ?? "多平台"}</span><span className="ml-auto font-semibold text-signal-strong">{candidate.final_score >= 0.75 ? "高关注" : candidate.final_score >= 0.5 ? "值得判断" : "待补证据"}</span></div>
                <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-signal-strong">下一步：{candidate.suggested_next_action ?? explanationText(candidate, "recommendation") ?? "等待更多证据"}</p>
              </button>
            ))}
          </CardContent></Card>}
          detail={
          <>
          {selectedItem?.source_type === "monitoring" ? (
            <Card className="grid min-h-80 place-items-center p-8 text-center"><div><Radar className="mx-auto size-8 text-signal" /><h2 className="mt-3 font-display text-2xl font-semibold">这是监控任务产生的变化</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted">变化、事件更新、反向证据和长期记忆都保留在监控任务详情中。</p>{selectedItem.mission_id ? <Button className="mt-5" asChild><Link to={`/monitoring/${encodeURIComponent(selectedItem.mission_id)}`}>打开监控任务 <ExternalLink className="size-4" /></Link></Button> : null}</div></Card>
          ) : detail.isError ? <ErrorState title="发现详情加载失败" error={detail.error} onRetry={() => void detail.refetch()} /> : detail.data ? (
            <DiscoveryDetail
              candidate={detail.data}
              spaces={spaces.data ?? []}
              selectedSpaceId={effectiveSpaceId}
              onSpaceChange={setSpaceId}
              feedbackPending={feedback.isPending}
              continuePending={continueResearch.isPending}
              addPending={addToSpace.isPending}
              analyzePending={analyzeOpportunity.isPending}
              onAnalyzeOpportunity={analyzeSelectedOpportunity}
              onFeedback={giveFeedback}
              onUndo={() => lastFeedback ? feedback.mutate({ candidateId: effectiveId, feedback: { undo_feedback_id: lastFeedback.id } }) : undefined}
              lastFeedbackLabel={lastFeedback?.feedback_type}
              onContinue={() => continueResearch.mutate({ candidateId: effectiveId, request: followUpRequest.trim() || undefined }, { onSuccess: () => void navigate("/research") })}
              followUpRequest={followUpRequest}
              onFollowUpRequestChange={setFollowUpRequest}
              onAddToSpace={() => { if (effectiveSpaceId) addToSpace.mutate({ candidateId: effectiveId, spaceId: effectiveSpaceId }); }}
              error={feedback.error ?? continueResearch.error ?? addToSpace.error ?? analyzeOpportunity.error ?? spaces.error}
            />
          ) : (
            <Card className="grid min-h-80 place-items-center"><p className="text-sm text-muted">选择一条发现查看解释和后续动作。</p></Card>
          )}
          </>
          }
        />
      )}
    </div>
  );
}

function DiscoveryDetail({
  candidate,
  spaces,
  selectedSpaceId,
  onSpaceChange,
  feedbackPending,
  continuePending,
  addPending,
  analyzePending,
  onFeedback,
  onUndo,
  lastFeedbackLabel,
  onContinue,
  followUpRequest,
  onFollowUpRequestChange,
  onAddToSpace,
  onAnalyzeOpportunity,
  error,
}: {
  candidate: DiscoveryCandidateDetail;
  spaces: ResearchSpaceSummary[];
  selectedSpaceId: string;
  onSpaceChange: (value: string) => void;
  feedbackPending: boolean;
  continuePending: boolean;
  addPending: boolean;
  analyzePending: boolean;
  onFeedback: (value: DiscoveryFeedbackType) => void;
  onUndo?: () => void;
  lastFeedbackLabel?: string;
  onContinue: () => void;
  followUpRequest: string;
  onFollowUpRequestChange: (value: string) => void;
  onAddToSpace: () => void;
  onAnalyzeOpportunity: () => void;
  error: unknown;
}) {
  const explanation = candidate.score_explanation;
  const eventAggregation = asRecord(explanation.event_aggregation);
  const eventPlatforms = asStringList(eventAggregation?.platforms);
  const relatedEntities = asStringList(eventAggregation?.related_entities);
  const [tab, setTab] = useState<"overview" | "evidence" | "why" | "related" | "actions" | "technical">("overview");
  const metrics = [
    ["证据强度", candidate.evidence_strength_score],
    ["独立来源", candidate.source_independence_score],
    ["可行动性", candidate.actionability_score],
  ] as const;
  const feedbackItems = [
    { label: "有价值", onSelect: () => onFeedback("valuable"), icon: <ThumbsUp className="size-4" /> },
    { label: "证据不足", onSelect: () => onFeedback("needs_more_evidence"), icon: <Search className="size-4" /> },
    { label: "稍后", onSelect: () => onFeedback("follow"), icon: <Clock3 className="size-4" /> },
    { label: "不相关", onSelect: () => onFeedback("irrelevant"), icon: <ThumbsDown className="size-4" /> },
    { label: "已经知道", onSelect: () => onFeedback("already_known"), icon: <Check className="size-4" /> },
    { label: "重复", onSelect: () => onFeedback("duplicate"), icon: <RotateCcw className="size-4" /> },
    { label: "降低同类优先级", onSelect: () => onFeedback("deprioritize_similar"), icon: <ArrowDown className="size-4" /> },
    { label: "静默主题", onSelect: () => onFeedback("mute_topic"), icon: <VolumeX className="size-4" /> },
    ...(onUndo ? [{ label: `撤销最近反馈${lastFeedbackLabel ? `（${lastFeedbackLabel}）` : ""}`, onSelect: onUndo }] : []),
  ].map((item) => ({ ...item, disabled: feedbackPending }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="border-b border-line pb-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="section-kicker">{candidateTypeLabels[candidate.candidate_type] ?? candidate.candidate_type}</p><h2 className="mt-1 break-words font-display text-2xl font-semibold">{candidate.title}</h2><p className="mt-2 text-sm leading-6 text-muted">{candidate.summary}</p></div><Badge variant={stateVariants[candidate.state] ?? "neutral"}>{stateLabels[candidate.state] ?? candidate.state}</Badge></div><div className="mt-4 rounded-xl border border-signal/20 bg-signal/[0.04] p-3 text-sm"><p className="font-semibold">为什么值得判断</p><p className="mt-1 leading-5 text-muted">{typeof explanation.recommendation === "string" ? explanation.recommendation : candidate.suggested_next_action ?? "等待更多来源"}</p></div></CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 pt-4"><div className="grid min-w-0 flex-1 grid-cols-3 gap-2 sm:max-w-md">{metrics.map(([label, value]) => <div key={label} className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{percent(value)}</p></div>)}</div><Button disabled={continuePending} onClick={onContinue}>{continuePending ? "创建中…" : "继续研究"}<ArrowRight className="size-4" /></Button><ActionMenu label="判断" items={feedbackItems} /></CardContent>
      </Card>

      <SegmentedTabs value={tab} onChange={setTab} label="发现详情" items={[{ value: "overview", label: "概览" }, { value: "evidence", label: "证据", count: candidate.sources.length }, { value: "why", label: "为什么推荐" }, { value: "related", label: "相关对象" }, { value: "actions", label: "后续动作" }, { value: "technical", label: "技术详情" }]} />

      {tab === "overview" ? <div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><p className="section-kicker">当前判断</p><h3 className="mt-1 font-display text-xl font-semibold">这条发现说明了什么</h3></CardHeader><CardContent className="space-y-3"><InfoLine label="类型" value={candidateTypeLabels[candidate.candidate_type] ?? candidate.candidate_type} /><InfoLine label="来源" value={candidate.source_platform ?? "多平台"} /><InfoLine label="建议下一步" value={candidate.suggested_next_action ?? "等待更多来源"} /></CardContent></Card><Card><CardHeader><p className="section-kicker">证据概览</p><h3 className="mt-1 font-display text-xl font-semibold">证据够不够</h3></CardHeader><CardContent className="space-y-3"><InfoLine label="独立来源" value={`${candidate.independent_source_count} 个`} /><InfoLine label="涉及平台" value={`${candidate.platform_count} 个`} /><InfoLine label="转载线索" value={`${candidate.suspected_repost_count} 条`} /><p className="text-sm leading-6 text-muted">点击“证据”查看具体来源；点击“为什么推荐”查看系统解释。</p></CardContent></Card></div> : null}

      {tab === "why" ? <Card><CardHeader><p className="section-kicker">推荐解释</p><h3 className="mt-1 font-display text-xl font-semibold">系统为什么把它放进收件箱</h3></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{[["为什么相关", "why_relevant"], ["为什么是新的", "why_new"], ["证据与来源", "evidence"], ["来源独立性", "source_independence"], ["反向证据", "counterevidence"], ["排序风险", "risks"]].map(([label, key]) => <div key={key} className="rounded-xl border border-line p-3 text-sm"><p className="font-semibold">{label}</p><p className="mt-1 leading-5 text-muted">{typeof explanation[key] === "string" ? explanation[key] : "暂无解释"}</p></div>)}</CardContent></Card> : null}

      {tab === "related" ? <Card><CardHeader><p className="section-kicker">相关对象</p><h3 className="mt-1 font-display text-xl font-semibold">事件、平台和实体</h3></CardHeader><CardContent className="space-y-3">{eventAggregation ? <div className="rounded-xl bg-paper p-4 text-sm"><p className="font-semibold">时间范围</p><p className="mt-1 text-muted">{typeof eventAggregation.first_seen === "string" ? eventAggregation.first_seen : "未记录"} → {typeof eventAggregation.latest_seen === "string" ? eventAggregation.latest_seen : "未记录"}</p><p className="mt-2 text-muted">平台：{eventPlatforms.length ? eventPlatforms.join("、") : "未记录"}</p><p className="mt-2 text-muted">正向证据 {asCount(eventAggregation.positive_evidence_count)} · 负向证据 {asCount(eventAggregation.negative_evidence_count)} · 未知 {asCount(eventAggregation.unknown_evidence_count)}</p></div> : <p className="text-sm text-muted">当前没有聚合事件。</p>}{relatedEntities.length ? <div><p className="text-sm font-semibold">相关实体</p><div className="mt-2 flex flex-wrap gap-2">{relatedEntities.map((entity) => <Badge key={entity} variant="neutral">{entity}</Badge>)}</div></div> : null}</CardContent></Card> : null}

      {tab === "evidence" ? <Card><CardHeader><p className="section-kicker">来源 · {candidate.sources.length}</p><h3 className="mt-1 font-display text-xl font-semibold">来源与独立性</h3></CardHeader><CardContent className="space-y-2">{candidate.sources.length === 0 ? <p className="text-sm text-muted">没有可展示的来源。</p> : candidate.sources.map((source) => <article key={source.id} className="rounded-xl border border-line p-3 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="font-semibold">{source.source_title ?? "未命名来源"}</p><p className="mt-1 text-xs text-muted">{source.platform ?? "未知平台"} · {source.source_author ?? "未知作者"} · {source.independent_group ?? "独立性未标记"}</p></div><Badge variant={source.is_repost ? "warning" : "success"}>{source.is_repost ? "疑似转载" : "独立来源"}</Badge></div>{source.content_id ? <Link className="mt-2 inline-flex items-center gap-1 text-xs text-signal hover:underline" to={`/memory/contents/${encodeURIComponent(source.content_id)}`}>查看证据 <ExternalLink className="size-3" /></Link> : null}</article>)}</CardContent></Card> : null}

      {tab === "actions" ? <div className="space-y-3"><CollapsibleSection title="继续研究" description="把这条发现交给新的研究任务" count={followUpRequest.trim() ? 1 : undefined}><div className="space-y-3"><textarea className="min-h-24 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15" value={followUpRequest} onChange={(event) => onFollowUpRequestChange(event.currentTarget.value)} placeholder={`默认：继续研究「${candidate.title}」`} aria-label="后续研究说明" /><Button disabled={continuePending} onClick={onContinue}>{continuePending ? "创建中…" : "创建后续研究"}<ArrowRight className="size-4" /></Button></div></CollapsibleSection><CollapsibleSection title="分析机会" description="证据足够时再进入机会判断"><p className="text-sm leading-6 text-muted">系统会保留来源、转载关系和独立来源；证据不足时会明确返回，不会强行生成机会。</p><Button className="mt-3" variant="secondary" disabled={analyzePending} onClick={onAnalyzeOpportunity}><Sparkles className="size-4" />{analyzePending ? "分析中…" : "分析是否形成机会"}</Button></CollapsibleSection><CollapsibleSection title="加入研究空间" description="把它放进长期上下文"><div className="space-y-3">{spaces.length > 0 ? <select className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm" value={selectedSpaceId} onChange={(event) => onSpaceChange(event.currentTarget.value)} aria-label="选择研究空间">{spaces.map((space) => <option key={space.id} value={space.id}>{space.name} · {space.item_count} 项</option>)}</select> : <p className="rounded-xl bg-paper p-3 text-sm text-muted">还没有研究空间，先创建一个再收藏这条发现。</p>}<div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={addPending || !selectedSpaceId} onClick={onAddToSpace}><FolderPlus className="size-4" />{addPending ? "加入中…" : "加入空间"}</Button><Button asChild variant="ghost"><Link to="/spaces">管理研究空间<ExternalLink className="size-3.5" /></Link></Button></div></div></CollapsibleSection></div> : null}

      {tab === "technical" ? <CollapsibleSection title="技术详情" description="内部评分、数量和生命周期信息" count={candidate.scores.length + candidate.lifecycle.length}><div className="grid gap-3 sm:grid-cols-2">{[["相关性", candidate.relevance_score], ["新颖性", candidate.novelty_score], ["最终排序", candidate.final_score], ["内容数量", candidate.content_count], ["平台数量", candidate.platform_count], ["转载数量", candidate.suspected_repost_count]].map(([label, value]) => <div key={label} className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{typeof value === "number" && value <= 1 ? percent(value) : String(value)}</p></div>)}</div>{candidate.experimental_status ? <p className="mt-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-muted">扩展关系暂不可用：{candidate.experimental_status}</p> : null}</CollapsibleSection> : null}

      {error ? <p className="rounded-lg border border-danger/20 bg-danger/8 px-3 py-2 text-sm text-danger" role="alert">{errorMessage(error)}</p> : null}
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return <div className="flex items-start justify-between gap-3 border-b border-line/70 pb-2 text-sm last:border-0 last:pb-0"><span className="text-muted">{label}</span><span className="max-w-[70%] text-right font-semibold">{value}</span></div>;
}

import {
  ArrowDown,
  ArrowRight,
  Check,
  Clock3,
  ExternalLink,
  Filter,
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
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";
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
  const [selectedId, setSelectedId] = useState("");
  const discoveries = useDiscoveriesQuery({ state: state || undefined });
  const effectiveItems = useMemo(
    () => (discoveries.data ?? []).filter((item) => candidateMatches(item, search.trim())),
    [discoveries.data, search],
  );
  const effectiveId = candidateId ?? selectedId ?? effectiveItems[0]?.id ?? "";
  const selectedItem = effectiveItems.find((item) => item.id === effectiveId);
  const detail = useDiscoveryQuery(effectiveId, selectedItem?.source_type !== "monitoring");
  const spaces = useResearchSpacesQuery();
  const feedback = useDiscoveryFeedbackMutation();
  const continueResearch = useContinueDiscoveryMutation();
  const addToSpace = useAddDiscoveryToSpaceMutation();
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

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Bounded discovery · 8D-1"
        title="发现收件箱"
        description="研究过程中出现的新实体、主题、事件、痛点和机会会先进入这里。每条发现都保留来源、独立性、证据强度和排序理由。"
        action={
          <Button asChild variant="secondary">
            <Link to="/research">回到 AI 研究</Link>
          </Button>
        }
      />

      <Card>
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_190px_auto]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.currentTarget.value)}
              placeholder="搜索发现、摘要或平台"
              aria-label="搜索发现"
            />
          </div>
          <div className="relative">
            <Filter className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <select
              className="h-10 w-full rounded-lg border border-line bg-white pl-9 pr-3 text-sm"
              value={state}
              onChange={(event) => setState(event.currentTarget.value)}
              aria-label="按状态筛选发现"
            >
              <option value="">全部状态</option>
              {Object.entries(stateLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-paper px-3 text-xs text-muted">
            <Sparkles className="size-4 text-signal" />
            {discoveries.data?.length ?? 0} 条真实候选
          </div>
        </CardContent>
      </Card>

      {discoveries.isError ? (
        <ErrorState title="发现收件箱加载失败" error={discoveries.error} onRetry={() => void discoveries.refetch()} />
      ) : (
        <section className="grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.4fr)]">
          <Card className="h-fit overflow-hidden">
            <CardHeader className="border-b border-line pb-4">
              <p className="section-kicker">Discovery queue</p>
              <h2 className="mt-1 font-display text-xl font-semibold">候选列表</h2>
            </CardHeader>
            <CardContent className="space-y-2 p-3">
              {discoveries.isPending ? Array.from({ length: 4 }, (_, index) => <div key={index} className="h-24 animate-pulse rounded-xl bg-paper" />) : null}
              {!discoveries.isPending && effectiveItems.length === 0 ? <p className="rounded-xl bg-paper p-5 text-sm text-muted">暂时没有符合筛选条件的发现。完成一轮有真实来源的研究后，候选会自动进入这里。</p> : null}
            {effectiveItems.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => selectCandidate(candidate)}
                  className={`w-full rounded-xl border p-3 text-left transition ${effectiveId === candidate.id ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-semibold">{candidate.title}</span>
                    <Badge variant={candidate.source_type === "monitoring" ? "info" : stateVariants[candidate.state] ?? "neutral"}>{candidate.source_type === "monitoring" ? attentionLabels[candidate.attention_level ?? ""] ?? "监控变化" : stateLabels[candidate.state] ?? candidate.state}</Badge>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">{candidate.summary}</p>
                  <div className="mt-3 flex items-center justify-between text-xs text-muted">
                    <span>{candidate.source_type === "monitoring" ? `监控 · ${candidate.change_type ?? "变化"}` : `${candidateTypeLabels[candidate.candidate_type] ?? candidate.candidate_type} · ${candidate.source_platform ?? "多平台"}`}</span>
                    <span className="font-semibold text-signal-strong">{percent(candidate.final_score)}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-1 text-[11px] text-muted">
                    <span>独立来源 {candidate.independent_source_count} · 平台 {candidate.platform_count}</span>
                    <span>内容 {candidate.content_count} · 转载 {candidate.suspected_repost_count}</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-muted">
                    {candidate.source_type === "monitoring" ? `监控任务：${candidate.source_mission_title ?? "未命名"}` : `相关：${explanationText(candidate, "why_relevant") ?? "暂无相关性解释"}`}
                  </p>
                  <p className="line-clamp-2 text-[11px] leading-5 text-muted">
                    {candidate.source_type === "monitoring" ? `独立来源 ${candidate.independent_source_count} · 平台 ${candidate.platform_count}` : `新颖：${explanationText(candidate, "why_new") ?? "暂无新颖性解释"}`}
                  </p>
                  <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-signal-strong">
                    下一步：{candidate.suggested_next_action ?? explanationText(candidate, "recommendation") ?? "等待更多证据"}
                  </p>
                </button>
              ))}
            </CardContent>
          </Card>

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
              onFeedback={giveFeedback}
              onUndo={() => lastFeedback ? feedback.mutate({ candidateId: effectiveId, feedback: { undo_feedback_id: lastFeedback.id } }) : undefined}
              lastFeedbackLabel={lastFeedback?.feedback_type}
              onContinue={() => continueResearch.mutate({ candidateId: effectiveId, request: followUpRequest.trim() || undefined }, { onSuccess: () => void navigate("/research") })}
              followUpRequest={followUpRequest}
              onFollowUpRequestChange={setFollowUpRequest}
              onAddToSpace={() => { if (effectiveSpaceId) addToSpace.mutate({ candidateId: effectiveId, spaceId: effectiveSpaceId }); }}
              error={feedback.error ?? continueResearch.error ?? addToSpace.error ?? spaces.error}
            />
          ) : (
            <Card className="grid min-h-80 place-items-center"><p className="text-sm text-muted">选择一条发现查看解释和后续动作。</p></Card>
          )}
        </section>
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
  onFeedback,
  onUndo,
  lastFeedbackLabel,
  onContinue,
  followUpRequest,
  onFollowUpRequestChange,
  onAddToSpace,
  error,
}: {
  candidate: DiscoveryCandidateDetail;
  spaces: ResearchSpaceSummary[];
  selectedSpaceId: string;
  onSpaceChange: (value: string) => void;
  feedbackPending: boolean;
  continuePending: boolean;
  addPending: boolean;
  onFeedback: (value: DiscoveryFeedbackType) => void;
  onUndo?: () => void;
  lastFeedbackLabel?: string;
  onContinue: () => void;
  followUpRequest: string;
  onFollowUpRequestChange: (value: string) => void;
  onAddToSpace: () => void;
  error: unknown;
}) {
  const explanation = candidate.score_explanation;
  const eventAggregation = asRecord(explanation.event_aggregation);
  const eventPlatforms = asStringList(eventAggregation?.platforms);
  const relatedEntities = asStringList(eventAggregation?.related_entities);
  const metrics = [
    ["最终排序", candidate.final_score],
    ["相关性", candidate.relevance_score],
    ["新颖性", candidate.novelty_score],
    ["证据强度", candidate.evidence_strength_score],
    ["来源独立", candidate.source_independence_score],
    ["可行动性", candidate.actionability_score],
  ] as const;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="border-b border-line pb-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="section-kicker">Candidate · {candidateTypeLabels[candidate.candidate_type] ?? candidate.candidate_type}</p>
              <h2 className="mt-1 break-words font-display text-2xl font-semibold">{candidate.title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted">{candidate.summary}</p>
            </div>
            <Badge variant={stateVariants[candidate.state] ?? "neutral"}>{stateLabels[candidate.state] ?? candidate.state}</Badge>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {metrics.map(([label, value]) => <div key={label} className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{percent(value)}</p></div>)}
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <div className="grid gap-3 md:grid-cols-2">
            {[
              ["为什么相关", "why_relevant"],
              ["为什么是新的", "why_new"],
              ["证据与来源", "evidence"],
              ["来源独立性", "source_independence"],
              ["反向证据", "counterevidence"],
              ["排序风险", "risks"],
            ].map(([label, key]) => (
              <div key={key} className="rounded-xl border border-line p-3 text-sm">
                <p className="font-semibold">{label}</p>
                <p className="mt-1 leading-5 text-muted">{typeof explanation[key] === "string" ? explanation[key] : "暂无解释"}</p>
              </div>
            ))}
          </div>
          {candidate.experimental_status ? (
            <div className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm">
              <p className="font-semibold">扩展关系/推荐暂不可用</p>
              <p className="mt-1 leading-5 text-muted">扩展关系/推荐暂不可用：{candidate.experimental_status}</p>
            </div>
          ) : null}
          {eventAggregation ? (
            <div className="rounded-xl border border-line bg-paper p-4 text-sm">
              <p className="font-semibold">事件聚合</p>
              <p className="mt-1 leading-5 text-muted">
                {typeof eventAggregation.first_seen === "string" ? eventAggregation.first_seen : "未记录"}
                {" → "}
                {typeof eventAggregation.latest_seen === "string" ? eventAggregation.latest_seen : "未记录"}
              </p>
              <p className="mt-1 leading-5 text-muted">平台：{eventPlatforms.length > 0 ? eventPlatforms.join("、") : "未记录"}</p>
              <p className="mt-1 leading-5 text-muted">
                正向证据 {asCount(eventAggregation.positive_evidence_count)} · 负向证据 {asCount(eventAggregation.negative_evidence_count)} · 未知 {asCount(eventAggregation.unknown_evidence_count)}
              </p>
              {relatedEntities.length > 0 ? <p className="mt-1 leading-5 text-muted">相关实体：{relatedEntities.join("、")}</p> : null}
            </div>
          ) : null}
          <div className="rounded-xl border border-signal/20 bg-signal/[0.04] p-4 text-sm">
            <p className="font-semibold">建议下一步</p>
            <p className="mt-1 leading-5 text-muted">{typeof explanation.recommendation === "string" ? explanation.recommendation : candidate.suggested_next_action ?? "等待更多来源"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><p className="section-kicker">Owner feedback</p><h3 className="mt-1 font-display text-xl font-semibold">告诉系统这条发现是否有价值</h3></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={feedbackPending} onClick={() => onFeedback("valuable")}><ThumbsUp className="size-4" />有价值</Button>
            <Button variant="secondary" size="sm" disabled={feedbackPending} onClick={() => onFeedback("follow")}><Clock3 className="size-4" />稍后处理</Button>
            <Button variant="secondary" size="sm" disabled={feedbackPending} onClick={() => onFeedback("needs_more_evidence")}><Search className="size-4" />需要更多证据</Button>
            <Button variant="ghost" size="sm" disabled={feedbackPending} onClick={() => onFeedback("deprioritize_similar")}><ArrowDown className="size-4" />降低同类优先级</Button>
            <Button variant="ghost" size="sm" disabled={feedbackPending} onClick={() => onFeedback("mute_topic")}><VolumeX className="size-4" />屏蔽此主题</Button>
            <Button variant="ghost" size="sm" disabled={feedbackPending} onClick={() => onFeedback("already_known")}><Check className="size-4" />已知</Button>
            <Button variant="ghost" size="sm" disabled={feedbackPending} onClick={() => onFeedback("irrelevant")}><ThumbsDown className="size-4" />不相关</Button>
            <Button variant="ghost" size="sm" disabled={feedbackPending} onClick={() => onFeedback("duplicate")}><RotateCcw className="size-4" />重复</Button>
            {onUndo ? <Button variant="ghost" size="sm" disabled={feedbackPending} onClick={onUndo}>撤销最近反馈（{lastFeedbackLabel}）</Button> : null}
          </div>
          <p className="text-xs leading-5 text-muted">“稍后处理”只保存未来关注意图，不启动长期监控任务。</p>
          {error ? <p className="text-sm text-danger">{errorMessage(error)}</p> : null}
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><p className="section-kicker">Continue research</p><h3 className="mt-1 font-display text-xl font-semibold">把发现转成独立研究任务</h3></CardHeader>
          <CardContent className="space-y-3">
            <textarea
              className="min-h-24 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15"
              value={followUpRequest}
              onChange={(event) => onFollowUpRequestChange(event.currentTarget.value)}
              placeholder={`默认：继续研究「${candidate.title}」`}
              minLength={0}
            />
            <Button disabled={continuePending} onClick={onContinue}>{continuePending ? "创建中…" : "创建后续研究"} <ArrowRight className="size-4" /></Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><p className="section-kicker">Research space</p><h3 className="mt-1 font-display text-xl font-semibold">加入长期研究空间</h3></CardHeader>
          <CardContent className="space-y-3">
            {spaces.length > 0 ? <select className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm" value={selectedSpaceId} onChange={(event) => onSpaceChange(event.currentTarget.value)} aria-label="选择研究空间">{spaces.map((space) => <option key={space.id} value={space.id}>{space.name} · {space.item_count} 项</option>)}</select> : <p className="rounded-xl bg-paper p-3 text-sm text-muted">还没有研究空间，先创建一个再收藏这条发现。</p>}
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={addPending || !selectedSpaceId} onClick={onAddToSpace}><FolderPlus className="size-4" />{addPending ? "加入中…" : "加入空间"}</Button>
              <Button asChild variant="ghost"><Link to="/spaces">管理研究空间 <ExternalLink className="size-3.5" /></Link></Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><p className="section-kicker">Evidence sources · {candidate.sources.length}</p><h3 className="mt-1 font-display text-xl font-semibold">来源与独立性</h3></CardHeader>
        <CardContent className="space-y-2">
          {candidate.sources.length === 0 ? <p className="text-sm text-muted">没有可展示的来源。</p> : candidate.sources.map((source) => <article key={source.id} className="rounded-xl border border-line p-3 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="font-semibold">{source.source_title ?? source.content_id ?? "未命名来源"}</p><p className="mt-1 text-xs text-muted">{source.platform ?? "未知平台"} · {source.source_author ?? "未知作者"} · {source.independent_group ?? "独立性未标记"}</p></div><Badge variant={source.is_repost ? "warning" : "success"}>{source.is_repost ? "疑似转载" : "独立来源"}</Badge></div>{source.content_id ? <Link className="mt-2 inline-flex items-center gap-1 text-xs text-signal hover:underline" to={`/memory/contents/${encodeURIComponent(source.content_id)}`}>查看证据 <ExternalLink className="size-3" /></Link> : null}</article>)}
        </CardContent>
      </Card>
    </div>
  );
}

import {
  ArrowLeft,
  ArrowRight,
  Check,
  ExternalLink,
  FileCheck2,
  FolderPlus,
  Plus,
  Sparkles,
  Target,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import type { OpportunityAction, OpportunityDetail, OpportunityPlan, OpportunitySummary } from "../api/opportunity";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { ActionMenu } from "../components/ui/action-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "../components/ui/alert-dialog";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { CollapsibleSection } from "../components/ui/collapsible-section";
import { FilterBar } from "../components/ui/filter-bar";
import { Input } from "../components/ui/input";
import { SegmentedTabs } from "../components/ui/segmented-tabs";
import {
  useAddOpportunityToSpaceMutation,
  useApproveValidationPlanMutation,
  useCreateOpportunityActionMutation,
  useCreateValidationPlanMutation,
  useOpportunityFeedbackMutation,
  useOpportunityQuery,
  useOpportunitiesQuery,
  useRecordOpportunityOutcomeMutation,
  useRecordValidationResultMutation,
  useStartValidationResearchMutation,
  useUpdateOpportunityActionMutation,
} from "../features/opportunity/hooks/use-opportunity-queries";
import { useResearchSpacesQuery } from "../features/research/hooks/use-discovery-queries";
import { errorMessage } from "../lib/utils";

const opportunityTypeLabels: Record<OpportunitySummary["opportunity_type"], string> = {
  product_opportunity: "产品机会",
  business_opportunity: "商业机会",
  content_opportunity: "内容机会",
  research_opportunity: "研究机会",
};

const readinessLabels: Record<OpportunitySummary["readiness"], string> = {
  insufficient_evidence: "证据不足",
  needs_more_evidence: "需要更多证据",
  review_ready: "待用户判断",
  validation_ready: "可以验证",
  validated: "已完成验证",
};

const statusLabels: Record<OpportunitySummary["status"], string> = {
  weak_signal: "弱信号",
  evidence_building: "补充证据中",
  candidate: "机会候选",
  review_ready: "待判断",
  validation_ready: "可验证",
  accepted: "已接受",
  rejected: "已拒绝",
  deferred: "稍后处理",
  validating: "验证中",
  validated: "已验证",
  invalidated: "已否定",
  converted_to_action: "已形成行动",
  archived: "已归档",
};

const planStatusLabels: Record<OpportunityPlan["status"], string> = {
  draft: "草稿",
  ready: "已确认",
  in_progress: "验证中",
  completed: "已完成",
  abandoned: "已放弃",
};

const actionStatusLabels: Record<OpportunityAction["status"], string> = {
  proposed: "待用户批准",
  approved: "已批准",
  in_progress: "进行中",
  completed: "已完成",
  abandoned: "已放弃",
};

const sourceRoleLabels: Record<string, string> = {
  core: "核心证据",
  supporting: "支持证据",
  counterevidence: "反向证据",
  background: "背景材料",
};

type DetailTab = "overview" | "evidence" | "validation" | "research" | "actions" | "technical";

function scorePercent(value: number | undefined): string {
  return value === undefined ? "未记录" : `${Math.round(value * 100)}%`;
}

function stringValue(value: unknown, fallback = "未记录"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
}

function opportunityVariant(readiness: OpportunitySummary["readiness"]): "neutral" | "info" | "success" | "warning" | "danger" {
  if (readiness === "validated" || readiness === "validation_ready") return "success";
  if (readiness === "review_ready") return "info";
  if (readiness === "insufficient_evidence") return "danger";
  return "warning";
}

export function OpportunitiesPage() {
  const { opportunityId } = useParams<{ opportunityId: string }>();
  const opportunities = useOpportunitiesQuery();
  const detail = useOpportunityQuery(opportunityId ?? "");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [readiness, setReadiness] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("judgment");
  const filteredOpportunities = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return [...(opportunities.data ?? [])]
      .filter((item) => !needle || `${item.title} ${item.description} ${item.why_attention}`.toLowerCase().includes(needle))
      .filter((item) => type === "all" || item.opportunity_type === type)
      .filter((item) => readiness === "all" || item.readiness === readiness)
      .filter((item) => status === "all" || item.status === status)
      .sort((left, right) => {
        if (sort === "latest") return right.updated_at.localeCompare(left.updated_at);
        if (sort === "evidence") return (right.scores.evidence_strength ?? 0) - (left.scores.evidence_strength ?? 0);
        if (sort === "verifiable") return Number(right.readiness === "validation_ready" || right.readiness === "validated") - Number(left.readiness === "validation_ready" || left.readiness === "validated");
        return Number(right.readiness === "review_ready" || right.readiness === "validation_ready") - Number(left.readiness === "review_ready" || left.readiness === "validation_ready");
      });
  }, [opportunities.data, readiness, search, sort, status, type]);

  if (opportunityId) {
    return <OpportunityDetailPage opportunityId={opportunityId} detail={detail.data} loading={detail.isPending} error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="机会与行动"
        description="把研究中的证据整理成可判断、可验证的下一步。"
        action={<Button asChild variant="secondary"><Link to="/research">回到 AI 研究 <ArrowRight className="size-4" /></Link></Button>}
      />
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="搜索机会标题或说明"
        resultCount={filteredOpportunities.length}
        filters={<>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">类型</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={type} onChange={(event) => setType(event.currentTarget.value)} aria-label="机会类型"><option value="all">全部</option>{Object.entries(opportunityTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">成熟度</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={readiness} onChange={(event) => setReadiness(event.currentTarget.value)} aria-label="机会成熟度"><option value="all">全部</option>{Object.entries(readinessLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">状态</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.currentTarget.value)} aria-label="机会状态"><option value="all">全部</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </>}
        sort={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">排序</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={sort} onChange={(event) => setSort(event.currentTarget.value)} aria-label="机会排序"><option value="judgment">最值得判断</option><option value="latest">最新更新</option><option value="evidence">证据最强</option><option value="verifiable">可验证优先</option></select></label>}
        chips={[...(type !== "all" ? [{ label: `类型：${opportunityTypeLabels[type as OpportunitySummary["opportunity_type"]] ?? type}`, onRemove: () => setType("all") }] : []), ...(readiness !== "all" ? [{ label: `成熟度：${readinessLabels[readiness as OpportunitySummary["readiness"]] ?? readiness}`, onRemove: () => setReadiness("all") }] : []), ...(status !== "all" ? [{ label: `状态：${statusLabels[status as OpportunitySummary["status"]] ?? status}`, onRemove: () => setStatus("all") }] : []), ...(sort !== "judgment" ? [{ label: `排序：${sort === "latest" ? "最新更新" : sort === "evidence" ? "证据最强" : "可验证优先"}`, onRemove: () => setSort("judgment") }] : [])]}
        onClear={() => { setSearch(""); setType("all"); setReadiness("all"); setStatus("all"); setSort("judgment"); }}
      />
      {opportunities.isError ? <ErrorState title="机会加载失败" error={opportunities.error} onRetry={() => void opportunities.refetch()} /> : null}
      {opportunities.isPending ? <OpportunityListSkeleton /> : null}
      {!opportunities.isPending && !opportunities.isError && opportunities.data?.length === 0 ? (
        <Card className="grid min-h-72 place-items-center p-8 text-center">
          <div className="max-w-lg">
            <Sparkles className="mx-auto size-8 text-signal" />
            <h2 className="mt-4 font-display text-2xl font-semibold">目前还没有足够证据形成值得行动的机会</h2>
            <p className="mt-3 text-sm leading-6 text-muted">继续研究、运行监控，或在发现收件箱中标记有价值的线索后，AI会逐步形成机会候选。</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2"><Button asChild><Link to="/research">继续研究</Link></Button><Button asChild variant="secondary"><Link to="/discoveries">打开发现收件箱</Link></Button></div>
          </div>
        </Card>
      ) : null}
      {!opportunities.isPending && !opportunities.isError && opportunities.data?.length && filteredOpportunities.length === 0 ? <Card className="p-6 text-sm text-muted">没有符合当前筛选条件的机会。</Card> : null}
      {filteredOpportunities.length ? (
        <section className="space-y-2" aria-label="机会候选列表">
          {filteredOpportunities.map((opportunity) => <OpportunityCard key={opportunity.id} opportunity={opportunity} />)}
        </section>
      ) : null}
    </div>
  );
}

function OpportunityListSkeleton() {
  return <section className="space-y-2">{Array.from({ length: 5 }, (_, index) => <div key={index} className="h-28 animate-pulse rounded-xl bg-paper" />)}</section>;
}

function OpportunityCard({ opportunity }: { opportunity: OpportunitySummary }) {
  const independent = opportunity.score_explanation.independent_source_count;
  const sourceCount = typeof independent === "number" ? independent : opportunity.scores.source_independence === undefined ? null : Math.round(opportunity.scores.source_independence * 3);
  return <Link to={`/opportunities/${encodeURIComponent(opportunity.id)}`} className="group block"><Card className="transition group-hover:border-signal/35 group-hover:bg-signal/[0.02]"><CardContent className="flex flex-wrap items-center gap-3 p-4"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><Badge variant="info">{opportunityTypeLabels[opportunity.opportunity_type]}</Badge><Badge variant={opportunityVariant(opportunity.readiness)}>{readinessLabels[opportunity.readiness]}</Badge></div><h2 className="mt-2 line-clamp-2 font-display text-lg font-semibold">{opportunity.title}</h2><p className="mt-1 line-clamp-1 text-sm text-muted">{opportunity.description}</p></div><div className="grid w-full grid-cols-2 gap-2 text-xs sm:w-auto sm:min-w-64 sm:grid-cols-3"><Metric label="证据状态" value={scorePercent(opportunity.scores.evidence_strength)} /><Metric label="来源" value={sourceCount === null ? "未记录" : `${sourceCount} 个`} /><Metric label="建议下一步" value={opportunity.next_step.length > 14 ? `${opportunity.next_step.slice(0, 14)}…` : opportunity.next_step} /></div></CardContent></Card></Link>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-line/70 bg-white p-2"><p className="text-[11px] text-muted">{label}</p><p className="mt-1 truncate font-semibold">{value}</p></div>;
}

function OpportunityDetailPage({ opportunityId, detail, loading, error, onRetry }: { opportunityId: string; detail: OpportunityDetail | undefined; loading: boolean; error: unknown; onRetry: () => void }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<DetailTab>("overview");
  const feedback = useOpportunityFeedbackMutation(opportunityId);
  const createPlan = useCreateValidationPlanMutation(opportunityId);
  const approvePlan = useApproveValidationPlanMutation(opportunityId);
  const startResearch = useStartValidationResearchMutation(opportunityId);
  const recordValidation = useRecordValidationResultMutation(opportunityId);
  const createAction = useCreateOpportunityActionMutation(opportunityId);
  const updateAction = useUpdateOpportunityActionMutation(opportunityId);
  const recordOutcome = useRecordOpportunityOutcomeMutation(opportunityId);
  const addToSpace = useAddOpportunityToSpaceMutation(opportunityId);
  const spaces = useResearchSpacesQuery();
  const [spaceId, setSpaceId] = useState("");
  const [validationOutcome, setValidationOutcome] = useState("supported");
  const [validationWhat, setValidationWhat] = useState("");
  const [validationResult, setValidationResult] = useState("");
  const [validationNext, setValidationNext] = useState("");
  const [actionTitle, setActionTitle] = useState("");
  const [outcomeActionId, setOutcomeActionId] = useState("");
  const [outcomeWhat, setOutcomeWhat] = useState("");
  const [outcomeResult, setOutcomeResult] = useState("");
  const [outcomeLesson, setOutcomeLesson] = useState("");
  const [outcomeNext, setOutcomeNext] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);

  if (loading) return <div className="h-96 animate-pulse rounded-2xl bg-paper" />;
  if (error || !detail) return <ErrorState title="机会详情加载失败" error={error ?? new Error("机会不存在")} onRetry={onRetry} />;
  const current = detail;
  const plan = current.validation_plans[0];
  const completedActions = current.actions.filter((action) => action.status === "completed");
  const showError = feedback.error ?? createPlan.error ?? approvePlan.error ?? startResearch.error ?? recordValidation.error ?? createAction.error ?? updateAction.error ?? recordOutcome.error ?? addToSpace.error ?? spaces.error;

  function createActionForOpportunity() {
    const title = actionTitle.trim() || `验证「${current.title}」的最小假设`;
    createAction.mutate({ opportunity_id: current.id, validation_plan_id: plan?.id, source_type: "opportunity", source_id: current.id, action_type: "validate", title, why: current.next_step, expected_result: "得到一个可记录的支持、否定或不确定结果", success_criteria: "完成一次有明确记录的最小验证" }, { onSuccess: () => setActionTitle("") });
  }

  function recordOutcomeForAction() {
    const actionId = outcomeActionId || completedActions[0]?.id;
    if (!actionId || !outcomeWhat.trim() || !outcomeResult.trim() || !outcomeLesson.trim() || !outcomeNext.trim()) return;
    recordOutcome.mutate({ actionId, values: { what_happened: outcomeWhat.trim(), result: outcomeResult.trim(), evidence: [], metrics: {}, lesson: outcomeLesson.trim(), next_step: outcomeNext.trim() } }, { onSuccess: () => { setOutcomeWhat(""); setOutcomeResult(""); setOutcomeLesson(""); setOutcomeNext(""); } });
  }

  const tabs: Array<[DetailTab, string]> = [["overview", "概览"], ["evidence", "证据"], ["validation", "验证计划"], ["research", "相关研究"], ["actions", "行动与结果"], ["technical", "技术详情"]];
  const canCreatePlan = !plan && ["review_ready", "validation_ready", "validated"].includes(detail.readiness);
  const feedbackItems = [
    { label: "有价值", onSelect: () => feedback.mutate({ feedback_type: "valuable" }), icon: <Check className="size-4" /> },
    { label: "证据不足", onSelect: () => feedback.mutate({ feedback_type: "evidence_insufficient" }) },
    { label: "稍后", onSelect: () => feedback.mutate({ feedback_type: "defer" }) },
    { label: "拒绝", onSelect: () => setRejectOpen(true), tone: "danger" as const },
  ].map((item) => ({ ...item, disabled: feedback.isPending }));
  return (
    <div className="space-y-5">
      <PageHeader title={detail.title} description={detail.description} action={<Button asChild variant="secondary"><Link to="/opportunities"><ArrowLeft className="size-4" />机会列表</Link></Button>} />
      <Card className="sticky top-16 z-10 border-signal/15 bg-white/95 backdrop-blur-lg">
        <CardContent className="p-4 sm:p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="text-sm font-semibold">{detail.problem}</p><p className="mt-1 line-clamp-1 text-xs leading-5 text-muted">面向：{detail.target_user}</p></div><div className="flex flex-wrap gap-2"><Badge variant="info">{statusLabels[detail.status]}</Badge><Badge variant={opportunityVariant(detail.readiness)}>{readinessLabels[detail.readiness]}</Badge></div></div><div className="mt-4 flex flex-wrap gap-2"><Button size="sm" disabled={createPlan.isPending || (!canCreatePlan && !plan)} onClick={() => { if (canCreatePlan) createPlan.mutate({}); else setTab(plan ? "validation" : "research"); }}>{createPlan.isPending ? "生成中…" : plan ? "继续验证" : canCreatePlan ? "创建验证计划" : "继续研究"}</Button><ActionMenu label="判断" items={feedbackItems} /></div></CardContent>
      </Card>
      <AlertDialog open={rejectOpen} onOpenChange={setRejectOpen}><AlertDialogContent><AlertDialogTitle>拒绝这个机会？</AlertDialogTitle><AlertDialogDescription>机会会保留在历史中并标记为已拒绝，后续不会继续作为当前验证入口。</AlertDialogDescription><div className="mt-5 flex justify-end gap-2"><AlertDialogCancel asChild><Button variant="ghost">返回</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={feedback.isPending} onClick={() => { feedback.mutate({ feedback_type: "reject" }); setRejectOpen(false); }}>{feedback.isPending ? "保存中…" : "确认拒绝"}</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
      <SegmentedTabs value={tab} onChange={setTab} label="机会详情标签页" items={tabs.map(([value, label]) => ({ value, label }))} />
      {showError ? <p className="rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">{errorMessage(showError)}</p> : null}
      {tab === "overview" ? <OverviewTab detail={detail} onCreatePlan={() => createPlan.mutate({})} planPending={createPlan.isPending} /> : null}
      {tab === "evidence" ? <EvidenceTab detail={detail} /> : null}
      {tab === "validation" ? <ValidationTab detail={detail} plan={plan} approvePending={approvePlan.isPending} researchPending={startResearch.isPending} resultPending={recordValidation.isPending} onCreatePlan={() => createPlan.mutate({})} createPending={createPlan.isPending} onApprove={() => plan && approvePlan.mutate(plan.id)} onResearch={() => plan && startResearch.mutate(plan.id)} outcome={validationOutcome} onOutcome={setValidationOutcome} what={validationWhat} onWhat={setValidationWhat} result={validationResult} onResult={setValidationResult} nextStep={validationNext} onNextStep={setValidationNext} onRecord={() => plan && validationWhat.trim() && validationResult.trim() && validationNext.trim() ? recordValidation.mutate({ planId: plan.id, values: { outcome: validationOutcome, what_happened: validationWhat.trim(), result: validationResult.trim(), evidence: [], next_step: validationNext.trim() } }) : undefined} /> : null}
      {tab === "research" ? <ResearchTab detail={detail} /> : null}
      {tab === "actions" ? <ActionsTab detail={detail} actionTitle={actionTitle} onActionTitle={setActionTitle} onCreate={createActionForOpportunity} createPending={createAction.isPending} onStatus={(action, status) => updateAction.mutate({ actionId: action.id, status })} updatePending={updateAction.isPending} completedActions={completedActions} outcomeActionId={outcomeActionId} onOutcomeAction={setOutcomeActionId} outcomeWhat={outcomeWhat} onOutcomeWhat={setOutcomeWhat} outcomeResult={outcomeResult} onOutcomeResult={setOutcomeResult} outcomeLesson={outcomeLesson} onOutcomeLesson={setOutcomeLesson} outcomeNext={outcomeNext} onOutcomeNext={setOutcomeNext} onRecordOutcome={recordOutcomeForAction} outcomePending={recordOutcome.isPending} /> : null}
      {tab === "technical" ? <TechnicalTab detail={detail} /> : null}
      <CollapsibleSection title="关联研究空间与来源" description="把机会放入长期上下文，或回到发现路径"><div className="flex flex-wrap items-center gap-3"><Target className="size-4 text-signal" /><span className="text-sm text-muted">成熟度来自证据、来源独立性和反向证据，不代替最终判断。</span>{spaces.data?.length ? <><select className="h-9 rounded-lg border border-line bg-white px-2 text-sm" value={spaceId || spaces.data[0].id} onChange={(event) => setSpaceId(event.currentTarget.value)} aria-label="选择研究空间">{spaces.data.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}</select><Button size="sm" variant="secondary" disabled={addToSpace.isPending} onClick={() => { addToSpace.mutate({ spaceId: spaceId || spaces.data?.[0]?.id || "" }); }}>{addToSpace.isPending ? "加入中…" : "加入研究空间"}<FolderPlus className="size-4" /></Button></> : <Button asChild size="sm" variant="secondary"><Link to="/spaces">先建立研究空间</Link></Button>}<Button size="sm" variant="ghost" onClick={() => { void navigate("/discoveries"); }}>查看发现路径 <ExternalLink className="size-3.5" /></Button></div></CollapsibleSection>
    </div>
  );
}

function OverviewTab({ detail, onCreatePlan, planPending }: { detail: OpportunityDetail; onCreatePlan: () => void; planPending: boolean }) {
  const unknowns = stringList(detail.unknowns);
  return <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]"><Card><CardHeader><p className="section-kicker">机会概览</p><h2 className="mt-1 font-display text-xl font-semibold">为什么现在值得看</h2></CardHeader><CardContent className="space-y-4"><InfoBlock label="机会是什么" value={detail.description} /><InfoBlock label="为什么是现在" value={detail.why_now} /><InfoBlock label="建议下一步" value={detail.next_step} /><div><p className="text-sm font-semibold">关键未知</p>{unknowns.length ? <ul className="mt-2 space-y-2 text-sm leading-5 text-muted">{unknowns.map((unknown) => <li key={unknown} className="rounded-lg bg-paper px-3 py-2">{unknown}</li>)}</ul> : <p className="mt-2 text-sm text-muted">暂未记录关键未知。</p>}</div></CardContent></Card><Card><CardHeader><p className="section-kicker">成熟度</p><h2 className="mt-1 font-display text-xl font-semibold">成熟度与下一步</h2></CardHeader><CardContent className="space-y-3"><div className="grid grid-cols-2 gap-2"><Metric label="证据强度" value={scorePercent(detail.scores.evidence_strength)} /><Metric label="来源独立" value={scorePercent(detail.scores.source_independence)} /><Metric label="可行动性" value={scorePercent(detail.scores.actionability)} /><Metric label="反向证据" value={scorePercent(detail.scores.counterevidence)} /></div><p className="rounded-xl bg-warning/8 p-3 text-sm leading-5 text-muted">{detail.readiness === "validation_ready" || detail.readiness === "validated" ? "当前证据允许进入用户确认的验证流程。" : "当前更适合补充证据或继续研究，不应直接当成已验证机会。"}</p><Button disabled={planPending || !["review_ready", "validation_ready", "validated"].includes(detail.readiness)} onClick={onCreatePlan}><FileCheck2 className="size-4" />{planPending ? "生成中…" : "创建验证计划"}</Button></CardContent></Card>{detail.opportunity_type === "content_opportunity" ? <ContentDetails details={detail.content_details} /> : null}</div>;
}

function InfoBlock({ label, value }: { label: string; value: string }) { return <div><p className="text-sm font-semibold">{label}</p><p className="mt-1 text-sm leading-6 text-muted">{value}</p></div>; }

function EvidenceTab({ detail }: { detail: OpportunityDetail }) {
  const grouped = ["core", "supporting", "counterevidence", "background"];
  return <div className="space-y-5"><Card><CardHeader><p className="section-kicker">证据包 · {detail.sources.length}</p><h2 className="mt-1 font-display text-xl font-semibold">支持、反向证据和未知</h2></CardHeader><CardContent className="space-y-4">{grouped.map((role) => { const sources = detail.sources.filter((source) => source.source_role === role); return <div key={role}><div className="flex items-center justify-between gap-3"><h3 className="font-semibold">{sourceRoleLabels[role]}</h3><span className="text-xs text-muted">{sources.length} 条</span></div>{sources.length ? <div className="mt-2 grid gap-2 md:grid-cols-2">{sources.map((source) => <article key={source.id} className="rounded-xl border border-line p-3 text-sm"><div className="flex items-start justify-between gap-2"><p className="font-semibold">{source.source_title ?? "未命名证据"}</p><Badge variant={source.is_repost ? "warning" : role === "counterevidence" ? "danger" : "success"}>{source.is_repost ? "转载合并" : sourceRoleLabels[role]}</Badge></div><p className="mt-2 leading-5 text-muted">{source.support_explanation}</p><p className="mt-2 text-xs text-muted">{source.source_platform ?? "未知平台"} · {source.independent_group ?? "独立性未标记"} · {source.evidence_kind}</p>{source.content_id ? <Link className="mt-2 inline-flex items-center gap-1 text-xs text-signal hover:underline" to={`/memory/contents/${encodeURIComponent(source.content_id)}`}>打开证据 <ExternalLink className="size-3" /></Link> : null}</article>)}</div> : <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-sm text-muted">暂未记录。</p>}</div>; })}</CardContent></Card></div>;
}

function ValidationTab({ detail, plan, approvePending, researchPending, resultPending, onCreatePlan, createPending, onApprove, onResearch, outcome, onOutcome, what, onWhat, result, onResult, nextStep, onNextStep, onRecord }: { detail: OpportunityDetail; plan: OpportunityPlan | undefined; approvePending: boolean; researchPending: boolean; resultPending: boolean; onCreatePlan: () => void; createPending: boolean; onApprove: () => void; onResearch: () => void; outcome: string; onOutcome: (value: string) => void; what: string; onWhat: (value: string) => void; result: string; onResult: (value: string) => void; nextStep: string; onNextStep: (value: string) => void; onRecord: () => void }) {
  if (!plan) return <Card className="p-8 text-center"><FileCheck2 className="mx-auto size-8 text-signal" /><h2 className="mt-3 font-display text-xl font-semibold">还没有验证计划</h2><p className="mt-2 text-sm text-muted">只有达到“待用户判断”或更高成熟度的机会，才可以生成最小验证动作。</p><Button className="mt-5" disabled={createPending || !["review_ready", "validation_ready", "validated"].includes(detail.readiness)} onClick={onCreatePlan}>创建验证计划</Button></Card>;
  return <div className="space-y-3"><Card><CardHeader><p className="section-kicker">验证计划 · {planStatusLabels[plan.status]}</p><h2 className="mt-1 font-display text-xl font-semibold">先验证最关键的假设</h2></CardHeader><CardContent className="space-y-4"><InfoBlock label="机会假设" value={plan.opportunity_hypothesis} /><InfoBlock label="关键假设" value={plan.critical_assumptions.join("；") || "未记录"} /><InfoBlock label="最小验证动作" value={plan.cheapest_next_test} /><InfoBlock label="成功标准" value={plan.success_criteria.join("；") || "未记录"} /><InfoBlock label="失败标准" value={plan.failure_criteria.join("；") || "未记录"} /><div className="flex flex-wrap gap-2">{plan.status === "draft" ? <Button disabled={approvePending} onClick={onApprove}>{approvePending ? "确认中…" : "我确认这个验证计划"}</Button> : null}{plan.status === "ready" ? <Button disabled={researchPending} onClick={onResearch}>{researchPending ? "创建研究中…" : "创建独立验证研究"}<ArrowRight className="size-4" /></Button> : null}</div></CardContent></Card><CollapsibleSection title="记录真实验证结果" description="完成验证后记录发生了什么、结果和下一步" count={plan.results.length}><div className="space-y-3"><select className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm" value={outcome} onChange={(event) => onOutcome(event.currentTarget.value)} aria-label="验证结果"><option value="supported">支持</option><option value="partially_supported">部分支持</option><option value="not_supported">不支持</option><option value="inconclusive">无法判断</option></select><textarea className="min-h-20 w-full rounded-xl border border-line px-3 py-2 text-sm" value={what} onChange={(event) => onWhat(event.currentTarget.value)} placeholder="发生了什么？" /><textarea className="min-h-20 w-full rounded-xl border border-line px-3 py-2 text-sm" value={result} onChange={(event) => onResult(event.currentTarget.value)} placeholder="结果说明" /><Input value={nextStep} onChange={(event) => onNextStep(event.currentTarget.value)} placeholder="下一步" /><Button variant="secondary" disabled={resultPending || !what.trim() || !result.trim() || !nextStep.trim() || !["ready", "in_progress"].includes(plan.status)} onClick={onRecord}>{resultPending ? "保存中…" : "保存真实结果"}</Button>{plan.results.length ? <div className="border-t border-line pt-3 text-sm"><p className="font-semibold">历史结果</p>{plan.results.map((item) => <p key={item.id} className="mt-2 rounded-lg bg-paper p-2 text-muted">{item.outcome} · {item.result}</p>)}</div> : null}</div></CollapsibleSection></div>;
}

function ResearchTab({ detail }: { detail: OpportunityDetail }) {
  return <div className="grid gap-5 md:grid-cols-2"><Card><CardHeader><p className="section-kicker">证据来源链</p><h2 className="mt-1 font-display text-xl font-semibold">发现路径</h2></CardHeader><CardContent className="space-y-3 text-sm">{detail.related_research_task_id ? <Link className="flex items-center gap-2 text-signal hover:underline" to="/research">来自研究任务 <ExternalLink className="size-3.5" /></Link> : <p className="text-muted">没有直接关联的研究任务。</p>}{detail.related_discovery_candidate_id ? <Link className="flex items-center gap-2 text-signal hover:underline" to={`/discoveries/${encodeURIComponent(detail.related_discovery_candidate_id)}`}>来自发现候选 <ExternalLink className="size-3.5" /></Link> : null}{detail.related_monitoring_mission_id ? <Link className="flex items-center gap-2 text-signal hover:underline" to={`/monitoring/${encodeURIComponent(detail.related_monitoring_mission_id)}`}>来自监控任务 <ExternalLink className="size-3.5" /></Link> : null}</CardContent></Card><Card><CardHeader><p className="section-kicker">未解决问题</p><h2 className="mt-1 font-display text-xl font-semibold">还需要知道什么</h2></CardHeader><CardContent><ul className="space-y-2 text-sm leading-5 text-muted">{(detail.unknowns.length ? detail.unknowns : ["没有新增未知项；仍需由用户确认下一步。"]).map((unknown) => <li key={unknown} className="rounded-lg bg-paper p-3">{unknown}</li>)}</ul></CardContent></Card></div>;
}

function ActionsTab({ detail, actionTitle, onActionTitle, onCreate, createPending, onStatus, updatePending, completedActions, outcomeActionId, onOutcomeAction, outcomeWhat, onOutcomeWhat, outcomeResult, onOutcomeResult, outcomeLesson, onOutcomeLesson, outcomeNext, onOutcomeNext, onRecordOutcome, outcomePending }: { detail: OpportunityDetail; actionTitle: string; onActionTitle: (value: string) => void; onCreate: () => void; createPending: boolean; onStatus: (action: OpportunityAction, status: "approved" | "in_progress" | "completed" | "abandoned") => void; updatePending: boolean; completedActions: OpportunityAction[]; outcomeActionId: string; onOutcomeAction: (value: string) => void; outcomeWhat: string; onOutcomeWhat: (value: string) => void; outcomeResult: string; onOutcomeResult: (value: string) => void; outcomeLesson: string; onOutcomeLesson: (value: string) => void; outcomeNext: string; onOutcomeNext: (value: string) => void; onRecordOutcome: () => void; outcomePending: boolean }) {
  const [abandonId, setAbandonId] = useState<string | null>(null);
  const abandonAction = detail.actions.find((action) => action.id === abandonId);
  return <div className="space-y-3"><CollapsibleSection title="提出一个最小行动" description="准备好执行时再填写行动" count={detail.actions.length}><div className="flex flex-col gap-3 sm:flex-row"><Input className="flex-1" value={actionTitle} onChange={(event) => onActionTitle(event.currentTarget.value)} placeholder="例如：访谈 3 位正在经历这个问题的用户" aria-label="行动标题" /><Button disabled={createPending} onClick={onCreate}><Plus className="size-4" />{createPending ? "提出中…" : "提出行动"}</Button></div></CollapsibleSection><Card><CardHeader><p className="section-kicker">行动记录</p><h2 className="mt-1 font-display text-xl font-semibold">已提出的行动</h2></CardHeader><CardContent className="space-y-3">{detail.actions.length ? detail.actions.map((action) => <article key={action.id} className="rounded-xl border border-line p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="font-semibold">{action.title}</p><p className="mt-1 text-sm leading-5 text-muted">{action.why}</p><p className="mt-2 text-xs text-muted">成功标准：{action.success_criteria}</p></div><Badge variant={action.status === "completed" ? "success" : action.status === "abandoned" ? "neutral" : "info"}>{actionStatusLabels[action.status]}</Badge></div><div className="mt-3 flex flex-wrap gap-2">{action.status === "proposed" ? <Button size="sm" onClick={() => onStatus(action, "approved")} disabled={updatePending}>批准</Button> : null}{action.status === "approved" ? <Button size="sm" onClick={() => onStatus(action, "in_progress")} disabled={updatePending}>开始</Button> : null}{action.status === "in_progress" ? <Button size="sm" onClick={() => onStatus(action, "completed")} disabled={updatePending}>标记完成</Button> : null}{["proposed", "approved", "in_progress"].includes(action.status) ? <Button size="sm" variant="ghost" onClick={() => setAbandonId(action.id)} disabled={updatePending}>放弃</Button> : null}</div>{action.outcomes.map((outcome) => <div key={outcome.id} className="mt-3 rounded-lg bg-paper p-3 text-sm"><p className="font-semibold">结果：{outcome.result}</p><p className="mt-1 text-muted">经验：{outcome.lesson}</p></div>)}</article>) : <p className="rounded-xl bg-paper p-4 text-sm text-muted">还没有行动。先接受一个机会，再由用户批准具体行动。</p>}</CardContent></Card><CollapsibleSection title="记录行动结果" description="完成行动后记录结果，更新长期记忆" count={completedActions.length}><div className="space-y-3">{completedActions.length ? <select className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm" value={outcomeActionId || completedActions[0].id} onChange={(event) => onOutcomeAction(event.currentTarget.value)} aria-label="选择已完成行动">{completedActions.map((action) => <option key={action.id} value={action.id}>{action.title}</option>)}</select> : <p className="rounded-lg bg-paper p-3 text-sm text-muted">完成一个行动后，才能记录结果并更新长期记忆。</p>}<textarea className="min-h-20 w-full rounded-xl border border-line px-3 py-2 text-sm" value={outcomeWhat} onChange={(event) => onOutcomeWhat(event.currentTarget.value)} placeholder="发生了什么？" disabled={!completedActions.length} aria-label="行动发生了什么" /><textarea className="min-h-20 w-full rounded-xl border border-line px-3 py-2 text-sm" value={outcomeResult} onChange={(event) => onOutcomeResult(event.currentTarget.value)} placeholder="结果" disabled={!completedActions.length} aria-label="行动结果" /><Input value={outcomeLesson} onChange={(event) => onOutcomeLesson(event.currentTarget.value)} placeholder="经验教训" disabled={!completedActions.length} aria-label="经验教训" /><Input value={outcomeNext} onChange={(event) => onOutcomeNext(event.currentTarget.value)} placeholder="下一步" disabled={!completedActions.length} aria-label="行动下一步" /><Button variant="secondary" disabled={outcomePending || !completedActions.length || !outcomeWhat.trim() || !outcomeResult.trim() || !outcomeLesson.trim() || !outcomeNext.trim()} onClick={onRecordOutcome}>{outcomePending ? "保存中…" : "保存结果并更新记忆"}</Button></div></CollapsibleSection><AlertDialog open={Boolean(abandonAction)} onOpenChange={(open) => { if (!open) setAbandonId(null); }}><AlertDialogContent><AlertDialogTitle>放弃这个行动？</AlertDialogTitle><AlertDialogDescription>行动会保留在记录中并标记为已放弃，不会再作为当前待执行动作。</AlertDialogDescription><div className="mt-5 flex justify-end gap-2"><AlertDialogCancel asChild><Button variant="ghost">返回</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={updatePending} onClick={() => { if (abandonAction) onStatus(abandonAction, "abandoned"); setAbandonId(null); }}>{updatePending ? "保存中…" : "确认放弃"}</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog></div>;
}

function ContentDetails({ details }: { details: Record<string, unknown> }) {
  const angles = stringList(details.angles);
  return <Card className="lg:col-span-2"><CardHeader><p className="section-kicker">内容机会</p><h2 className="mt-1 font-display text-xl font-semibold">内容缺口，而不是伪热点</h2></CardHeader><CardContent className="grid gap-4 md:grid-cols-2"><InfoBlock label="目标受众" value={stringValue(details.audience)} /><InfoBlock label="内容缺口" value={stringValue(details.content_gap)} /><InfoBlock label="饱和度说明" value={stringValue(details.saturation_statement)} /><div><p className="text-sm font-semibold">差异化角度</p>{angles.length ? <ul className="mt-2 space-y-2 text-sm text-muted">{angles.map((angle) => <li key={angle} className="rounded-lg bg-paper p-2">{angle}</li>)}</ul> : <p className="mt-2 text-sm text-muted">暂无来自证据的角度。</p>}</div></CardContent></Card>;
}

function TechnicalTab({ detail }: { detail: OpportunityDetail }) {
  const scoreLabels: Record<string, string> = { evidence_strength: "证据强度", source_independence: "来源独立", actionability: "可行动性", counterevidence: "反向证据", novelty: "新颖性", relevance: "相关性" };
  return <div className="grid gap-5 md:grid-cols-2"><Card><CardHeader><p className="section-kicker">历史版本</p><h2 className="mt-1 font-display text-xl font-semibold">机会变化记录</h2></CardHeader><CardContent className="space-y-2">{detail.versions.map((version) => <div key={version.id} className="rounded-lg bg-paper p-3 text-sm"><div className="flex justify-between gap-2"><span>版本 {version.version}</span><span className="text-muted">{version.change_reason}</span></div><p className="mt-1 text-xs text-muted">{version.readiness_before ?? "初始"} → {version.readiness_after}</p></div>)}</CardContent></Card><Card><CardHeader><p className="section-kicker">技术详情</p><h2 className="mt-1 font-display text-xl font-semibold">评分解释</h2></CardHeader><CardContent className="space-y-2">{Object.entries(detail.scores).map(([key, value]) => <div key={key} className="flex items-center justify-between gap-3 text-sm"><span className="text-muted">{scoreLabels[key] ?? "评分项"}</span><span className="font-semibold">{scorePercent(value)}</span></div>)}<p className="border-t border-line pt-3 text-xs leading-5 text-muted">{stringValue(detail.score_explanation.summary, "评分只用于解释证据准备度，不代表商业成功概率。")} </p></CardContent></Card></div>;
}

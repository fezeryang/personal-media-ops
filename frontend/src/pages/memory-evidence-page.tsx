import { BookOpenCheck, FileQuestion, Library, Link2, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";

import type { ResearchTaskDetail } from "../api/research";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { FilterBar } from "../components/ui/filter-bar";
import { MasterDetailLayout } from "../components/ui/master-detail-layout";
import { SegmentedTabs } from "../components/ui/segmented-tabs";
import {
  useResearchTaskQuery,
  useResearchTasksQuery,
} from "../features/research/hooks/use-research-queries";

const supportLabels: Record<string, string> = {
  direct: "直接证据",
  contradictory: "反向证据",
  contextual: "背景证据",
  background: "背景证据",
};

const supportVariants: Record<string, "info" | "danger" | "neutral"> = {
  direct: "info",
  contradictory: "danger",
  contextual: "neutral",
  background: "neutral",
};

const memoryLabels: Record<string, string> = {
  fact: "已确认事实",
  inference: "研究推测",
  preference: "用户偏好",
  change: "变化记忆",
};

const unknownLabels: Record<string, string> = {
  open: "待处理",
  discovered: "已发现",
  verified: "已验证",
  unresolved: "仍未解决",
};

function readableValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "未记录";
  try {
    return JSON.stringify(value);
  } catch {
    return "无法展示";
  }
}

function taskStatusLabel(status: string): string {
  return {
    Draft: "草稿",
    Planning: "规划中",
    Researching: "研究中",
    WaitingCrawl: "等待采集",
    WaitingLogin: "等待登录",
    Summarizing: "整理中",
    AwaitingReview: "待确认",
    Done: "已完成",
    BudgetExceeded: "预算触发",
    Failed: "失败",
    Cancelled: "已取消",
  }[status] ?? status;
}

export function MemoryEvidencePage() {
  const tasks = useResearchTasksQuery();
  const [selectedId, setSelectedId] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("updated");
  const effectiveId = selectedId || tasks.data?.[0]?.id || "";
  const detail = useResearchTaskQuery(effectiveId);
  const filteredTasks = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return [...(tasks.data ?? [])]
      .filter((task) => !needle || task.objective.toLowerCase().includes(needle))
      .filter((task) => status === "all" || (status === "active" ? !["Done", "Failed", "Cancelled"].includes(task.status) : status === "done" ? task.status === "Done" : ["Failed", "Cancelled"].includes(task.status)))
      .sort((left, right) => sort === "created" ? right.created_at.localeCompare(left.created_at) : right.updated_at.localeCompare(left.updated_at));
  }, [search, sort, status, tasks.data]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="记忆与证据"
        description="按研究记录查看沉淀的结论、证据、未解决问题和长期记忆。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link to="/research"><Sparkles className="size-4" />开始新研究</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/tools/crawls"><Library className="size-4" />工具中心</Link>
            </Button>
          </div>
        }
      />

      {tasks.isError ? (
        <ErrorState title="研究记忆加载失败" error={tasks.error} onRetry={() => void tasks.refetch()} />
      ) : (
        <>
          <FilterBar search={search} onSearchChange={setSearch} searchPlaceholder="搜索研究记录" resultCount={filteredTasks.length} filters={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">状态</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.currentTarget.value)} aria-label="记忆研究状态"><option value="all">全部</option><option value="active">进行中</option><option value="done">已完成</option><option value="failed">失败或取消</option></select></label>} sort={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">排序</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={sort} onChange={(event) => setSort(event.currentTarget.value)} aria-label="记忆研究排序"><option value="updated">最近更新</option><option value="created">最近创建</option></select></label>} chips={[...(status !== "all" ? [{ label: `状态：${status === "active" ? "进行中" : status === "done" ? "已完成" : "失败或取消"}`, onRemove: () => setStatus("all") }] : []), ...(sort !== "updated" ? [{ label: "排序：最近创建", onRemove: () => setSort("updated") }] : [])]} onClear={() => { setSearch(""); setStatus("all"); setSort("updated"); }} />
          <MasterDetailLayout
            listLabel="研究记录列表"
            storageKey="mediaops.master-detail.memory.collapsed"
            list={<Card className="overflow-hidden">
            <CardHeader className="border-b border-line pb-4">
              <p className="section-kicker">研究记录</p>
              <h2 className="mt-1 font-display text-xl font-semibold">研究记录</h2>
            </CardHeader>
            <CardContent className="space-y-2 p-3">
              {tasks.isPending
                ? Array.from({ length: 3 }, (_, index) => <div key={index} className="h-20 animate-pulse rounded-xl bg-paper" />)
                : null}
              {!tasks.isPending && filteredTasks.length === 0 ? (
                <p className="rounded-xl bg-paper p-5 text-sm leading-6 text-muted">还没有研究记忆。完成一次研究后，结论和证据会在这里按任务保留。</p>
              ) : null}
              {filteredTasks.map((task) => (
                <button
                  key={task.id}
                  type="button"
                  onClick={() => setSelectedId(task.id)}
                  className={`w-full rounded-xl border p-3 text-left transition ${effectiveId === task.id ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="line-clamp-3 text-sm font-semibold">{task.objective}</span>
                    <Badge variant={task.status === "Done" ? "success" : "info"}>{taskStatusLabel(task.status)}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted">{task.finding_count} 条结论 · {task.event_count} 个事件 · 更新于 {new Date(task.updated_at).toLocaleString("zh-CN")}</p>
                </button>
              ))}
            </CardContent>
          </Card>}
            detail={detail.isError ? (
            <ErrorState title="研究记忆详情加载失败" error={detail.error} onRetry={() => void detail.refetch()} />
          ) : detail.data ? (
            <MemoryEvidenceDetail task={detail.data} />
          ) : (
            <Card className="grid min-h-80 place-items-center p-8 text-center">
              <div><BookOpenCheck className="mx-auto size-8 text-muted" /><p className="mt-3 text-sm text-muted">选择一条研究记录，查看它沉淀的结论和证据。</p></div>
            </Card>
          )}
          />
        </>
      )}
    </div>
  );
}

function MemoryEvidenceDetail({ task }: { task: ResearchTaskDetail }) {
  const unknowns = task.unknowns ?? [];
  const memoryItems = task.memory_items ?? [];
  const evidence = useMemo(
    () => task.findings.flatMap((finding) => finding.evidence),
    [task.findings],
  );
  const evidenceCounts = evidence.reduce<Record<string, number>>((counts, item) => {
    const supportType = item.support_type ?? "contextual";
    counts[supportType] = (counts[supportType] ?? 0) + 1;
    return counts;
  }, {});
  const [tab, setTab] = useState<"overview" | "findings" | "evidence" | "unknowns" | "memory">("overview");
  const [evidenceSearch, setEvidenceSearch] = useState("");
  const [support, setSupport] = useState("all");
  const [platform, setPlatform] = useState("all");
  const [memoryView, setMemoryView] = useState("current");
  const [memoryKind, setMemoryKind] = useState("all");
  const [memorySearch, setMemorySearch] = useState("");
  const platforms = useMemo(() => Array.from(new Set(evidence.map((item) => item.platform).filter((value): value is string => Boolean(value)))).sort(), [evidence]);
  const visibleEvidence = useMemo(() => {
    const needle = evidenceSearch.trim().toLowerCase();
    return evidence.filter((item) => {
      const type = item.support_type ?? "contextual";
      return (!needle || `${item.title ?? ""} ${item.support_explanation ?? ""} ${item.author_name ?? ""}`.toLowerCase().includes(needle)) && (support === "all" || type === support) && (platform === "all" || item.platform === platform);
    });
  }, [evidence, evidenceSearch, platform, support]);
  const visibleMemory = memoryItems.filter((item) => (memoryView === "all" || (memoryView === "current" ? item.is_current : !item.is_current)) && (memoryKind === "all" || item.memory_type === memoryKind) && (!memorySearch.trim() || `${item.memory_key} ${readableValue(item.value)}`.toLowerCase().includes(memorySearch.trim().toLowerCase())));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="border-b border-line pb-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="section-kicker">研究沉淀</p>
              <h2 className="mt-1 break-words font-display text-2xl font-semibold">{task.objective}</h2>
              <p className="mt-2 text-sm text-muted">{taskStatusLabel(task.status)} · 最近更新 {new Date(task.updated_at).toLocaleDateString("zh-CN")}</p>
            </div>
            <Badge variant={task.findings.length > 0 ? "success" : "neutral"}>{task.findings.length} 条结论</Badge>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
          <Metric label="结论" value={String(task.findings.length)} />
          <Metric label="证据" value={String(evidence.length)} />
          <Metric label="未解决问题" value={String(unknowns.length)} />
          <Metric label="长期记忆" value={String(memoryItems.length)} />
        </CardContent>
      </Card>
      <SegmentedTabs value={tab} onChange={setTab} label="记忆与证据详情" items={[{ value: "overview", label: "概览" }, { value: "findings", label: "结论", count: task.findings.length }, { value: "evidence", label: "证据", count: evidence.length }, { value: "unknowns", label: "未解决", count: unknowns.length }, { value: "memory", label: "记忆", count: memoryItems.length }]} />

      {tab === "overview" ? <div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><p className="section-kicker">研究主题</p><h3 className="mt-1 font-display text-xl font-semibold">这条记录沉淀了什么</h3></CardHeader><CardContent className="space-y-3"><p className="text-sm leading-6 text-muted">结论、证据和记忆已经分开整理。需要核对来源时再打开证据，不必在概览里阅读全文。</p><div className="grid grid-cols-2 gap-2"><Metric label="结论" value={String(task.findings.length)} /><Metric label="证据" value={String(evidence.length)} /><Metric label="未解决" value={String(unknowns.length)} /><Metric label="记忆" value={String(memoryItems.length)} /></div></CardContent></Card><Card><CardHeader><p className="section-kicker">下一步</p><h3 className="mt-1 font-display text-xl font-semibold">从哪里继续</h3></CardHeader><CardContent className="space-y-3"><p className="text-sm leading-6 text-muted">优先查看未解决问题或反向证据；如果需要验证具体说法，再进入证据列表查看来源。</p><div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => setTab(unknowns.length ? "unknowns" : "evidence")}>{unknowns.length ? "查看未解决问题" : "查看证据"}</Button><Button asChild variant="ghost"><Link to="/research">继续研究</Link></Button></div></CardContent></Card></div> : null}

      {tab === "findings" ? <Card>
          <CardHeader><p className="section-kicker">结论关系</p><h3 className="mt-1 font-display text-xl font-semibold">结论与证据关系</h3></CardHeader>
          <CardContent className="space-y-3">
            {task.findings.length === 0 ? <Empty text="这条研究还没有可引用的结论。" /> : task.findings.map((finding) => (
              <article key={finding.id} className="rounded-xl border border-line p-4">
                <div className="flex flex-wrap items-center gap-2"><Badge variant={finding.kind === "fact" ? "info" : "warning"}>{finding.kind === "fact" ? "事实" : "推测"}</Badge><span className="text-xs text-muted">第 {finding.round_number} 轮</span></div>
                <p className="mt-3 text-sm leading-6">{finding.statement}</p>
                {finding.derivation ? <p className="mt-2 text-xs leading-5 text-muted">推导：{finding.derivation}</p> : null}
                <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-xs leading-5 text-muted">反向证据：{finding.counterevidence_explanation || "未记录"}</p>
              </article>
            ))}
          </CardContent>
        </Card> : null}

      {tab === "evidence" ? <div className="space-y-3"><FilterBar search={evidenceSearch} onSearchChange={setEvidenceSearch} searchPlaceholder="搜索证据标题或说明" resultCount={visibleEvidence.length} filters={<><label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">用途</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={support} onChange={(event) => setSupport(event.currentTarget.value)} aria-label="证据用途"><option value="all">全部</option><option value="direct">直接</option><option value="contradictory">反向</option><option value="contextual">背景</option></select></label><label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">平台</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={platform} onChange={(event) => setPlatform(event.currentTarget.value)} aria-label="证据平台"><option value="all">全部</option>{platforms.map((value) => <option key={value} value={value}>{value}</option>)}</select></label></>} chips={[...(support !== "all" ? [{ label: `用途：${supportLabels[support] ?? support}`, onRemove: () => setSupport("all") }] : []), ...(platform !== "all" ? [{ label: `平台：${platform}`, onRemove: () => setPlatform("all") }] : [])]} onClear={() => { setEvidenceSearch(""); setSupport("all"); setPlatform("all"); }} /><Card><CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">证据用途分布</p><h3 className="mt-1 font-display text-xl font-semibold">支持、反向与背景</h3></div><Link2 className="size-5 text-signal" /></div></CardHeader><CardContent className="space-y-3"><div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{[["direct", "直接"], ["contradictory", "反向"], ["contextual", "背景"], ["background", "背景"]].map(([key, label]) => <Metric key={key} label={label} value={String(evidenceCounts[key] ?? 0)} />)}</div>{visibleEvidence.length === 0 ? <Empty text="没有符合条件的证据。" /> : visibleEvidence.map((item) => { const supportType = item.support_type ?? "contextual"; return <article key={`${item.content_id}-${supportType}`} className="rounded-xl border border-line p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="break-words text-sm font-semibold">{item.title ?? "未命名证据"}</p><p className="mt-1 text-xs text-muted">{item.platform ?? "未知平台"} · {item.author_name ?? "未知作者"}</p></div><Badge variant={supportVariants[supportType] ?? "neutral"}>{supportLabels[supportType] ?? "背景证据"}</Badge></div><p className="mt-2 text-xs leading-5 text-muted">{item.support_explanation ?? "未记录证据说明。"}</p><Link className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-signal hover:underline" to={`/memory/contents/${encodeURIComponent(item.content_id)}`}>浏览来源资料 <Link2 className="size-3" /></Link></article>; })}</CardContent></Card></div> : null}

      {tab === "unknowns" ? <Card>
          <CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">未解决问题</p><h3 className="mt-1 font-display text-xl font-semibold">数据缺口</h3></div><FileQuestion className="size-5 text-signal" /></div></CardHeader>
          <CardContent className="space-y-2">{unknowns.length === 0 ? <Empty text="当前没有记录的数据缺口。" /> : unknowns.map((unknown) => <article key={unknown.id} className="rounded-xl border border-line p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold">{unknown.unknown}</p><Badge variant={unknown.status === "verified" ? "success" : "warning"}>{unknownLabels[unknown.status] ?? unknown.status}</Badge></div><p className="mt-2 text-xs text-muted">优先级 {unknown.priority} · 已关联证据 {unknown.evidence_count} 条</p>{unknown.resolution ? <p className="mt-2 text-xs leading-5 text-muted">结论：{unknown.resolution}</p> : null}</article>)}</CardContent>
        </Card> : null}

      {tab === "memory" ? <Card>
          <CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">长期记忆</p><h3 className="mt-1 font-display text-xl font-semibold">长期记忆来源</h3></div><BookOpenCheck className="size-5 text-signal" /></div></CardHeader>
          <CardContent className="space-y-3"><FilterBar search={memorySearch} onSearchChange={setMemorySearch} searchPlaceholder="搜索记忆键或内容" resultCount={visibleMemory.length} filters={<><label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">版本</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={memoryView} onChange={(event) => setMemoryView(event.currentTarget.value)} aria-label="记忆版本"><option value="current">当前</option><option value="history">历史</option><option value="all">全部</option></select></label><label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">类型</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={memoryKind} onChange={(event) => setMemoryKind(event.currentTarget.value)} aria-label="记忆类型"><option value="all">全部</option>{Object.entries(memoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></>} onClear={() => { setMemorySearch(""); setMemoryView("current"); setMemoryKind("all"); }} chips={[...(memoryView !== "current" ? [{ label: `版本：${memoryView === "history" ? "历史" : "全部"}`, onRemove: () => setMemoryView("current") }] : []), ...(memoryKind !== "all" ? [{ label: `类型：${memoryLabels[memoryKind] ?? memoryKind}`, onRemove: () => setMemoryKind("all") }] : [])]} /><div className="space-y-2">{visibleMemory.length === 0 ? <Empty text="尚未写入符合条件的长期记忆。" /> : visibleMemory.map((memory) => <article key={memory.id} className="rounded-xl border border-line p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="break-words text-sm font-semibold">{memory.memory_key}</p><Badge variant={memory.is_current ? "info" : "neutral"}>{memory.is_current ? "当前" : "历史"}</Badge></div><p className="mt-2 text-xs leading-5 text-muted">{memoryLabels[memory.memory_type] ?? "研究记忆"} · 置信度 {(memory.confidence * 100).toFixed(0)}%</p><p className="mt-1 text-sm leading-5">{readableValue(memory.value)}</p><details className="mt-2"><summary className="cursor-pointer text-xs font-semibold text-muted">技术详情</summary><p className="mt-1 break-all text-[11px] text-muted">来源标识：{memory.source_content_id ?? memory.source_query_id ?? memory.source_finding_id ?? "未记录"}</p></details></article>)}</div></CardContent>
        </Card> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-xl bg-paper p-4 text-sm leading-6 text-muted">{text}</p>;
}

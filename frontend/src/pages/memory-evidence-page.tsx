import { BookOpenCheck, FileQuestion, Library, Link2, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";

import type { ResearchTaskDetail } from "../api/research";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
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
  const effectiveId = selectedId || tasks.data?.[0]?.id || "";
  const detail = useResearchTaskQuery(effectiveId);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Long-term memory · evidence"
        title="记忆与证据"
        description="这里保存研究结论、直接与反向证据、未解决问题和长期记忆来源。原始资料只作为可追溯证据被引用，不是主工作流。"
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
        <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
          <Card className="h-fit overflow-hidden">
            <CardHeader className="border-b border-line pb-4">
              <p className="section-kicker">Research memory</p>
              <h2 className="mt-1 font-display text-xl font-semibold">研究记录</h2>
            </CardHeader>
            <CardContent className="space-y-2 p-3">
              {tasks.isPending
                ? Array.from({ length: 3 }, (_, index) => <div key={index} className="h-20 animate-pulse rounded-xl bg-paper" />)
                : null}
              {!tasks.isPending && tasks.data?.length === 0 ? (
                <p className="rounded-xl bg-paper p-5 text-sm leading-6 text-muted">还没有研究记忆。完成一次研究后，结论和证据会在这里按任务保留。</p>
              ) : null}
              {tasks.data?.map((task) => (
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
          </Card>

          {detail.isError ? (
            <ErrorState title="研究记忆详情加载失败" error={detail.error} onRetry={() => void detail.refetch()} />
          ) : detail.data ? (
            <MemoryEvidenceDetail task={detail.data} />
          ) : (
            <Card className="grid min-h-80 place-items-center p-8 text-center">
              <div><BookOpenCheck className="mx-auto size-8 text-muted" /><p className="mt-3 text-sm text-muted">选择一条研究记录，查看它沉淀的结论和证据。</p></div>
            </Card>
          )}
        </section>
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

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="border-b border-line pb-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="section-kicker">Research memory snapshot</p>
              <h2 className="mt-1 break-words font-display text-2xl font-semibold">{task.objective}</h2>
              <p className="mt-2 text-sm text-muted">{taskStatusLabel(task.status)} · {task.platforms.join("、") || "未指定平台"}</p>
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

      <section className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><p className="section-kicker">Findings</p><h3 className="mt-1 font-display text-xl font-semibold">结论与证据关系</h3></CardHeader>
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
        </Card>

        <Card>
          <CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">Evidence roles</p><h3 className="mt-1 font-display text-xl font-semibold">证据用途分布</h3></div><Link2 className="size-5 text-signal" /></div></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[["direct", "直接"], ["contradictory", "反向"], ["contextual", "背景"], ["background", "背景"]].map(([key, label]) => <Metric key={key} label={label} value={String(evidenceCounts[key] ?? 0)} />)}
            </div>
            {evidence.length === 0 ? <Empty text="暂时没有已绑定的证据来源。" /> : evidence.map((item) => {
              const supportType = item.support_type ?? "contextual";
              return (
                <article key={`${item.content_id}-${supportType}`} className="rounded-xl border border-line p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="break-words text-sm font-semibold">{item.title ?? item.content_id}</p><p className="mt-1 text-xs text-muted">{item.platform ?? "未知平台"} · {item.author_name ?? "未知作者"}</p></div><Badge variant={supportVariants[supportType] ?? "neutral"}>{supportLabels[supportType] ?? supportType}</Badge></div>
                  <p className="mt-2 text-xs leading-5 text-muted">{item.support_explanation ?? "未记录证据说明。"}</p>
                  <Link className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-signal hover:underline" to={`/memory/contents/${encodeURIComponent(item.content_id)}`}>浏览来源资料 <Link2 className="size-3" /></Link>
                </article>
              );
            })}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">Unresolved questions</p><h3 className="mt-1 font-display text-xl font-semibold">数据缺口</h3></div><FileQuestion className="size-5 text-signal" /></div></CardHeader>
          <CardContent className="space-y-2">{unknowns.length === 0 ? <Empty text="当前没有记录的数据缺口。" /> : unknowns.map((unknown) => <article key={unknown.id} className="rounded-xl border border-line p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold">{unknown.unknown}</p><Badge variant={unknown.status === "verified" ? "success" : "warning"}>{unknownLabels[unknown.status] ?? unknown.status}</Badge></div><p className="mt-2 text-xs text-muted">优先级 {unknown.priority} · 已关联证据 {unknown.evidence_count} 条</p>{unknown.resolution ? <p className="mt-2 text-xs leading-5 text-muted">结论：{unknown.resolution}</p> : null}</article>)}</CardContent>
        </Card>

        <Card>
          <CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">Durable memory</p><h3 className="mt-1 font-display text-xl font-semibold">长期记忆来源</h3></div><BookOpenCheck className="size-5 text-signal" /></div></CardHeader>
          <CardContent className="space-y-2">{memoryItems.length === 0 ? <Empty text="尚未写入长期记忆。" /> : memoryItems.map((memory) => <article key={memory.id} className="rounded-xl border border-line p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="break-words text-sm font-semibold">{memory.memory_key}</p><Badge variant={memory.is_current ? "info" : "neutral"}>{memory.is_current ? "当前" : "历史"}</Badge></div><p className="mt-2 text-xs leading-5 text-muted">{memoryLabels[memory.memory_type] ?? memory.memory_type} · 置信度 {(memory.confidence * 100).toFixed(0)}%</p><p className="mt-1 text-sm leading-5">{readableValue(memory.value)}</p><p className="mt-2 text-xs text-muted">来源：{memory.source_content_id ?? memory.source_query_id ?? memory.source_finding_id ?? "未记录"}</p></article>)}</CardContent>
        </Card>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-xl bg-paper p-4 text-sm leading-6 text-muted">{text}</p>;
}

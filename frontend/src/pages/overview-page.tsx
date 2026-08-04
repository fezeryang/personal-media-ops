import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  CircleAlert,
  Server,
  Timer,
  Wrench,
} from "lucide-react";
import { Link } from "react-router";

import { getAiHealth, getUsage } from "../api/ai";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import {
  useCrawlerCapabilitiesQuery,
  useCrawlerTasksQuery,
  useHealthQuery,
} from "../features/crawler/hooks/use-crawler-queries";
import { useResearchTasksQuery } from "../features/research/hooks/use-research-queries";
import { formatDateTime } from "../lib/utils";

const activeResearchStatuses = new Set([
  "Draft",
  "Planning",
  "Researching",
  "WaitingCrawl",
  "WaitingLogin",
  "Summarizing",
  "BudgetExceeded",
]);

const healthStatusLabels: Record<string, string> = {
  healthy: "健康",
  degraded: "降级",
  unreachable: "不可达",
  authentication_failed: "认证失败",
  model_not_found: "模型不存在",
  rate_limited: "限流",
  protocol_error: "协议错误",
  disabled: "未启用",
};

const platformStatusLabels: Record<string, string> = {
  enabled: "可用",
  disabled: "已禁用",
  deferred_resource_constrained: "资源受限，暂缓",
  deferred_upstream_breakage: "上游异常，暂缓",
  deferred_login_required: "等待登录",
  deferred_platform_change: "平台变更，暂缓",
};

const verificationLabels: Record<string, string> = {
  not_implemented: "未实现",
  code_ready: "代码就绪",
  production_verified: "生产已验证",
};

const researchStatusLabels: Record<string, string> = {
  Draft: "草稿",
  Planning: "规划中",
  Researching: "研究中",
  WaitingCrawl: "等待采集",
  WaitingLogin: "等待登录",
  Summarizing: "整理中",
  BudgetExceeded: "预算触发",
};

function healthVariant(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "healthy") return "success";
  if (status === "degraded" || status === "rate_limited") return "warning";
  if (status === "disabled") return "neutral";
  return "danger";
}

export function OverviewPage() {
  const health = useHealthQuery();
  const research = useResearchTasksQuery();
  const crawlerTasks = useCrawlerTasksQuery();
  const capabilities = useCrawlerCapabilitiesQuery();
  const aiHealth = useQuery({
    queryKey: ["ai", "health"],
    queryFn: ({ signal }) => getAiHealth(signal),
    refetchInterval: 60_000,
  });
  const usage = useQuery({
    queryKey: ["ai", "usage"],
    queryFn: ({ signal }) => getUsage(signal),
    refetchInterval: 60_000,
  });

  const activeResearch = (research.data ?? []).filter((task) =>
    activeResearchStatuses.has(task.status),
  );
  const activeCrawler = (crawlerTasks.data ?? []).filter((task) =>
    ["pending", "running", "waiting_login"].includes(task.status),
  );
  const failedCrawlerCount =
    crawlerTasks.data?.filter((task) => task.status === "failed").length ?? 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Runtime operations"
        title="运行概览"
        description="只展示服务健康、活跃研究、采集队列、平台能力、模型健康和资源用量。研究结论与历史运营模块分别在各自工作区维护。"
        action={
          <Button asChild variant="secondary">
            <Link to="/research">打开 AI Research</Link>
          </Button>
        }
      />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="运行指标">
        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted">API 服务</p>
            <Server className="size-4 text-signal" />
          </div>
          <p className="mt-5 font-display text-3xl font-semibold">
            {health.isPending ? "加载中…" : health.data?.status === "ok" ? "正常" : "—"}
          </p>
          <p className="mt-1 text-[11px] text-muted">
            {health.data?.service ?? "服务状态"}
          </p>
        </Card>
        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted">活跃研究</p>
            <Activity className="size-4 text-signal" />
          </div>
          <p className="mt-5 font-display text-3xl font-semibold tabular-nums">
            {research.isPending || research.isError ? "—" : activeResearch.length}
          </p>
          <p className="mt-1 text-[11px] text-muted">不含等待所有者确认的任务</p>
        </Card>
        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted">活动采集</p>
            <Wrench className="size-4 text-signal" />
          </div>
          <p className="mt-5 font-display text-3xl font-semibold tabular-nums">
            {crawlerTasks.isPending || crawlerTasks.isError ? "—" : activeCrawler.length}
          </p>
          <p className="mt-1 text-[11px] text-muted">单 Worker 串行队列</p>
        </Card>
        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted">失败采集</p>
            <CircleAlert className="size-4 text-warning-strong" />
          </div>
          <p className="mt-5 font-display text-3xl font-semibold tabular-nums">
            {crawlerTasks.isPending || crawlerTasks.isError ? "—" : failedCrawlerCount}
          </p>
          <p className="mt-1 text-[11px] text-muted">当前返回的任务历史</p>
        </Card>
      </section>

      {health.isError ? <ErrorState error={health.error} /> : null}
      {research.isError ? <ErrorState error={research.error} /> : null}
      {crawlerTasks.isError ? <ErrorState error={crawlerTasks.error} /> : null}
      {capabilities.isError ? <ErrorState error={capabilities.error} /> : null}
      {aiHealth.isError ? <ErrorState error={aiHealth.error} /> : null}
      {usage.isError ? <ErrorState error={usage.error} /> : null}

      <section className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardHeader>
            <p className="section-kicker">Platform health</p>
            <h2 className="mt-1 font-display text-xl font-semibold">平台能力状态</h2>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            {(capabilities.data?.platforms ?? []).map((platform) => (
              <div
                key={platform.platform}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line/80 bg-paper/60 p-3"
              >
                <div>
                  <p className="font-semibold">{platform.display_name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {verificationLabels[platform.verification_status] ??
                      platform.verification_status}
                  </p>
                </div>
                <Badge
                  variant={
                    platform.availability_status === "enabled"
                      ? "success"
                      : "warning"
                  }
                >
                  {platformStatusLabels[platform.availability_status] ??
                    platform.availability_status}
                </Badge>
              </div>
            ))}
            {!capabilities.isPending && !capabilities.data?.platforms.length ? (
              <p className="py-8 text-center text-sm text-muted">
                尚无平台能力记录。
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <p className="section-kicker">Model health</p>
            <h2 className="mt-1 font-display text-xl font-semibold">模型健康</h2>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            {(aiHealth.data ?? []).map((record) => (
              <div
                key={record.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line/80 bg-paper/60 p-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Bot className="size-4 shrink-0 text-signal" />
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{record.provider_name}</p>
                    <p className="mt-1 truncate text-xs text-muted">
                      {record.model_id ?? "默认模型路由"} · {formatDateTime(record.checked_at)}
                    </p>
                  </div>
                </div>
                <Badge variant={healthVariant(record.status)}>
                  {healthStatusLabels[record.status] ?? record.status}
                </Badge>
              </div>
            ))}
            {!aiHealth.isPending && !aiHealth.data?.length ? (
              <p className="py-8 text-center text-sm text-muted">
                尚无模型健康记录。
              </p>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <p className="section-kicker">Resource usage</p>
            <h2 className="mt-1 font-display text-xl font-semibold">资源用量</h2>
          </CardHeader>
          <CardContent>
            {usage.data ? (
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-paper p-3">
                  <p className="text-xs text-muted">模型调用</p>
                  <p className="mt-2 font-display text-2xl font-semibold tabular-nums">
                    {usage.data.totals.invocation_count.toLocaleString("zh-CN")}
                  </p>
                </div>
                <div className="rounded-xl bg-paper p-3">
                  <p className="text-xs text-muted">成功率</p>
                  <p className="mt-2 font-display text-2xl font-semibold tabular-nums">
                    {usage.data.totals.success_rate === null
                      ? "—"
                      : `${(usage.data.totals.success_rate * 100).toFixed(1)}%`}
                  </p>
                </div>
                <div className="rounded-xl bg-paper p-3">
                  <p className="text-xs text-muted">输入 / 输出 tokens</p>
                  <p className="mt-2 font-semibold tabular-nums">
                    {usage.data.totals.input_tokens.toLocaleString("zh-CN")} /{" "}
                    {usage.data.totals.output_tokens.toLocaleString("zh-CN")}
                  </p>
                </div>
                <div className="rounded-xl bg-paper p-3">
                  <p className="text-xs text-muted">估算费用</p>
                  <p className="mt-2 font-semibold tabular-nums">
                    {usage.data.totals.estimated_cost ?? "未计费"}{" "}
                    {usage.data.totals.price_currency ?? ""}
                  </p>
                </div>
              </div>
            ) : usage.isPending ? (
              <p className="py-8 text-center text-sm text-muted">正在加载资源用量…</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <div>
              <p className="section-kicker">Active runtime</p>
              <h2 className="mt-1 font-display text-xl font-semibold">当前执行</h2>
            </div>
            <Timer className="size-5 text-signal" />
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {activeResearch.map((task) => (
              <div key={task.id} className="rounded-xl border border-line/80 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">研究任务</p>
                  <Badge variant="info">
                    {researchStatusLabels[task.status] ?? task.status}
                  </Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-sm">{task.objective}</p>
                <p className="mt-1 text-xs text-muted">
                  {task.current_step ?? "等待下一步"} · 更新于 {formatDateTime(task.updated_at)}
                </p>
              </div>
            ))}
            {activeCrawler.map((task) => (
              <div key={task.id} className="rounded-xl border border-line/80 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">采集任务 · {task.platform}</p>
                  <Badge variant={task.status === "waiting_login" ? "warning" : "info"}>
                    {task.status === "waiting_login"
                      ? "等待登录"
                      : task.status === "running"
                        ? "运行中"
                        : "排队中"}
                  </Badge>
                </div>
                <p className="mt-2 text-sm">
                  {task.mode} · {task.keywords ?? "目标任务"}
                </p>
                <p className="mt-1 text-xs text-muted">
                  创建于 {formatDateTime(task.created_at)}
                </p>
              </div>
            ))}
            {!activeResearch.length && !activeCrawler.length ? (
              <div className="rounded-xl border border-success/20 bg-success/5 p-4 text-sm text-success">
                当前没有活动研究或采集任务。
              </div>
            ) : null}
            <div className="flex flex-wrap gap-3 text-sm">
              <Link to="/research" className="font-semibold text-signal-strong hover:underline">
                查看研究工作台 →
              </Link>
              <Link to="/tools/crawls" className="font-semibold text-signal-strong hover:underline">
                查看采集队列 →
              </Link>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

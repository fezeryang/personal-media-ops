import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookMarked,
  CheckCircle2,
  Clock3,
  Compass,
  RadioTower,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router";

import { getLatestBrief, listTrends } from "../api/intelligence";
import { getLibraryStats, listLibraryContents } from "../api/library";
import { listSubscriptions } from "../api/subscriptions";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import {
  useCrawlerCapabilitiesQuery,
  useCrawlerTasksQuery,
} from "../features/crawler/hooks/use-crawler-queries";
import { formatDateTime } from "../lib/utils";

function startOfToday(): string {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return now.toISOString();
}

export function OverviewPage() {
  const stats = useQuery({
    queryKey: ["library", "stats"],
    queryFn: ({ signal }) => getLibraryStats(signal),
  });
  const today = useQuery({
    queryKey: ["library", "today"],
    queryFn: ({ signal }) =>
      listLibraryContents(
        { date_from: startOfToday(), sort: "first_collected_desc", limit: 50 },
        signal,
      ),
  });
  const subscriptions = useQuery({
    queryKey: ["subscriptions"],
    queryFn: ({ signal }) => listSubscriptions(signal),
  });
  const trends = useQuery({
    queryKey: ["intelligence", "trends"],
    queryFn: ({ signal }) => listTrends(signal),
  });
  const brief = useQuery({
    queryKey: ["intelligence", "brief", "latest"],
    queryFn: ({ signal }) => getLatestBrief(signal),
    retry: false,
  });
  const tasks = useCrawlerTasksQuery();
  const capabilities = useCrawlerCapabilitiesQuery();
  const activeSubscriptions =
    subscriptions.data?.filter((item) => item.enabled).length ?? 0;
  const recentRuns = (subscriptions.data ?? [])
    .filter((item) => item.last_run_at)
    .sort((a, b) => (b.last_run_at ?? "").localeCompare(a.last_run_at ?? ""))
    .slice(0, 4);
  const activeTasks =
    tasks.data?.filter((task) =>
      ["pending", "running", "waiting_login"].includes(task.status),
    ) ?? [];

  return (
    <div className="space-y-8">
      <header className="command-hero overflow-hidden rounded-[28px] border border-[#cfe2de] px-6 py-7 sm:px-9 sm:py-9">
        <div className="grid gap-8 xl:grid-cols-[1fr_340px] xl:items-end">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-signal-strong">
              Command center · {new Date().toLocaleDateString("zh-CN")}
            </p>
            <h1 className="mt-3 max-w-3xl font-display text-4xl font-semibold leading-tight tracking-[-0.045em] sm:text-5xl">
              今天的互联网，
              <br className="hidden sm:block" />
              有哪些变化值得你知道？
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">
              这里汇总真实入库内容、订阅运行、趋势证据和创作者动态。没有模拟统计，也不把规则判断伪装成 AI 结论。
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild>
                <Link to="/today">
                  查看今日情报 <ArrowUpRight className="size-4" />
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link to="/subscriptions">管理订阅</Link>
              </Button>
            </div>
          </div>
          <div className="rounded-2xl border border-white/80 bg-white/80 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted">最新简报</span>
              <BookMarked className="size-4 text-signal" />
            </div>
            {brief.data ? (
              <>
                <p className="mt-5 font-display text-2xl font-semibold">
                  {brief.data.items.length} 个情报段落
                </p>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {brief.data.evidence_count} 项关联证据 · 版本{" "}
                  {brief.data.version}
                </p>
                <Link
                  to="/today"
                  className="mt-5 inline-flex text-xs font-bold text-signal-strong"
                >
                  阅读简报 →
                </Link>
              </>
            ) : (
              <p className="mt-5 text-sm leading-6 text-muted">
                尚无简报。进入今日情报可基于真实资料手动生成。
              </p>
            )}
          </div>
        </div>
      </header>

      <section
        className="grid grid-cols-2 gap-3 lg:grid-cols-4"
        aria-label="真实情报统计"
      >
        {[
          {
            label: "今日新增",
            value: today.data?.items.length,
            hint: "按首次入库时间",
            icon: Compass,
          },
          {
            label: "活跃订阅",
            value: activeSubscriptions,
            hint: `共 ${subscriptions.data?.length ?? 0} 条`,
            icon: RadioTower,
          },
          {
            label: "上升主题",
            value: trends.data?.filter((item) => item.status === "detected")
              .length,
            hint: "达到样本门槛",
            icon: Sparkles,
          },
          {
            label: "资料总量",
            value: stats.data?.contents,
            hint: `${stats.data?.creators ?? "—"} 位创作者`,
            icon: BookMarked,
          },
        ].map((item) => (
          <Card key={item.label} className="metric-card p-4 sm:p-5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-muted">{item.label}</p>
              <item.icon className="size-4 text-signal" />
            </div>
            <p className="mt-5 font-display text-3xl font-semibold tabular-nums">
              {typeof item.value === "number"
                ? item.value.toLocaleString("zh-CN")
                : "—"}
            </p>
            <p className="mt-1 text-[11px] text-muted">{item.hint}</p>
          </Card>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <p className="section-kicker">Signal board</p>
              <h2 className="mt-1 font-display text-xl font-semibold">
                热度变化主题
              </h2>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to="/trends">趋势雷达</Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            {(trends.data ?? []).slice(0, 5).map((trend) => (
              <div
                key={trend.id}
                className="flex items-center gap-4 rounded-xl border border-line/80 bg-paper/60 p-3"
              >
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white font-display text-lg font-semibold tabular-nums text-signal-strong">
                  {Math.round(trend.score)}
                </span>
                <div className="min-w-0">
                  <p className="truncate font-semibold">{trend.topic}</p>
                  <p className="mt-1 truncate text-xs text-muted">
                    {trend.explanation}
                  </p>
                </div>
                <Badge
                  className="ml-auto shrink-0"
                  variant={
                    trend.status === "detected" ? "success" : "neutral"
                  }
                >
                  {trend.status === "detected" ? "趋势" : "数据不足"}
                </Badge>
              </div>
            ))}
            {!trends.data?.length ? (
              <p className="py-10 text-center text-sm text-muted">
                尚无趋势信号，生成后将在这里显示。
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <p className="section-kicker">Operations</p>
            <h2 className="mt-1 font-display text-xl font-semibold">
              最近运行与待处理
            </h2>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {activeTasks.length ? (
              <div className="rounded-xl border border-warning/20 bg-warning/5 p-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-warning-strong">
                  <Clock3 className="size-4" />
                  {activeTasks.length} 个采集任务待处理
                </p>
              </div>
            ) : (
              <div className="rounded-xl border border-success/20 bg-success/5 p-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-success">
                  <CheckCircle2 className="size-4" />
                  当前没有活动采集任务
                </p>
              </div>
            )}
            {recentRuns.map((subscription) => (
              <div
                key={subscription.id}
                className="flex items-start justify-between gap-3 border-b border-line/70 pb-3 last:border-0"
              >
                <div>
                  <p className="text-sm font-semibold">{subscription.name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {subscription.last_run_at
                      ? formatDateTime(subscription.last_run_at)
                      : "尚未运行"}
                  </p>
                </div>
                <Badge
                  variant={
                    subscription.last_error ? "danger" : "success"
                  }
                >
                  {subscription.last_error ? "需检查" : "正常"}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="rounded-2xl border border-line bg-white p-5">
        <div className="flex flex-wrap items-center gap-3">
          <p className="mr-2 text-sm font-semibold">平台能力</p>
          {(capabilities.data?.platforms ?? []).map((platform) => (
            <Badge
              key={platform.platform}
              variant={platform.enabled ? "success" : "neutral"}
            >
              {platform.display_name} · {platform.availability_status}
            </Badge>
          ))}
        </div>
      </section>
    </div>
  );
}

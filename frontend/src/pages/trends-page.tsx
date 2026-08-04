import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { listTrends } from "../api/intelligence";
import { ErrorState } from "../components/error-state";
import { LegacySurfaceNotice } from "../components/legacy-surface-notice";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Card, CardContent } from "../components/ui/card";
import { formatDateTime } from "../lib/utils";

const scoreParts = [
  ["volume_score", "数量", "35%"],
  ["velocity_score", "增速", "30%"],
  ["cross_platform_score", "跨平台", "20%"],
  ["engagement_score", "互动变化", "15%"],
] as const;

export function TrendsPage() {
  const trends = useQuery({
    queryKey: ["intelligence", "trends"],
    queryFn: ({ signal }) => listTrends(signal),
  });
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Explainable signals"
        title="趋势雷达"
        description="保留历史趋势信号及其固定公式、样本和证据，不再从这里重新计算新的运营趋势。"
      />
      <LegacySurfaceNotice
        surface="趋势雷达"
        replacement="AI Research 与 Discovery Inbox"
        replacementPath="/discoveries"
      />
      {trends.isError ? (
        <ErrorState
          error={trends.error}
          onRetry={() => void trends.refetch()}
        />
      ) : null}

      <section className="grid gap-5 xl:grid-cols-2">
        {(trends.data ?? []).map((trend) => (
          <Card key={trend.id} className="trend-card overflow-hidden">
            <CardContent>
              <div className="flex items-start gap-4">
                <div className="score-orbit grid size-20 shrink-0 place-items-center rounded-full">
                  <div className="grid size-16 place-items-center rounded-full bg-white">
                    <span className="font-display text-2xl font-semibold tabular-nums">
                      {trend.score.toFixed(1)}
                    </span>
                  </div>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={
                        trend.status === "detected" ? "success" : "warning"
                      }
                    >
                      {trend.status === "detected" ? "趋势成立" : "数据不足"}
                    </Badge>
                    <span className="text-[11px] text-muted">
                      {trend.formula_version}
                    </span>
                  </div>
                  <h2 className="mt-2 font-display text-2xl font-semibold">
                    {trend.topic}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {trend.explanation}
                  </p>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {scoreParts.map(([key, label, weight]) => (
                  <div
                    key={key}
                    className="rounded-xl border border-line bg-paper/60 p-3"
                  >
                    <p className="text-[10px] uppercase tracking-wider text-muted">
                      {label} · {weight}
                    </p>
                    <p className="mt-2 font-mono text-lg font-semibold tabular-nums">
                      {trend[key].toFixed(1)}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-line pt-4 text-xs text-muted">
                <span>
                  窗口 {formatDateTime(trend.window_start)} —{" "}
                  {formatDateTime(trend.window_end)}
                </span>
                <span>·</span>
                <span>{trend.platforms.join("、") || "无平台样本"}</span>
                <span>·</span>
                <span>{trend.content_ids.length} 条证据内容</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
      {!trends.isPending && !trends.data?.length ? (
        <Card className="grid min-h-72 place-items-center p-8 text-center">
          <div>
            <BarChart3 className="mx-auto size-8 text-muted" />
            <p className="mt-3 font-semibold">尚无趋势信号</p>
            <p className="mt-2 text-sm text-muted">
              历史趋势信号将在这里展示真实证据；新的研究结果请从 AI Research 查看。
            </p>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

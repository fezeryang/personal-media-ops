import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, RefreshCw, Sparkles } from "lucide-react";

import {
  generateBrief,
  generateTrends,
  getLatestBrief,
  listTrends,
} from "../api/intelligence";
import { listLibraryContents } from "../api/library";
import { ApiError } from "../api/client";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { ContentCard } from "../features/library/components/content-card";
import { formatDateTime } from "../lib/utils";

function todayStart(): string {
  const value = new Date();
  value.setHours(0, 0, 0, 0);
  return value.toISOString();
}

const conclusionLabel = {
  fact: "事实",
  calculation: "计算结果",
  rule: "规则判断",
  insufficient_data: "数据不足",
  unknown: "未知",
};

export function TodayPage() {
  const queryClient = useQueryClient();
  const contents = useQuery({
    queryKey: ["library", "today", "detail"],
    queryFn: ({ signal }) =>
      listLibraryContents(
        { date_from: todayStart(), sort: "first_collected_desc", limit: 30 },
        signal,
      ),
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
  const refresh = useMutation({
    mutationFn: async () => {
      await generateTrends();
      try {
        return await generateBrief(false);
      } catch (error: unknown) {
        if (error instanceof ApiError && error.status === 409) {
          return generateBrief(true);
        }
        throw error;
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["intelligence"] });
    },
  });

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Daily intelligence"
        title="今日情报"
        description="把当日新增、趋势变化和可追溯简报放在同一条阅读流中。所有结论都保留类型与证据。"
        action={
          <Button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
          >
            <RefreshCw
              className={`size-4 ${refresh.isPending ? "animate-spin" : ""}`}
            />
            {brief.data ? "重新生成简报" : "生成今日简报"}
          </Button>
        }
      />

      {refresh.isError ? <ErrorState error={refresh.error} /> : null}

      <section className="grid gap-5 xl:grid-cols-[0.86fr_1.14fr]">
        <Card className="brief-sheet overflow-hidden">
          <CardHeader className="border-b border-line/70 pb-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="section-kicker">Deterministic brief</p>
                <h2 className="mt-2 font-display text-2xl font-semibold">
                  每日情报简报
                </h2>
              </div>
              <BookOpenCheck className="size-5 text-signal" />
            </div>
            {brief.data ? (
              <p className="mt-3 text-xs text-muted">
                {formatDateTime(brief.data.window_start)} —{" "}
                {formatDateTime(brief.data.window_end)} ·{" "}
                {brief.data.evidence_count} 项证据
              </p>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-5">
            {brief.data ? (
              brief.data.items.map((item) => (
                <article key={item.id} className="brief-item">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={
                        item.conclusion_type === "insufficient_data" ||
                        item.conclusion_type === "unknown"
                          ? "warning"
                          : "info"
                      }
                    >
                      {conclusionLabel[item.conclusion_type]}
                    </Badge>
                    <span className="text-[11px] uppercase tracking-wider text-muted">
                      {item.section}
                    </span>
                  </div>
                  <h3 className="mt-3 font-display text-lg font-semibold">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {item.body}
                  </p>
                  <p className="mt-3 text-xs text-muted">
                    证据：{item.content_ids.length} 条内容 ·{" "}
                    {item.trend_ids.length} 个趋势
                  </p>
                </article>
              ))
            ) : (
              <div className="py-14 text-center">
                <BookOpenCheck className="mx-auto size-7 text-muted" />
                <p className="mt-3 font-semibold">尚未生成简报</p>
                <p className="mt-2 text-sm text-muted">
                  生成器只使用当前资料库中的真实数据。
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <p className="section-kicker">Cross-platform topics</p>
                <h2 className="mt-1 font-display text-xl font-semibold">
                  最新趋势信号
                </h2>
              </div>
              <Sparkles className="size-5 text-signal" />
            </CardHeader>
            <CardContent className="grid gap-3 pt-4 sm:grid-cols-2">
              {(trends.data ?? []).slice(0, 6).map((trend) => (
                <div
                  key={trend.id}
                  className="rounded-xl border border-line bg-paper/50 p-4"
                >
                  <div className="flex items-center justify-between">
                    <Badge
                      variant={
                        trend.status === "detected" ? "success" : "neutral"
                      }
                    >
                      {trend.status === "detected" ? "已识别" : "数据不足"}
                    </Badge>
                    <span className="font-mono text-sm font-semibold text-signal-strong">
                      {trend.score.toFixed(1)}
                    </span>
                  </div>
                  <h3 className="mt-3 font-semibold">{trend.topic}</h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">
                    {trend.explanation}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between">
          <div>
            <p className="section-kicker">New today</p>
            <h2 className="mt-1 font-display text-2xl font-semibold">
              当日新增内容
            </h2>
          </div>
          <span className="text-xs text-muted">
            {contents.data?.items.length ?? 0} 条
          </span>
        </div>
        <div className="space-y-4">
          {(contents.data?.items ?? []).map((content) => (
            <ContentCard key={content.id} content={content} />
          ))}
          {!contents.isPending && !contents.data?.items.length ? (
            <Card className="p-10 text-center text-sm text-muted">
              今天尚无新内容。订阅运行后会在这里按首次入库时间出现。
            </Card>
          ) : null}
        </div>
      </section>
    </div>
  );
}

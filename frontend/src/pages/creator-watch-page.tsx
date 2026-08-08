import { useQuery } from "@tanstack/react-query";
import { Eye, UserRound } from "lucide-react";
import { Link } from "react-router";

import { listWatches } from "../api/watchlist";
import { ErrorState } from "../components/error-state";
import { LegacySurfaceNotice } from "../components/legacy-surface-notice";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Card, CardContent } from "../components/ui/card";
import { formatDateTime } from "../lib/utils";

export function CreatorWatchPage() {
  const watches = useQuery({
    queryKey: ["watchlist"],
    queryFn: ({ signal }) => listWatches(signal),
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Historical creator watch"
        title="创作者观察"
        description="保留历史观察项、检查时间和错误记录，供审计与迁移参考。"
      />

      <LegacySurfaceNotice
        surface="创作者观察"
        replacement="AI 研究与监控任务"
        replacementPath="/research"
      />

      {watches.isError ? (
        <ErrorState
          error={watches.error}
          onRetry={() => void watches.refetch()}
        />
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        {(watches.data ?? []).map((watch) => (
          <Card key={watch.id}>
            <CardContent>
              <div className="flex items-start gap-4">
                <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[#e7f5f1] text-signal-strong">
                  <UserRound className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/library/creators/${encodeURIComponent(watch.creator_id)}`}
                      className="font-display text-xl font-semibold hover:text-signal-strong"
                    >
                      {watch.creator_name ?? watch.creator_id}
                    </Link>
                    <Badge
                      variant={watch.enabled ? "success" : "neutral"}
                    >
                      {watch.enabled ? "历史配置：已启用" : "历史配置：已暂停"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    {watch.platform} · {watch.check_frequency} · 每次最多{" "}
                    {watch.requested_count} 条
                  </p>
                </div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 rounded-xl bg-paper p-4 text-xs">
                <div>
                  <p className="text-muted">最近检查</p>
                  <p className="mt-1 font-semibold">
                    {watch.last_checked_at
                      ? formatDateTime(watch.last_checked_at)
                      : "尚未检查"}
                  </p>
                </div>
                <div>
                  <p className="text-muted">下次检查</p>
                  <p className="mt-1 font-semibold">
                    {watch.next_check_at
                      ? formatDateTime(watch.next_check_at)
                      : "未安排"}
                  </p>
                </div>
              </div>
              {watch.last_error ? (
                <p className="mt-3 text-xs text-danger">{watch.last_error}</p>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </section>

      {!watches.isPending && !watches.data?.length ? (
        <Card className="grid min-h-64 place-items-center p-8 text-center">
          <div>
            <Eye className="mx-auto size-8 text-muted" />
            <p className="mt-3 font-semibold">没有历史观察项</p>
            <p className="mt-2 text-sm text-muted">
              新的关注目标请从 AI Research 创建，不会在这里新增观察任务。
            </p>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

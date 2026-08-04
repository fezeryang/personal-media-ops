import { useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";

import { listSubscriptions, type Subscription } from "../api/subscriptions";
import { ErrorState } from "../components/error-state";
import { LegacySurfaceNotice } from "../components/legacy-surface-notice";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Card, CardContent } from "../components/ui/card";
import { formatDateTime } from "../lib/utils";

const scheduleLabels: Record<Subscription["schedule_type"], string> = {
  manual: "手动",
  every_6_hours: "每 6 小时",
  daily: "每天",
  weekdays: "工作日",
  weekly: "每周",
};

export function SubscriptionsPage() {
  const subscriptions = useQuery({
    queryKey: ["subscriptions"],
    queryFn: ({ signal }) => listSubscriptions(signal),
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Historical automation"
        title="订阅中心"
        description="保留历史关键词订阅的真实配置、运行时间和错误记录，供审计与迁移参考。"
      />

      <LegacySurfaceNotice
        surface="订阅中心"
        replacement="AI Research 与未来的统一监控模块（8E）"
        replacementPath="/research"
      />

      {subscriptions.isError ? (
        <ErrorState
          error={subscriptions.error}
          onRetry={() => void subscriptions.refetch()}
        />
      ) : null}

      <section className="grid gap-4">
        {(subscriptions.data ?? []).map((subscription) => (
          <Card key={subscription.id} className="subscription-card">
            <CardContent className="grid gap-5 lg:grid-cols-[1fr_220px] lg:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-display text-xl font-semibold">
                    {subscription.name}
                  </h2>
                  <Badge
                    variant={subscription.enabled ? "success" : "neutral"}
                  >
                    {subscription.enabled ? "历史配置：已启用" : "历史配置：已暂停"}
                  </Badge>
                  <Badge variant="info">
                    {scheduleLabels[subscription.schedule_type]}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-muted">
                  关键词「{subscription.query}」 ·{" "}
                  {subscription.platforms
                    .map((platform) => platform.platform)
                    .join("、")}
                </p>
                {subscription.last_error ? (
                  <p className="mt-2 text-xs text-danger">
                    {subscription.last_error}
                  </p>
                ) : null}
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-muted">最近运行</p>
                  <p className="mt-1 font-semibold">
                    {subscription.last_run_at
                      ? formatDateTime(subscription.last_run_at)
                      : "尚未运行"}
                  </p>
                </div>
                <div>
                  <p className="text-muted">下次运行</p>
                  <p className="mt-1 font-semibold">
                    {subscription.next_run_at
                      ? formatDateTime(subscription.next_run_at)
                      : "未安排"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {!subscriptions.isPending && !subscriptions.data?.length ? (
          <Card className="grid min-h-64 place-items-center p-8 text-center">
            <div>
              <CalendarClock className="mx-auto size-8 text-muted" />
              <p className="mt-3 font-semibold">没有历史关键词订阅</p>
              <p className="mt-2 text-sm text-muted">
                新的研究目标请从 AI Research 创建，不会在这里新增订阅。
              </p>
            </div>
          </Card>
        ) : null}
      </section>
    </div>
  );
}

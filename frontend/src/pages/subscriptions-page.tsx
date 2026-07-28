import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  CirclePause,
  CirclePlay,
  Pencil,
  Play,
  Plus,
  X,
} from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import {
  listSubscriptions,
  runSubscription,
  saveSubscription,
  setSubscriptionEnabled,
  type Subscription,
  type SubscriptionInput,
} from "../api/subscriptions";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { useCrawlerCapabilitiesQuery } from "../features/crawler/hooks/use-crawler-queries";
import { formatDateTime } from "../lib/utils";

const scheduleLabels = {
  manual: "手动",
  every_6_hours: "每 6 小时",
  daily: "每天",
  weekdays: "工作日",
  weekly: "每周",
};

interface Draft {
  id?: string;
  name: string;
  query: string;
  platforms: string[];
  requestedCount: number;
  enabled: boolean;
  scheduleType: Subscription["schedule_type"];
  timeOfDay: string;
  weekday: number;
  timezone: string;
}

function emptyDraft(): Draft {
  return {
    name: "",
    query: "",
    platforms: [],
    requestedCount: 5,
    enabled: false,
    scheduleType: "manual",
    timeOfDay: "09:00",
    weekday: 0,
    timezone:
      Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
  };
}

function subscriptionDraft(item: Subscription): Draft {
  return {
    id: item.id,
    name: item.name,
    query: item.query,
    platforms: item.platforms.map((platform) => platform.platform),
    requestedCount: item.platforms[0]?.requested_count ?? 5,
    enabled: item.enabled,
    scheduleType: item.schedule_type,
    timeOfDay: item.schedule_config.time_of_day ?? "09:00",
    weekday: item.schedule_config.weekday ?? 0,
    timezone: item.timezone,
  };
}

export function SubscriptionsPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const subscriptions = useQuery({
    queryKey: ["subscriptions"],
    queryFn: ({ signal }) => listSubscriptions(signal),
    refetchInterval: 8_000,
  });
  const capabilities = useCrawlerCapabilitiesQuery();
  const availablePlatforms = useMemo(
    () =>
      (capabilities.data?.platforms ?? []).filter((platform) => {
        const search = platform.modes.find((mode) => mode.mode === "search");
        return (
          platform.enabled &&
          search?.enabled &&
          search.status === "production_verified"
        );
      }),
    [capabilities.data],
  );
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
  const save = useMutation({
    mutationFn: (input: SubscriptionInput) =>
      saveSubscription(input, draft?.id),
    onSuccess: async () => {
      setDraft(null);
      await invalidate();
    },
  });
  const toggle = useMutation({
    mutationFn: ({
      id,
      enabled,
    }: {
      id: string;
      enabled: boolean;
    }) => setSubscriptionEnabled(id, enabled),
    onSuccess: invalidate,
  });
  const run = useMutation({
    mutationFn: runSubscription,
    onSuccess: invalidate,
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft?.platforms.length) return;
    const timed = ["daily", "weekdays", "weekly"].includes(
      draft.scheduleType,
    );
    save.mutate({
      name: draft.name.trim(),
      query: draft.query.trim(),
      platforms: draft.platforms.map((platform) => ({
        platform,
        requested_count: draft.requestedCount,
      })),
      enabled: draft.enabled,
      schedule_type: draft.scheduleType,
      schedule_config: {
        ...(timed ? { time_of_day: draft.timeOfDay } : {}),
        ...(draft.scheduleType === "weekly"
          ? { weekday: draft.weekday }
          : {}),
      },
      timezone: draft.timezone,
    });
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Continuous discovery"
        title="订阅中心"
        description="为关注主题建立低频、可恢复的自动采集计划。平台任务始终进入现有单浏览器串行队列。"
        action={
          <Button onClick={() => setDraft(emptyDraft())}>
            <Plus className="size-4" /> 创建订阅
          </Button>
        }
      />

      {draft ? (
        <Card className="overflow-hidden border-signal/25">
          <CardHeader className="flex flex-row items-center justify-between border-b border-line pb-5">
            <div>
              <p className="section-kicker">
                {draft.id ? "Edit subscription" : "New subscription"}
              </p>
              <h2 className="mt-1 font-display text-xl font-semibold">
                {draft.id ? "编辑订阅" : "创建关键词订阅"}
              </h2>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label="关闭订阅表单"
              onClick={() => setDraft(null)}
            >
              <X className="size-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={submit}
              className="grid gap-5 lg:grid-cols-2"
              aria-label="订阅表单"
            >
              <label className="text-sm font-semibold">
                名称
                <Input
                  className="mt-2"
                  value={draft.name}
                  onChange={(event) =>
                    setDraft({ ...draft, name: event.currentTarget.value })
                  }
                  required
                />
              </label>
              <label className="text-sm font-semibold">
                关键词
                <Input
                  className="mt-2"
                  value={draft.query}
                  onChange={(event) =>
                    setDraft({ ...draft, query: event.currentTarget.value })
                  }
                  required
                />
              </label>
              <fieldset className="lg:col-span-2">
                <legend className="text-sm font-semibold">采集平台</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {availablePlatforms.map((platform) => (
                    <label
                      key={platform.platform}
                      className="flex cursor-pointer items-center gap-2 rounded-xl border border-line bg-paper px-3 py-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={draft.platforms.includes(platform.platform)}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            platforms: event.currentTarget.checked
                              ? [...draft.platforms, platform.platform]
                              : draft.platforms.filter(
                                  (item) => item !== platform.platform,
                                ),
                          })
                        }
                      />
                      {platform.display_name}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="text-sm font-semibold">
                频率
                <select
                  className="form-select mt-2"
                  value={draft.scheduleType}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      scheduleType: event.currentTarget
                        .value as Subscription["schedule_type"],
                      enabled:
                        event.currentTarget.value === "manual"
                          ? false
                          : draft.enabled,
                    })
                  }
                >
                  {Object.entries(scheduleLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-semibold">
                每平台数量（1–20）
                <Input
                  className="mt-2"
                  type="number"
                  min={1}
                  max={20}
                  value={draft.requestedCount}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      requestedCount: Number(event.currentTarget.value),
                    })
                  }
                />
              </label>
              {["daily", "weekdays", "weekly"].includes(
                draft.scheduleType,
              ) ? (
                <label className="text-sm font-semibold">
                  本地执行时间
                  <Input
                    className="mt-2"
                    type="time"
                    value={draft.timeOfDay}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        timeOfDay: event.currentTarget.value,
                      })
                    }
                  />
                </label>
              ) : null}
              <label className="text-sm font-semibold">
                IANA 时区
                <Input
                  className="mt-2"
                  value={draft.timezone}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      timezone: event.currentTarget.value,
                    })
                  }
                />
              </label>
              <label className="flex items-center gap-3 text-sm font-semibold lg:col-span-2">
                <input
                  type="checkbox"
                  disabled={draft.scheduleType === "manual"}
                  checked={draft.enabled}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      enabled: event.currentTarget.checked,
                    })
                  }
                />
                保存后启用自动调度
              </label>
              {save.isError ? (
                <div className="lg:col-span-2">
                  <ErrorState error={save.error} />
                </div>
              ) : null}
              <div className="flex justify-end gap-3 lg:col-span-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setDraft(null)}
                >
                  取消
                </Button>
                <Button
                  type="submit"
                  disabled={
                    save.isPending ||
                    !draft.platforms.length ||
                    !draft.name.trim() ||
                    !draft.query.trim()
                  }
                >
                  {save.isPending ? "正在保存…" : "保存订阅"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      {subscriptions.isError ? (
        <ErrorState
          error={subscriptions.error}
          onRetry={() => void subscriptions.refetch()}
        />
      ) : null}

      <section className="grid gap-4">
        {(subscriptions.data ?? []).map((subscription) => (
          <Card key={subscription.id} className="subscription-card">
            <CardContent className="grid gap-5 lg:grid-cols-[1fr_220px_auto] lg:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-display text-xl font-semibold">
                    {subscription.name}
                  </h2>
                  <Badge
                    variant={subscription.enabled ? "success" : "neutral"}
                  >
                    {subscription.enabled ? "运行中" : "已暂停"}
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
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setDraft(subscriptionDraft(subscription))}
                >
                  <Pencil className="size-3.5" /> 编辑
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={run.isPending}
                  onClick={() => run.mutate(subscription.id)}
                >
                  <Play className="size-3.5" /> 手动执行
                </Button>
                {subscription.schedule_type !== "manual" ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={toggle.isPending}
                    onClick={() =>
                      toggle.mutate({
                        id: subscription.id,
                        enabled: !subscription.enabled,
                      })
                    }
                  >
                    {subscription.enabled ? (
                      <CirclePause className="size-3.5" />
                    ) : (
                      <CirclePlay className="size-3.5" />
                    )}
                    {subscription.enabled ? "暂停" : "恢复"}
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}
        {!subscriptions.isPending && !subscriptions.data?.length ? (
          <Card className="grid min-h-64 place-items-center p-8 text-center">
            <div>
              <CalendarClock className="mx-auto size-8 text-muted" />
              <p className="mt-3 font-semibold">还没有关键词订阅</p>
              <p className="mt-2 text-sm text-muted">
                创建后可先保持暂停，用手动运行验证结果。
              </p>
            </div>
          </Card>
        ) : null}
      </section>
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Eye,
  Pause,
  Play,
  Plus,
  RefreshCw,
  UserRound,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { listLibraryCreators } from "../api/library";
import {
  createWatch,
  listWatches,
  runWatch,
  setWatchEnabled,
} from "../api/watchlist";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { useCrawlerCapabilitiesQuery } from "../features/crawler/hooks/use-crawler-queries";
import { formatDateTime } from "../lib/utils";

export function CreatorWatchPage() {
  const queryClient = useQueryClient();
  const [creatorId, setCreatorId] = useState("");
  const watches = useQuery({
    queryKey: ["watchlist"],
    queryFn: ({ signal }) => listWatches(signal),
    refetchInterval: 8_000,
  });
  const creators = useQuery({
    queryKey: ["library", "creators", "watch-options"],
    queryFn: ({ signal }) => listLibraryCreators({ limit: 100 }, signal),
  });
  const capabilities = useCrawlerCapabilitiesQuery();
  const supported = new Set(
    (capabilities.data?.platforms ?? [])
      .filter((platform) =>
        platform.modes.some(
          (mode) =>
            mode.mode === "creator" &&
            mode.enabled &&
            mode.status === "production_verified",
        ),
      )
      .map((platform) => platform.platform),
  );
  const watchedCreators = new Set(
    (watches.data ?? []).map((watch) => watch.creator_id),
  );
  const options = (creators.data?.items ?? []).filter(
    (creator) =>
      supported.has(creator.platform) && !watchedCreators.has(creator.id),
  );
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["watchlist"] });
  const create = useMutation({
    mutationFn: () =>
      createWatch({
        creator_id: creatorId,
        enabled: false,
        check_frequency: "daily",
        requested_count: 3,
        timezone:
          Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
      }),
    onSuccess: async () => {
      setCreatorId("");
      await invalidate();
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      setWatchEnabled(id, enabled),
    onSuccess: invalidate,
  });
  const run = useMutation({
    mutationFn: runWatch,
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Creator watchlist"
        title="创作者观察"
        description="复用已验证 creator 能力，串行检查创作者新内容与指标变化。默认只创建暂停的监控项。"
      />

      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <select
            className="form-select flex-1"
            aria-label="选择可监控创作者"
            value={creatorId}
            onChange={(event) => setCreatorId(event.currentTarget.value)}
          >
            <option value="">选择资料库中的已验证创作者</option>
            {options.map((creator) => (
              <option key={creator.id} value={creator.id}>
                {creator.display_name ?? creator.source_creator_id} ·{" "}
                {creator.platform}
              </option>
            ))}
          </select>
          <Button
            disabled={!creatorId || create.isPending}
            onClick={() => create.mutate()}
          >
            <Plus className="size-4" />
            加入观察
          </Button>
        </div>
      </Card>
      {create.isError ? <ErrorState error={create.error} /> : null}

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
                      {watch.enabled ? "持续监控" : "已暂停"}
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
              <div className="mt-5 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={run.isPending}
                  onClick={() => run.mutate(watch.id)}
                >
                  <RefreshCw className="size-3.5" /> 手动检查
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={toggle.isPending}
                  onClick={() =>
                    toggle.mutate({
                      id: watch.id,
                      enabled: !watch.enabled,
                    })
                  }
                >
                  {watch.enabled ? (
                    <Pause className="size-3.5" />
                  ) : (
                    <Play className="size-3.5" />
                  )}
                  {watch.enabled ? "暂停监控" : "开始监控"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

      {!watches.isPending && !watches.data?.length ? (
        <Card className="grid min-h-64 place-items-center p-8 text-center">
          <div>
            <Eye className="mx-auto size-8 text-muted" />
            <p className="mt-3 font-semibold">观察列表为空</p>
            <p className="mt-2 text-sm text-muted">
              先采集创作者资料，再从上方加入观察。
            </p>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

import {
  ArrowLeft,
  ArrowUpRight,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ErrorState } from "../components/error-state";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { ContentCard } from "../features/library/components/content-card";
import { SafeImage } from "../features/library/components/safe-image";
import { useLibraryCreatorQuery } from "../features/library/hooks/use-library-queries";
import { formatDateTime } from "../lib/utils";
import { listCreatorMetrics } from "../api/library";

export function LibraryCreatorPage() {
  const { creatorId = "" } = useParams();
  const query = useLibraryCreatorQuery(creatorId);
  const metrics = useQuery({
    queryKey: ["library", "creators", creatorId, "metrics"],
    queryFn: ({ signal }) => listCreatorMetrics(creatorId, signal),
    enabled: Boolean(creatorId),
  });
  if (query.isPending) {
    return <div className="h-96 animate-pulse rounded-2xl bg-white" />;
  }
  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="无法打开创作者资料"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }
  const creator = query.data;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm">
        <Link to="/library">
          <ArrowLeft className="size-4" />
          返回资料库
        </Link>
      </Button>
      <Card>
        <CardContent className="grid gap-5 sm:grid-cols-[96px_minmax(0,1fr)]">
          <SafeImage
            src={creator.avatar_url}
            alt={creator.display_name ?? "创作者头像"}
            className="size-24 rounded-2xl"
          />
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-signal-strong">
              <UserRound className="size-4" />
              {creator.platform} 创作者
            </div>
            <h1 className="mt-2 font-display text-3xl font-semibold">
              {creator.display_name ?? creator.source_creator_id}
            </h1>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted">
              {creator.description ?? "暂无简介"}
            </p>
            <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted">
              <span>粉丝 {creator.follower_count ?? "—"}</span>
              <span>关注 {creator.following_count ?? "—"}</span>
              <span>内容 {creator.content_count ?? "—"}</span>
              <span>最近采集 {formatDateTime(creator.last_collected_at)}</span>
              {creator.profile_url ? (
                <a
                  href={creator.profile_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex items-center gap-1 text-signal-strong"
                >
                  原始主页
                  <ArrowUpRight className="size-3" />
                </a>
              ) : null}
            </div>
            <p className="mt-5 rounded-xl border border-warning/25 bg-warning/5 px-3 py-2 text-xs leading-5 text-muted">
              创作者观察仅保留历史审计；新的监控能力将由未来统一监控模块替代。
            </p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent>
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-signal" />
            <h2 className="font-display text-lg font-semibold">
              创作者指标快照
            </h2>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {(metrics.data?.items ?? []).slice(-3).map((snapshot) => (
              <div
                key={snapshot.id}
                className="rounded-xl border border-line bg-paper p-3 text-xs"
              >
                <p className="text-muted">
                  {formatDateTime(snapshot.captured_at)}
                </p>
                <p className="mt-2 font-semibold">
                  粉丝 {snapshot.follower_count ?? "—"}
                </p>
                <p className="mt-1 text-muted">
                  内容 {snapshot.content_count ?? "—"}
                </p>
              </div>
            ))}
            {!metrics.data?.items.length ? (
              <p className="text-sm text-muted">尚无指标快照</p>
            ) : null}
          </div>
        </CardContent>
      </Card>
      <section>
        <h2 className="mb-4 font-display text-xl font-semibold">关联内容</h2>
        <div className="space-y-4">
          {creator.contents.length ? (
            creator.contents.map((content) => (
              <ContentCard key={content.id} content={content} />
            ))
          ) : (
            <Card className="p-8 text-center text-sm text-muted">
              暂无关联内容
            </Card>
          )}
        </div>
      </section>
    </div>
  );
}

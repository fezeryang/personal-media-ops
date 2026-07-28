import { ArrowLeft, ArrowUpRight, UserRound } from "lucide-react";
import { Link, useParams } from "react-router";

import { ErrorState } from "../components/error-state";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { ContentCard } from "../features/library/components/content-card";
import { SafeImage } from "../features/library/components/safe-image";
import { useLibraryCreatorQuery } from "../features/library/hooks/use-library-queries";
import { formatDateTime } from "../lib/utils";

export function LibraryCreatorPage() {
  const { creatorId = "" } = useParams();
  const query = useLibraryCreatorQuery(creatorId);

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

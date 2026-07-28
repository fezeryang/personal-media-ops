import { ArrowLeft, ArrowUpRight, MessageCircle } from "lucide-react";
import { Link, useParams } from "react-router";

import { ErrorState } from "../components/error-state";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { SafeImage } from "../features/library/components/safe-image";
import { useLibraryContentQuery } from "../features/library/hooks/use-library-queries";
import { formatDateTime } from "../lib/utils";

function metric(label: string, value: number | null) {
  return (
    <div className="rounded-xl border border-line bg-paper p-3">
      <p className="text-[10px] font-semibold text-muted">{label}</p>
      <p className="mt-1 font-semibold tabular-nums">
        {value === null ? "—" : value.toLocaleString("zh-CN")}
      </p>
    </div>
  );
}

export function LibraryContentPage() {
  const { contentId = "" } = useParams();
  const query = useLibraryContentQuery(contentId);

  if (query.isPending) {
    return <div className="h-96 animate-pulse rounded-2xl bg-white" />;
  }
  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="无法打开内容资料"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }
  const content = query.data;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm">
        <Link to="/library">
          <ArrowLeft className="size-4" />
          返回资料库
        </Link>
      </Button>
      <header className="grid gap-6 border-b border-line pb-7 md:grid-cols-[220px_minmax(0,1fr)]">
        <SafeImage
          src={content.cover_url}
          alt={content.title ?? "内容封面"}
          className="aspect-video w-full rounded-2xl md:aspect-square"
        />
        <div>
          <p className="text-xs font-semibold text-signal-strong">
            {content.platform} · {content.content_type}
          </p>
          <h1 className="mt-2 whitespace-pre-wrap font-display text-3xl font-semibold tracking-tight">
            {content.title ?? "无标题内容"}
          </h1>
          <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-muted">
            {content.description ?? "暂无摘要"}
          </p>
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted">
            <span>源 ID {content.source_content_id}</span>
            <span>最近采集 {formatDateTime(content.last_collected_at)}</span>
            {content.source_url ? (
              <a
                href={content.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 font-semibold text-signal-strong"
              >
                打开原始链接
                <ArrowUpRight className="size-3" />
              </a>
            ) : null}
          </div>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {metric("浏览", content.view_count)}
        {metric("点赞", content.like_count)}
        {metric("收藏", content.favorite_count)}
        {metric("评论", content.comment_count)}
        {metric("分享", content.share_count)}
      </section>

      {content.creator ? (
        <Card>
          <CardContent>
            <p className="text-xs font-semibold text-muted">关联创作者</p>
            <Link
              to={`/library/creators/${encodeURIComponent(content.creator.id)}`}
              className="mt-2 inline-block font-display text-xl font-semibold text-ink hover:text-signal-strong"
            >
              {content.creator.display_name ?? content.creator.source_creator_id}
            </Link>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent>
          <div className="flex items-center gap-2">
            <MessageCircle className="size-4 text-signal" />
            <h2 className="font-display text-lg font-semibold">
              评论 {content.comments.length}
            </h2>
          </div>
          <div className="mt-4 divide-y divide-line">
            {content.comments.length ? (
              content.comments.map((comment) => (
                <article key={comment.id} className="py-4">
                  <div className="flex flex-wrap justify-between gap-2 text-xs text-muted">
                    <span>{comment.author_name ?? "匿名用户"}</span>
                    <span>{formatDateTime(comment.published_at)}</span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-ink">
                    {comment.body}
                  </p>
                  {comment.parent_comment_id ? (
                    <p className="mt-2 text-[11px] text-muted">
                      回复于 {comment.parent_comment_id}
                    </p>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="py-8 text-center text-sm text-muted">尚未采集评论</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <p className="text-xs font-semibold text-muted">采集溯源</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {content.tasks.map((task) => (
              <Link
                key={task.task_id}
                to={`/crawler/tasks/${encodeURIComponent(task.task_id)}`}
                className="rounded-lg border border-line bg-paper px-3 py-2 font-mono text-xs text-ink"
              >
                {task.task_id}
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

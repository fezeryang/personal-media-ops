import {
  ArrowLeft,
  ArrowUpRight,
  Heart,
  MessageCircle,
  TrendingUp,
  X,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ErrorState } from "../components/error-state";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { SafeImage } from "../features/library/components/safe-image";
import { useLibraryContentQuery } from "../features/library/hooks/use-library-queries";
import { formatDateTime } from "../lib/utils";
import { listContentMetrics } from "../api/library";
import {
  addTag,
  listTags,
  removeTag,
  setFavorite,
} from "../api/organization";

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

const metricKeys = [
  "view_count",
  "like_count",
  "favorite_count",
  "comment_count",
  "share_count",
] as const;

export function LibraryContentPage() {
  const { contentId = "" } = useParams();
  const query = useLibraryContentQuery(contentId);
  const queryClient = useQueryClient();
  const tags = useQuery({
    queryKey: ["library", "tags"],
    queryFn: ({ signal }) => listTags(signal),
  });
  const metrics = useQuery({
    queryKey: ["library", "contents", contentId, "metrics"],
    queryFn: ({ signal }) => listContentMetrics(contentId, signal),
    enabled: Boolean(contentId),
  });
  const refreshContent = () =>
    queryClient.invalidateQueries({
      queryKey: ["library", "contents", contentId],
    });
  const favorite = useMutation({
    mutationFn: (value: boolean) => setFavorite(contentId, value),
    onSuccess: refreshContent,
  });
  const assignTag = useMutation({
    mutationFn: (tagId: string) => addTag(contentId, tagId),
    onSuccess: refreshContent,
  });
  const unassignTag = useMutation({
    mutationFn: (tagId: string) => removeTag(contentId, tagId),
    onSuccess: refreshContent,
  });

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
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button
              variant={content.is_favorite ? "secondary" : "ghost"}
              size="sm"
              onClick={() => favorite.mutate(!content.is_favorite)}
            >
              <Heart
                className="size-4"
                fill={content.is_favorite ? "currentColor" : "none"}
              />
              {content.is_favorite ? "已收藏" : "收藏"}
            </Button>
            {content.tags?.map((tag) => (
              <button
                type="button"
                key={tag.id}
                className="inline-flex items-center gap-1 rounded-full bg-[#e7f5f1] px-2.5 py-1 text-xs font-semibold text-signal-strong"
                onClick={() => unassignTag.mutate(tag.id)}
              >
                #{tag.name} <X className="size-3" />
              </button>
            ))}
            <select
              className="h-8 rounded-lg border border-line bg-white px-2 text-xs"
              aria-label="给内容添加标签"
              value=""
              onChange={(event) => {
                if (event.currentTarget.value) {
                  assignTag.mutate(event.currentTarget.value);
                }
              }}
            >
              <option value="">＋ 添加标签</option>
              {(tags.data ?? [])
                .filter(
                  (tag) =>
                    !content.tags?.some((current) => current.id === tag.id),
                )
                .map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.name}
                  </option>
                ))}
            </select>
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

      <Card>
        <CardContent>
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-signal" />
            <h2 className="font-display text-lg font-semibold">指标快照</h2>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-xs">
              <thead className="text-muted">
                <tr>
                  <th className="pb-2 font-semibold">采集时间</th>
                  <th className="pb-2 font-semibold">浏览</th>
                  <th className="pb-2 font-semibold">点赞</th>
                  <th className="pb-2 font-semibold">收藏</th>
                  <th className="pb-2 font-semibold">评论</th>
                  <th className="pb-2 font-semibold">分享</th>
                </tr>
              </thead>
              <tbody>
                {(metrics.data?.items ?? []).map((snapshot) => (
                  <tr key={snapshot.id} className="border-t border-line">
                    <td className="py-3">
                      {formatDateTime(snapshot.captured_at)}
                    </td>
                    {metricKeys.map((key) => {
                      const value = snapshot[key];
                      return (
                        <td key={key} className="py-3 tabular-nums">
                          {value === null ? "—" : value}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {!metrics.data?.items.length ? (
              <p className="py-6 text-center text-sm text-muted">
                尚无指标快照
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

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

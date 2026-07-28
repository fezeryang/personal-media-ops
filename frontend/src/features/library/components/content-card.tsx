import { ArrowUpRight, Heart, MessageCircle } from "lucide-react";
import { Link } from "react-router";

import type { LibraryContent } from "../../../api/library";
import { Badge } from "../../../components/ui/badge";
import { formatDateTime } from "../../../lib/utils";
import { SafeImage } from "./safe-image";

interface ContentCardProps {
  content: LibraryContent;
  onFavoriteChange?: (contentId: string, isFavorite: boolean) => void;
}

function metric(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("zh-CN");
}

export function ContentCard({
  content,
  onFavoriteChange,
}: ContentCardProps) {
  return (
    <article className="grid gap-4 rounded-2xl border border-line bg-white p-4 sm:grid-cols-[128px_minmax(0,1fr)]">
      <SafeImage
        src={content.cover_url}
        alt={content.title ?? "内容封面"}
        className="aspect-video w-full rounded-xl sm:aspect-square"
      />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="neutral">{content.platform}</Badge>
          <span className="text-[11px] text-muted">{content.content_type}</span>
          {content.has_comments ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-signal-strong">
              <MessageCircle className="size-3" />
              已有评论
            </span>
          ) : null}
          {onFavoriteChange ? (
            <button
              type="button"
              aria-label={content.is_favorite ? "取消收藏" : "收藏内容"}
              className={`ml-auto inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${
                content.is_favorite
                  ? "bg-warning/10 text-warning-strong"
                  : "text-muted hover:bg-paper"
              }`}
              onClick={() =>
                onFavoriteChange(content.id, !content.is_favorite)
              }
            >
              <Heart
                className="size-3.5"
                fill={content.is_favorite ? "currentColor" : "none"}
              />
              {content.is_favorite ? "已收藏" : "收藏"}
            </button>
          ) : null}
        </div>
        <h2 className="mt-2 line-clamp-2 font-display text-lg font-semibold text-ink">
          <Link
            to={`/library/contents/${encodeURIComponent(content.id)}`}
            className="hover:text-signal-strong"
          >
            {content.title ?? "无标题内容"}
          </Link>
        </h2>
        <p className="mt-1 line-clamp-2 whitespace-pre-wrap text-sm leading-6 text-muted">
          {content.description ?? "暂无摘要"}
        </p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          <span>作者 {content.author_name ?? "未知"}</span>
          <span>赞 {metric(content.like_count)}</span>
          <span>评 {metric(content.comment_count)}</span>
          <span>采集 {formatDateTime(content.last_collected_at)}</span>
        </div>
        {content.tags?.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {content.tags.map((tag) => (
              <span
                key={tag.id}
                className="rounded-full bg-[#e7f5f1] px-2 py-1 text-[11px] font-semibold text-signal-strong"
              >
                #{tag.name}
              </span>
            ))}
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
          <Link
            to={`/library/contents/${encodeURIComponent(content.id)}`}
            className="font-semibold text-signal-strong"
          >
            查看资料详情
          </Link>
          {content.source_url ? (
            <a
              href={content.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-muted hover:text-ink"
            >
              原始链接
              <ArrowUpRight className="size-3" />
            </a>
          ) : null}
        </div>
      </div>
    </article>
  );
}

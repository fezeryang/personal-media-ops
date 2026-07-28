import type { CrawlerResult } from "../../../api/crawler";

export interface NormalizedCrawlerResult {
  title: string;
  description: string | null;
  author: string;
  contentUrl: string | null;
  coverUrl: string | null;
  playCount: string;
  likeCount: string;
  favoriteCount: string;
  commentCount: string;
  shareCount: string;
  publishedAt: number | null;
  sourceKeyword: string | null;
  rawPayload: Record<string, unknown>;
}

function displayCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("zh-CN");
}

function safeHttpUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

export function normalizeCrawlerResult(
  record: CrawlerResult,
): NormalizedCrawlerResult {
  return {
    title: record.title.trim() || record.description?.trim() || "未提供标题",
    description: record.description?.trim() || null,
    author: record.author_name?.trim() || "未知作者",
    contentUrl: safeHttpUrl(record.content_url),
    coverUrl: safeHttpUrl(record.cover_url),
    playCount: displayCount(record.metrics.play_count),
    likeCount: displayCount(record.metrics.like_count),
    favoriteCount: displayCount(record.metrics.favorite_count),
    commentCount: displayCount(record.metrics.comment_count),
    shareCount: displayCount(record.metrics.share_count),
    publishedAt: record.published_at,
    sourceKeyword: record.source_keyword?.trim() || null,
    rawPayload: record.raw_payload,
  };
}

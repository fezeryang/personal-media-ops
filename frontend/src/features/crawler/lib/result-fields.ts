export interface NormalizedCrawlerResult {
  title: string;
  author: string;
  videoUrl: string | null;
  coverUrl: string | null;
  playCount: string;
  likeCount: string;
  favoriteCount: string;
  commentCount: string;
  publishedAt: string | null;
  sourceKeyword: string | null;
}

function firstValue(
  record: Record<string, unknown>,
  keys: readonly string[],
): unknown {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }
  return null;
}

function displayValue(value: unknown, fallback: string): string {
  if (typeof value === "string") {
    return value.trim() || fallback;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return fallback;
}

function nullableText(value: unknown): string | null {
  const text = displayValue(value, "");
  return text || null;
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

function videoUrl(record: Record<string, unknown>): string | null {
  const direct = safeHttpUrl(
    firstValue(record, ["video_url", "url", "target_url", "note_url"]),
  );
  if (direct) return direct;

  const bvid = firstValue(record, ["bvid", "video_id"]);
  if (typeof bvid === "string" && /^BV[0-9A-Za-z]+$/.test(bvid)) {
    return `https://www.bilibili.com/video/${bvid}`;
  }
  return null;
}

export function normalizeCrawlerResult(
  record: Record<string, unknown>,
): NormalizedCrawlerResult {
  return {
    title: displayValue(
      firstValue(record, ["title", "video_name", "desc"]),
      "未提供标题",
    ),
    author: displayValue(
      firstValue(record, [
        "nickname",
        "author",
        "user_name",
        "uname",
        "creator_nickname",
      ]),
      "未知作者",
    ),
    videoUrl: videoUrl(record),
    coverUrl: safeHttpUrl(
      firstValue(record, ["cover", "cover_url", "pic", "image_url"]),
    ),
    playCount: displayValue(
      firstValue(record, [
        "video_play_count",
        "play_count",
        "view_count",
        "view",
      ]),
      "—",
    ),
    likeCount: displayValue(
      firstValue(record, ["liked_count", "like_count", "like"]),
      "—",
    ),
    favoriteCount: displayValue(
      firstValue(record, [
        "collected_count",
        "favorite_count",
        "fav_count",
        "favorite",
      ]),
      "—",
    ),
    commentCount: displayValue(
      firstValue(record, [
        "video_comment",
        "comment_count",
        "comments_count",
        "reply",
      ]),
      "—",
    ),
    publishedAt: nullableText(
      firstValue(record, [
        "publish_time",
        "published_at",
        "create_time",
        "pubdate",
      ]),
    ),
    sourceKeyword: nullableText(
      firstValue(record, ["source_keyword", "keyword", "search_keyword"]),
    ),
  };
}

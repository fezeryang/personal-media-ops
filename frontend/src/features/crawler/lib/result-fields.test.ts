import { normalizeCrawlerResult } from "./result-fields";

describe("crawler result normalization", () => {
  it("formats the unified crawler result contract", () => {
    expect(
      normalizeCrawlerResult({
        platform: "bili",
        content_id: "BV123",
        content_type: "video",
        title: "A useful video",
        description: null,
        author_name: "Uploader",
        content_url: "https://www.bilibili.com/video/BV123",
        cover_url: "https://i.example.test/cover.jpg",
        published_at: 1700000000,
        source_keyword: "AI Agent",
        metrics: {
          play_count: 12000,
          like_count: 456,
          favorite_count: 78,
          comment_count: 9,
          share_count: 3,
        },
      }),
    ).toMatchObject({
      title: "A useful video",
      author: "Uploader",
      contentUrl: "https://www.bilibili.com/video/BV123",
      coverUrl: "https://i.example.test/cover.jpg",
      playCount: "12,000",
      likeCount: "456",
      favoriteCount: "78",
      commentCount: "9",
      publishedAt: 1700000000,
      sourceKeyword: "AI Agent",
    });
  });

  it("rejects unsafe URLs and degrades missing fields", () => {
    expect(
      normalizeCrawlerResult({
        platform: "xhs",
        content_id: "note-1",
        content_type: "note",
        title: "<img src=x onerror=alert(1)>",
        description: null,
        author_name: null,
        content_url: "javascript:alert(1)",
        cover_url: "data:text/html,bad",
        published_at: null,
        source_keyword: null,
        metrics: {
          play_count: null,
          like_count: null,
          favorite_count: null,
          comment_count: null,
          share_count: null,
        },
      }),
    ).toEqual({
      title: "<img src=x onerror=alert(1)>",
      author: "未知作者",
      contentUrl: null,
      coverUrl: null,
      playCount: "—",
      likeCount: "—",
      favoriteCount: "—",
      commentCount: "—",
      publishedAt: null,
      sourceKeyword: null,
    });
  });
});

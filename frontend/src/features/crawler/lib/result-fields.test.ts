import { normalizeCrawlerResult } from "./result-fields";

describe("crawler result normalization", () => {
  it("normalizes common MediaCrawler Bilibili fields", () => {
    expect(
      normalizeCrawlerResult({
        title: "A useful video",
        nickname: "Uploader",
        video_url: "https://www.bilibili.com/video/BV123",
        cover: "https://i.example.test/cover.jpg",
        video_play_count: "1.2万",
        liked_count: 456,
        collected_count: "78",
        video_comment: 9,
        publish_time: "2026-07-26 18:00:00",
        source_keyword: "AI Agent",
      }),
    ).toMatchObject({
      title: "A useful video",
      author: "Uploader",
      videoUrl: "https://www.bilibili.com/video/BV123",
      coverUrl: "https://i.example.test/cover.jpg",
      playCount: "1.2万",
      likeCount: "456",
      favoriteCount: "78",
      commentCount: "9",
      publishedAt: "2026-07-26 18:00:00",
      sourceKeyword: "AI Agent",
    });
  });

  it("constructs a safe Bilibili URL from bvid", () => {
    expect(normalizeCrawlerResult({ bvid: "BV1AB411C7M9" }).videoUrl).toBe(
      "https://www.bilibili.com/video/BV1AB411C7M9",
    );
  });

  it("rejects unsafe URLs and degrades missing fields", () => {
    expect(
      normalizeCrawlerResult({
        title: "<img src=x onerror=alert(1)>",
        video_url: "javascript:alert(1)",
        cover: "data:text/html,bad",
        bvid: "../unsafe",
      }),
    ).toEqual({
      title: "<img src=x onerror=alert(1)>",
      author: "未知作者",
      videoUrl: null,
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

import {
  getLibraryContent,
  getLibraryCreator,
  getLibraryStats,
  listLibraryComments,
  listLibraryContents,
  listLibraryCreators,
} from "./library";

const content = {
  id: "content-1",
  platform: "bili",
  source_content_id: "BV1",
  content_type: "video",
  title: "<script>alert(1)</script>Visible",
  description: null,
  source_url: "https://www.bilibili.com/video/BV1",
  cover_url: null,
  author_source_id: "42",
  author_name: "Creator",
  published_at: null,
  first_collected_at: "2026-07-28T00:00:00Z",
  last_collected_at: "2026-07-28T00:01:00Z",
  source_keyword: "AI",
  view_count: null,
  like_count: 1,
  favorite_count: null,
  comment_count: 1,
  share_count: null,
  has_comments: true,
};

const creator = {
  id: "creator-1",
  platform: "bili",
  source_creator_id: "42",
  display_name: "Creator",
  profile_url: "https://space.bilibili.com/42",
  avatar_url: null,
  description: null,
  follower_count: null,
  following_count: null,
  content_count: null,
  first_collected_at: "2026-07-28T00:00:00Z",
  last_collected_at: "2026-07-28T00:01:00Z",
};

const comment = {
  id: "comment-1",
  platform: "bili",
  source_comment_id: "100",
  source_content_id: "BV1",
  parent_comment_id: null,
  author_source_id: "84",
  author_name: "Reader",
  body: "<img src=x onerror=alert(1)>plain",
  like_count: null,
  reply_count: 0,
  published_at: null,
  collected_at: "2026-07-28T00:01:00Z",
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("library API", () => {
  it("loads filtered content and stable details", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({
          items: [content],
          offset: 0,
          limit: 20,
          next_offset: 1,
          has_more: false,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...content,
          raw_payload: null,
          creator,
          comments: [comment],
          tasks: [
            {
              task_id: "task-1",
              collected_at: "2026-07-28T00:01:00Z",
            },
          ],
        }),
      );

    await expect(
      listLibraryContents({ platform: "bili", keyword: "AI", has_comments: true }),
    ).resolves.toMatchObject({ items: [{ source_content_id: "BV1" }] });
    await expect(getLibraryContent("content/1")).resolves.toMatchObject({
      creator: { source_creator_id: "42" },
      comments: [{ source_comment_id: "100" }],
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/library/contents?platform=bili&keyword=AI&has_comments=true",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/library/contents/content%2F1",
    );
  });

  it("loads stats, creator details, and comments", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({ contents: 1, creators: 1, comments: 1 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...creator,
          raw_payload: null,
          contents: [content],
          tasks: [],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [comment],
          offset: 0,
          limit: 5,
          next_offset: 1,
          has_more: false,
        }),
      );

    await expect(getLibraryStats()).resolves.toEqual({
      contents: 1,
      creators: 1,
      comments: 1,
    });
    await expect(getLibraryCreator("creator-1")).resolves.toMatchObject({
      contents: [{ id: "content-1" }],
    });
    const comments = await listLibraryComments({
      source_content_id: "BV1",
      limit: 5,
    });
    expect(comments.items[0]?.body).toContain("plain");
  });

  it("loads filtered creator pages without empty query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({
        items: [creator],
        offset: 0,
        limit: 20,
        next_offset: 1,
        has_more: false,
      }),
    );

    await expect(
      listLibraryCreators({ platform: "bili", query: "", offset: 0 }),
    ).resolves.toMatchObject({
      items: [{ source_creator_id: "42" }],
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/library/creators?platform=bili&offset=0",
    );
  });

  it("rejects unsafe source URLs at the client contract boundary", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({
        items: [{ ...content, source_url: "javascript:alert(1)" }],
        offset: 0,
        limit: 20,
        next_offset: 1,
        has_more: false,
      }),
    );

    await expect(listLibraryContents()).rejects.toMatchObject({
      status: 502,
    });
  });
});

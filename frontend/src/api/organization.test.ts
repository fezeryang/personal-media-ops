import {
  addCollectionItem,
  addTag,
  createCollection,
  createTag,
  getCollection,
  listCollections,
  listTags,
  removeCollectionItem,
  removeTag,
  setFavorite,
} from "./organization";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const tag = {
  id: "tag-1",
  name: "研究",
  content_count: 0,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
};

const content = {
  id: "content-1",
  platform: "bili",
  source_content_id: "BV1",
  content_type: "video",
  title: "Evidence",
  description: null,
  source_url: "https://www.bilibili.com/video/BV1",
  cover_url: null,
  author_source_id: "creator-source",
  author_name: "Creator",
  published_at: null,
  first_collected_at: "2026-07-28T00:00:00Z",
  last_collected_at: "2026-07-28T00:00:00Z",
  source_keyword: "AI Agent",
  view_count: 1,
  like_count: null,
  favorite_count: null,
  comment_count: null,
  share_count: null,
  has_comments: false,
  is_favorite: false,
  tags: [],
};

const collection = {
  id: "collection-1",
  name: "AI Agent",
  description: "Research evidence",
  content_count: 1,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
};

const collectionDetail = {
  ...collection,
  items: [
    {
      content,
      position: 0,
      created_at: "2026-07-28T00:00:00Z",
    },
  ],
};

describe("organization API", () => {
  it("covers tags, favorites, collections, and encoded item paths", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([tag]))
      .mockResolvedValueOnce(jsonResponse(tag))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        jsonResponse({ id: "content/1", is_favorite: true }),
      )
      .mockResolvedValueOnce(jsonResponse([collection]))
      .mockResolvedValueOnce(jsonResponse(collectionDetail))
      .mockResolvedValueOnce(jsonResponse(collectionDetail))
      .mockResolvedValueOnce(
        jsonResponse({
          content,
          position: 2,
          created_at: "2026-07-28T00:00:00Z",
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(listTags()).resolves.toEqual([tag]);
    await expect(createTag("研究")).resolves.toEqual(tag);
    await addTag("content/1", "tag/1");
    await removeTag("content/1", "tag/1");
    await expect(setFavorite("content/1", true)).resolves.toEqual({
      id: "content/1",
      is_favorite: true,
    });
    await expect(listCollections()).resolves.toEqual([collection]);
    await expect(getCollection("collection/1")).resolves.toEqual(
      collectionDetail,
    );
    await expect(
      createCollection({
        name: "AI Agent",
        description: "Research evidence",
      }),
    ).resolves.toEqual(collectionDetail);
    await expect(
      addCollectionItem("collection/1", "content/1", 2),
    ).resolves.toMatchObject({ position: 2 });
    await removeCollectionItem("collection/1", "content/1");

    expect(fetchMock.mock.calls[2]?.[0]).toBe(
      "/api/library/contents/content%2F1/tags/tag%2F1",
    );
    expect(fetchMock.mock.calls[6]?.[0]).toBe(
      "/api/library/collections/collection%2F1",
    );
    expect(fetchMock.mock.calls[9]?.[0]).toBe(
      "/api/library/collections/collection%2F1/items/content%2F1",
    );
  });
});

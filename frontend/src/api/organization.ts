import { z } from "zod";

import { requestEmpty, requestJson } from "./client";
import { libraryContentSchema } from "./library";

export const tagSchema = z.object({
  id: z.string(),
  name: z.string(),
  content_count: z.number().int().nonnegative(),
  created_at: z.string(),
  updated_at: z.string(),
});

const collectionSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  content_count: z.number().int().nonnegative(),
  created_at: z.string(),
  updated_at: z.string(),
});

const collectionDetailSchema = collectionSchema.extend({
  items: z.array(
    z.object({
      content: libraryContentSchema,
      position: z.number().int().nonnegative(),
      created_at: z.string(),
    }),
  ),
});

export type Tag = z.infer<typeof tagSchema>;
export type Collection = z.infer<typeof collectionSchema>;

export function listTags(signal?: AbortSignal): Promise<Tag[]> {
  return requestJson("/api/library/tags", z.array(tagSchema), { signal });
}

export function createTag(name: string): Promise<Tag> {
  return requestJson("/api/library/tags", tagSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function addTag(contentId: string, tagId: string): Promise<void> {
  return requestEmpty(
    `/api/library/contents/${encodeURIComponent(contentId)}/tags/${encodeURIComponent(tagId)}`,
    { method: "POST" },
  );
}

export function removeTag(contentId: string, tagId: string): Promise<void> {
  return requestEmpty(
    `/api/library/contents/${encodeURIComponent(contentId)}/tags/${encodeURIComponent(tagId)}`,
    { method: "DELETE" },
  );
}

export function setFavorite(contentId: string, isFavorite: boolean) {
  return requestJson(
    `/api/library/contents/${encodeURIComponent(contentId)}/favorite`,
    z.object({ id: z.string(), is_favorite: z.boolean() }),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_favorite: isFavorite }),
    },
  );
}

export function listCollections(
  signal?: AbortSignal,
): Promise<Collection[]> {
  return requestJson("/api/library/collections", z.array(collectionSchema), {
    signal,
  });
}

export function getCollection(id: string, signal?: AbortSignal) {
  return requestJson(
    `/api/library/collections/${encodeURIComponent(id)}`,
    collectionDetailSchema,
    { signal },
  );
}

export function createCollection(input: {
  name: string;
  description: string | null;
}) {
  return requestJson("/api/library/collections", collectionDetailSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function addCollectionItem(
  collectionId: string,
  contentId: string,
  position: number,
) {
  return requestJson(
    `/api/library/collections/${encodeURIComponent(collectionId)}/items`,
    z.object({
      content: libraryContentSchema,
      position: z.number().int(),
      created_at: z.string(),
    }),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content_id: contentId, position }),
    },
  );
}

export function removeCollectionItem(
  collectionId: string,
  contentId: string,
): Promise<void> {
  return requestEmpty(
    `/api/library/collections/${encodeURIComponent(collectionId)}/items/${encodeURIComponent(contentId)}`,
    { method: "DELETE" },
  );
}

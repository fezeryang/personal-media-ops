import { z } from "zod";

import { requestJson } from "./client";

const optionalHttpUrlSchema = z
  .string()
  .url()
  .refine((value) => {
    const protocol = new URL(value).protocol;
    return protocol === "http:" || protocol === "https:";
  })
  .nullable();

export const libraryContentSchema = z.object({
  id: z.string(),
  platform: z.string(),
  source_content_id: z.string(),
  content_type: z.string(),
  title: z.string().nullable(),
  description: z.string().nullable(),
  source_url: optionalHttpUrlSchema,
  cover_url: optionalHttpUrlSchema,
  author_source_id: z.string().nullable(),
  author_name: z.string().nullable(),
  published_at: z.string().nullable(),
  first_collected_at: z.string(),
  last_collected_at: z.string(),
  source_keyword: z.string().nullable(),
  view_count: z.number().int().nonnegative().nullable(),
  like_count: z.number().int().nonnegative().nullable(),
  favorite_count: z.number().int().nonnegative().nullable(),
  comment_count: z.number().int().nonnegative().nullable(),
  share_count: z.number().int().nonnegative().nullable(),
  has_comments: z.boolean(),
  created_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

export const libraryCreatorSchema = z.object({
  id: z.string(),
  platform: z.string(),
  source_creator_id: z.string(),
  display_name: z.string().nullable(),
  profile_url: optionalHttpUrlSchema,
  avatar_url: optionalHttpUrlSchema,
  description: z.string().nullable(),
  follower_count: z.number().int().nonnegative().nullable(),
  following_count: z.number().int().nonnegative().nullable(),
  content_count: z.number().int().nonnegative().nullable(),
  first_collected_at: z.string(),
  last_collected_at: z.string(),
  created_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

export const libraryCommentSchema = z.object({
  id: z.string(),
  platform: z.string(),
  source_comment_id: z.string(),
  source_content_id: z.string(),
  parent_comment_id: z.string().nullable(),
  author_source_id: z.string().nullable(),
  author_name: z.string().nullable(),
  body: z.string(),
  like_count: z.number().int().nonnegative().nullable(),
  reply_count: z.number().int().nonnegative().nullable(),
  published_at: z.string().nullable(),
  collected_at: z.string(),
});

const taskProvenanceSchema = z.object({
  task_id: z.string(),
  collected_at: z.string(),
});

const pageFields = {
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  next_offset: z.number().int().nonnegative(),
  has_more: z.boolean(),
};

const libraryContentPageSchema = z.object({
  items: z.array(libraryContentSchema),
  ...pageFields,
});

const libraryCreatorPageSchema = z.object({
  items: z.array(libraryCreatorSchema),
  ...pageFields,
});

const libraryCommentPageSchema = z.object({
  items: z.array(libraryCommentSchema),
  ...pageFields,
});

const libraryContentDetailSchema = libraryContentSchema.extend({
  raw_payload: z.record(z.string(), z.unknown()).nullable(),
  creator: libraryCreatorSchema.nullable(),
  comments: z.array(libraryCommentSchema),
  tasks: z.array(taskProvenanceSchema),
});

const libraryCreatorDetailSchema = libraryCreatorSchema.extend({
  raw_payload: z.record(z.string(), z.unknown()).nullable(),
  contents: z.array(libraryContentSchema),
  tasks: z.array(taskProvenanceSchema),
});

const libraryStatsSchema = z.object({
  contents: z.number().int().nonnegative(),
  creators: z.number().int().nonnegative(),
  comments: z.number().int().nonnegative(),
});

export type LibraryContent = z.infer<typeof libraryContentSchema>;
export type LibraryCreator = z.infer<typeof libraryCreatorSchema>;
export type LibraryComment = z.infer<typeof libraryCommentSchema>;
export type LibraryContentPage = z.infer<typeof libraryContentPageSchema>;
export type LibraryCreatorPage = z.infer<typeof libraryCreatorPageSchema>;
export type LibraryCommentPage = z.infer<typeof libraryCommentPageSchema>;
export type LibraryContentDetail = z.infer<
  typeof libraryContentDetailSchema
>;
export type LibraryCreatorDetail = z.infer<
  typeof libraryCreatorDetailSchema
>;
export type LibraryStats = z.infer<typeof libraryStatsSchema>;

export interface ContentFilters {
  platform?: string;
  content_type?: string;
  keyword?: string;
  creator?: string;
  date_from?: string;
  date_to?: string;
  has_comments?: boolean;
  sort?:
    | "last_collected_desc"
    | "published_desc"
    | "published_asc"
    | "first_collected_desc";
  offset?: number;
  limit?: number;
}

function queryString(
  values: object,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export function getLibraryStats(signal?: AbortSignal): Promise<LibraryStats> {
  return requestJson("/api/library/stats", libraryStatsSchema, { signal });
}

export function listLibraryContents(
  filters: ContentFilters = {},
  signal?: AbortSignal,
): Promise<LibraryContentPage> {
  return requestJson(
    `/api/library/contents${queryString(filters)}`,
    libraryContentPageSchema,
    { signal },
  );
}

export function getLibraryContent(
  contentId: string,
  signal?: AbortSignal,
): Promise<LibraryContentDetail> {
  return requestJson(
    `/api/library/contents/${encodeURIComponent(contentId)}`,
    libraryContentDetailSchema,
    { signal },
  );
}

export function listLibraryCreators(
  filters: {
    platform?: string;
    query?: string;
    offset?: number;
    limit?: number;
  } = {},
  signal?: AbortSignal,
): Promise<LibraryCreatorPage> {
  return requestJson(
    `/api/library/creators${queryString(filters)}`,
    libraryCreatorPageSchema,
    { signal },
  );
}

export function getLibraryCreator(
  creatorId: string,
  signal?: AbortSignal,
): Promise<LibraryCreatorDetail> {
  return requestJson(
    `/api/library/creators/${encodeURIComponent(creatorId)}`,
    libraryCreatorDetailSchema,
    { signal },
  );
}

export function listLibraryComments(
  filters: {
    platform?: string;
    source_content_id?: string;
    parent_comment_id?: string;
    offset?: number;
    limit?: number;
  } = {},
  signal?: AbortSignal,
): Promise<LibraryCommentPage> {
  return requestJson(
    `/api/library/comments${queryString(filters)}`,
    libraryCommentPageSchema,
    { signal },
  );
}

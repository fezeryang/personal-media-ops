import { z } from "zod";

import { ApiError, requestBlob, requestJson, requestText } from "./client";

export const crawlerTaskStatusSchema = z.enum([
  "pending",
  "running",
  "waiting_login",
  "succeeded",
  "failed",
  "cancelled",
]);

export const crawlerTaskSchema = z.object({
  id: z.string(),
  platform: z.string(),
  crawler_type: z.string(),
  keywords: z.string(),
  login_type: z.string(),
  status: crawlerTaskStatusSchema,
  requested_count: z.number().int(),
  actual_count: z.number().int(),
  output_dir: z.string(),
  log_path: z.string(),
  qrcode_path: z.string(),
  pid: z.number().int().nullable(),
  error_message: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  cancel_requested: z.boolean(),
});

const crawlerTaskListSchema = z.array(crawlerTaskSchema);

const capabilityOptionSchema = z.object({
  value: z.string(),
  label: z.string(),
});

export const crawlerPlatformCapabilitySchema = z.object({
  platform: z.string(),
  display_name: z.string(),
  icon_label: z.string().min(1).max(4),
  enabled: z.boolean(),
  verification_status: z.enum([
    "not_implemented",
    "code_ready",
    "production_verified",
  ]),
  availability_status: z.enum([
    "enabled",
    "disabled",
    "deferred_resource_constrained",
    "deferred_upstream_breakage",
    "deferred_login_required",
  ]),
  login_prompt: z.string().min(1),
  crawler_types: z.array(capabilityOptionSchema).min(1),
  login_types: z.array(capabilityOptionSchema).min(1),
  requested_count: z.object({
    minimum: z.number().int().positive(),
    maximum: z.number().int().positive(),
    default: z.number().int().positive(),
  }),
  supports_comments: z.boolean(),
  supports_sub_comments: z.boolean(),
});

const crawlerCapabilitiesSchema = z.object({
  max_concurrent_tasks: z.number().int().positive(),
  platforms: z.array(crawlerPlatformCapabilitySchema),
});

function isSafeHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

const optionalHttpUrlSchema = z
  .string()
  .refine(isSafeHttpUrl)
  .nullable();

export const crawlerResultSchema = z.object({
  platform: z.string(),
  content_id: z.string(),
  content_type: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  author_name: z.string().nullable(),
  content_url: optionalHttpUrlSchema,
  cover_url: optionalHttpUrlSchema,
  published_at: z.number().int().nonnegative().nullable(),
  source_keyword: z.string().nullable(),
  raw_payload: z.record(z.string(), z.unknown()),
  metrics: z.object({
    play_count: z.number().int().nonnegative().nullable(),
    like_count: z.number().int().nonnegative().nullable(),
    favorite_count: z.number().int().nonnegative().nullable(),
    comment_count: z.number().int().nonnegative().nullable(),
    share_count: z.number().int().nonnegative().nullable(),
  }),
});

const crawlerResultsSchema = z.object({
  items: z.array(crawlerResultSchema),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  next_offset: z.number().int().nonnegative(),
  has_more: z.boolean(),
});

export type CrawlerTaskStatus = z.infer<typeof crawlerTaskStatusSchema>;
export type CrawlerTask = z.infer<typeof crawlerTaskSchema>;
export type CrawlerPlatformCapability = z.infer<
  typeof crawlerPlatformCapabilitySchema
>;
export type CrawlerCapabilities = z.infer<typeof crawlerCapabilitiesSchema>;
export type CrawlerResult = z.infer<typeof crawlerResultSchema>;
export type CrawlerResults = z.infer<typeof crawlerResultsSchema>;

export interface CreateCrawlerTaskInput {
  platform: string;
  crawler_type: string;
  keywords: string;
  requested_count: number;
}

export function getCrawlerCapabilities(
  signal?: AbortSignal,
): Promise<CrawlerCapabilities> {
  return requestJson("/api/crawler/capabilities", crawlerCapabilitiesSchema, {
    signal,
  });
}

export function listCrawlerTasks(signal?: AbortSignal): Promise<CrawlerTask[]> {
  return requestJson("/api/crawler/tasks", crawlerTaskListSchema, { signal });
}

export function getCrawlerTask(
  taskId: string,
  signal?: AbortSignal,
): Promise<CrawlerTask> {
  return requestJson(
    `/api/crawler/tasks/${encodeURIComponent(taskId)}`,
    crawlerTaskSchema,
    { signal },
  );
}

export function createCrawlerTask(
  input: CreateCrawlerTaskInput,
  signal?: AbortSignal,
): Promise<CrawlerTask> {
  return requestJson("/api/crawler/tasks", crawlerTaskSchema, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function cancelCrawlerTask(
  taskId: string,
  signal?: AbortSignal,
): Promise<CrawlerTask> {
  return requestJson(
    `/api/crawler/tasks/${encodeURIComponent(taskId)}/cancel`,
    crawlerTaskSchema,
    { method: "POST", signal },
  );
}

export function getCrawlerTaskLogs(
  taskId: string,
  tail = 300,
  signal?: AbortSignal,
): Promise<string> {
  const query = new URLSearchParams({ tail: String(tail) });
  return requestText(
    `/api/crawler/tasks/${encodeURIComponent(taskId)}/logs?${query.toString()}`,
    { signal },
  );
}

export async function getCrawlerTaskQrcode(
  taskId: string,
  signal?: AbortSignal,
): Promise<Blob | null> {
  const cacheBuster = Date.now().toString();
  try {
    return await requestBlob(
      `/api/crawler/tasks/${encodeURIComponent(taskId)}/qrcode?t=${cacheBuster}`,
      { signal },
    );
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function getCrawlerTaskResults(
  taskId: string,
  offset: number,
  limit: number,
  signal?: AbortSignal,
): Promise<CrawlerResults> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  return requestJson(
    `/api/crawler/tasks/${encodeURIComponent(taskId)}/results?${query.toString()}`,
    crawlerResultsSchema,
    { signal },
  );
}

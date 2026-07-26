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

const crawlerResultsSchema = z.object({
  items: z.array(z.record(z.string(), z.unknown())),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  next_offset: z.number().int().nonnegative(),
  has_more: z.boolean(),
});

export type CrawlerTaskStatus = z.infer<typeof crawlerTaskStatusSchema>;
export type CrawlerTask = z.infer<typeof crawlerTaskSchema>;
export type CrawlerResults = z.infer<typeof crawlerResultsSchema>;

export interface CreateCrawlerTaskInput {
  platform: "bili";
  crawler_type: "search";
  keywords: string;
  requested_count: number;
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

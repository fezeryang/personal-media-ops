import { z } from "zod";

import { requestJson } from "./client";

const watchRunSchema = z.object({
  id: z.string(),
  watch_id: z.string(),
  scheduled_for: z.string(),
  trigger: z.enum(["manual", "scheduled"]),
  task_id: z.string(),
  status: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  new_content_count: z.number().int().nonnegative(),
  existing_content_count: z.number().int().nonnegative(),
  changed_content_count: z.number().int().nonnegative(),
  error_summary: z.string().nullable(),
  created_at: z.string(),
});

const watchSchema = z.object({
  id: z.string(),
  creator_id: z.string(),
  platform: z.string(),
  creator_name: z.string().nullable(),
  enabled: z.boolean(),
  check_frequency: z.string(),
  requested_count: z.number().int().positive(),
  timezone: z.string(),
  last_checked_at: z.string().nullable(),
  next_check_at: z.string().nullable(),
  last_success_at: z.string().nullable(),
  consecutive_failures: z.number().int().nonnegative(),
  last_error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  runs: z.array(watchRunSchema),
});

export type Watch = z.infer<typeof watchSchema>;

export function listWatches(signal?: AbortSignal): Promise<Watch[]> {
  return requestJson("/api/watchlist", z.array(watchSchema), { signal });
}

export function createWatch(input: {
  creator_id: string;
  enabled: boolean;
  check_frequency: "every_6_hours" | "daily" | "weekly";
  requested_count: number;
  timezone: string;
}): Promise<Watch> {
  return requestJson("/api/watchlist", watchSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function setWatchEnabled(id: string, enabled: boolean): Promise<Watch> {
  return requestJson(`/api/watchlist/${encodeURIComponent(id)}`, watchSchema, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export function runWatch(id: string) {
  return requestJson(
    `/api/watchlist/${encodeURIComponent(id)}/run`,
    watchRunSchema,
    { method: "POST" },
  );
}

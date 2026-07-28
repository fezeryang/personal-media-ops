import { z } from "zod";

import { requestJson } from "./client";

export const trendSchema = z.object({
  id: z.string(),
  topic: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  score: z.number(),
  volume_score: z.number(),
  velocity_score: z.number(),
  cross_platform_score: z.number(),
  engagement_score: z.number(),
  platforms: z.array(z.string()),
  content_ids: z.array(z.string()),
  explanation: z.string(),
  evidence: z.record(z.string(), z.unknown()),
  status: z.enum(["detected", "insufficient_data"]),
  formula_version: z.string(),
  created_at: z.string(),
});

const briefItemSchema = z.object({
  id: z.string(),
  section: z.string(),
  conclusion_type: z.enum([
    "fact",
    "calculation",
    "rule",
    "insufficient_data",
    "unknown",
  ]),
  title: z.string(),
  body: z.string(),
  position: z.number().int(),
  evidence: z.record(z.string(), z.unknown()),
  content_ids: z.array(z.string()),
  trend_ids: z.array(z.string()),
});

export const briefSchema = z.object({
  id: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  timezone: z.string(),
  version: z.number().int().positive(),
  generator: z.enum(["deterministic", "ai_enhanced"]),
  ai_provider: z.string(),
  status: z.string(),
  created_at: z.string(),
  evidence_count: z.number().int().nonnegative(),
  items: z.array(briefItemSchema),
});

const briefScheduleSchema = z.object({
  id: z.string(),
  enabled: z.boolean(),
  timezone: z.string(),
  time_of_day: z.string(),
  last_run_at: z.string().nullable(),
  next_run_at: z.string().nullable(),
  consecutive_failures: z.number().int().nonnegative(),
  last_error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type Trend = z.infer<typeof trendSchema>;
export type Brief = z.infer<typeof briefSchema>;

export function listTrends(signal?: AbortSignal): Promise<Trend[]> {
  return requestJson("/api/intelligence/trends", z.array(trendSchema), {
    signal,
  });
}

export function getLatestBrief(signal?: AbortSignal): Promise<Brief> {
  return requestJson("/api/intelligence/briefs/latest", briefSchema, {
    signal,
  });
}

export function generateTrends(): Promise<Trend[]> {
  return requestJson("/api/intelligence/trends/generate", z.array(trendSchema), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      window_end: new Date().toISOString(),
      window_hours: 24,
    }),
  });
}

export function generateBrief(regenerate = false): Promise<Brief> {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  return requestJson("/api/intelligence/briefs", briefSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      window_start: start.toISOString(),
      window_end: end.toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      regenerate,
    }),
  });
}

export function getBriefSchedule(signal?: AbortSignal) {
  return requestJson(
    "/api/intelligence/briefs/schedule",
    briefScheduleSchema,
    { signal },
  );
}

export function setBriefSchedule(input: {
  enabled: boolean;
  timezone: string;
  time_of_day: string;
}) {
  return requestJson(
    "/api/intelligence/briefs/schedule",
    briefScheduleSchema,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

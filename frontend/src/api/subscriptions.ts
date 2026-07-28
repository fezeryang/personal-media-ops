import { z } from "zod";

import { requestJson } from "./client";

const platformSchema = z.object({
  platform: z.string(),
  requested_count: z.number().int().positive(),
});

const platformRunSchema = z.object({
  platform: z.string(),
  sequence: z.number().int().nonnegative(),
  task_id: z.string(),
  task_status: z.string(),
  new_content_count: z.number().int().nonnegative(),
  existing_content_count: z.number().int().nonnegative(),
  changed_content_count: z.number().int().nonnegative(),
  error_summary: z.string().nullable(),
});

export const subscriptionRunSchema = z.object({
  id: z.string(),
  subscription_id: z.string(),
  scheduled_for: z.string(),
  trigger: z.enum(["manual", "scheduled"]),
  status: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  new_content_count: z.number().int().nonnegative(),
  existing_content_count: z.number().int().nonnegative(),
  changed_content_count: z.number().int().nonnegative(),
  error_summary: z.string().nullable(),
  created_at: z.string(),
  platform_results: z.array(platformRunSchema),
});

export const subscriptionSchema = z.object({
  id: z.string(),
  name: z.string(),
  query: z.string(),
  platforms: z.array(platformSchema),
  enabled: z.boolean(),
  schedule_type: z.enum([
    "manual",
    "every_6_hours",
    "daily",
    "weekdays",
    "weekly",
  ]),
  schedule_config: z.object({
    time_of_day: z.string().optional(),
    weekday: z.number().int().optional(),
  }),
  timezone: z.string(),
  last_run_at: z.string().nullable(),
  next_run_at: z.string().nullable(),
  last_success_at: z.string().nullable(),
  consecutive_failures: z.number().int().nonnegative(),
  last_error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

const subscriptionDetailSchema = subscriptionSchema.extend({
  runs: z.array(subscriptionRunSchema),
});

export type Subscription = z.infer<typeof subscriptionSchema>;
export type SubscriptionRun = z.infer<typeof subscriptionRunSchema>;

export interface SubscriptionInput {
  name: string;
  query: string;
  platforms: { platform: string; requested_count: number }[];
  enabled: boolean;
  schedule_type: Subscription["schedule_type"];
  schedule_config: { time_of_day?: string; weekday?: number };
  timezone: string;
}

export function listSubscriptions(
  signal?: AbortSignal,
): Promise<Subscription[]> {
  return requestJson("/api/subscriptions", z.array(subscriptionSchema), {
    signal,
  });
}

export function getSubscription(
  id: string,
  signal?: AbortSignal,
) {
  return requestJson(
    `/api/subscriptions/${encodeURIComponent(id)}`,
    subscriptionDetailSchema,
    { signal },
  );
}

export function saveSubscription(
  input: SubscriptionInput,
  id?: string,
): Promise<Subscription> {
  return requestJson(
    id
      ? `/api/subscriptions/${encodeURIComponent(id)}`
      : "/api/subscriptions",
    subscriptionSchema,
    {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

export function setSubscriptionEnabled(
  id: string,
  enabled: boolean,
): Promise<Subscription> {
  return requestJson(
    `/api/subscriptions/${encodeURIComponent(id)}/${enabled ? "resume" : "pause"}`,
    subscriptionSchema,
    { method: "POST" },
  );
}

export function runSubscription(id: string): Promise<SubscriptionRun> {
  return requestJson(
    `/api/subscriptions/${encodeURIComponent(id)}/run`,
    subscriptionRunSchema,
    { method: "POST" },
  );
}

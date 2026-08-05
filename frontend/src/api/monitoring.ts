import { z } from "zod";

import { requestJson } from "./client";

const jsonHeaders = { "Content-Type": "application/json" };

const missionTypeSchema = z.enum([
  "topic",
  "entity",
  "creator",
  "event",
  "research_question",
  "query",
]);
const missionStatusSchema = z.enum([
  "draft",
  "active",
  "paused",
  "running",
  "waiting_platform",
  "waiting_login",
  "completed_run",
  "degraded",
  "failed",
  "archived",
]);
const scheduleSchema = z.enum(["manual", "daily", "weekly", "custom"]);
const budgetSchema = z.object({
  max_model_calls: z.number().int().nonnegative(),
  max_total_tokens: z.number().int().nonnegative(),
  max_collection_count: z.number().int().nonnegative(),
  max_platforms: z.number().int().nonnegative(),
  max_runtime_seconds: z.number().int().positive(),
  daily_token_budget: z.number().int().nonnegative(),
  weekly_run_budget: z.number().int().positive(),
});
const targetSchema = z.object({
  id: z.string().optional(),
  target_type: missionTypeSchema,
  target_value: z.string(),
  normalized_key: z.string().optional(),
  created_at: z.string().optional(),
});

export const monitoringMissionSchema = z.object({
  id: z.string(),
  title: z.string(),
  goal: z.string(),
  mission_type: missionTypeSchema,
  status: missionStatusSchema,
  schedule_type: scheduleSchema,
  schedule_config: z.record(z.string(), z.unknown()),
  platforms: z.array(z.string()),
  understanding: z.record(z.string(), z.unknown()),
  budget: budgetSchema,
  next_run_at: z.string().nullable(),
  last_run_at: z.string().nullable(),
  last_run_status: z.string().nullable(),
  latest_change: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const monitoringMissionDetailSchema = monitoringMissionSchema.extend({
  targets: z.array(targetSchema),
  importance_rule: z.string().nullable(),
  ignored_content_rule: z.string().nullable(),
  consecutive_failures: z.number().int().nonnegative(),
  last_error: z.string().nullable(),
});

const runStatusSchema = z.enum([
  "queued",
  "running",
  "waiting_platform",
  "waiting_login",
  "completed",
  "no_meaningful_change",
  "degraded",
  "failed",
  "cancelled",
]);
export const monitoringRunSchema = z.object({
  id: z.string(),
  mission_id: z.string(),
  research_task_id: z.string().nullable(),
  status: runStatusSchema,
  trigger: z.string(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  baseline_created: z.boolean(),
  change_count: z.number().int().nonnegative(),
  notification_count: z.number().int().nonnegative(),
  resource: z.record(z.string(), z.unknown()),
  failure_reason: z.string().nullable(),
  backoff_until: z.string().nullable(),
  claimed_at: z.string().nullable(),
  created_at: z.string(),
  queries: z.array(z.record(z.string(), z.unknown())),
});

export const monitoringBaselineSchema = z.object({
  id: z.string(),
  mission_id: z.string(),
  version: z.number().int().positive(),
  snapshot: z.record(z.string(), z.unknown()),
  source_run_id: z.string().nullable(),
  created_at: z.string(),
});

export const monitoringChangeSchema = z.object({
  id: z.string(),
  source_type: z.literal("monitoring"),
  mission_id: z.string(),
  run_id: z.string(),
  change_type: z.string(),
  fingerprint: z.string(),
  title: z.string(),
  summary: z.string(),
  first_seen_at: z.string().nullable(),
  latest_seen_at: z.string().nullable(),
  relevance_score: z.number(),
  novelty_score: z.number(),
  evidence_strength_score: z.number(),
  source_independence_score: z.number(),
  cross_platform_score: z.number(),
  actionability_score: z.number(),
  persistence_score: z.number(),
  noise_risk_score: z.number(),
  attention_level: z.enum([
    "immediate_attention",
    "daily_digest",
    "normal_record",
    "silent_memory",
    "ignored",
  ]),
  state: z.enum(["new", "read", "deferred", "ignored", "merged"]),
  explanation: z.record(z.string(), z.unknown()),
  sources: z.array(z.record(z.string(), z.unknown())),
  memory_update: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const monitoringNotificationSchema = z.object({
  id: z.string(),
  mission_id: z.string(),
  change_id: z.string(),
  level: z.enum([
    "immediate_attention",
    "daily_digest",
    "normal_record",
    "silent_memory",
    "ignored",
  ]),
  status: z.enum(["unread", "read", "deferred", "ignored"]),
  title: z.string(),
  summary: z.string(),
  created_at: z.string(),
  read_at: z.string().nullable(),
  deferred_until: z.string().nullable(),
  ignored_at: z.string().nullable(),
});

export const monitoringRunResultSchema = monitoringRunSchema.extend({
  baseline: monitoringBaselineSchema.nullable(),
  changes: z.array(z.record(z.string(), z.unknown())),
  outcome: z.string(),
});

export type MonitoringMission = z.infer<typeof monitoringMissionSchema>;
export type MonitoringMissionDetail = z.infer<typeof monitoringMissionDetailSchema>;
export type MonitoringRun = z.infer<typeof monitoringRunSchema>;
export type MonitoringRunResult = z.infer<typeof monitoringRunResultSchema>;
export type MonitoringBaseline = z.infer<typeof monitoringBaselineSchema>;
export type MonitoringChange = z.infer<typeof monitoringChangeSchema>;
export type MonitoringNotification = z.infer<typeof monitoringNotificationSchema>;

export interface MonitoringMissionInput {
  goal: string;
  title?: string;
  mission_type?: z.infer<typeof missionTypeSchema>;
  targets?: Array<{ target_type: z.infer<typeof missionTypeSchema>; target_value: string }>;
  platforms?: string[];
  schedule_type?: z.infer<typeof scheduleSchema>;
  schedule_config?: Record<string, unknown>;
  importance_rule?: string;
  ignored_content_rule?: string;
  confirmed?: boolean;
}

export function listMonitoringMissions(signal?: AbortSignal) {
  return requestJson("/api/monitoring/missions", z.array(monitoringMissionSchema), { signal });
}

export function createMonitoringMission(input: MonitoringMissionInput) {
  return requestJson("/api/monitoring/missions", monitoringMissionDetailSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export function getMonitoringMission(missionId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}`,
    monitoringMissionDetailSchema,
    { signal },
  );
}

export function updateMonitoringMission(
  missionId: string,
  input: Record<string, unknown>,
) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}`,
    monitoringMissionDetailSchema,
    { method: "PATCH", headers: jsonHeaders, body: JSON.stringify(input) },
  );
}

export function confirmMonitoringMission(missionId: string) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}/confirm`,
    monitoringMissionDetailSchema,
    { method: "POST", headers: jsonHeaders },
  );
}

export function runMonitoringMission(missionId: string) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}/run`,
    monitoringRunResultSchema,
    { method: "POST", headers: jsonHeaders },
  );
}

function controlMission(missionId: string, action: "pause" | "resume" | "archive") {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}/${action}`,
    monitoringMissionDetailSchema,
    { method: "POST", headers: jsonHeaders },
  );
}

export const pauseMonitoringMission = (missionId: string) => controlMission(missionId, "pause");
export const resumeMonitoringMission = (missionId: string) => controlMission(missionId, "resume");
export const archiveMonitoringMission = (missionId: string) => controlMission(missionId, "archive");

export function listMonitoringRuns(missionId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}/runs`,
    z.array(monitoringRunSchema),
    { signal },
  );
}

export function listMonitoringChanges(missionId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}/changes`,
    z.array(monitoringChangeSchema),
    { signal },
  );
}

export function getMonitoringBaseline(missionId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/monitoring/missions/${encodeURIComponent(missionId)}/baseline`,
    monitoringBaselineSchema.nullable(),
    { signal },
  );
}

export function listMonitoringNotifications(signal?: AbortSignal) {
  return requestJson("/api/notifications", z.array(monitoringNotificationSchema), { signal });
}

export function updateMonitoringNotification(
  notificationId: string,
  action: "read" | "defer" | "ignore",
  until?: string,
) {
  return requestJson(
    `/api/notifications/${encodeURIComponent(notificationId)}/${action}`,
    monitoringNotificationSchema,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(until ? { until } : {}),
    },
  );
}

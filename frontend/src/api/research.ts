import { z } from "zod";

import { requestJson } from "./client";

const statusSchema = z.enum([
  "Draft",
  "Planning",
  "Researching",
  "WaitingCrawl",
  "WaitingLogin",
  "Summarizing",
  "AwaitingReview",
  "Done",
  "BudgetExceeded",
  "Failed",
  "Cancelled",
]);

const consumptionSchema = z.object({
  crawl_count: z.number().int().nonnegative(),
  content_count: z.number().int().nonnegative(),
  duration_seconds: z.number().int().nonnegative(),
  input_tokens: z.number().int().nonnegative(),
  output_tokens: z.number().int().nonnegative(),
  cached_tokens: z.number().int().nonnegative(),
  estimated_cost: z.string().nullable(),
  cost_enabled: z.boolean(),
  cost_currency: z.string().nullable(),
});

const evidenceSchema = z.object({
  content_id: z.string(),
  platform: z.string().nullable(),
  title: z.string().nullable(),
  source_url: z.string().nullable(),
  author_name: z.string().nullable(),
  published_at: z.string().nullable(),
  collected_at: z.string().nullable(),
  crawl_task_id: z.string().nullable(),
  support_type: z.enum(["direct", "contextual", "contradictory", "background"]).optional(),
  support_strength: z.enum(["strong", "medium", "weak"]).optional(),
  support_explanation: z.string().optional(),
  occurrences: z.array(
    z.object({
      id: z.string(),
      research_task_id: z.string(),
      finding_id: z.string().nullable(),
      content_id: z.string(),
      crawler_task_id: z.string().nullable(),
      research_query_id: z.string().nullable(),
      first_seen_at: z.string(),
      last_seen_at: z.string(),
      occurrence_count: z.number().int().positive(),
    }),
  ).optional(),
});

const findingSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  round_number: z.number().int().nonnegative(),
  kind: z.enum(["fact", "inference"]),
  statement: z.string(),
  derivation: z.string().nullable(),
  counterevidence_status: z.enum(["found", "not_found", "unknown"]).optional(),
  counterevidence_explanation: z.string().optional(),
  status: z.enum(["active", "superseded"]),
  evidence: z.array(evidenceSchema),
  created_at: z.string(),
  updated_at: z.string(),
});

const eventSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  round_number: z.number().int().nonnegative(),
  fingerprint: z.string(),
  title: z.string(),
  summary: z.string(),
  content_ids: z.array(z.string()),
  created_at: z.string(),
  updated_at: z.string(),
});

const actionSchema = z.object({
  id: z.string(),
  action: z.string(),
  reason: z.string(),
  payload: z.record(z.string(), z.unknown()),
  status: z.enum(["pending", "approved", "rejected"]),
  created_at: z.string(),
  decided_at: z.string().nullable(),
});

const traceSchema = z.object({
  sequence: z.number().int().positive(),
  event: z.string(),
  status: statusSchema.nullable(),
  reason: z.string().nullable(),
  round_number: z.number().int().nullable(),
  step: z.string().nullable(),
  tool_name: z.string().nullable(),
  tool_arguments: z.record(z.string(), z.unknown()).nullable(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  route_role: z.string().nullable(),
  request_correlation_id: z.string().nullable(),
  input_tokens: z.number().int().nonnegative().nullable(),
  output_tokens: z.number().int().nonnegative().nullable(),
  elapsed_ms: z.number().int().nonnegative().nullable(),
  created_at: z.string(),
});

const budgetSchema = z.object({
  crawl_limit: z.number().int().nonnegative(),
  content_limit: z.number().int().nonnegative(),
  duration_seconds: z.number().int().positive(),
  token_limit: z.number().int().positive(),
  cost_limit: z.string().nullable(),
  cost_currency: z.string().nullable(),
});

const researchResultSchema = z
  .object({
    summary: z.string().optional(),
    summary_markdown: z.string().optional(),
    summary_html: z.string().optional(),
    evidence_count: z.number().int().nonnegative().optional(),
    new_content_count: z.number().int().nonnegative().optional(),
    existing_content_count: z.number().int().nonnegative().optional(),
    updated_content_count: z.number().int().nonnegative().optional(),
    duplicate_evidence_count: z.number().int().nonnegative().optional(),
    independent_evidence_count: z.number().int().nonnegative().optional(),
    discovery_count: z.number().int().nonnegative().optional(),
  })
  .passthrough();

export const researchTaskSummarySchema = z.object({
  id: z.string(),
  task_type: z.string(),
  objective: z.string(),
  platforms: z.array(z.string()),
  status: statusSchema,
  current_round: z.number().int().nonnegative(),
  current_step: z.string().nullable(),
  paused: z.boolean(),
  consumption: consumptionSchema,
  finding_count: z.number().int().nonnegative(),
  event_count: z.number().int().nonnegative(),
  action_count: z.number().int().nonnegative(),
  created_at: z.string(),
  updated_at: z.string(),
  finished_at: z.string().nullable(),
  failure_reason: z.string().nullable(),
});

export const researchTaskDetailSchema = researchTaskSummarySchema.extend({
  plan: z.record(z.string(), z.unknown()),
  context: z.record(z.string(), z.unknown()),
  result: researchResultSchema.nullable(),
  route_snapshot: z.record(z.string(), z.unknown()),
  budget: budgetSchema,
  trace: z.array(traceSchema),
  findings: z.array(findingSchema),
  queries: z.array(
    z.object({
      id: z.string(),
      research_task_id: z.string(),
      query: z.string(),
      normalized_query: z.string(),
      query_type: z.enum([
        "product",
        "tool",
        "company",
        "creator",
        "person",
        "event",
        "need",
        "scenario",
        "technology",
        "generic_topic",
      ]),
      platform: z.string(),
      source_type: z.string(),
      source_content_id: z.string().nullable(),
      source_finding_id: z.string().nullable(),
      parent_query_id: z.string().nullable(),
      generation_reason: z.string(),
      relevance_score: z.number().min(0).max(1).nullable(),
      specificity_score: z.number().min(0).max(1),
      novelty_score: z.number().min(0).max(1),
      noise_risk_score: z.number().min(0).max(1),
      expected_value_score: z.number().min(0).max(1).nullable(),
      status: z.enum(["candidate", "approved", "rejected", "running", "completed", "failed"]),
      rejection_reason: z.string().nullable(),
      crawler_task_id: z.string().nullable(),
      executed_at: z.string().nullable(),
      result_count: z.number().int().nonnegative(),
      new_content_count: z.number().int().nonnegative(),
      existing_content_count: z.number().int().nonnegative(),
      updated_content_count: z.number().int().nonnegative(),
      duplicate_evidence_count: z.number().int().nonnegative(),
      created_at: z.string(),
      updated_at: z.string(),
    }),
  ).optional(),
  events: z.array(eventSchema),
  actions: z.array(actionSchema),
});

export type ResearchTaskSummary = z.infer<typeof researchTaskSummarySchema>;
export type ResearchTaskDetail = z.infer<typeof researchTaskDetailSchema>;
export type ResearchStatus = z.infer<typeof statusSchema>;

export interface ResearchTaskInput {
  objective: string;
  platforms: string[];
  budget: {
    crawl_limit: number;
    content_limit: number;
    duration_seconds: number;
    token_limit: number;
    cost_limit: string | null;
    cost_currency: string | null;
  };
}

const jsonHeaders = { "Content-Type": "application/json" };

export function listResearchTasks(signal?: AbortSignal) {
  return requestJson("/api/research/tasks", z.array(researchTaskSummarySchema), {
    signal,
  });
}

export function getResearchTask(taskId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/research/tasks/${encodeURIComponent(taskId)}`,
    researchTaskDetailSchema,
    { signal },
  );
}

export function createResearchTask(input: ResearchTaskInput) {
  return requestJson("/api/research/tasks", researchTaskDetailSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

function controlTask(taskId: string, action: "pause" | "resume" | "cancel" | "rerun") {
  return requestJson(
    `/api/research/tasks/${encodeURIComponent(taskId)}/${action}`,
    researchTaskDetailSchema,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify({}) },
  );
}

export const pauseResearchTask = (taskId: string) => controlTask(taskId, "pause");
export const resumeResearchTask = (taskId: string) => controlTask(taskId, "resume");
export const cancelResearchTask = (taskId: string) => controlTask(taskId, "cancel");
export const rerunResearchTask = (taskId: string) => controlTask(taskId, "rerun");

export function completeResearchTask(taskId: string) {
  return requestJson(
    `/api/research/tasks/${encodeURIComponent(taskId)}/complete`,
    researchTaskDetailSchema,
    { method: "POST" },
  );
}

export function decideResearchAction(
  taskId: string,
  actionId: string,
  decision: "approve" | "reject",
) {
  return requestJson(
    `/api/research/tasks/${encodeURIComponent(taskId)}/actions/${encodeURIComponent(actionId)}/${decision}`,
    actionSchema,
    { method: "POST" },
  );
}

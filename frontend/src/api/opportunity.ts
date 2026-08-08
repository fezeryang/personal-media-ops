import { z } from "zod";

import { requestJson } from "./client";

const jsonHeaders = { "Content-Type": "application/json" };

const opportunityTypeSchema = z.enum([
  "product_opportunity",
  "business_opportunity",
  "content_opportunity",
  "research_opportunity",
]);
const readinessSchema = z.enum([
  "insufficient_evidence",
  "needs_more_evidence",
  "review_ready",
  "validation_ready",
  "validated",
]);
const statusSchema = z.enum([
  "weak_signal", "evidence_building", "candidate", "review_ready", "validation_ready",
  "accepted", "rejected", "deferred", "validating", "validated", "invalidated",
  "converted_to_action", "archived",
]);
const sourceSchema = z.object({
  id: z.string(),
  signal_id: z.string().nullable(),
  source_type: z.string(),
  source_id: z.string(),
  evidence_id: z.string().nullable(),
  content_id: z.string().nullable(),
  finding_id: z.string().nullable(),
  source_role: z.enum(["core", "supporting", "counterevidence", "background"]),
  evidence_kind: z.enum(["direct", "inference", "estimate", "unknown"]),
  support_explanation: z.string(),
  source_platform: z.string().nullable(),
  source_url: z.string().nullable(),
  source_title: z.string().nullable(),
  independent_group: z.string().nullable(),
  is_repost: z.boolean(),
  created_at: z.string(),
});
const scoreSchema = z.object({
  id: z.string(),
  version: z.number().int(),
  scores: z.record(z.string(), z.number()),
  explanation: z.record(z.string(), z.unknown()),
  readiness: readinessSchema,
  created_at: z.string(),
});
const feedbackSchema = z.object({
  id: z.string(),
  opportunity_id: z.string(),
  feedback_type: z.string(),
  note: z.string().nullable(),
  undone_at: z.string().nullable(),
  created_at: z.string(),
});
const versionSchema = z.object({
  id: z.string(),
  version: z.number().int(),
  snapshot: z.record(z.string(), z.unknown()),
  readiness_before: readinessSchema.nullable(),
  readiness_after: readinessSchema,
  change_reason: z.string(),
  created_at: z.string(),
});
const resultSchema = z.object({
  id: z.string(),
  plan_id: z.string(),
  outcome: z.enum(["supported", "partially_supported", "not_supported", "inconclusive"]),
  what_happened: z.string(),
  result: z.string(),
  evidence: z.array(z.record(z.string(), z.unknown())),
  user_notes: z.string().nullable(),
  next_step: z.string(),
  created_at: z.string(),
});
const planSchema = z.object({
  id: z.string(),
  opportunity_id: z.string(),
  source_version: z.number().int(),
  status: z.enum(["draft", "ready", "in_progress", "completed", "abandoned"]),
  opportunity_hypothesis: z.string(),
  target_user: z.string(),
  problem_hypothesis: z.string(),
  value_hypothesis: z.string(),
  critical_assumptions: z.array(z.string()),
  unknowns: z.array(z.string()),
  validation_questions: z.array(z.string()),
  evidence_needed: z.array(z.string()),
  cheapest_next_test: z.string(),
  success_criteria: z.array(z.string()),
  failure_criteria: z.array(z.string()),
  estimated_effort: z.string(),
  risk: z.string(),
  next_decision: z.string(),
  approved_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  results: z.array(resultSchema),
});
const outcomeSchema = z.object({
  id: z.string(),
  action_id: z.string(),
  what_happened: z.string(),
  result: z.string(),
  evidence: z.array(z.record(z.string(), z.unknown())),
  metrics: z.record(z.string(), z.unknown()),
  lesson: z.string(),
  next_step: z.string(),
  published_url: z.string().nullable(),
  manual_views: z.number().int().nullable(),
  manual_engagement: z.number().int().nullable(),
  user_observation: z.string().nullable(),
  memory_update_id: z.string().nullable(),
  created_at: z.string(),
});
const actionSchema = z.object({
  id: z.string(),
  opportunity_id: z.string().nullable(),
  validation_plan_id: z.string().nullable(),
  source_type: z.string(),
  source_id: z.string(),
  action_type: z.enum(["research", "validate", "prototype", "interview", "compare", "write", "review", "monitor", "manual_other"]),
  title: z.string(),
  why: z.string(),
  expected_result: z.string(),
  success_criteria: z.string(),
  status: z.enum(["proposed", "approved", "in_progress", "completed", "abandoned"]),
  user_notes: z.string().nullable(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  outcomes: z.array(outcomeSchema),
});
export const opportunitySummarySchema = z.object({
  id: z.string(),
  opportunity_type: opportunityTypeSchema,
  title: z.string(),
  description: z.string(),
  target_user: z.string(),
  problem: z.string(),
  why_attention: z.string(),
  why_now: z.string(),
  next_step: z.string(),
  status: statusSchema,
  readiness: readinessSchema,
  version: z.number().int().positive(),
  scores: z.record(z.string(), z.number()),
  score_explanation: z.record(z.string(), z.unknown()),
  unknowns: z.array(z.string()),
  content_details: z.record(z.string(), z.unknown()),
  related_research_task_id: z.string().nullable(),
  related_monitoring_mission_id: z.string().nullable(),
  related_monitoring_change_id: z.string().nullable(),
  related_discovery_candidate_id: z.string().nullable(),
  research_space_id: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export const opportunityDetailSchema = opportunitySummarySchema.extend({
  sources: z.array(sourceSchema),
  versions: z.array(versionSchema),
  score_history: z.array(scoreSchema),
  feedback: z.array(feedbackSchema),
  validation_plans: z.array(planSchema),
  actions: z.array(actionSchema),
});

export type OpportunitySummary = z.infer<typeof opportunitySummarySchema>;
export type OpportunityDetail = z.infer<typeof opportunityDetailSchema>;
export type OpportunityPlan = z.infer<typeof planSchema>;
export type OpportunityAction = z.infer<typeof actionSchema>;
export type OpportunityOutcome = z.infer<typeof outcomeSchema>;

export function listOpportunities(signal?: AbortSignal) {
  return requestJson("/api/opportunities", z.array(opportunitySummarySchema), { signal });
}

export function getOpportunity(opportunityId: string, signal?: AbortSignal) {
  return requestJson(`/api/opportunities/${encodeURIComponent(opportunityId)}`, opportunityDetailSchema, { signal });
}

export function analyzeOpportunity(input: { source_type: "research_task" | "discovery_candidate" | "monitoring_change" | "research_space" | "manual"; source_id: string; opportunity_type: z.infer<typeof opportunityTypeSchema> }) {
  return requestJson("/api/opportunities/analyze", z.object({
    status: z.enum(["opportunity_identified", "no_opportunity_identified", "needs_more_evidence"]),
    explanation: z.string(),
    signal_count: z.number().int().nonnegative(),
    independent_source_count: z.number().int().nonnegative(),
    opportunities: z.array(opportunitySummarySchema),
  }), { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function submitOpportunityFeedback(opportunityId: string, input: { feedback_type: string; note?: string }) {
  return requestJson(`/api/opportunities/${encodeURIComponent(opportunityId)}/feedback`, feedbackSchema, { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function createValidationPlan(opportunityId: string, input: Record<string, unknown> = {}) {
  return requestJson(`/api/opportunities/${encodeURIComponent(opportunityId)}/validation-plan`, planSchema, { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function approveValidationPlan(planId: string) {
  return requestJson(`/api/opportunities/validation-plans/${encodeURIComponent(planId)}/approve`, planSchema, { method: "POST", headers: jsonHeaders });
}

export function startValidationResearch(planId: string) {
  return requestJson(`/api/opportunities/validation-plans/${encodeURIComponent(planId)}/research`, z.record(z.string(), z.unknown()), { method: "POST", headers: jsonHeaders });
}

export function recordValidationResult(planId: string, input: Record<string, unknown>) {
  return requestJson(`/api/opportunities/validation-plans/${encodeURIComponent(planId)}/result`, resultSchema, { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function createOpportunityAction(input: Record<string, unknown>) {
  return requestJson("/api/actions", actionSchema, { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function updateOpportunityAction(actionId: string, input: { status: string; user_notes?: string }) {
  return requestJson(`/api/actions/${encodeURIComponent(actionId)}`, actionSchema, { method: "PATCH", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function recordOpportunityOutcome(actionId: string, input: Record<string, unknown>) {
  return requestJson(`/api/actions/${encodeURIComponent(actionId)}/outcome`, outcomeSchema, { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) });
}

export function addOpportunityToSpace(opportunityId: string, spaceId: string, note?: string) {
  return requestJson(`/api/research/spaces/${encodeURIComponent(spaceId)}/items`, z.record(z.string(), z.unknown()), { method: "POST", headers: jsonHeaders, body: JSON.stringify({ item_type: "opportunity", item_id: opportunityId, note }) });
}

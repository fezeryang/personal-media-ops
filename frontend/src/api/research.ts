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

const intentTypeSchema = z.enum([
  "discovery",
  "verification",
  "comparison",
  "trend_tracking",
  "pain_point_research",
  "competitor_scan",
  "creator_scan",
  "content_opportunity",
  "market_mapping",
  "product_opportunity",
  "monitoring",
]);

const intentContractSchema = z.object({
  id: z.string().nullable().optional(),
  research_task_id: z.string().nullable().optional(),
  original_request: z.string(),
  original_intent: z.string(),
  interpreted_goal: z.string(),
  primary_intent: intentTypeSchema,
  secondary_intents: z.array(intentTypeSchema),
  subject: z.record(z.string(), z.unknown()),
  known_entities: z.array(z.unknown()),
  known_constraints: z.array(z.unknown()),
  unknowns_to_discover: z.array(z.string()),
  time_scope: z.record(z.string(), z.unknown()),
  platform_preferences: z.array(z.string()),
  target_audience: z.string().nullable(),
  evidence_requirements: z.array(z.string()),
  negative_evidence_requirements: z.array(z.string()),
  exclusions: z.array(z.string()),
  desired_output: z.array(z.string()),
  success_criteria: z.array(z.string()),
  confidence: z.number().min(0).max(1),
  ambiguities: z.array(z.string()),
  assumptions: z.array(z.string()),
  current_research_hypothesis: z.string(),
  intent_revisions: z.array(z.record(z.string(), z.unknown())),
  intent_source: z.enum(["model", "fallback_default", "legacy_migrated", "owner_revised"]),
  clarification_question: z.string().nullable().optional(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
});

const intentVersionSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  version: z.number().int().positive(),
  contract: z.record(z.string(), z.unknown()),
  change_reason: z.string(),
  created_at: z.string(),
});

const intentAssumptionSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  intent_version: z.number().int().positive(),
  assumption: z.string(),
  status: z.string(),
  created_at: z.string(),
  resolved_at: z.string().nullable(),
});

const unknownSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  unknown: z.string(),
  priority: z.number().int().nonnegative(),
  status: z.enum(["open", "discovered", "verified", "unresolved"]),
  evidence_count: z.number().int().nonnegative(),
  resolution: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

const alignmentReviewSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  alignment_score: z.number().min(0).max(1),
  covered_requirements: z.array(z.string()),
  missing_requirements: z.array(z.string()),
  scope_drift: z.record(z.string(), z.unknown()),
  recommended_next_step: z.string().nullable(),
  review_status: z.enum(["passed", "needs_more_research", "partial_completion"]),
  created_at: z.string(),
});

const discoveryCandidateTypeSchema = z.enum([
  "entity",
  "creator",
  "topic",
  "event",
  "query",
  "pain_point",
  "need",
  "product_opportunity_signal",
  "content_opportunity_signal",
]);

const discoveryCandidateStateSchema = z.enum([
  "generated",
  "scored",
  "queued",
  "accepted",
  "ignored",
  "deferred",
  "converted_to_research",
  "added_to_space",
  "dismissed_duplicate",
  "expired",
]);

const discoveryFeedbackTypeSchema = z.enum([
  "valuable",
  "irrelevant",
  "already_known",
  "duplicate",
  "follow",
  "mute_topic",
  "deprioritize_similar",
  "needs_more_evidence",
  "converted_to_research",
  "added_to_space",
]);

const discoveryFeedbackScopeSchema = z.enum([
  "global",
  "platform",
  "research_intent",
  "research_space",
  "topic",
]);

const discoverySourceSchema = z.object({
  id: z.string(),
  seed_id: z.string().nullable(),
  research_task_id: z.string(),
  content_id: z.string().nullable(),
  platform: z.string().nullable(),
  source_kind: z.string(),
  source_title: z.string().nullable(),
  source_author: z.string().nullable(),
  source_url: z.string().nullable(),
  is_repost: z.boolean(),
  repost_of_content_id: z.string().nullable(),
  similarity_score: z.number().min(0).max(1).nullable(),
  independent_group: z.string().nullable(),
  created_at: z.string(),
});

const discoveryScoreSchema = z.object({
  id: z.string(),
  candidate_id: z.string(),
  scoring_version: z.string(),
  final_score: z.number().min(0).max(1),
  components: z.record(z.string(), z.unknown()),
  explanation: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

const discoveryFeedbackSchema = z.object({
  id: z.string(),
  candidate_id: z.string().nullable(),
  target_type: z.string(),
  target_key: z.string(),
  feedback_type: discoveryFeedbackTypeSchema,
  scope: discoveryFeedbackScopeSchema,
  scope_key: z.string().nullable(),
  weight: z.number().min(-1).max(1),
  reason: z.string().nullable(),
  follow_up_task_id: z.string().nullable(),
  undone_at: z.string().nullable(),
  created_at: z.string(),
});

export const discoveryCandidateSummarySchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  candidate_type: discoveryCandidateTypeSchema,
  title: z.string(),
  summary: z.string(),
  normalized_key: z.string(),
  parent_candidate_id: z.string().nullable(),
  source_seed_id: z.string().nullable(),
  source_content_id: z.string().nullable(),
  source_platform: z.string().nullable(),
  relevance_score: z.number().min(0).max(1),
  novelty_score: z.number().min(0).max(1),
  evidence_strength_score: z.number().min(0).max(1),
  source_independence_score: z.number().min(0).max(1),
  cross_platform_score: z.number().min(0).max(1),
  counterevidence_score: z.number().min(0).max(1),
  actionability_score: z.number().min(0).max(1),
  feedback_score: z.number().min(0).max(1),
  noise_risk_score: z.number().min(0).max(1),
  marketing_risk_score: z.number().min(0).max(1),
  saturation_score: z.number().min(0).max(1),
  resource_cost_score: z.number().min(0).max(1),
  final_score: z.number().min(0).max(1),
  score_explanation: z.record(z.string(), z.unknown()),
  content_count: z.number().int().nonnegative(),
  independent_source_count: z.number().int().nonnegative(),
  platform_count: z.number().int().nonnegative(),
  suspected_repost_count: z.number().int().nonnegative(),
  depth: z.number().int().min(0).max(1),
  state: discoveryCandidateStateSchema,
  suggested_next_action: z.string().nullable(),
  experimental_status: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const discoveryCandidateDetailSchema = discoveryCandidateSummarySchema.extend({
  sources: z.array(discoverySourceSchema),
  scores: z.array(discoveryScoreSchema),
  feedback: z.array(discoveryFeedbackSchema),
  lifecycle: z.array(z.record(z.string(), z.unknown())),
});

const discoverySeedSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  run_id: z.string(),
  seed_type: z.string(),
  source_content_id: z.string().nullable(),
  source_finding_id: z.string().nullable(),
  source_entity_candidate_id: z.string().nullable(),
  source_event_candidate_id: z.string().nullable(),
  source_candidate_id: z.string().nullable(),
  relation_to_intent: z.string(),
  novelty: z.number().min(0).max(1),
  confidence: z.number().min(0).max(1),
  information_utility: z.string(),
  depth: z.number().int().min(0).max(1),
  status: z.string(),
  created_at: z.string(),
});

const researchSpaceItemTypeSchema = z.enum([
  "research_task",
  "discovery_candidate",
  "evidence",
  "entity",
  "event",
  "finding",
  "unresolved_question",
  "memory",
]);

const researchSpaceItemSchema = z.object({
  id: z.string(),
  space_id: z.string(),
  item_type: researchSpaceItemTypeSchema,
  item_id: z.string(),
  position: z.number().int().nonnegative(),
  note: z.string().nullable(),
  source_candidate_id: z.string().nullable(),
  item: z.record(z.string(), z.unknown()),
  created_at: z.string(),
  updated_at: z.string(),
});

export const researchSpaceSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  status: z.enum(["active", "archived"]),
  item_count: z.number().int().nonnegative(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const researchSpaceDetailSchema = researchSpaceSummarySchema.extend({
  items: z.array(researchSpaceItemSchema),
});

const researchPreferencesSchema = z.object({
  feature_flags: z.record(z.string(), z.boolean()),
  rules: z.array(z.record(z.string(), z.unknown())),
});

const informationUtilitySchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  content_id: z.string(),
  utility_type: z.enum([
    "core_evidence",
    "discovery_seed",
    "background_context",
    "event_signal",
    "counterevidence",
    "memory_update",
    "action_trigger",
    "noise",
    "duplicate",
  ]),
  rationale: z.string(),
  confidence: z.number().min(0).max(1),
  research_query_id: z.string().nullable(),
  source_finding_id: z.string().nullable(),
  created_at: z.string(),
});

const entityCandidateSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  entity_type: z.string(),
  normalized_name: z.string(),
  source_content_id: z.string().nullable(),
  relevance_to_intent: z.number().min(0).max(1),
  novelty: z.number().min(0).max(1),
  confidence: z.number().min(0).max(1),
  suggested_next_action: z.string().nullable(),
  status: z.enum(["candidate_discovery", "accepted", "dismissed"]),
  created_at: z.string(),
  updated_at: z.string(),
});

const eventCandidateSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  event_type: z.string(),
  title: z.string(),
  summary: z.string(),
  source_content_id: z.string().nullable(),
  confidence: z.number().min(0).max(1),
  status: z.enum(["candidate", "accepted", "dismissed"]),
  created_at: z.string(),
  updated_at: z.string(),
});

const memoryItemSchema = z.object({
  id: z.string(),
  research_task_id: z.string(),
  memory_type: z.string(),
  memory_key: z.string(),
  value: z.unknown(),
  source_content_id: z.string().nullable(),
  source_query_id: z.string().nullable(),
  source_finding_id: z.string().nullable(),
  confidence: z.number().min(0).max(1),
  is_current: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

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
  model_call_count: z.number().int().nonnegative().optional(),
  subscription_calls: z.number().int().nonnegative().optional(),
  subscription_tokens: z.number().int().nonnegative().optional(),
  payg_calls: z.number().int().nonnegative().optional(),
  payg_tokens: z.number().int().nonnegative().optional(),
  relay_calls: z.number().int().nonnegative().optional(),
  relay_tokens: z.number().int().nonnegative().optional(),
  uncosted_call_count: z.number().int().nonnegative().optional(),
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
  source_independence: z.enum(["independent", "repost", "unknown"]).optional(),
  content_completeness: z.enum(["complete", "partial", "missing", "unknown"]).optional(),
  evidence_quality: z.enum(["high", "medium", "low", "unknown"]).optional(),
  is_repost: z.boolean().optional(),
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
      source_query_ids: z.array(z.string()).optional(),
      source_crawler_task_ids: z.array(z.string()).optional(),
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
  max_input_tokens: z.number().int().positive().nullable().optional(),
  max_output_tokens: z.number().int().positive().nullable().optional(),
  max_model_calls: z.number().int().positive().optional(),
  route_policy: z.enum(["prefer_subscription", "prefer_payg", "balanced", "quality_first", "manual"]).optional(),
  max_total_tokens: z.number().int().positive().optional(),
  max_crawl_tasks: z.number().int().nonnegative().optional(),
  max_new_contents: z.number().int().nonnegative().optional(),
  max_runtime_seconds: z.number().int().positive().optional(),
  max_payg_amount: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
});

const coverageSchema = z.object({
  target_platform_count: z.number().int().nonnegative(),
  target_entity_count: z.number().int().nonnegative(),
  target_negative_evidence_count: z.number().int().nonnegative(),
  max_single_entity_evidence_ratio: z.number().min(0).max(1),
  target_independent_evidence_count: z.number().int().nonnegative(),
  target_new_content_count: z.number().int().nonnegative(),
  low_marginal_value_threshold: z.number().min(0).max(1),
  low_marginal_round_limit: z.number().int().positive(),
  stop_reason: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
});

const platformCoverageSchema = z.object({
  id: z.string().optional(),
  research_task_id: z.string().optional(),
  platform: z.string(),
  order_index: z.number().int().nonnegative(),
  status: z.string(),
  planned_query_count: z.number().int().nonnegative(),
  actual_query_count: z.number().int().nonnegative(),
  result_count: z.number().int().nonnegative(),
  new_content_count: z.number().int().nonnegative(),
  independent_evidence_count: z.number().int().nonnegative(),
  negative_evidence_count: z.number().int().nonnegative(),
  failure_reason: z.string().nullable(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});

const entityCoverageSchema = z.object({
  canonical_name: z.string(),
  entity_type: z.string(),
  entity_query_count: z.number().int().nonnegative(),
  entity_evidence_count: z.number().int().nonnegative(),
  entity_new_content_count: z.number().int().nonnegative(),
  entity_platform_count: z.number().int().nonnegative(),
  entity_coverage_ratio: z.number().min(0).max(1),
  saturated: z.boolean(),
});

const contentDecisionSchema = z.object({
  content_id: z.string(),
  research_query_id: z.string().nullable(),
  decision: z.string(),
  not_adopted_reason: z.string().nullable(),
  source_independence: z.string(),
  content_completeness: z.string(),
  evidence_quality: z.string(),
  is_repost: z.boolean(),
  repost_of_content_id: z.string().nullable(),
  similarity_score: z.number().nullable(),
});

const stepUsageSchema = z.object({
  step: z.string(),
  sequence: z.number().int().positive(),
  provider_instance_id: z.string().nullable(),
  vendor: z.string().nullable(),
  model: z.string().nullable(),
  billing_mode: z.enum(["subscription_fixed", "pay_as_you_go", "prepaid_balance", "quota_bundle", "relay", "unknown"]).nullable(),
  estimated_cost: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  price_source: z.string().nullable().optional(),
  input_tokens: z.number().int().nonnegative().nullable(),
  output_tokens: z.number().int().nonnegative().nullable(),
  cached_tokens: z.number().int().nonnegative().nullable(),
  latency_ms: z.number().int().nonnegative().nullable(),
  fallback_from_provider_instance_id: z.string().nullable(),
  fallback_reason: z.string().nullable(),
  invocation_id: z.string().nullable(),
  created_at: z.string(),
});

const budgetEventSchema = z.object({
  event_type: z.string(),
  amount: z.string().nullable(),
  unit: z.string(),
  provider_instance_id: z.string().nullable(),
  vendor: z.string().nullable(),
  billing_mode: z.string().nullable(),
  currency: z.string().nullable(),
  estimated_cost: z.string().nullable(),
  reason: z.string().nullable(),
  created_at: z.string(),
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
    repost_count: z.number().int().nonnegative().optional(),
    negative_evidence_count: z.number().int().nonnegative().optional(),
    information_utility_counts: z.record(z.string(), z.number().int().nonnegative()).optional(),
    discovery_seed_count: z.number().int().nonnegative().optional(),
    core_evidence_count: z.number().int().nonnegative().optional(),
    background_context_count: z.number().int().nonnegative().optional(),
    event_signal_count: z.number().int().nonnegative().optional(),
    noise_count: z.number().int().nonnegative().optional(),
    duplicate_count: z.number().int().nonnegative().optional(),
    alignment_review: alignmentReviewSchema.optional(),
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
  stop_reason: z.string().nullable().optional(),
  primary_intent: intentTypeSchema.nullable().optional(),
  intent_confidence: z.number().min(0).max(1).nullable().optional(),
});

export const researchTaskDetailSchema = researchTaskSummarySchema.extend({
  plan: z.record(z.string(), z.unknown()),
  context: z.record(z.string(), z.unknown()),
  result: researchResultSchema.nullable(),
  route_snapshot: z.record(z.string(), z.unknown()),
  budget: budgetSchema,
  coverage: coverageSchema.optional(),
  platform_coverage: z.array(platformCoverageSchema).optional(),
  entity_coverage: z.array(entityCoverageSchema).optional(),
  content_decisions: z.array(contentDecisionSchema).optional(),
  step_usage: z.array(stepUsageSchema).optional(),
  budget_events: z.array(budgetEventSchema).optional(),
  research_plan: z.record(z.string(), z.unknown()).optional(),
  intent_contract: intentContractSchema.nullable().optional(),
  intent_versions: z.array(intentVersionSchema).optional(),
  intent_assumptions: z.array(intentAssumptionSchema).optional(),
  unknowns: z.array(unknownSchema).optional(),
  alignment_review: alignmentReviewSchema.nullable().optional(),
  information_utilities: z.array(informationUtilitySchema).optional(),
  entity_candidates: z.array(entityCandidateSchema).optional(),
  event_candidates: z.array(eventCandidateSchema).optional(),
  memory_items: z.array(memoryItemSchema).optional(),
  discovery_candidates: z.array(discoveryCandidateSummarySchema).optional(),
  discovery_seeds: z.array(discoverySeedSchema).optional(),
  trace: z.array(traceSchema),
  findings: z.array(findingSchema),
  queries: z.array(
    z.object({
      id: z.string(),
      research_task_id: z.string(),
      intent_id: z.string().nullable().optional(),
      record_type: z.enum(["user_goal", "execution_query"]).optional(),
      gate_status: z.enum(["not_applicable", "pending", "allow", "transform", "hold", "reject", "completed"]).optional(),
      decision: z.enum(["allow", "transform", "hold", "reject"]).optional(),
      query_role: z.enum([
        "seed_discovery",
        "entity_expansion",
        "cross_platform_validation",
        "counterevidence",
        "competitor_scan",
        "trend_probe",
        "creator_scan",
        "pain_point_probe",
      ]).optional(),
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
      status: z.enum([
        "generated",
        "rejected_generic",
        "rejected_duplicate",
        "rejected_low_relevance",
        "rejected_low_value",
        "approved_pending",
        "executing",
        "skipped_budget",
        "skipped_saturation",
        "skipped_low_marginal_value",
        "superseded",
        "cancelled",
        "candidate",
        "approved",
        "rejected",
        "running",
        "completed",
        "failed",
      ]),
      rejection_reason: z.string().nullable(),
      crawler_task_id: z.string().nullable(),
      executed_at: z.string().nullable(),
      result_count: z.number().int().nonnegative(),
      new_content_count: z.number().int().nonnegative(),
      existing_content_count: z.number().int().nonnegative(),
      updated_content_count: z.number().int().nonnegative(),
      duplicate_evidence_count: z.number().int().nonnegative(),
      lifecycle_status: z.string().nullable().optional(),
      unexecuted_reason: z.string().nullable().optional(),
      entity_diversity_bonus: z.number().min(0).optional(),
      platform_diversity_bonus: z.number().min(0).optional(),
      negative_evidence_bonus: z.number().min(0).optional(),
      estimated_resource_use: z.number().nonnegative().optional(),
      expected_evidence_role: z.enum(["direct", "contextual", "contradictory", "background"]).nullable().optional(),
      new_content_rate: z.number().min(0).max(1).nullable().optional(),
      new_entity_count: z.number().int().nonnegative().nullable().optional(),
      new_independent_evidence_count: z.number().int().nonnegative().nullable().optional(),
      duplicate_rate: z.number().min(0).max(1).nullable().optional(),
      marginal_value_score: z.number().min(0).max(1).nullable().optional(),
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
export type DiscoveryCandidateSummary = z.infer<typeof discoveryCandidateSummarySchema>;
export type DiscoveryCandidateDetail = z.infer<typeof discoveryCandidateDetailSchema>;
export type DiscoveryFeedbackType = z.infer<typeof discoveryFeedbackTypeSchema>;
export type DiscoveryFeedbackScope = z.infer<typeof discoveryFeedbackScopeSchema>;
export type ResearchSpaceSummary = z.infer<typeof researchSpaceSummarySchema>;
export type ResearchSpaceDetail = z.infer<typeof researchSpaceDetailSchema>;
export type ResearchSpaceItem = z.infer<typeof researchSpaceItemSchema>;
export type ResearchSpaceItemType = z.infer<typeof researchSpaceItemTypeSchema>;
export type ResearchPreferences = z.infer<typeof researchPreferencesSchema>;
export type DiscoveryFeedbackInput =
  | {
      feedback_type: DiscoveryFeedbackType;
      scope?: DiscoveryFeedbackScope;
      scope_key?: string | null;
      reason?: string | null;
      weight?: number;
    }
  | { undo_feedback_id: string };

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
    max_input_tokens?: number | null;
    max_output_tokens?: number | null;
    max_model_calls?: number;
    route_policy?: "prefer_subscription" | "prefer_payg" | "balanced" | "quality_first" | "manual";
    max_total_tokens?: number;
    max_crawl_tasks?: number;
    max_new_contents?: number;
    max_runtime_seconds?: number;
    max_payg_amount?: string | null;
    currency?: string | null;
  };
  coverage?: {
    target_platform_count?: number;
    target_entity_count?: number;
    target_negative_evidence_count?: number;
    max_single_entity_evidence_ratio?: number;
    target_independent_evidence_count?: number;
    target_new_content_count?: number;
    low_marginal_value_threshold?: number;
    low_marginal_round_limit?: number;
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

export function reviseResearchIntent(taskId: string, request: string) {
  return requestJson(
    `/api/research/tasks/${encodeURIComponent(taskId)}/intent/revise`,
    researchTaskDetailSchema,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ request }),
    },
  );
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

export function listDiscoveries(
  options: { state?: string; researchTaskId?: string; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (options.state) params.set("state", options.state);
  if (options.researchTaskId) params.set("research_task_id", options.researchTaskId);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.offset !== undefined) params.set("offset", String(options.offset));
  const query = params.toString();
  return requestJson(
    `/api/research/discoveries${query ? `?${query}` : ""}`,
    z.array(discoveryCandidateSummarySchema),
    { signal },
  );
}

export function getDiscovery(candidateId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/research/discoveries/${encodeURIComponent(candidateId)}`,
    discoveryCandidateDetailSchema,
    { signal },
  );
}

export function giveDiscoveryFeedback(
  candidateId: string,
  input: DiscoveryFeedbackInput,
) {
  return requestJson(
    `/api/research/discoveries/${encodeURIComponent(candidateId)}/feedback`,
    discoveryCandidateDetailSchema,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) },
  );
}

export function continueDiscovery(candidateId: string, request?: string) {
  return requestJson(
    `/api/research/discoveries/${encodeURIComponent(candidateId)}/continue`,
    researchTaskDetailSchema,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(request ? { request } : {}),
    },
  );
}

export function addDiscoveryToSpace(
  candidateId: string,
  input: { space_id: string; position?: number; note?: string | null },
) {
  return requestJson(
    `/api/research/discoveries/${encodeURIComponent(candidateId)}/add-to-space`,
    researchSpaceItemSchema,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) },
  );
}

export function listResearchSpaces(signal?: AbortSignal) {
  return requestJson("/api/research/spaces", z.array(researchSpaceSummarySchema), { signal });
}

export function createResearchSpace(input: { name: string; description?: string | null }) {
  return requestJson("/api/research/spaces", researchSpaceDetailSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export function getResearchSpace(spaceId: string, signal?: AbortSignal) {
  return requestJson(
    `/api/research/spaces/${encodeURIComponent(spaceId)}`,
    researchSpaceDetailSchema,
    { signal },
  );
}

export function addResearchSpaceItem(
  spaceId: string,
  input: { item_type: ResearchSpaceItemType; item_id: string; position?: number; note?: string | null },
) {
  return requestJson(
    `/api/research/spaces/${encodeURIComponent(spaceId)}/items`,
    researchSpaceItemSchema,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) },
  );
}

export function getResearchPreferences(signal?: AbortSignal) {
  return requestJson("/api/research/preferences", researchPreferencesSchema, { signal });
}

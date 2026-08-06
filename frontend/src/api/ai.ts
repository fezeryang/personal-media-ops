import { z } from "zod";

import { ApiError, requestEmpty, requestJson, requestResponse } from "./client";

export const providerProtocols = [
  "anthropic_compatible",
  "openai_compatible",
] as const;
export const providerTypes = [
  "minimax",
  "deepseek",
  "glm",
  "anthropic",
  "openai",
  "custom_anthropic",
  "custom_openai",
] as const;
export const routeRoles = [
  "default",
  "fast",
  "deep",
  "tool_calling",
  "final_report",
  "fallback",
] as const;

const nullableBoolean = z.boolean().nullable();
const nullableString = z.string().nullable();
const nullableNumber = z.number().nullable();
const protocolSchema = z.enum(providerProtocols);
const providerTypeSchema = z.enum(providerTypes);
const routeRoleSchema = z.enum(routeRoles);
const healthStatusSchema = z.enum([
  "healthy",
  "degraded",
  "unreachable",
  "authentication_failed",
  "model_not_found",
  "rate_limited",
  "protocol_error",
  "disabled",
]);

export const providerTemplateSchema = z.object({
  id: providerTypeSchema,
  display_name: z.string(),
  protocol: protocolSchema,
  base_url: nullableString,
});

export const aiProviderSchema = z.object({
  id: z.string(),
  name: z.string(),
  provider_type: providerTypeSchema,
  protocol: protocolSchema,
  base_url: z.string(),
  enabled: z.boolean(),
  timeout_seconds: z.number(),
  max_retries: z.number().int(),
  concurrency_limit: z.number().int(),
  credentials_configured: z.boolean(),
  model_count: z.number().int().nonnegative(),
  last_health_status: healthStatusSchema.nullable(),
  last_health_latency_ms: z.number().int().nonnegative().nullable(),
  last_health_checked_at: nullableString,
  created_at: z.string(),
  updated_at: z.string(),
});

const modelCapabilitiesSchema = z.object({
  supports_streaming: nullableBoolean,
  supports_tools: nullableBoolean,
  supports_thinking: nullableBoolean,
  supports_vision: nullableBoolean,
  supports_files: nullableBoolean,
  supports_structured_output: nullableBoolean,
});

export const modelCandidateSchema = z.object({
  model_id: z.string(),
  display_name: nullableString,
  capabilities: modelCapabilitiesSchema,
});

export const aiModelSchema = modelCapabilitiesSchema.extend({
  id: z.string(),
  provider_id: z.string(),
  model_id: z.string(),
  display_name: z.string(),
  enabled: z.boolean(),
  context_window: z.number().int().positive().nullable(),
  max_output_tokens: z.number().int().positive().nullable(),
  capabilities_source: z.enum(["unknown", "provider", "user", "tested"]),
  last_health_status: healthStatusSchema.nullable(),
  last_health_checked_at: nullableString,
  input_price_per_million: nullableString,
  output_price_per_million: nullableString,
  cached_input_price_per_million: nullableString,
  price_currency: nullableString,
  price_effective_at: nullableString,
  created_at: z.string(),
  updated_at: z.string(),
  provider_name: z.string(),
  protocol: protocolSchema,
  provider_enabled: z.boolean(),
});

export const modelRouteSchema = z.object({
  role: routeRoleSchema,
  model_record_id: nullableString,
  updated_at: z.string(),
  model_id: nullableString,
  display_name: nullableString,
  model_enabled: nullableBoolean,
  provider_id: nullableString,
  provider_name: nullableString,
  provider_enabled: nullableBoolean,
});

export const providerHealthSchema = z.object({
  status: healthStatusSchema,
  checked_at: z.string(),
  latency_ms: z.number().int().nonnegative().nullable().optional(),
  error_code: nullableString.optional(),
  error_summary: nullableString.optional(),
  check_kind: z.string(),
  model_id: nullableString.optional(),
});

const healthRecordSchema = providerHealthSchema.extend({
  id: z.string(),
  provider_id: z.string(),
  provider_name: z.string(),
});

const usageGroupSchema = z.object({
  key: z.string(),
  label: z.string(),
  invocation_count: z.number().int().nonnegative(),
  success_count: z.number().int().nonnegative(),
  success_rate: nullableNumber,
  average_latency_ms: nullableNumber,
  input_tokens: z.number().int().nonnegative(),
  output_tokens: z.number().int().nonnegative(),
  cached_tokens: z.number().int().nonnegative(),
});

const usageTotalsSchema = z.object({
  invocation_count: z.number().int().nonnegative(),
  success_count: z.number().int().nonnegative(),
  failure_count: z.number().int().nonnegative(),
  success_rate: nullableNumber,
  average_latency_ms: nullableNumber,
  input_tokens: z.number().int().nonnegative(),
  output_tokens: z.number().int().nonnegative(),
  cached_tokens: z.number().int().nonnegative(),
  uncosted_invocation_count: z.number().int().nonnegative(),
  costed_invocation_count: z.number().int().nonnegative(),
  estimated_cost: nullableString,
  price_currency: nullableString,
});

const invocationSchema = z.object({
  id: z.string(),
  provider_id: z.string(),
  model_record_id: z.string(),
  model_id: z.string(),
  route_role: nullableString,
  status: z.string(),
  started_at: z.string(),
  finished_at: nullableString,
  latency_ms: z.number().int().nonnegative().nullable(),
  input_tokens: z.number().int().nonnegative().nullable(),
  output_tokens: z.number().int().nonnegative().nullable(),
  cached_tokens: z.number().int().nonnegative().nullable(),
  estimated_cost: nullableString,
  price_currency: nullableString,
  pricing_effective_at: nullableString,
  error_code: nullableString,
  error_summary: nullableString,
  request_correlation_id: z.string(),
  attempt_number: z.number().int().positive(),
  is_fallback: z.boolean(),
  fallback_from_provider_id: nullableString,
  fallback_from_model_id: nullableString,
  fallback_reason: nullableString,
  provider_name: z.string(),
  display_name: z.string(),
});

export const usageSummarySchema = z.object({
  totals: usageTotalsSchema,
  by_provider: z.array(usageGroupSchema),
  by_model: z.array(usageGroupSchema),
  by_role: z.array(usageGroupSchema),
  cost_by_currency: z.array(
    z.object({ currency: z.string(), estimated_cost: z.string() }),
  ),
  recent_invocations: z.array(invocationSchema),
});

const usageSchema = z.object({
  input_tokens: z.number().int().nonnegative().nullable(),
  output_tokens: z.number().int().nonnegative().nullable(),
  cached_tokens: z.number().int().nonnegative().nullable(),
  total_tokens: z.number().int().nonnegative().nullable(),
});
const toolCallSchema = z.object({
  id: nullableString,
  name: z.string(),
  arguments: z.record(z.string(), z.unknown()),
});
const modelResponseSchema = z.object({
  content: nullableString,
  thinking_content: nullableString,
  tool_calls: z.array(toolCallSchema).nullable(),
  finish_reason: nullableString,
  usage: usageSchema.nullable(),
  provider: z.string(),
  model: nullableString,
  request_id: nullableString,
  latency_ms: z.number().int().nonnegative().nullable(),
});
export const gatewayResponseSchema = z.object({
  response: modelResponseSchema,
  route_role: routeRoleSchema.nullable(),
  fallback_used: z.boolean(),
  request_correlation_id: z.string(),
  initial_provider_id: z.string(),
  initial_model_id: z.string(),
  final_provider_id: z.string(),
  final_model_id: z.string(),
});

const promptVersionStatusSchema = z.enum([
  "draft",
  "candidate",
  "active",
  "deprecated",
  "rollback",
]);
const promptVersionSchema = z.object({
  prompt_key: z.string(),
  role: z.string(),
  version: z.string(),
  status: promptVersionStatusSchema,
  model_family: z.string(),
  temperature: z.number().nullable(),
  max_tokens: z.number().int().nullable(),
  change_reason: z.string(),
  activated_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export const promptDefinitionSchema = z.object({
  prompt_key: z.string(),
  role: z.string(),
  active_version: z.string(),
  candidate_version: z.string().nullable(),
  activated_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  recent_eval: z.record(z.string(), z.unknown()).nullable(),
  versions: z.array(promptVersionSchema),
});
export const evalCaseSchema = z.object({
  id: z.string(),
  slug: z.string(),
  task: z.string(),
  expected_intent: z.string(),
  key_unknowns: z.array(z.string()),
  required_evidence_types: z.array(z.string()),
  forbidden_scope_drift: z.array(z.string()),
  minimum_sources: z.number().int().nonnegative(),
  partial_completion_allowed: z.boolean(),
  last_result: z.record(z.string(), z.unknown()).nullable(),
});
export const evalReplayResultSchema = z.object({
  run_id: z.string(),
  prompt_key: z.string(),
  prompt_version: z.string(),
  context_version: z.string(),
  recorded_task_id: z.string(),
  case_count: z.number().int().nonnegative(),
  status_counts: z.record(z.string(), z.number().int().nonnegative()),
});

export const modelStreamEventSchema = z.object({
  type: z.enum([
    "start",
    "content_delta",
    "thinking_delta",
    "tool_call_delta",
    "completed",
  ]),
  content_delta: nullableString.optional(),
  thinking_delta: nullableString.optional(),
  tool_call_index: z.number().int().nonnegative().nullable().optional(),
  tool_call_id: nullableString.optional(),
  tool_name: nullableString.optional(),
  tool_arguments_delta: nullableString.optional(),
  response: modelResponseSchema.nullable().optional(),
  fallback_used: nullableBoolean.optional(),
  request_correlation_id: nullableString.optional(),
  initial_provider_id: nullableString.optional(),
  initial_model_id: nullableString.optional(),
  final_provider_id: nullableString.optional(),
  final_model_id: nullableString.optional(),
});

export type AiProvider = z.infer<typeof aiProviderSchema>;
export type ProviderTemplate = z.infer<typeof providerTemplateSchema>;
export type AiModel = z.infer<typeof aiModelSchema>;
export type ModelCandidate = z.infer<typeof modelCandidateSchema>;
export type ModelRoute = z.infer<typeof modelRouteSchema>;
export type RouteRole = (typeof routeRoles)[number];
export type ProviderHealth = z.infer<typeof providerHealthSchema>;
export type ProviderCheckKind = "text" | "streaming" | "tools" | "thinking";
export type UsageSummary = z.infer<typeof usageSummarySchema>;
export type GatewayResponse = z.infer<typeof gatewayResponseSchema>;
export type ModelStreamEvent = z.infer<typeof modelStreamEventSchema>;
export type PromptDefinition = z.infer<typeof promptDefinitionSchema>;
export type PromptVersion = z.infer<typeof promptVersionSchema>;
export type EvalCase = z.infer<typeof evalCaseSchema>;
export type EvalReplayResult = z.infer<typeof evalReplayResultSchema>;

export interface ProviderInput {
  name: string;
  provider_type: (typeof providerTypes)[number];
  protocol: (typeof providerProtocols)[number];
  base_url: string;
  enabled: boolean;
  timeout_seconds: number;
  max_retries: number;
  concurrency_limit: number;
  api_key?: string;
  clear_api_key?: boolean;
}

export interface ModelInput {
  provider_id: string;
  model_id: string;
  display_name: string;
  enabled: boolean;
  context_window: number | null;
  max_output_tokens: number | null;
  supports_streaming: boolean | null;
  supports_tools: boolean | null;
  supports_thinking: boolean | null;
  supports_vision: boolean | null;
  supports_files: boolean | null;
  supports_structured_output: boolean | null;
  capabilities_source: "unknown" | "provider" | "user" | "tested";
  input_price_per_million: string | null;
  output_price_per_million: string | null;
  cached_input_price_per_million: string | null;
  price_currency: string | null;
  price_effective_at: string | null;
}

export interface DebugInput {
  message: string;
  route_role: RouteRole | null;
  model_record_id?: string | null;
  stream: boolean;
}

const jsonHeaders = { "Content-Type": "application/json" };

export function listProviderTemplates(signal?: AbortSignal) {
  return requestJson("/api/ai/provider-templates", z.array(providerTemplateSchema), {
    signal,
  });
}

export function listAiProviders(signal?: AbortSignal) {
  return requestJson("/api/ai/providers", z.array(aiProviderSchema), { signal });
}

export function createAiProvider(input: ProviderInput) {
  return requestJson("/api/ai/providers", aiProviderSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export function updateAiProvider(id: string, input: ProviderInput) {
  return requestJson(`/api/ai/providers/${encodeURIComponent(id)}`, aiProviderSchema, {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export function deleteAiProvider(id: string) {
  return requestEmpty(`/api/ai/providers/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function testAiProvider(
  id: string,
  input: { model_record_id: string; check_kind: ProviderCheckKind },
) {
  return requestJson(
    `/api/ai/providers/${encodeURIComponent(id)}/test`,
    providerHealthSchema,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) },
  );
}

export function refreshProviderModels(id: string) {
  return requestJson(
    `/api/ai/providers/${encodeURIComponent(id)}/refresh-models`,
    z.array(modelCandidateSchema),
    { method: "POST" },
  );
}

export function listAiModels(signal?: AbortSignal) {
  return requestJson("/api/ai/models", z.array(aiModelSchema), { signal });
}

export function createModel(input: ModelInput) {
  return requestJson("/api/ai/models", aiModelSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export function updateModel(id: string, input: Omit<ModelInput, "provider_id" | "model_id">) {
  return requestJson(`/api/ai/models/${encodeURIComponent(id)}`, aiModelSchema, {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export function deleteModel(id: string) {
  return requestEmpty(`/api/ai/models/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function listRoutes(signal?: AbortSignal) {
  return requestJson("/api/ai/routes", z.array(modelRouteSchema), { signal });
}

export function updateRoutes(routes: Partial<Record<RouteRole, string | null>>) {
  return requestJson("/api/ai/routes", z.array(modelRouteSchema), {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify({ routes }),
  });
}

export function getUsage(signal?: AbortSignal) {
  return requestJson("/api/ai/usage", usageSummarySchema, { signal });
}

export function getAiHealth(signal?: AbortSignal) {
  return requestJson("/api/ai/health", z.array(healthRecordSchema), { signal });
}

export function listPromptDefinitions(signal?: AbortSignal) {
  return requestJson("/api/ai/prompts", z.array(promptDefinitionSchema), { signal });
}

export function listAiEvalCases(signal?: AbortSignal) {
  return requestJson("/api/ai/evals", z.array(evalCaseSchema), { signal });
}

export function replayAiEval(input: { promptKey: string; promptVersion: string }) {
  return requestJson("/api/ai/evals/replay", evalReplayResultSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      prompt_key: input.promptKey,
      prompt_version: input.promptVersion,
    }),
  });
}

export function activatePrompt(promptKey: string, version: string) {
  return requestJson(
    `/api/ai/prompts/${encodeURIComponent(promptKey)}/activate`,
    promptDefinitionSchema,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ version }),
    },
  );
}

export function rollbackPrompt(promptKey: string) {
  return requestJson(
    `/api/ai/prompts/${encodeURIComponent(promptKey)}/rollback`,
    promptDefinitionSchema,
    { method: "POST" },
  );
}

export function debugModel(input: DebugInput) {
  return requestJson("/api/ai/debug", gatewayResponseSchema, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(input),
  });
}

export async function* streamDebugModel(
  input: DebugInput,
  signal?: AbortSignal,
): AsyncGenerator<ModelStreamEvent> {
  const response = await requestResponse("/api/ai/debug", {
    method: "POST",
    headers: { ...jsonHeaders, Accept: "text/event-stream" },
    body: JSON.stringify({ ...input, stream: true }),
    signal,
  });
  if (!response.headers.get("content-type")?.includes("text/event-stream")) {
    throw new ApiError(502, "服务返回了无法识别的流式数据格式");
  }
  if (!response.body) throw new ApiError(502, "服务未返回流式响应");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue;
        let payload: unknown;
        try {
          payload = JSON.parse(data);
        } catch {
          throw new ApiError(502, "服务返回了无法识别的流式事件");
        }
        const error = z
          .object({ type: z.literal("error"), error_summary: z.string() })
          .safeParse(payload);
        if (error.success) throw new ApiError(502, error.data.error_summary);
        const parsed = modelStreamEventSchema.safeParse(payload);
        if (!parsed.success) {
          throw new ApiError(502, "服务返回了无法识别的流式事件");
        }
        yield parsed.data;
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}

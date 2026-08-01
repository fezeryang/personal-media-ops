# AI Model Gateway foundation

Phase 8A adds the server-side model runtime used by future AI product features.
It does not add a research agent, autonomous collection, event aggregation,
MCP, Notion synchronization, remote agents, or automatic publishing.

## Architecture and ownership

```text
Media Ops product feature
→ AI Orchestrator (future)
→ Model Gateway
→ Provider Adapter
→ configured model service
```

Product code must not call a vendor SDK or reproduce vendor request logic.
`ModelGateway` is the only execution boundary. Provider adapters depend only
on the unified domain protocol and async HTTP; they do not depend on React,
FastAPI responses, or database ORM models.

The first protocols are `anthropic_compatible` and `openai_compatible`.
Anthropic and OpenAI native endpoints use the same adapters when their native
wire contract is compatible. Templates are available for MiniMax, DeepSeek,
GLM / 智谱, Anthropic, OpenAI, and both custom-compatible protocols. Templates
contain no model list, capability claim, price, or credential.

## Unified protocol

The domain layer defines `ModelRequest`, `ModelResponse`, `ModelMessage`,
`ModelUsage`, `ModelToolDefinition`, `ModelToolCall`, `ModelToolResult`,
`ModelCapabilities`, `ProviderHealth`, and `ProviderError`.

Requests support system content, ordered messages, model, temperature, output
limit, streaming, tools, tool choice, metadata, and timeout. Responses preserve
text, thinking text, normalized tool calls, finish reason, usage, actual
provider/model, provider request ID, and latency. Missing upstream fields stay
`null`; the gateway never invents token counts, thinking, request IDs, model
capabilities, or cost.

The OpenAI adapter converts internal tools to `type=function` definitions and
normalizes `tool_calls[].function.arguments`. The Anthropic adapter converts
system content and content blocks, including `tool_use` and `tool_result`, and
normalizes `tool_use` blocks. Both adapters convert provider errors to the same
safe codes and stream vendor SSE into `ModelStreamEvent` values.

## Persistence and secret boundary

Alembic revision `0010_ai_model_gateway` adds:

- `ai_providers` and an enabled-provider index;
- `ai_provider_secrets` with one encrypted secret per provider;
- `ai_models` and a provider/enabled index;
- `ai_model_routes` and a routed-model index;
- `ai_provider_health_checks` and a provider/time index;
- `ai_model_invocations` with time, provider/model, role, and correlation
  indexes.

Provider keys use AES-256-GCM with a new 96-bit nonce for every encryption.
Authenticated additional data binds the ciphertext to the gateway format,
key version, and provider ID. A changed ciphertext, nonce, provider ID, or
version fails authentication and is never treated as a usable key.

Production keeps the 32-byte master key in the service-owned secrets directory,
outside Git, SQLite, ordinary logs, `.env`, database backups, and the frontend.
The deployment stage creates it atomically when absent, validates rather than
replaces an existing key, and enforces directory/file modes 0700/0600. The API
only returns `credentials_configured`; create/update accepts a password field
but no read response contains plaintext, ciphertext, nonce, key version, or a
server secret path.

`key_version` is persisted for a future explicit rotation workflow. Phase 8A
does not perform automatic key rotation.

## Routing, retries, and audit

Six routes are seeded with no target: `default`, `fast`, `deep`,
`tool_calling`, `final_report`, and `fallback`. Only an enabled model owned by
an enabled provider may be assigned. A future AI task must resolve and persist
its route snapshot when it starts; later route changes affect new tasks only.

The first failure policy is bounded:

```text
retryable error
→ same model, at most provider.max_retries
→ configured fallback model once
→ explicit failure
```

Non-retryable authentication, model, validation, and protocol errors do not
loop. Provider concurrency uses one async semaphore per configured provider.
The shared async HTTP client has bounded total and keepalive connections, and
every request has a timeout. Cancellation propagates to the HTTP request and
records a cancelled invocation. After a streaming response has emitted model
content, the gateway never silently asks another model to continue it.

Each attempt creates an invocation row with actual provider/model, route role,
attempt number, correlation ID, status, latency, returned usage, safe error,
and fallback provenance. Prompt and full output are not persisted. If model
pricing is configured, the invocation stores the contemporaneous currency,
effective date, and calculated cost. Missing or incomplete pricing stays
`null`, never zero. Mixed or partially uncosted totals do not claim one complete
cost value.

## Owner API

All reads require an owner session. Browser writes additionally require
same-origin CSRF validation.

```text
GET    /api/ai/provider-templates
GET    /api/ai/providers
POST   /api/ai/providers
GET    /api/ai/providers/{id}
PUT    /api/ai/providers/{id}
DELETE /api/ai/providers/{id}
POST   /api/ai/providers/{id}/test
POST   /api/ai/providers/{id}/refresh-models
GET    /api/ai/models
POST   /api/ai/models
PUT    /api/ai/models/{id}
DELETE /api/ai/models/{id}
GET    /api/ai/routes
PUT    /api/ai/routes
GET    /api/ai/usage
GET    /api/ai/health
POST   /api/ai/debug
```

Provider refresh returns candidates only. It does not create or enable models.
Connection checks are real low-output requests. Text, streaming, tools, and
thinking are tested independently, so successful text generation does not
claim a tool or thinking capability. Health stores only a bounded safe error.

The debug endpoint accepts one short message, either a route or explicit model,
and streaming or non-streaming mode. It is a gateway diagnostic, not a chat
workspace. The response identifies actual provider/model, latency, usage,
correlation ID, and whether fallback occurred.

## Model center UI

`/ai/models` provides five operational views:

- Providers: create, edit, test, enable/disable, and guarded deletion; API Key
  is a password input and is blank on every edit.
- Models: manual creation, provider candidates, editable tri-state abilities,
  limits, health, and optional price metadata. Imported candidates default to
  disabled.
- Routes: the six role mappings, limited to enabled providers and models.
- Usage: real totals and provider/model/role breakdowns, or an explicit empty
  state when no invocation exists.
- Debug test: one bounded request with route/direct and stream controls.

The layout uses the existing responsive workbench primitives and remains usable
at 390 px. No page synthesizes provider health, usage, chart data, or cost.

## Production acceptance

Before any real key is entered, verify the migration, key-file permission gate,
page access, creation of an unconfigured provider, secret-free API responses,
route validation, old features, both services, database integrity, and zero
active crawler tasks.

The owner then enters one provider key in the Model Center web page. The key
must not be sent through chat. Continue with separate real text, streaming,
tool, and (if claimed) thinking checks; unsupported abilities remain accurately
false or unknown. Set default and fallback routes only after those checks, then
inspect invocation usage and verify that no API or log response contains the
key.

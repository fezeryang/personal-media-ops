# AI Model Gateway Foundation

## Goal

Deliver stage 8A as the production foundation for all future AI features in
Personal Media Ops. An authenticated owner can configure, test, enable,
disable, and switch model providers and models in an AI Model Center. All
model traffic flows through one server-side Model Gateway and provider
adapters; no business feature calls a vendor SDK or vendor HTTP contract.

The execution baseline is the real `origin/main` and production commit at the
time work begins. On 2026-08-01 both were
`a111100600c80f98ca7f62551aa71f1cdedfed1f`; production API and Worker were
active and the production worktree was clean.

## Requirements

### Architecture and boundary

- Enforce `product feature -> future AI Orchestrator -> Model Gateway ->
  Provider Adapter -> vendor`.
- Implement `anthropic_compatible` and `openai_compatible` once. Native
  Anthropic/OpenAI templates reuse those adapters when their wire contracts
  match; do not duplicate implementations for labels.
- Provider code must not depend on React, FastAPI response classes, or the
  database ORM/repository.
- Run inside the existing FastAPI process with an async HTTP client, bounded
  connection pool, per-provider concurrency, finite timeouts, cancellation
  cleanup, and no effect on the single-concurrency crawler Worker.
- Add no Redis, Celery, Kafka, database server, proxy daemon, or browser.

### Internal protocol

- Define typed `ModelRequest`, `ModelResponse`, `ModelMessage`, `ModelUsage`,
  `ModelToolDefinition`, `ModelToolCall`, `ModelToolResult`,
  `ModelCapabilities`, `ProviderHealth`, `ProviderError`, `ModelInfo`, and
  typed streaming events.
- Requests support system instructions, message history, model, temperature,
  maximum output tokens, streaming, tools, tool choice, metadata, and timeout.
- Responses support visible content, thinking content, normalized tool calls,
  finish reason, usage, actual provider/model, request ID, and latency.
- Preserve absent upstream fields as `null`; never synthesize usage,
  reasoning, capabilities, prices, or request identifiers.
- Normalize Anthropic tool-use blocks and OpenAI function calls into the same
  tool call structure, including streamed arguments.

### Provider templates and adapters

- Supply templates for MiniMax, DeepSeek, GLM / Zhipu, Anthropic, OpenAI,
  Custom Anthropic Compatible, and Custom OpenAI Compatible.
- Templates may contain current display labels, compatible protocol, and
  editable default base URLs. They must not contain API keys, fixed model
  lists, permanent capability claims, or prices.
- Implement `AnthropicCompatibleProvider` and `OpenAICompatibleProvider` with
  `health_check`, `list_models`, `generate`, `stream`, and `capabilities`.
- Convert provider HTTP/network/auth/model/rate-limit/protocol failures into
  sanitized typed errors. Do not expose response bodies that may contain
  submitted prompts or credentials.

### Persistence

- Add Alembic revision `0010_ai_model_gateway` from the real current head.
- Add `ai_providers`, `ai_provider_secrets`, `ai_models`, `ai_model_routes`,
  `ai_provider_health_checks`, and `ai_model_invocations` with foreign keys,
  checks, uniqueness constraints, and query indexes.
- Providers store name, template/provider type, protocol, base URL, enabled,
  timeout, finite retry count, concurrency limit, and timestamps.
- Secrets store provider ID, authenticated ciphertext, nonce, key version,
  and timestamps. They never appear in normal repository DTOs.
- Models store editable identity, limits, capability flags, capability source,
  health, and optional per-million input/output/cache prices with currency and
  effective time. Unknown cost remains `null`, never zero.
- Routes cover `default`, `fast`, `deep`, `tool_calling`, `final_report`, and
  `fallback`. An unconfigured installation may have null routes; non-null
  routes must point to enabled providers and enabled models.
- Invocation rows contain actual provider/model/role/status/timing/token/cost
  data, correlation ID, attempt/fallback provenance, and sanitized error data.
  Full prompts and full outputs are not persisted in stage 8A.
- Provider/model deletion fails while routes or invocation history reference
  the record. Disabling prevents new routing without corrupting history.

### Secret encryption and deployment

- Encrypt API keys with AES-256-GCM using a unique random 96-bit nonce and
  associated data binding provider ID and key version. Invalid tags fail
  closed and are covered by tests.
- Load the 32-byte master key only from
  `/var/lib/mediaops/secrets/model-gateway-master.key` (configurable to a
  temporary path in tests). The directory is mode `0700`; the file is `0600`.
- The master key is never committed, stored in SQLite, included in database
  backups, logged, serialized, sent to the frontend, or printed in deployment
  output.
- Add a guarded non-secret-output server script that creates the directory
  and key as `mediaops` only when absent. It must never overwrite an existing
  key. Extend the root helper only if the existing `mediaops` ownership
  boundary proves insufficient.
- Reserve `key_version`; full key rotation is out of scope.

### Gateway, routing, retry, and fallback

- Resolve a route once per new gateway request and expose a route snapshot
  seam for future persistent AI tasks. Route changes affect only subsequent
  requests/tasks.
- Decrypt credentials just in time, validate model/provider state and required
  capabilities, enforce provider concurrency, call the adapter, normalize the
  response, calculate cost from the invocation-time price snapshot, and write
  an invocation record.
- Retry only explicitly retryable failures, up to the provider's bounded
  `max_retries`. Then try the configured fallback model once, unless it is the
  same model or is disabled/incompatible. Otherwise fail explicitly.
- Record every failed attempt and the fallback's original provider/model and
  failure reason under one correlation ID.
- Once a streaming response has emitted content, do not transparently switch
  models. Always close streaming HTTP responses on completion, error, or
  cancellation.

### Owner API

- Add authenticated `/api/ai` APIs for provider CRUD, provider connection
  tests, model refresh candidates, model CRUD, routes, usage, and health.
- Add a bounded debug generation endpoint supporting route selection or an
  explicit provider/model and streaming/non-streaming verification.
- Every read requires an owner session. Every write additionally uses the
  existing Origin and CSRF dependency. Scoped Agent API keys do not receive
  Model Center access in stage 8A.
- Provider writes accept an API key only on create/update. Later responses
  expose only `credentials_configured: true/false`; never ciphertext, nonce,
  key material, key paths, or full keys.
- Custom base URLs accept valid HTTPS URLs and loopback HTTP for development;
  reject embedded credentials, queries/fragments, and malformed endpoints.
- Connection testing performs a real minimal text request. Streaming, tools,
  and thinking are separate explicit checks and never inferred from basic
  text success.
- Persist health as one of `healthy`, `degraded`, `unreachable`,
  `authentication_failed`, `model_not_found`, `rate_limited`,
  `protocol_error`, or `disabled`, plus checked time, latency, check kind, and
  a sanitized error.

### AI Model Center frontend

- Add an authenticated `AI 模型中心` navigation entry and page.
- Provider UI shows name, protocol, base URL, credential-configured marker,
  enabled state, model count, last health, and latency; supports add, edit,
  test, enable/disable, and safe delete.
- API key fields use `type=password`; edit never refills the stored key.
- Model UI shows provider, model ID/display name, editable capabilities,
  limits, enabled/health state, and optional price configuration.
- Refreshing models displays returned candidates and requires explicit user
  action to add/enable them.
- Route UI edits all six roles and rejects disabled selections.
- Usage UI shows real totals and provider/model/role breakdowns; empty data
  renders an empty state and unknown cost renders `未配置`.
- Debug UI accepts one short message, route or explicit provider/model, and
  stream choice; it displays normalized response, actual provider/model,
  latency, usage, and fallback. It is not a chat workspace.
- Render and test the primary flows at a 390 px viewport without hiding
  actions or forcing fixed desktop layouts.

### Compatibility, documentation, and rollout

- Keep existing crawler, library, subscription, intelligence, Agent API, and
  Worker behavior green. Do not connect the disabled stage-seven brief seam
  to the new gateway in stage 8A.
- Update API, deployment, server operations, intelligence boundary, and old
  MCP/Notion roadmap wording so the real product direction is explicit.
- Migration tests cover a blank database and upgrade from revision 0009 while
  preserving existing task/library/subscription/intelligence rows and passing
  `PRAGMA integrity_check`.
- Before production migration: all local gates pass, the SQLite backup is
  verified, the master key exists with required modes, and deployment uses
  `--allow-migrations`.
- Initial production acceptance uses no real provider secret: Model Center is
  reachable; an unconfigured provider can be created; secrets never appear;
  validation works; old functionality works; API and Worker are active.
- Then pause once for the user to enter one provider API key in the web page,
  never in chat. Resume after the user replies `已完成` to perform real text,
  stream, and tool checks; set default and fallback routes; review invocation
  records and confirm no secret leakage. Unsupported capabilities remain
  accurately unsupported/degraded rather than failing the whole provider.

## Acceptance Criteria

- [ ] Provider CRUD, enable/disable, deletion guards, credentials update, and
      owner Session/CSRF protection are tested.
- [ ] API and logs never expose plaintext keys, ciphertext, nonce, master key,
      or master-key path.
- [ ] AES-GCM round-trip and tamper detection pass.
- [ ] Anthropic and OpenAI non-streaming request/response/tool conversions
      pass fixture-based tests.
- [ ] Both streaming formats normalize text, thinking/reasoning where present,
      tool arguments, finish reason, usage, request ID, and cleanup correctly.
- [ ] Health/error mapping, retry ceiling, concurrency, cancellation, disabled
      state, routing, fallback, and no-midstream-fallback behavior pass.
- [ ] Invocation/token/cost semantics pass, including unknown prices remaining
      null and fallback provenance.
- [ ] New/old database upgrade tests preserve existing entities and pass
      integrity checks.
- [ ] Frontend provider/model/route/usage/debug/error/390 px tests pass and API
      key edit fields remain blank.
- [ ] `uv run pytest`, frontend lint/test/build, Bash syntax checks, existing
      ShellCheck when available, and production build pass.
- [ ] Code is committed and pushed; production migration/deployment completes
      from `origin/main`; database, services, route checks, and worktrees pass.
- [ ] At least one real compatible model passes production text and streaming
      checks; tool support is tested and recorded accurately.

## Definition of Done

- Tests and executable documentation cover every security and data boundary.
- Database migration and backup/forward-fix rollback order are reviewed.
- Production API and Worker are active, activity count is zero at final gate,
  static build matches Git, SQLite is at head and integral, and no secret was
  leaked.
- Final report contains the 27 requested evidence categories, exact commits,
  backup path/hash, commands, results, remaining work, and stage 8B advice.

## Technical Approach

- Use official `httpx` as a production dependency and `cryptography` AESGCM.
  Retain `httpx2` only as the current FastAPI/Starlette TestClient development
  transport; application/provider code does not import it.
- Keep wire conversions as pure/testable provider classes with injectable
  async transports. Use one bounded async client owned by application
  lifespan and a semaphore per provider.
- Keep repository SQL parameterized and explicit, matching existing SQLite
  conventions. Use one transaction for route replacement and one invocation
  row per actual upstream attempt.
- Use Pydantic at the API/domain boundary and Zod for frontend responses.
- Use SSE for the debug streaming endpoint; frontend consumes it without
  retaining a conversation history.

## Decision (ADR-lite)

**Context**: The system needs several changing compatible vendors on a small
host, while future business modules must not embed vendor behavior.

**Decision**: Build two wire-level compatible adapters behind a typed internal
gateway; persist editable model facts and routes in SQLite; encrypt each
provider key with a host-only AES-GCM master key; record attempts without
prompts/outputs; provide one owner-only administrative surface.

**Consequences**: Provider labels can reuse adapters and new vendors can be
added without business-code changes. Compatibility claims remain conservative:
users must explicitly record capabilities, and vendor-specific features not
expressible through the two contracts stay out of stage 8A. The host master key
becomes required operational state and must be protected separately from the
database backup.

## Out of Scope

- Full AI chat, research jobs, multi-step Agent loops, automatic crawler tool
  calls, active monitoring, self-propagating information, candidate discovery,
  feedback memory, event aggregation, opportunity cards, final-report
  generation, MCP, Notion, Claude Code bridge, remote agents, and publishing.
- Prompt/output persistence, automatic model enablement, permanent vendor
  model catalogs, permanent capability assertions, and full key rotation.
- Major removal/redesign of command center, daily intelligence, trend, or
  other existing workbench pages.

## Research References

- [`research/provider-protocols.md`](research/provider-protocols.md) — current
  compatible API contracts and conservative template defaults.
- [`research/secret-and-runtime.md`](research/secret-and-runtime.md) — AES-GCM,
  deployment-key, async resource, and repository constraints.

## Technical Notes

- Production read-only survey on 2026-08-01: commit `a111100`, clean worktree,
  API/Worker active, localhost health OK, zero crawler failures in the prior 24
  hours. External observer returned `SSL_ERROR_SYSCALL`; it is not accepted as
  healthy without the existing helper/Nginx/SNI composite release gate.
- Current migration head is `0009_metrics_and_intelligence`; stage 8A becomes
  revision `0010_ai_model_gateway`.
- Existing owner dependencies already distinguish read session access from
  CSRF-protected write access and will be reused, not reimplemented.
- `CLAUDE.md` was already untracked before this task and remains outside task
  commits unless the user separately authorizes it.

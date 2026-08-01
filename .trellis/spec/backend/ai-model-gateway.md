# AI Model Gateway

## Scenario: Add or extend a model-backed product capability

### 1. Scope / Trigger

Apply this contract whenever code configures a model provider, invokes a model,
adds a model route, converts tool calls/streams, calculates usage, or handles a
provider credential. Product modules must call `ModelGateway`; they must never
call vendor SDKs or duplicate vendor wire logic.

### 2. Signatures

```python
class ModelProvider:
    async def health_check(self) -> ProviderHealth: ...
    async def list_models(self) -> list[ModelInfo]: ...
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...
    def capabilities(self, model_id: str) -> ModelCapabilities: ...
```

Owner API signatures are `/api/ai/providers`, `/api/ai/models`,
`/api/ai/routes`, `/api/ai/usage`, `/api/ai/health`, and `/api/ai/debug`, plus
provider detail/test/refresh endpoints. Alembic head `0010_ai_model_gateway`
owns `ai_providers`, `ai_provider_secrets`, `ai_models`, `ai_model_routes`,
`ai_provider_health_checks`, and `ai_model_invocations`.

### 3. Contracts

- Protocols: `anthropic_compatible`, `openai_compatible`.
- Route roles: `default`, `fast`, `deep`, `tool_calling`, `final_report`,
  `fallback`.
- `ModelRequest` carries system, ordered messages, model, temperature,
  max_tokens, stream, tools, tool_choice, metadata, and timeout.
- `ModelResponse` carries nullable content/thinking/tool calls/finish/usage plus
  actual provider, model, nullable request ID, and nullable latency.
- Missing provider facts stay `None`; do not infer abilities, tokens, or cost.
- AES-256-GCM uses a fresh 12-byte nonce and AAD containing format version,
  key version, and provider ID. Only just-in-time adapter construction decrypts.
- The shared `httpx.AsyncClient` has bounded total/keepalive connections;
  per-provider semaphores enforce `concurrency_limit`.
- Invocations store metadata, safe errors, usage, pricing snapshot, and fallback
  provenance, never prompt/output bodies or any credential.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Anonymous AI read/write | HTTP 401 |
| Session write without valid Origin/CSRF | HTTP 403 |
| Disabled provider/model chosen | HTTP 409 before HTTP call |
| Route points to disabled target | HTTP 409 |
| Provider/model still referenced | deletion HTTP 409 |
| Missing credential | explicit configuration failure |
| Ciphertext/AAD/nonce tampered | decryption error; no provider call |
| Authentication/model/protocol failure | normalized non-retryable error |
| Rate limit/unreachable/server failure | bounded same-model retry, then fallback |
| Stream fails after content emitted | fail; never cross-model continuation |
| Price incomplete or usage missing | cost remains `None` |

### 5. Good / Base / Bad Cases

- Good: future report code calls `gateway.generate(..., route_role="final_report")`
  and persists its task route snapshot.
- Base: provider refresh returns candidates; the owner explicitly creates a
  disabled model and later confirms its abilities.
- Bad: a feature imports an OpenAI/Anthropic SDK, hardcodes a model or price,
  marks tools healthy after a text-only request, or logs request/response bodies.

### 6. Tests Required

- Domain message/tool validation and both provider request/response transforms.
- Fragmented SSE conversion, tool call deltas, safe provider errors, and health.
- AES-GCM round trip, unique nonce, permissions, and tamper/provider-ID failure.
- CRUD/secret-free response/owner/CSRF/deletion guards/migration preservation.
- Route selection, disabled targets, bounded retry, fallback provenance,
  no-fallback-after-stream-content, cancellation, invocation tokens, and null
  cost semantics.
- Full backend `ruff`, pytest, and migration head checks.

### 7. Wrong vs Correct

#### Wrong

```python
response = await openai_client.chat.completions.create(model="vendor-model", ...)
```

#### Correct

```python
response = await model_gateway.generate(
    request,
    route_role="tool_calling",
)
```

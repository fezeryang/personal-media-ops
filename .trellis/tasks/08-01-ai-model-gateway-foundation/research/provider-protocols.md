# Provider protocol research

## Sources checked on 2026-08-01

- Anthropic official Python SDK/API materials: Messages uses `POST
  /v1/messages`; requests include model, messages, required maximum tokens,
  system, tools, tool choice, and stream. Raw SSE event families include
  `message_start`, content block start/delta/stop, `message_delta`, and
  `message_stop`; ping is ignorable and error events are failures.
- Anthropic official tool-use documentation: authentication uses `x-api-key`,
  the stable protocol header is `anthropic-version: 2023-06-01`, tool schemas
  use `input_schema`, response tool blocks are `tool_use`, and a tool request
  stops with `tool_use`.
- OpenAI official API documentation: Chat Completions uses `POST
  /v1/chat/completions`, Bearer authentication, message arrays, function tools,
  streamed choice deltas, finish reasons, and usage. Cached input tokens are
  nested in prompt token details when reported. Request IDs are headers or
  opaque response identifiers and must remain optional.
- MiniMax official compatibility documentation: the OpenAI-compatible base is
  currently `https://api.minimax.io/v1`; tool calls and streaming are exposed
  through the compatible contract. Model names remain dynamic.
- DeepSeek official documentation: the standard compatible base is currently
  `https://api.deepseek.com`; Chat Completions and tools use the OpenAI shape.
  Model names have changed over time and must not be hardcoded.
- Zhipu official documentation: the OpenAI-compatible base is currently
  `https://open.bigmodel.cn/api/paas/v4`; model names remain dynamic.
- OpenAI official authentication/reference documentation: the native base is
  `https://api.openai.com/v1`, API keys use Bearer authentication, and opaque
  request IDs must not be parsed or assumed stable.

## Adapter decisions

1. Use raw HTTP rather than vendor SDKs. This prevents business code from
   depending on a vendor package and keeps compatible endpoints first-class.
2. Join paths to a normalized editable base URL. Templates provide current
   defaults only; the database value is authoritative.
3. Anthropic conversion:
   - send system separately;
   - map internal function schemas to `name`, `description`, `input_schema`;
   - map assistant `tool_use` and user `tool_result` content blocks;
   - combine text blocks, keep thinking blocks separate when present, and
     normalize `tool_use` blocks;
   - aggregate input/cache/output usage only when returned.
4. OpenAI conversion:
   - prepend a system message;
   - map tools to `{type: function, function: ...}`;
   - map assistant `tool_calls` and `tool` result messages;
   - normalize visible content, optional reasoning fields, function calls,
     finish reason, and nested cached token usage.
5. Streaming conversion is incremental. Tool argument fragments are keyed by
   block/call index and emitted as normalized deltas; the final assembled tool
   call is validated as JSON. Unknown future event fields are ignored, while
   structurally invalid required fields produce `protocol_error`.
6. The provider's static `capabilities()` returns only protocol-level unknowns.
   Real model capabilities come from editable `ai_models` rows or explicit
   test results; successful text does not prove tools, thinking, files, vision,
   structured output, or even streaming.

## Error mapping

- Missing credentials or HTTP 401/403: `authentication_failed`, not retryable.
- HTTP 404/model-specific not-found response: `model_not_found`, not retryable.
- HTTP 429: `rate_limited`, retryable with bounded backoff and optional
  `Retry-After` cap.
- Connect/read timeout and transport failures: `unreachable`, retryable.
- Malformed successful JSON/SSE or incompatible response: `protocol_error`,
  not retryable by default.
- HTTP 5xx: sanitized `provider_error`, retryable.
- Never retain or return raw error bodies; allow only bounded, sanitized vendor
  error codes/messages after secret-like text redaction.

## Template defaults

| Template | Protocol | Editable default base URL |
| --- | --- | --- |
| MiniMax | `openai_compatible` | `https://api.minimax.io/v1` |
| DeepSeek | `openai_compatible` | `https://api.deepseek.com` |
| GLM / Zhipu | `openai_compatible` | `https://open.bigmodel.cn/api/paas/v4` |
| Anthropic | `anthropic_compatible` | `https://api.anthropic.com` |
| OpenAI | `openai_compatible` | `https://api.openai.com/v1` |
| Custom Anthropic | `anthropic_compatible` | empty/user supplied |
| Custom OpenAI | `openai_compatible` | empty/user supplied |

These are template conveniences, not permanent service facts. No template
contains model IDs, prices, user credentials, or model capability truth.

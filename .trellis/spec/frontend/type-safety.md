# Type Safety

## Scenario: FastAPI crawler boundary

### 1. Scope / Trigger

Apply this contract whenever the frontend changes crawler API calls, platform
selection, task rendering, or normalized result fields.

### 2. Signatures

```text
GET  /api/crawler/capabilities
GET  /api/crawler/tasks
POST /api/crawler/tasks
GET  /api/crawler/tasks/{task_id}
GET  /api/crawler/tasks/{task_id}/logs?tail=N|offset=N
GET  /api/crawler/tasks/{task_id}/qrcode
GET  /api/crawler/tasks/{task_id}/results?offset=N&limit=N
POST /api/crawler/tasks/{task_id}/cancel
```

All endpoint functions accept an optional `AbortSignal`. `requestJson` parses
responses with Zod before returning inferred TypeScript types.

### 3. Contracts

- Capabilities expose `platform`, display name, enabled state, verification
  state, fixed crawler/login options, count bounds, and comment support.
- The create form derives its platform and fixed labels from capabilities. It
  sends only `platform`, `crawler_type`, `keywords`, and `requested_count`.
- Task status remains the six-value backend enum.
- Results are a paginated unified schema with safe nullable URLs, publication
  time, source keyword, and nullable numeric metrics.
- `VITE_API_BASE_URL` defaults to empty same-origin.
- Task paths and PID may exist in the compatibility response but are never
  rendered.

### 4. Validation & Error Matrix

| Condition | Frontend behavior |
| --- | --- |
| Non-2xx JSON detail | Throw `ApiError(status, detail)` |
| FastAPI validation issues | Join field paths/messages |
| Network failure | Throw `ApiError(0, localized message)` |
| Abort | Preserve `AbortError` |
| Invalid successful JSON | Throw response-format `ApiError(502)` |
| QR 404 | Return `null` as not-ready |
| QR non-PNG | Throw QR-format `ApiError(502)` |
| Non-HTTP(S) result URL | Zod rejects the response |
| Disabled capability | Show it as disabled; never submit it |

### 5. Good / Base / Bad Cases

- Good: a newly registered backend platform appears without a frontend
  platform allowlist change.
- Base: missing optional result fields render neutral placeholders.
- Bad: cast raw JSON to a task/result type, render HTML, or silently substitute
  mock capabilities after a request failure.

### 6. Tests Required

Test capability parsing, exact create body, encoded IDs, bounded logs,
pagination, QR behavior, unified result formatting, unsafe URLs, active status
logic, and capability-driven form submission.

### 7. Wrong vs Correct

Wrong:

```typescript
const result = (await response.json()) as CrawlerResult;
```

Correct:

```typescript
const result = await requestJson(path, crawlerResultSchema, { signal });
```

Use `unknown` at untrusted boundaries and narrow explicitly. TypeScript `any`
is forbidden.

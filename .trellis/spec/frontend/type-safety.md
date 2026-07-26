# Type Safety

> Type safety patterns and the browser-to-FastAPI contract.

## Scenario: FastAPI crawler boundary

### 1. Scope / Trigger

This contract applies whenever the frontend adds or changes a call to the
FastAPI crawler routes, or maps MediaCrawler JSONL records to UI fields.

### 2. Signatures

```text
GET  /api/health
GET  /api/crawler/tasks
POST /api/crawler/tasks
GET  /api/crawler/tasks/{task_id}
GET  /api/crawler/tasks/{task_id}/logs?tail=N|offset=N
GET  /api/crawler/tasks/{task_id}/qrcode
GET  /api/crawler/tasks/{task_id}/results?offset=N&limit=N
POST /api/crawler/tasks/{task_id}/cancel
```

`requestJson<T>(path, schema, init)` validates JSON before returning `T`.
`requestText` handles logs and `requestBlob` handles PNG data.

### 3. Contracts

- Task creation sends only `platform: "bili"`, `crawler_type: "search"`,
  `keywords: string`, and `requested_count: 1..20`.
- Status is one of `pending`, `running`, `waiting_login`, `succeeded`,
  `failed`, or `cancelled`.
- Results are `{items, offset, limit, next_offset, has_more}` where each item is
  `Record<string, unknown>`.
- `VITE_API_BASE_URL` is optional and defaults to the empty same-origin base.
- All API functions accept an optional `AbortSignal`.

### 4. Validation & Error Matrix

| Condition | Frontend behavior |
|---|---|
| Non-2xx JSON with string detail | Throw `ApiError(status, detail)` |
| FastAPI 422 issue list | Join field names and messages |
| Non-JSON error | Throw an HTTP-status fallback |
| Network failure | Throw `ApiError(0, localized message)` |
| Query abort | Preserve `AbortError` |
| Successful JSON violates Zod schema | Throw response-format `ApiError(502)` |
| QR returns 404 | Return `null` ("not ready"), not a page error |
| QR returns 200 without `image/png` | Throw QR-format `ApiError(502)` |
| Result URL is not HTTP(S) | Return `null` and omit the link/image |

### 5. Good/Base/Bad Cases

- Good: a complete Bilibili record displays title, author, safe links, metrics,
  publication time, and source keyword.
- Base: missing optional JSONL fields display neutral placeholders.
- Bad: `javascript:` links, HTML-shaped strings, malformed task responses, and
  unknown creation controls never become trusted UI behavior.

### 6. Tests Required

- Assert endpoint method, encoded task ID, request body, and pagination query.
- Assert FastAPI validation, network, non-JSON, and invalid-schema errors.
- Assert all task statuses map to Chinese and active state is exact.
- Assert common/missing/malicious JSONL records normalize safely.
- Run backend pytest when frontend contract usage changes.

### 7. Wrong vs Correct

#### Wrong

```typescript
const task = (await response.json()) as CrawlerTask;
element.innerHTML = task.error_message ?? "";
```

#### Correct

```typescript
const task = await requestJson(path, crawlerTaskSchema, { signal });
return <p>{task.error_message}</p>;
```

Types are inferred from Zod schemas where possible. Use `unknown` for untrusted
record fields and narrow with explicit helpers. `any` is forbidden.

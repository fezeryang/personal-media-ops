# Crawler Platform Contract

## 1. Scope / Trigger

Apply this contract when adding a crawler platform, changing Runner arguments,
normalizing MediaCrawler JSONL, or exposing platform choices to the frontend.

## 2. Signatures

```text
GET  /api/crawler/capabilities
POST /api/crawler/tasks
GET  /api/crawler/tasks/{task_id}/results?offset=N&limit=N
MEDIAOPS_ENABLED_PLATFORMS=bili[,xhs,dy]
```

Adapters implement capability metadata, fixed Runner arguments,
`is_login_success(line)`, content-file discovery, and `normalize_result(raw)`.

## 3. Contracts

- Registry keys are `bili`, `xhs`, and `dy`; it is the backend source of truth.
- `bili` is `verified`; `xhs` and `dy` are `code_ready`.
- Only explicitly enabled platforms accept new tasks; the default is `bili`.
- Search, QR login, count `1..20`, one global task, no comments, no
  sub-comments, and no proxy are fixed service constraints.
- The Worker calls fixed Python and Runner paths with an argument array.
- The existing Bilibili Runner argument contract remains compatible. Proxy is
  disabled inside the reviewed Runner, not exposed as a new Worker argument.
- Result items use the unified Pydantic schema and are read incrementally,
  path-checked, paginated, and capped at `requested_count`.

## 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Unknown platform | Task API returns 422 |
| Registered but disabled platform | Task API returns 409 |
| Unknown enabled-platform config | API/Worker startup fails |
| Unsafe stored result path | Results API returns 409 |
| Invalid JSONL object | Results API returns 500 |
| QR-save log line | Task remains `waiting_login` |
| `Login successful` log line | Task returns to `running` |

## 5. Good / Base / Bad Cases

- Good: add one Adapter, register it once, test normalized sample output, then
  let the capability API drive the UI.
- Base: a missing optional raw field becomes `null` or an empty display value.
- Bad: hard-code a platform list in the frontend or pass Cookie/path/command
  controls through the task API.

## 6. Tests Required

Test registry truthfulness, disabled/unknown platforms, fixed commands,
platform JSONL samples, unsafe URLs/paths, QR progression, result caps, and
cross-platform competing claims. Real platform tests require explicit
authorization and are not part of unit tests.

## 7. Wrong vs Correct

Wrong:

```typescript
const platforms = ["bili", "xhs", "dy"];
```

Correct:

```typescript
const capabilities = await getCrawlerCapabilities(signal);
const platforms = capabilities.platforms;
```

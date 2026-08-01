# Access, Automation, and Intelligence Contract

## 1. Scope / Trigger

Apply this contract when changing owner authentication, API-key scopes,
subscription/watch scheduling, library organization, metric snapshots, trend
signals, deterministic briefs, or `/api/v1` Agent resources. These features
share one SQLite database and the existing single-concurrency crawler Worker.

## 2. Signatures

```text
python -m app.cli create-owner --username owner

users | sessions | api_keys
subscriptions | subscription_platforms | subscription_runs
subscription_run_tasks
library_tags | library_content_tags
library_collections | library_collection_items
creator_watchlist | creator_watch_runs
content_metric_snapshots | creator_metric_snapshots
trend_signals | trend_signal_contents
briefs | brief_items | brief_item_contents | brief_item_trends
brief_schedules

POST /api/auth/login
GET  /api/auth/session
POST /api/auth/logout
GET|DELETE /api/auth/sessions[/{id}]
GET|POST|DELETE /api/auth/api-keys[/{id}]

GET|POST /api/subscriptions
GET|PUT  /api/subscriptions/{id}
POST /api/subscriptions/{id}/{pause|resume|run}
GET|POST /api/watchlist
PATCH /api/watchlist/{id}
POST  /api/watchlist/{id}/run

GET  /api/v1/library/search
GET  /api/v1/intelligence/trends
GET  /api/v1/intelligence/briefs/latest
GET  /api/v1/subscriptions
```

## 3. Contracts

- Passwords use pwdlib's Argon2id profile. The CLI reads them with `getpass`;
  neither requests nor process arguments accept owner passwords.
- Session, CSRF, and API-key secrets are high-entropy opaque values. SQLite
  stores only SHA-256 hashes. Browser sessions use a `Secure`, `HttpOnly`,
  `SameSite=Strict` cookie; the CSRF token stays in React memory.
- Unsafe session requests require an allowed origin and the matching
  synchronizer token. External API keys use `X-API-Key`, never the session
  cookie path. `admin` satisfies all scopes; other keys receive only explicit
  read/write scopes. Key/session administration remains browser-session-only,
  while organization and intelligence writes accept either a session or an
  explicitly issued `admin` key.
- Automatic subscriptions accept only enabled, production-verified `search`
  cells. Schedules are typed (`manual`, `every_6_hours`, `daily`, `weekdays`,
  `weekly`), retain an IANA timezone, and materialize UTC `next_run_at`.
- `BEGIN IMMEDIATE` plus unique `(subscription_id, scheduled_for)` ownership
  prevents duplicate runs. Every platform creates an ordinary crawler task in
  deterministic sequence; no automation path starts a browser directly.
- Watchlist checks accept only verified creator mode, use the same queue, and
  cap each check at five contents. Invalid due capability rows are disabled
  rather than turned into endless failed jobs.
- Library upsert distinguishes new, existing, and metric-changed content.
  Missing metrics remain `NULL`; equal snapshots inside 15 minutes deduplicate.
- Trend `rules-v1` uses fixed 35/30/20/15 volume, velocity, cross-platform,
  and engagement weights. Fewer than three current or five combined samples
  is always `insufficient_data`.
- `DeterministicBriefGenerator` labels facts, calculations, rules,
  insufficient data, and unknowns separately. Every substantive conclusion
  links stored content or trend evidence. Scheduled generation failures are
  persisted per schedule and do not stop the Worker loop.
- `AgentToolService` returns Pydantic-compatible stable dictionaries rather
  than database rows. `/api/v1` adds bounded pagination, nested source
  identity, scoped authorization, and a uniform `error` envelope without raw
  payloads, paths, cookies, or process fields.

## 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Anonymous protected request | HTTP 401 |
| API key lacks the required scope | HTTP 403 |
| Unsafe session request has missing/wrong origin or CSRF | HTTP 403 |
| Five failed owner logins | Temporary HTTP 429 lockout |
| Revoked/expired session or API key | HTTP 401 |
| Deferred/disabled/unverified subscription platform | HTTP 409; no run/task |
| Same subscription and UTC slot is claimed twice | Exactly one run |
| Worker restarts after task creation | Reconcile the existing run/task |
| Invalid due platform capability | Disable the automation row |
| Repeated entity with unchanged metrics | Existing count; no new count |
| Brief generator raises | Persist failure and continue other jobs |
| Too little trend evidence | Persist `insufficient_data` |
| `/api/v1` validation fails | Stable `invalid_request` error envelope |

## 5. Good / Base / Bad Cases

- Good: the Worker atomically claims a due subscription, enqueues two platform
  tasks, runs them one at a time, and reconciles three independent counters.
- Good: an Agent key with only `library:read` can search content but receives
  403 for trends or subscription writes.
- Base: a manual disabled subscription has no `next_run_at` but can be run by
  an authenticated explicit action.
- Bad: store a session/API key verbatim, put a token in local storage, accept a
  cron string, or execute a browser from the scheduler.
- Bad: overwrite a real metric with `NULL`, count an upsert as new, or describe
  a low-sample rule score as an AI fact.

## 6. Tests Required

- Migration tests upgrade a blank database and a populated `0005` database to
  head, preserve task/library rows, assert new tables/indexes, and pass
  `integrity_check`.
- Auth tests cover Argon2id verification, cookie attributes, CSRF/origin,
  lockout, logout/revocation, session listing, API-key hash/expiry/revocation,
  one-time secret output, and scope errors.
- Schedule tests cover IANA validation, spring gap, fall fold, typed bounds,
  duplicate claims, restart reconciliation, bounded backoff, platform order,
  pause behavior, and invalid-capability disablement.
- Ingestion tests assert new/existing/changed counts, nullable preservation,
  snapshot dedupe, and absolute metric deltas.
- Trend/brief tests assert the exact formula, evidence IDs, thresholds,
  regeneration versions, daily claim idempotency, and failure isolation.
- Agent tests assert pagination/source fields, omission of raw/path/PID data,
  unified errors, scope enforcement, and legacy API compatibility.

## 7. Wrong vs Correct

Wrong:

```python
for subscription in due:
    start_browser(subscription)
```

Correct:

```python
run = automation_repository.claim_due_subscription(subscription, scheduled_for)
automation_repository.create_ordered_crawler_tasks(run)
# The existing Worker lock remains the only browser execution boundary.
```

Wrong:

```python
database.execute("INSERT INTO api_keys (key) VALUES (?)", (full_key,))
```

Correct:

```python
full_key, record = auth_service.create_api_key(...)
# Persist only record.key_hash; return full_key once.
```

## Scenario: Bounded Research Runtime artifacts

### 1. Scope / Trigger

Apply when changing the persisted Research Agent state machine, evidence-bound
findings, or owner approval actions. Research execution remains inside the API
process and uses the existing single-concurrency crawler Worker.

### 2. Signatures

```text
ResearchRuntime.run_once() -> bool
ResearchTaskRepository.save_finding(..., content_ids: list[str])
ResearchTaskRepository.add_action(...)
```

The runtime may dispatch only the eight registered research tools. A crawl tool
returns immediately after persisting `WaitingCrawl`; the crawler completion
reconciliation wakes the task and never holds a browser lock or execution
thread open.

### 3. Contracts

- Every fact and inference is stored as a Finding that references one or more
  existing `content_id` values. An inference also requires a non-empty
  derivation.
- A research round checks the library before submitting a crawl and persists
  the plan, context, trace, route snapshot, and usage counters after each
  bounded step.
- If findings exist but an inference or owner action is missing, the runtime
  performs at most three artifact-repair turns. The follow-up action repair
  exposes only `propose_action` and runs for at most two turns; it cannot crawl
  or save another Finding.
- The artifact repair is skipped on provider-error convergence and is not
  allowed to exceed the task token/duration/crawl gates. A reached gate enters
  `BudgetExceeded` and then `Summarizing`; it must not silently spend more
  tokens to manufacture an action.
- `proposed_actions` are pending owner approvals. Runtime never executes the
  action itself.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Finding has no content evidence | Reject with a research conflict; write no Finding |
| Inference has no derivation | Reject with a research conflict; write no Finding |
| Repair model calls an unexposed tool | Record a bounded tool error; do not execute it |
| Action repair receives `save_finding` | Record a bounded tool error; keep the action pass isolated |
| Provider error after durable findings | Record safe error and converge to summary |
| Token/duration/crawl gate reached | `BudgetExceeded` → `Summarizing`; no hidden retry |
| Valid action proposal | Persist `pending` action and require owner decision |

### 5. Good / Base / Bad Cases

- Good: a real task completes two asynchronous crawls, stores evidence-bound
  facts and inferences, then creates one pending action for owner review.
- Base: a task with only facts uses the bounded inference repair and then the
  action-only repair before summary generation.
- Bad: keep exposing both repair tools while the model repeatedly saves facts,
  bypass the token gate to force an action, or execute a proposed action in the
  Runtime process.

### 6. Tests Required

- Runtime tests assert the inference/action artifact repair sequence, tool
  isolation, provider-error convergence, and budget short-circuit.
- Repository tests assert evidence-required Findings, inference derivation,
  pending action persistence, owner approval/rejection, and trace events.
- Real acceptance records two successful crawls, at least one inference with
  provenance, one pending action, route/model invocation totals, and `null`
  cost when pricing is not configured.

### 7. Wrong vs Correct

Wrong:

```python
# One unrestricted repair loop can keep saving facts forever.
tools = all_research_tools
while not action:
    await model.generate(tools=tools)
```

Correct:

```python
# Repair evidence first, then isolate the approval boundary.
await repair_findings(max_turns=3)
await repair_action_only(max_turns=2, tools={"propose_action"})
```

## Scenario: Research result Markdown and HTML

### 1. Scope / Trigger

Apply when the Research Runtime stores or serves a model-generated report.
Markdown is the audit/source format; HTML is a derived display/export format.

### 2. Signatures

```text
render_research_markdown(markdown: str) -> str
result.summary_markdown: string
result.summary_html: string
```

### 3. Contracts

- The Runtime preserves the exact bounded Markdown summary and derives
  `summary_html` with the server-side Markdown renderer and an explicit HTML
  allow-list.
- The API keeps the historical `summary` alias for old consumers and, for old
  rows missing the new fields, derives both formats during detail serialization
  without changing the stored Markdown.
- Allowed HTML is limited to report structure (headings, paragraphs, lists,
  emphasis, code, blockquotes, tables, and links). Only `http` and `https`
  links survive sanitization; scripts, event attributes, styles, iframes, and
  unsafe URL schemes do not.
- The frontend sanitizes the API HTML once more before DOM insertion and keeps a
  Markdown view/copy path. Findings and provenance remain separate structured
  evidence; HTML is never treated as evidence.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Empty model summary | Empty Markdown and HTML fields; honest empty state |
| Legacy result with only `summary` | API derives both explicit format fields |
| Raw script/event/iframe/unsafe URL | Escaped or stripped; no executable DOM node |
| HTML conversion failure | Preserve Markdown and show a readable fallback; do not fake HTML |
| Result API field is not a string | Zod/Pydantic boundary rejects or uses the plain-text fallback |

### 5. Good / Base / Bad Cases

- Good: a report heading/list/link renders in the Research Center and the
  original Markdown remains viewable.
- Base: a historical task with only `summary` renders after API compatibility
  derivation.
- Bad: pass model output directly to `dangerouslySetInnerHTML`, allow
  `javascript:` links, or discard Markdown after generating HTML.

### 6. Tests Required

- Renderer tests cover headings, lists, links, code, empty content and XSS
  payloads.
- API tests assert `summary_markdown`, `summary_html`, and legacy compatibility.
- Frontend tests assert rendered HTML, second-pass sanitization, Markdown toggle,
  empty result, and 390px layout.

### 7. Wrong vs Correct

Wrong:

```tsx
<div dangerouslySetInnerHTML={{ __html: result.summary }} />
```

Correct:

```tsx
const safe = DOMPurify.sanitize(result.summary_html, allowListOptions)
<div dangerouslySetInnerHTML={{ __html: safe }} />
```

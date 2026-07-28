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

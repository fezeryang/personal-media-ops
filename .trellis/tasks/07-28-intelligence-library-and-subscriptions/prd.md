# Stage Seven: Intelligence Library, Subscriptions, and Agent API Foundation

## Goal

Upgrade Personal Media Ops from a manually operated crawler and normalized
library into a low-resource, continuously running personal intelligence system.
The complete flow is:

```text
single-owner authentication
→ keyword subscriptions and creator watchlist
→ SQLite-backed scheduling inside the existing Worker
→ ordinary single-concurrency crawler tasks
→ idempotent library ingestion plus metric snapshots
→ tags, favorites, and ordered collections
→ deterministic trends and evidence-backed daily briefs
→ stable Agent Tool Service and REST API v1
→ bright intelligence-lab workbench
```

The system must remain truthful about platform × mode capabilities and must
never present deterministic rules as AI-generated facts.

## Confirmed Baseline

- The user explicitly started stage seven on 2026-07-28 and authorized the
  complete implementation, test, commit, push, migration, deployment, and
  production-validation loop without repeated technical approvals.
- Local `main`, `origin/main`, the production repository, build marker, and
  published marker begin at
  `668fec71e1ee18254acba173af72a66a0d41ed0d`.
- Production MediaCrawler is pinned and clean at
  `17f66121e0fcc40fc23958b995bec873d422667d`; it will not be updated.
- Production SQLite is healthy at `0005_library_entities`.
- The current production state is 57 crawler tasks, no active task, 27
  contents, 29 creators, 60 comments, and 132 task/entity provenance rows.
  This is newer than the stage-six archival snapshot because a later
  Xiaohongshu `AI工作台` search succeeded with 19 results.
- API and Worker are active; the Worker remains globally single-concurrency;
  browser residue, D-state processes, and swap usage are zero.
- The capability API returns seven platforms × five independent modes.
  Existing deferred states remain unchanged:
  Douyin resource-constrained; Kuaishou search and creator upstream-broken;
  Xiaohongshu signed-target modes login-context-deferred; Weibo and Tieba
  sub-comments platform-change-deferred.
- The production SNI loopback and restricted-helper checks pass. The external
  Codex observer still reproduces the already-recorded TLS reset.
- The user-owned untracked `CLAUDE.md` is outside scope and must remain
  untouched and uncommitted.

## Requirements

### Single-owner access control

- Add versioned `users`, `sessions`, and `api_keys` persistence with no public
  registration.
- Hash passwords with Argon2id through the current FastAPI-recommended
  `pwdlib` interface. Never store or log a plain password.
- Provide `uv run python -m app.cli create-owner`, using `getpass` for
  interactive input and refusing unsafe non-interactive password arguments.
- Use opaque, high-entropy browser session tokens stored only as SHA-256
  hashes. Send the token in an HttpOnly, Secure, SameSite cookie; support
  expiry, last-seen tracking, revocation, logout, and session invalidation.
- Protect cookie-authenticated unsafe requests with a per-session synchronizer
  CSRF token sent in `X-CSRF-Token`, plus strict same-origin validation.
  Keep authentication tokens out of localStorage.
- Limit login failures per account with persisted failure counters and a
  bounded lockout. Use a dummy password hash for unknown owners and uniform
  authentication errors.
- Keep `/api/health` public. Require an owner session or an appropriately
  scoped API key for all crawler, library, intelligence, subscription, and
  Agent endpoints. Browser-only administration requires a session.
- Store only API-key hashes, a non-secret prefix, name, scopes, timestamps,
  optional expiry, last-use time, and revocation state. Show a full key only
  in its creation response and never allow it to be read again.
- Support scopes `library:read`, `intelligence:read`, `tasks:read`,
  `tasks:write`, `subscriptions:read`, `subscriptions:write`, and `admin`.
  A session owner has all scopes; API keys receive only their explicit scopes.
- Redact passwords, session/CSRF tokens, authorization headers, and full API
  keys from application and crawler logs.
- Do not break localhost health checks, systemd, Nginx, or the restricted
  release helper. Production owner password creation is the single expected
  operator pause boundary.

### Keyword subscriptions and scheduling

- Add `subscriptions`, `subscription_platforms`, `subscription_runs`, and
  normalized run/task links.
- Store name, query, enabled state, schedule type/config, IANA timezone,
  per-platform bounded counts, last/next/success timestamps, consecutive
  failures, last error, and audit timestamps in UTC.
- Support only `manual`, `every_6_hours`, `daily`, `weekdays`, and `weekly`.
  Do not accept arbitrary cron expressions. The minimum automatic interval is
  six hours.
- Permit only globally enabled, production-verified `search` modes. Revalidate
  capability status when a subscription is saved and when it is scheduled.
  Never schedule Douyin or Kuaishou search, disabled/deferred search modes,
  comments, or sub-comments.
- Use browser timezone as the frontend default and permit a validated IANA
  timezone override. Resolve DST gaps deterministically by advancing to the
  first valid local minute and DST folds with `fold=0`; unique UTC
  `scheduled_for` values prevent duplicate execution.
- Run a low-frequency scheduler coordinator inside the existing Worker
  process. It atomically creates due runs and ordinary crawler tasks using
  `BEGIN IMMEDIATE`, a unique `(subscription_id, scheduled_for)` constraint,
  and persistent next-run timestamps.
- Queue all platform tasks for one run contiguously and let the existing
  global Worker lock execute them in FIFO order. Never launch a second
  browser or bypass the normal Adapter/Runner path.
- Persist explicit run/task ownership and per-platform results. Worker restart
  must preserve queued tasks, fail interrupted active tasks through the
  existing contract, and reconcile the owning run without rescheduling the
  same slot.
- Pausing a subscription stops future run creation but does not silently
  destroy already-created tasks. Manual execution refuses overlap with an
  already-active run.
- Apply bounded failure delay on top of the next nominal schedule, starting at
  six hours and capped at 24 hours. Never spin or retry indefinitely.

### Incremental results

- A subscription run records scheduled/started/finished timestamps, status,
  platform/task results, new content, existing content, changed metrics,
  failed platforms, and an error summary.
- Extend ingestion to distinguish content that did not previously exist,
  content that already existed, and existing content whose non-null metrics
  changed. Repeated content must not count as new intelligence.
- Expose recent/next execution, duration, per-platform state, counts, errors,
  and linked crawler tasks in the subscription detail and frontend.

### Tags, favorites, and collections

- Add unique owner-scoped tags and many-to-many content tags. Permit create,
  rename, deletion only when unused, assignment/removal, and filtering.
- Use one canonical favorite model: `library_contents.is_favorite`. Do not
  create a competing built-in favorites collection.
- Add owner-scoped collections with name, description, timestamps, ordered
  content items, and content count. Permit create/update, add/reorder/remove.
- Do not seed fake tags or collections. All organization writes require an
  owner session or the separately documented write scope where applicable.

### Creator monitoring and metric snapshots

- Add owner-scoped creator watchlist records, watch runs, and run/task links.
- Allow monitoring only when the creator's platform has an enabled,
  production-verified creator mode. Bound one run to at most five returned
  items and use only stored creator source IDs/profile URLs.
- Support start, pause, manual check, and `every_6_hours`, `daily`, or `weekly`
  check frequencies. Automatic runs use the same scheduler coordinator and
  ordinary single-concurrency crawler tasks.
- Upsert new creator content idempotently and record content and creator
  metric snapshots during normal ingestion and watch runs.
- Add indexed `content_metric_snapshots` and `creator_metric_snapshots`.
  Preserve missing fields as null, never overwrite a real current value with
  null, and deduplicate identical snapshots captured within a short window.
- Provide current values by default and load snapshot history/deltas only on
  demand with bounded pagination and interval selection.

### Deterministic trends and daily briefs

- Add persisted trend signals plus normalized content evidence links.
- First-version topics come only from stored subscription queries and source
  keywords; no unsupported semantic topic invention.
- Compute a documented, deterministic weighted score from volume, velocity,
  cross-platform reach, and engagement change. Record formula version,
  component scores, evidence contents/platforms, and a plain-language
  explanation.
- Mark signals `insufficient_data` unless the minimum current and comparison
  window evidence thresholds are met. Small samples must not be presented as
  high-confidence trends.
- Add `BriefGenerator`, production-default `DeterministicBriefGenerator`, and
  a disabled extension seam for `AIEnhancedBriefGenerator`. Enforce
  `MEDIAOPS_AI_PROVIDER=disabled`; do not require or call an external model.
- Persist briefs, versioned regeneration, structured brief items, and
  evidence links. Cover the time window, new content, topics, trends, creator
  activity, engagement, favorites, failures/data gaps, and source links.
- Label every item as `fact`, `calculation`, `rule`, `insufficient_data`, or
  `unknown`. Never state a rule result as a model fact.
- Support manual generation, explicit regeneration that retains earlier
  versions, and one owner-configurable daily automatic schedule.

### Agent Tool Service and REST API v1

- Add a framework-independent `app/services/agent_tools/` layer returning
  stable Pydantic schemas, never ORM/database rows.
- Provide `search_contents`, `get_content`, `get_creator`,
  `list_creator_activity`, `list_comments`, `list_trends`,
  `get_latest_brief`, `get_source_provenance`, `list_subscriptions`, and
  `get_subscription_status`.
- Every result includes stable internal IDs, platform source IDs/URLs,
  collection timestamps, provenance where relevant, pagination, and scope
  checks. Raw payloads, file paths, cookies, logs, and process IDs are absent.
- Add `/api/v1/library/search`, content/creator/activity/comment/provenance
  resources, `/api/v1/intelligence/trends`,
  `/api/v1/intelligence/briefs/latest`, `/api/v1/subscriptions`, subscription
  detail, and scoped crawler-task/subscription creation.
- Use `X-API-Key`, complete OpenAPI security descriptions, unified
  `{error:{code,message,details?}}` failures, uniform UTC RFC 3339 timestamps,
  and offset pagination for this bounded personal SQLite dataset.
- Preserve existing frontend API paths and response shapes aside from the
  intentional authentication boundary.

### Frontend product and visual system

- Add authenticated routing, login/logout/session-expiry behavior, CSRF-aware
  writes, API errors, and API-key one-time display/revocation.
- Establish design tokens for color, typography, spacing, radius, shadow,
  border, status, motion, and simple chart formatting.
- Use a bright mist-white/warm-gray intelligence laboratory, graphite text,
  restrained teal/cyan emphasis, and small warm-orange risk accents. Remove
  the large dark cyberpunk sidebar, cheap glow, and generic card-wall feel.
- Support desktop-first layouts and a verified 390 px navigation/content
  path with safe wrapping and no fabricated values.
- Implement navigation for Command Center, Today, Subscriptions, Library,
  Trends, Creator Watch, Collections, Collection Center, Agent &
  Integrations, and System Status.
- Command Center and Today prioritize real content/subscription/trend/brief/
  creator evidence. CPU, memory, and raw task totals are not the product hero.
- Implement full subscription, tags/favorite/collection, creator monitoring,
  trend evidence, brief, and API-key workflows. MCP and Notion are clearly
  marked planned with no fake connection controls.
- Continue to render untrusted content as React text only, validate remote
  URLs, and use safe external-link attributes.

### Documentation, migration, and rollout

- Add reviewed migrations `0006_access_control`, `0007_subscriptions`,
  `0008_library_organization`, and `0009_metrics_and_intelligence`, or an
  equivalently clear split.
- Upgrade safely from `0005`, initialize a fresh database at head, preserve
  all current tasks/library/provenance/raw JSONL, test existing-data upgrade,
  and verify SQLite integrity and indexes.
- Database downgrades must refuse when they would destroy stage-seven data.
  Rollback preference is Git revert or a reviewed forward fix; database
  restoration remains separately authorized.
- Update README, AGENTS, API/deployment/capability/Agent docs and the
  repository-native server skill. Add subscriptions, intelligence,
  access-control, external API, MCP roadmap, and Notion roadmap docs.
- Create the next planning task `external-agent-mcp-and-notion` without
  deploying MCP or connecting Notion.
- Run backend pytest with coverage, frontend lint/tests/build (and coverage),
  server shell syntax/tests, ShellCheck if already available, secret/runtime
  artifact scans, and production build before deployment.
- Commit and push all code. Back up SQLite, deploy through isolated marker
  stages and `--allow-migrations`, initialize the production owner
  interactively, then verify authentication, subscriptions, organization,
  creator watch, snapshots, trends, briefs, API scopes/revocation, services,
  zero active tasks, zero browser residue, and a clean production worktree.

## Technical Approach

1. Keep raw SQLite repositories and Pydantic contracts. Add cohesive auth,
   automation, intelligence, and Agent Tool services rather than exposing
   tables through routers.
2. Use `pwdlib[argon2]` with `PasswordHash.recommended()` for passwords.
   Session/API-key secrets are random 256-bit opaque values; the database
   stores only SHA-256 hashes because the tokens already have high entropy.
3. Use a synchronizer CSRF token stored as a hash on the session. The session
   status endpoint rotates and returns the non-authentication CSRF value for
   in-memory frontend use after reload.
4. Integrate one `AutomationCoordinator` into the existing Worker loop with a
   monotonic scheduler-poll deadline. SQLite transactions atomically create
   automation runs, task rows, and ownership links.
5. Use Python 3.11 `zoneinfo`; round-trip candidate local datetimes through UTC
   to detect gaps/folds. Store only resolved UTC schedule slots.
6. Return an ingestion result containing new/existing/metric-changed IDs,
   create deduplicated metric snapshots in the same transaction, and let the
   coordinator reconcile linked run state after every Worker iteration.
7. Use transparent trend formula version `rules-v1`:
   `0.35*volume + 0.30*velocity + 0.20*cross_platform + 0.15*engagement`.
   Persist every component and evidence link; gate presentation on evidence
   thresholds independently of the numeric score.
8. Build briefs from stable queries over persisted contents, snapshots,
   trends, watch runs, favorites, subscription failures, and provenance.
9. Keep the browser UI on compatibility APIs initially; make both compatibility
   routers and `/api/v1` call the same service layer.
10. Break implementation into reviewable migration/auth, automation/library,
    intelligence/API, and frontend/docs commits before one final production
    release.

## Decision (ADR-lite)

**Context:** The server has 2 vCPU and about 1.6 GiB RAM, the current Worker
already owns a process lock and single-browser queue, and the database is a
small versioned SQLite store. Stage seven also introduces secrets and an
external API boundary.

**Decision:** Use server-side opaque sessions plus synchronizer CSRF, hashed
scoped API keys, and a SQLite-backed scheduler embedded in the existing Worker.
Keep trends and briefs deterministic and evidence-linked. Add a stable service
layer shared by compatibility APIs, REST v1, the frontend, and future MCP.

**Consequences:** No Redis, broker, scheduler daemon, JWT signing secret,
external AI key, or new browser service is required. SQLite transactions and
unique slots provide restart-safe idempotency, while the single Worker remains
the only browser executor. The operator must create the first production owner
password interactively after deployment; this is intentionally not automated.

## Acceptance Criteria

- [x] Owner authentication, session revocation/logout, CSRF, login throttling,
      and scoped/revocable one-time API keys pass backend and frontend tests.
- [x] Only `/api/health` and authentication bootstrap routes are anonymous;
      protected compatibility and v1 routes enforce the documented boundary.
- [x] Subscription CRUD/pause/resume/manual/scheduled runs work for only
      verified search modes and are DST-safe, idempotent, restart-safe,
      sequential, and failure-bounded.
- [x] Run history accurately separates new, existing, and metric-changed
      content and links every platform task.
- [x] Tags, one canonical favorite state, and ordered collections work against
      real library content without deleting collected data.
- [x] Creator watch is available only for verified creator modes and creates
      new content plus deduplicated content/creator metric snapshots.
- [x] Trends use the documented formula and evidence; insufficient data is
      represented honestly.
- [x] Manual/automatic/versioned briefs contain typed conclusions, links, and
      evidence with AI disabled.
- [x] Agent Tool Service and `/api/v1` expose stable scoped schemas without raw
      payloads or server internals; compatibility APIs still function.
- [x] The bright intelligence-lab UI implements all stage-seven workflows and
      remains usable at 390 px without unsafe content rendering.
- [x] Fresh and `0005` upgrade tests pass; production data and raw JSONL remain
      intact; integrity check is `ok`.
- [x] Backend tests/coverage, frontend lint/tests/build/coverage, shell tests,
      production build, authentication, real subscription/watch/trend/brief/
      Agent API validation, service/resource checks, push, and clean worktrees
      are recorded.
- [x] Production reaches the final commit with an initialized owner, zero
      active tasks, zero browser residue, active API/Worker, and all historical
      capability statuses unchanged.

## Definition of Done

- All database, backend, Worker, frontend, tests, docs, operational changes,
  rollback cautions, and the phase-eight planning task are reviewed and
  committed.
- Production owner setup is completed without a password entering chat, Git,
  shell history, logs, or deployment output.
- The final report includes both production revisions, backup path/checksum,
  tables/indexes, auth/scopes, scheduling/idempotency evidence, real validation
  IDs/counts, quality results, service/resources, commits/push/worktrees, exact
  deployment commands, rollback cautions, and phase-eight scope.

## Out of Scope

- MediaCrawler updates, Douyin revalidation, Kuaishou search repair, or changes
  to any existing deferred platform/mode state without new real evidence.
- Redis, Celery, Kafka, RabbitMQ, Elasticsearch, time-series databases,
  additional browser concurrency, proxy pools, automated publishing, or
  independent per-subscription processes.
- Automatic comment/sub-comment subscriptions.
- External LLM calls, Agent chat UI, production MCP Server, Codex external
  connection, Notion OAuth/API/Webhook, or autonomous Agent write confirmation.
- Cloudflare Access, Cloudflare/security-group/firewall/sudoers/root changes,
  database replacement/restoration, or destructive deletion.

## Research References

- [`research/access-control-and-api.md`](research/access-control-and-api.md) —
  current FastAPI/pwdlib patterns and the selected session/API-key boundary.
- [`research/sqlite-scheduling-and-dst.md`](research/sqlite-scheduling-and-dst.md)
  — embedded scheduler, atomic slots, restart recovery, and DST policy.

## Technical Notes

- Stage-six source of truth:
  `archive/2026-07/07-28-platform-content-modes/production-validation.md`.
- Relevant code begins in `backend/app/main.py`, `backend/app/db.py`,
  `backend/app/repositories/`, `backend/app/workers/crawler_worker.py`,
  `backend/app/api/`, `frontend/src/app.tsx`, `frontend/src/api/`, and
  `frontend/src/styles.css`.
- Existing APIs expose server paths/PIDs in crawler responses. Compatibility
  remains owner-only; stable Agent v1 schemas explicitly omit those fields.
- The production password is the only known blocking input. It is deferred
  until tested code is deployed and `create-owner` can run interactively.

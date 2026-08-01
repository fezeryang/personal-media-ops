# AI Runtime and Controlled Research Task

## Goal

Build Phase 8B on top of the production Phase 8A Model Gateway.  Add one
controlled, auditable Research Agent runtime that can create a persisted
research task, plan and execute bounded rounds using the existing library and
single-concurrency crawler, save evidence-bound findings and proposed actions,
and expose the task/result lifecycle in one authenticated frontend page.
The implementation must remain inside the existing FastAPI, SQLite, process
queue, SSE, and fcntl-lock boundaries; it must not expand into MCP, Notion,
multi-agent, discovery, or autonomous publishing features.

## What I already know

* Production baseline is commit `02cd677091950c5989f28d7eb9794c517c8ef641`;
  Phase 8A is deployed with Alembic head `0010_ai_model_gateway`.
* `app.main.create_app()` constructs `AIRepository`, `ModelGateway`,
  `CrawlerTaskRepository`, `LibraryRepository`, `AgentToolService`, and the
  existing automation/intelligence services.  The gateway is exposed as
  `application.state.model_gateway`; API and Worker are separate systemd
  processes.
* `ModelGateway.generate()`/`stream()` is the only model execution boundary.
  It performs route selection, capability validation, bounded retry/fallback,
  cancellation, and invocation audit, but its invocation schema currently has
  no `research_task_id`.
* `AgentToolService` already returns stable DTOs for library search, content,
  creator history, provenance, trends, and subscriptions.  Library rows retain
  normalized content and `crawl_task_entities` provenance; `get_content()` can
  return source URL, author, publication time, comments, and crawl task/time.
* `CrawlerTaskRepository.claim_next()` uses `BEGIN IMMEDIATE` and refuses to
  claim while any task is `running` or `waiting_login`.  `CrawlerWorker` owns a
  process-wide fcntl lock, runs exactly one browser task, polls the SQLite
  queue, and atomically ingests results/provenance through
  `LibraryRepository.ingest_task()`.  There is no existing research wake event;
  completion is currently observed by queue polling and automation
  reconciliation.
* The frontend is a React/Vite authenticated shell with React Router,
  TanStack Query, typed Zod API modules, same-origin session/CSRF handling, and
  one existing AI Model Center route at `/ai/models`.  A new route/page can
  reuse these conventions without restructuring the navigation IA.
* The current backend uses stdlib `sqlite3` repositories and Alembic for all
  schema changes.  Startup verifies the head and never silently migrates.
* The current user requirements make Path A mandatory: research must use a
  native function-calling model route, with MiniMax and GLM five-capability
  checks recorded before they can be research-capable.  No structured-output
  fallback chain is allowed.

## Assumptions (confirmed)

* The architecture review was confirmed by the user before implementation.
  Runtime code, migration, production configuration, and the single frontend
  page are now in scope.
* The existing Worker remains the only browser executor and the only holder of
  the global crawler fcntl lock.  Research execution is a persisted state
  machine driven by short worker/API ticks, never a long-lived browser or
  `while True + sleep` research thread.
* The first real validation task is the supplied personal-AI-workbench
  research objective.  It must use real configured provider calls and real
  library/crawler data; mock data is not an acceptance path.

## Open Questions

* Resolved: the user confirmed execution against the live configured protocol
  rows.  No 8A Provider configuration was changed.  The live MiniMax and GLM
  capability results are recorded below and gate the research route.

## Requirements (evolving)

### Runtime and state

* Add the eleven persisted task states and transitions: `Draft`, `Planning`,
  `Researching`, `WaitingCrawl`, `WaitingLogin`, `Summarizing`,
  `AwaitingReview`, `Done`, `BudgetExceeded`, `Failed`, and `Cancelled`.
* Persist target, input, plan, context/evidence references, route snapshot,
  budget configuration and consumption, round number, current step, result,
  error, timestamps, and an append-only execution trace.  A restart resumes
  from the durable state without replaying already charged work.
* `submit_crawl` creates a normal existing `crawler_tasks` row after capability
  validation, records the research-task correlation, transitions to
  `WaitingCrawl`, and returns control immediately.  The research state is
  woken by a durable completion event/claim, not by a blocked coroutine.
* All agent writes go through `propose_action`; the runtime never writes user
  data, crawler configuration, or monitoring rows directly on the model's
  behalf.  Human approval is a separate explicit transition.

### Evidence and tools

* Hard-code exactly the eight in-process tools: `search_library`, `get_content`,
  `get_provenance`, `get_creator_history`, `submit_crawl`, `dedupe_check`,
  `save_finding`, and `propose_action`.  Calls outside this set are rejected
  and traced.
* `save_finding` requires at least one content reference for `fact`; inference
  findings are explicitly labeled and list the supporting fact/content IDs.
  Findings are references to existing content, never duplicated content
  payloads.  Events associate multiple content rows across platforms.
* Each round first searches the library.  A later round's plan is derived from
  actual first-round entities/results, not a repeat of the original query.
  Context assembly has deterministic budgets and records the prompt token
  estimate/actual gateway usage sent for the round.

### Budget, routing, and audit

* Four independent gates (crawl count, newly added content count, wall-clock
  duration, and tokens) transition to `BudgetExceeded` and force summarizing
  existing evidence.  Monetary gating is active only when the selected model
  has complete configured prices; otherwise it remains explicitly inactive and
  visible as `null`/not configured.
* Route snapshots are captured at task start.  Research/event-merge uses the
  strongest model whose five tool tests pass; high-frequency extraction and
  dedupe use the low-cost route.  Fallback preserves initial model,
  failure-safe summary, selected fallback, and final state in audit rows.
* Every model call uses Model Gateway and records `research_task_id`; no
  provider SDK, direct HTTP, or secret material crosses the Runtime boundary.

### API and UI

* Add owner-session + CSRF protected task create/list/detail/control/result
  endpoints and an SSE task-event stream.  Expose only redacted invocation
  metadata and real trace/tool arguments that are safe to display; never expose
  credentials, raw secrets, or unbounded prompt/output bodies.
* Add exactly one frontend Research Tasks page: list, create form (goal,
  platforms, four limits), detail/trace/evidence/findings/actions, budget and
  result/error state, and pause/continue/cancel/rerun-one-round controls.
  Preserve the existing fourteen-page structure and do not create an AI chat
  workspace.

### Deployment and tests

* Add a forward Alembic migration from `0010_ai_model_gateway` (revision number
  chosen from the actual head) with upgrade preservation, guarded downgrade or
  documented irreversible rationale, backup/integrity checks, and existing
  table count comparison.
* Cover state transitions/recovery, all four budget gates, async crawl
  suspend/wake/restart/login timeout, tool whitelist and evidence rules,
  route snapshots/fallback, invocation linkage, API auth/CSRF/redaction,
  migration preservation, frontend page/empty/error/narrow-screen behavior,
  and one real non-mock end-to-end research run.

## Acceptance Criteria (evolving)

* [ ] Architecture review is confirmed before implementation starts.
* [ ] All eleven states are reachable, durable, and restart-recoverable.
* [ ] `submit_crawl` is asynchronous and never occupies a browser lock or
      execution thread while waiting.
* [ ] Every budget gate forces `BudgetExceeded → Summarizing` with consumed
      amounts retained; cost gating is inactive when price data is incomplete.
* [ ] Only the eight hard-coded tools execute; unknown tools are traced and
      rejected.
* [ ] Every fact finding opens at least one real content/provenance chain;
      inference findings are visibly labeled and source-linked.
* [ ] Every model call is a Model Gateway invocation linked to the research
      task, with finite retry/fallback provenance.
* [ ] Existing crawler/library/subscription/intelligence data survives the
      migration and SQLite `integrity_check` is `ok`.
* [ ] The single Research Tasks page supports create, monitor, inspect,
      controls, evidence, and result/error viewing at 390 px.
* [ ] The supplied personal-AI-workbench objective completes once with real
      providers and at least two collection rounds; the second-round keywords
      come from first-round entities; at least one novel user-unexpected
      finding is recorded.
* [ ] Backend and frontend quality gates, migration tests, shell checks, and
      production service/secret checks pass; the tree is clean except the
      pre-existing untracked `CLAUDE.md`.

## Definition of Done (team quality bar)

* Tests added/updated for domain, repository, gateway linkage, Worker wake,
  API security, frontend contracts, and real-run acceptance evidence.
* `cd backend && uv run pytest`; frontend lint/test/build; migration and shell
  syntax checks are green.
* Production deploy uses the reviewed restricted helper, a verified backup,
  marker checkpoints, and post-deploy API/Worker/database checks.
* Documentation and the final report identify exact commits, migration,
  evidence, limitations, and 8C recommendations without calling reservations
  implemented features.

## Technical Approach

### Planned layers

```text
Research Tasks API / Research Tasks Page
        ↓ owner controls + SSE
ResearchTaskRuntime (durable tick/recovery boundary)
        ↓
ResearchOrchestrator (plan, round, tool dispatch, context, summarize)
        ↓
ResearchToolRegistry (exact eight in-process tools)
        ├── AgentToolService → LibraryRepository / provenance
        ├── CrawlerTaskRepository → existing Worker queue
        └── findings/events/action repositories
        ↓
ModelGateway → configured native function-calling provider
```

The runtime should execute one short state-machine tick per scheduling pass.
An API create/control action writes a durable task and a Worker/API tick claims
it with `BEGIN IMMEDIATE`; after a model/tool step it commits the next state
and trace before returning.  Long model calls remain cancellable async HTTP
operations.  A crawl submission commits `WaitingCrawl` and returns; the
existing crawler Worker later commits the normal crawler result and a small
research wake marker.  Recovery scans non-terminal tasks on startup/tick and
reconciles orphaned wake markers, crawler statuses, and unfinished invocation
rows without replaying completed trace steps.

### Async crawl wake design (implemented)

1. Runtime validates platform × mode with the current registry and creates a
   normal `crawler_tasks` row with `research_task_id`, then commits the
   research correlation and `WaitingCrawl` state.  No browser, fcntl lock, or
   blocking wait is held.  Startup recovery attaches a crawler created in the
   small crash window before the correlation commit.
2. The crawler Worker claims that row under its existing global fcntl lock.  On
   successful atomic library ingestion, it transitions the correlated research
   task to `Researching` with counts and completion time; failure/login timeout
   transitions it to a safe bounded failure.  Login signals additionally map
   `WaitingCrawl` ⇄ `WaitingLogin`.  The Worker remains single-concurrency.
3. A runtime tick scans the correlated SQLite statuses and appends a trace
   event before resuming the next round.  No `while True + sleep` coroutine
   waits for the crawl; the crawler row and research correlation are the
   restart source of truth.
4. On API/Worker restart, startup recovery reconciles terminal crawler rows and
   attaches orphaned rows created immediately before an API interruption.  QR
   login remains the existing crawler task's `waiting_login`; login timeout
   wakes the research task as a bounded failure, never an indefinite wait.

### Context and evidence policy

The durable context stores compact plan steps, entity IDs, finding IDs,
content IDs, tool summaries, and redacted trace metadata.  Each model round
receives: the user goal, current plan step, a bounded set of newest/most
relevant content summaries, provenance IDs, prior findings, and a compact
tool-result summary.  Full source payloads remain in the library and are
retrieved on demand; a deterministic token/character cap drops bodies before
identifiers, and the trace records the selected IDs plus estimated/actual
input tokens.  The final summary is generated only from saved evidence and
explicitly separates fact, inference, unknown, and proposed action.

### Data flow

```text
owner goal
  → research_tasks(Draft + budget + route snapshot)
  → Planning(ModelGateway, plan + trace)
  → Researching(round N; search_library first)
  → existing library evidence OR submit_crawl → crawler_tasks
       → single Worker/fcntl → ingest library + provenance → wake record
  → tool results/entities → findings(content M:N) + events(content M:N)
  → Budget gate / result evaluator
  → Summarizing(ModelGateway) → AwaitingReview / Done
  → owner controls: continue, cancel, rerun one round, approve actions
```

### Data model direction

* `research_tasks`: owner/goal/type/status, plan/context/result/error,
  route/budget snapshots, consumed counters, current round/step, timestamps.
* `research_tasks`: the task row owns the durable plan/context/result JSON,
  append-only execution-trace JSON, proposed-action queue JSON, route/budget
  snapshots, and the current waiting crawler ID.  This keeps the mandated
  schema boundary to the three new domain tables rather than inventing an
  unrequested task-log or action table.
* `findings`: task/round/type/text with the required many-to-many
  `finding_contents` relation to `library_contents`; no content duplication.
* `events`: normalized event identity/summary with the required
  `event_contents` relation to `library_contents`.
* Add a nullable `research_task_id` to existing `crawler_tasks` so the Worker
  can atomically mark a waiting task ready and append its wake/trace state in
  the owning `research_tasks` row.  Delivery is idempotent through the stored
  crawler ID and trace sequence, not a separate wake table.
* Add nullable `research_task_id` (and an index) to
  `ai_model_invocations`.  Reserve an `entity_graph` design note only; do not
  implement the graph in 8B.

## Decision (ADR-lite)

**Context**: The server has one SQLite-backed crawler queue and one global
fcntl browser lock, while the requested Research Agent needs multi-round tool
use, pause/resume, and restart recovery.

**Decision**: Use Path A native function calling with a persisted SQLite state
machine and short runtime ticks.  Reuse `AgentToolService`, library
repositories, the existing crawler queue/Worker, and Model Gateway.  Wake
research tasks through durable correlation/wake records rather than holding an
async task open.  Add only the research domain tables and invocation linkage;
do not add a broker or another database.

**Consequences**: This satisfies auditability, single-concurrency, and
restart safety, but it makes progress/event delivery eventually consistent
between Worker and API ticks, requires capability tests before enabling the
research route, and cannot transparently continue a partially emitted model
stream on fallback.  The first runtime remains one Research Agent with a
fixed eight-tool registry; future agents/skills can add roles and tools behind
the same persisted task boundary without shipping an empty framework now.

## Out of Scope

* Multi-agent collaboration, Agent self-creation, Skill Marketplace/Runtime,
  Discovery Engine, information self-propagation, long-term autonomous
  monitoring, public platform rankings, unrestricted web crawling.
* MCP Server, Notion sync, Webhook, local Claude Code bridge, remote agents,
  automatic publishing, and full AI chat workspace.
* Knowledge graph implementation (only an entity-graph schema design note),
  user feedback memory, opportunity cards, event aggregation beyond the
  minimal `events` evidence grouping, and navigation IA redesign.
* Redis, Celery, PostgreSQL, S3, Kafka, Elasticsearch, Docker, WebSocket, a
  second database, or any MediaCrawler core modification.

## Technical Notes

* Relevant specs: `.trellis/spec/backend/ai-model-gateway.md`,
  `database-guidelines.md`, `crawler-platforms.md`,
  `access-automation-intelligence.md`, frontend `ai-model-center.md`, and
  `guides/cross-layer-thinking-guide.md`.
* Key implementation files inspected: `backend/app/main.py`,
  `services/ai/model_gateway.py`, `models/ai.py`, `repositories/ai.py`,
  `repositories/crawler_tasks.py`, `workers/crawler_worker.py`,
  `repositories/library.py`, `services/agent_tools/service.py`,
  `frontend/src/app.tsx`, `components/app-shell.tsx`, `api/ai.ts`, and
  `pages/ai-model-center-page.tsx`.
* Production 8A evidence remains the baseline: no real research route is
  configured yet; DeepSeek tool capability is false under thinking mode.
  Preflight capability results on 2026-08-01 through the Model Gateway:
  MiniMax-M3 passed forced single call, multi-turn continuation, eight-tool
  selection, tool streaming, and long-context selection; its
  `supports_tools=1`, `supports_streaming=1`, and `capabilities_source=tested`.
  GLM `glm-5.2` passed forced single call, eight-tool selection, tool
  streaming, and long-context selection, but failed multi-turn continuation;
  its `supports_tools=0`, `supports_streaming=1`, and
  `capabilities_source=tested`.  The existing `tool_calling` route was cleared
  because GLM failed a hard condition.  MiniMax remains a candidate for the
  research/tool route; no research task route is enabled until Runtime route
  snapshot validation is implemented.

# Current architecture audit (2026-08-01)

## Baseline and production

* Repository and production are both at `02cd677091950c5989f28d7eb9794c517c8ef641`.
* Production Alembic revision is `0010_ai_model_gateway`; SQLite integrity is
  `ok`; current counts are 76 crawler tasks, 84 library contents, 270 task /
  entity provenance links, and 14 model invocations; active crawler tasks are
  0.
* `mediaops-api` and `mediaops-crawler-worker` are active, port 8000 listens,
  localhost health is `ok`, and the published frontend marker matches the
  repository commit.

## Backend reuse points

* `app.main.create_app()` builds repositories/services once and exposes them on
  `application.state`; the lifespan owns the shared bounded `httpx.AsyncClient`
  and closes it on shutdown.
* `ModelGateway` is already the single model boundary.  It resolves a route or
  explicit model, decrypts a provider secret just in time, validates model
  capabilities, uses a per-provider semaphore, performs finite retry/fallback,
  records safe invocation metadata, and propagates cancellation.  Product code
  must inject/use this object rather than adapter classes.
* `AgentToolService` already supplies stable DTOs for library search, content
  details, creator activity, and provenance.  `LibraryRepository` owns
  normalized content, creators, comments, and `crawl_task_entities`; its
  ingestion transaction marks a crawler task succeeded atomically with entity
  and provenance writes.
* `CrawlerTaskRepository` uses `BEGIN IMMEDIATE` to claim one oldest pending
  row while rejecting any running/waiting-login row.  `CrawlerWorker` holds a
  database-derived fcntl lock, launches one adapter Runner, handles QR/login
  states and cancellation, and then calls library ingestion.  It currently
  has no research callback or wake marker.
* `app.security.dependencies` provides owner-session authentication, Origin /
  Referer validation, and synchronizer-token CSRF for unsafe browser methods.
  API responses are Pydantic models; repositories return plain stable dicts.

## Frontend reuse points

* React Router is defined in `frontend/src/app.tsx`; the authenticated shell
  and desktop/mobile nav are in `components/app-shell.tsx`.  Pages compose
  TanStack Query hooks and shared `PageHeader`, `Card`, `Badge`, `Button`, and
  error primitives.
* `src/api/ai.ts` is the established pattern for Zod-validated contracts,
  `requestJson`/`requestResponse`, CSRF-aware mutations, and bounded SSE stream
  parsing with cancellation.  A Research Tasks API module/page can follow the
  same pattern without changing the existing AI Model Center.

## Production capability observation

The live database currently describes DeepSeek as `openai_compatible`, but the
configured GLM and MiniMax records are `custom_anthropic` / `anthropic_compatible`
(`GLMcodingplan` at the GLM Anthropic endpoint and a custom MiniMax Anthropic
endpoint).  The live `tool_calling` route points to `glm-5.2`, while DeepSeek
flash is the default and MiniMax is the deep route.  This differs from the
request's statement that all three are OpenAI Compatible.  No provider or route
was changed during this audit.  The five MiniMax/GLM tool tests and capability
write-back must therefore either use the configured protocols as the source of
truth or be preceded by an explicit 8A configuration correction; that choice
is a review confirmation item.

## Boundary conclusion

The smallest safe 8B addition is a new runtime/orchestrator service in the API
process, a durable research-task repository/state machine, a Worker-side
completion reconciliation hook, a migration for the mandated research tables
and invocation/crawler correlation columns, and one owner-only page.  No
broker, second database, MediaCrawler-core edit, or Provider rewrite is needed.

# Multi-platform Crawler Infrastructure and Initial Adapters

## Goal

Refactor Personal Media Ops from a Bilibili-specific crawler integration into
a platform-neutral, single-worker collection system. Preserve existing
Bilibili tasks and JSONL data, add formal SQLite migrations, prepare runnable
XHS and Douyin keyword-search adapters, and drive the React task form from a
real backend capability contract.

## Requirements

- Add a platform Adapter abstraction and a single registry for `bili`, `xhs`,
  and `dy`.
- Keep only keyword search and QR-code login.
- Keep `requested_count` at 1–20 and global browser concurrency at one.
- Keep comments, sub-comments, proxies, media download, AI, publishing, Agent,
  and MCP features disabled.
- Add `GET /api/crawler/capabilities` and make task creation validate the
  registry plus runtime-enabled platform set.
- Add `MEDIAOPS_ENABLED_PLATFORMS`, defaulting to `bili`; expose XHS and Douyin
  as `code_ready` but disabled unless explicitly enabled.
- Keep all existing task response fields, statuses, paths, cancellation,
  bounded logs, QR behavior, and pagination routes.
- Introduce a stable unified result item returned by the existing paginated
  results endpoint.
- Read legacy/raw platform JSONL incrementally through adapters and cap visible
  results/`actual_count` at `requested_count`.
- Fix QR state progression so only a successful-login log marker leaves
  `waiting_login`.
- Store a reviewed multi-platform Runner source in this repository; never
  modify or copy MediaCrawler core.
- Establish Alembic revisions for fresh databases and migration of the
  existing Bilibili-only table.
- API and Worker startup must verify schema head rather than silently migrate.
- Update deployment orchestration with an explicit migration opt-in and never
  run it in this task.
- Update frontend platform selection, labels, QR instructions, task details,
  engine summary, and unified result rendering without a broad visual rewrite.
- Update README, API contract, and deployment documentation.

## Acceptance Criteria

- [x] Capability API reports one global task and three truthful platform
      capabilities.
- [x] Bilibili is enabled and verified by default; XHS/Douyin default to
      disabled and code-ready.
- [x] Disabled or unknown platforms cannot create tasks.
- [x] Enabling XHS/Douyin allows only fixed search/QR/count inputs.
- [x] Worker commands for all adapters use fixed executables, no shell, one
      concurrency, no comments, and no proxy.
- [x] Concurrent claims still start at most one task across all platforms.
- [x] QR-save output does not prematurely clear `waiting_login`; a verified
      success marker does.
- [x] Bilibili legacy rows survive migration byte-for-byte at the column-value
      level.
- [x] Existing Bilibili JSONL is normalized without rewriting source files.
- [x] XHS and Douyin sample JSONL normalize to the same result schema.
- [x] Results remain bounded, paginated, path-safe, and capped at the request.
- [x] Alembic upgrades a blank database and the legacy schema to head.
- [x] Downgrade refuses to discard a constraint while non-Bilibili rows exist.
- [x] Frontend form is generated from capability data and shows code-ready
      platforms honestly.
- [x] Backend pytest, frontend lint/test/build, and server-script Bash syntax
      all pass.
- [x] No production migration, release, XHS/Douyin task, Nginx/network change,
      or `mediaops-release finalize` occurs.

## Definition of Done

- Adapter, API, Worker, migration, frontend, tests, docs, and deployment
  impacts are complete and mutually consistent.
- Code is committed and pushed to `main`.
- The local worktree is clean.
- A pre-deployment report lists migration and rollback steps, verified versus
  code-ready platforms, and the exact separately authorized deploy command.

## Technical Approach

Use lightweight Python adapters around the fixed external Runner. The registry
owns both capability metadata and executable behavior. API responses use
Pydantic models; the frontend validates them with Zod and never duplicates a
hard-coded supported-platform list.

Alembic owns schema history, but runtime reads/writes remain direct `sqlite3`.
Two revisions bootstrap the old schema and then rebuild the table with an
expanded platform constraint. Startup checks schema currency. Deployment gets
an explicit `--allow-migrations` gate and runs migrations only after backup
and all code quality gates.

## Decision (ADR-lite)

**Context**: XHS and Douyin exist in the installed MediaCrawler source but have
not been exercised on this server, and their platform page sizes exceed some
allowed task counts.

**Decision**: Ship runnable adapters and Runner support while defaulting those
platforms to disabled `code_ready` capabilities. Keep Bilibili as the only
default-enabled, verified platform. Normalize and cap results in the Personal
Media Ops boundary rather than changing MediaCrawler.

**Consequences**: The architecture and UI are complete without claiming false
production validation. Enabling a new platform is an explicit environment and
deployment decision. Raw output may contain more platform-page records than
the bounded API exposes.

## Implementation Plan

1. Add Alembic and migration tests for blank and legacy databases.
2. Add Adapter/registry/capability/result contracts with unit tests.
3. Refactor API and Worker onto the registry and add the reviewed Runner.
4. Update frontend API types, dynamic form, labels, QR copy, and result cards.
5. Make deployment migration-aware; update docs and run all quality gates.
6. Commit and push, then stop before production deployment.

## Out of Scope

- Production deployment or database migration
- Real XHS or Douyin login/search
- Cloudflare, Nginx, SSL, firewall, port, or network changes
- Comments, sub-comments, proxy pools, media downloads, or increased
  concurrency
- Cookie input or browser-state management UI
- Additional platforms, crawler modes, AI analysis, Agent/MCP, or automatic
  publishing
- Large-scale workbench redesign
- Automatic database restore or downgrade in production

## Research References

- [existing-contracts.md](research/existing-contracts.md)
- [migration-strategy.md](research/migration-strategy.md)
- [adapter-design.md](research/adapter-design.md)

## Technical Notes

- Production inspection was read-only and did not execute MediaCrawler.
- Production Runner remains Bilibili-only until a separately authorized
  deployment installs the reviewed repository source.
- The migration is an expand-only compatibility change for the old
  application; code rollback should not downgrade it.

# Stage Six: Platform Content Modes and Library Foundation

## Goal

Upgrade Personal Media Ops from search-only JSONL task browsing into a
mode-aware, persistent research library. The full flow is:

```text
validated task request
→ platform Adapter and reviewed Runner
→ isolated raw JSONL
→ normalized content/creator/comment entities
→ idempotent library upsert and task provenance
→ API and workbench
→ small real production validation
```

The production capability matrix must report each platform/mode independently
and must never infer detail, creator, comment, or sub-comment support from a
verified search task.

## Confirmed Baseline

- Stage four is `completed_with_deferred_platform`; stage five is complete and
  archived.
- Local `main` and `origin/main` began at
  `9d66834dafdb90db02224a74ebfcea538359acc5`.
- Production application, build marker, and published marker began at
  `4df42050ff35d1a61e3e55bcf983419a9cbd13b5`; the worktree was clean.
- Production Alembic revision is `0003_remaining_platforms`; the only
  application table is `crawler_tasks`, with 28 preserved tasks and no active
  task.
- The pinned external MediaCrawler revision is
  `17f66121e0fcc40fc23958b995bec873d422667d`; its production worktree is clean.
  It must not be updated automatically.
- Bilibili, Xiaohongshu, Zhihu, Weibo, and Tieba search are enabled and
  production-verified. Kuaishou search is
  `deferred_upstream_breakage`; Douyin is
  `deferred_resource_constrained`.
- API and Worker are active, browser residue and D-state process counts are
  zero, and the production SNI loopback passes. The Codex external observer
  still reproduces `SSL_ERROR_SYSCALL`.

## Requirements

### Mode-level capability registry

- Model `search`, `detail`, `creator`, `comments`, and `sub_comments`
  independently for `bili`, `xhs`, `zhihu`, `wb`, `tieba`, `ks`, and `dy`.
- Each platform/mode exposes one truthful status:
  `not_implemented`, `code_ready`, `enabled`, `production_verified`,
  `deferred_resource_constrained`, `deferred_upstream_breakage`,
  `deferred_login_required`, `deferred_platform_change`, or `disabled`.
- A mode is submittable only when it is enabled. Production verification is
  separate from implementation and enablement.
- Retain platform display, icon, login, browser, QR, request-limit, upstream
  limitation, and resource metadata in the Adapter/registry rather than API,
  Worker, frontend, or deployment conditionals.

### Unified task contract

- Make `mode` canonical while preserving legacy search clients and old task
  rows that use `crawler_type=search`.
- Support platform, mode, keywords, target IDs/URLs, creator IDs/URLs,
  parent content ID, parent comment ID, requested content count, requested
  comment count, requested sub-comment count, and login type.
- Validate mode-specific fields at the API boundary and again in the Adapter.
  Reject unsupported/disabled combinations with clear 4xx responses before
  they enter the Worker.
- Search accepts keywords. Detail accepts target IDs or URLs. Creator accepts
  creator IDs or URLs. Comments accepts one parent content ID or content URL.
  Sub-comments accepts one parent comment ID plus the content context required
  by that platform.
- Unknown fields and contradictory target fields are rejected.
- First-level comments are limited to 10 and sub-comments to 5; they remain
  explicit task modes and are never recursively or implicitly enabled.

### Adapter and Runner contract

- Adapters declare supported modes, per-mode state, input requirements,
  login/browser behavior, result file types, mappings, limits, upstream
  limitations, and empty-result policy.
- Adapters own mode request construction, content/creator/comment discovery,
  normalization, login/QR classification, and failure classification.
- The Runner supports upstream search/detail/creator and reviewed integration
  seams for bounded standalone comment/sub-comment collection without
  modifying `/opt/mediacrawler`.
- Each task retains an isolated output directory, log, and QR image; browser
  state stays platform-separated; concurrency remains one; proxies and media
  downloads remain disabled; timeout/cancel terminates the process group.
- A zero exit code is not sufficient for success. The Worker must validate
  expected files, parse records, normalize entities, commit the library
  transaction and task provenance, and reject anomalous empty output.

### Persistent library

- Add formal SQLite tables for contents, creators, comments,
  content/creator links, and crawl-task/entity provenance.
- Source identifiers are strings. Missing source values remain null rather
  than fabricated zeroes. Public source data remains privacy-normalized to the
  pinned teaching runtime’s contract.
- Preserve raw payloads as JSON text, never render them as HTML, and omit them
  from list responses by default.
- Add unique constraints for `(platform, source ID)`, foreign keys for internal
  entity relationships, and indexes for source IDs, publication/collection
  dates, and source keyword.
- Repeat collection uses atomic upserts, preserves first collection time,
  updates last collection time, and creates idempotent task provenance.
- Preserve all old tasks and raw JSONL. Existing task result endpoints remain
  compatible.
- Do not add metric snapshot tables in this stage. Current values are retained
  on the entity; historical trend snapshots belong to the next stage.

### API

- Retain crawler capability, create/list/detail/log/QR/result/cancel APIs.
- Add paginated read-only library endpoints for content, creator and comment
  lists/details.
- Content filters include platform, type, keyword, creator, date range,
  comment presence, sort, offset, and limit.
- Stable IDs, platform/source IDs, source URL, collection timestamps, task
  provenance, related creator, and comments are represented in the core API.
- Full raw payload is available only from an explicit detail/debug field and
  remains JSON data.
- Keep OpenAPI complete and document future read-only Agent operations in
  `docs/agent-api-foundation.md`; do not implement an MCP server.

### Frontend

- Build task fields dynamically from the selected mode and backend
  capabilities. Unsupported/deferred modes remain visible but cannot submit.
- Add a mode-level capability matrix.
- Add library content list, content detail, creator detail, and comment views.
- Show platform/source/provenance, safe normalized text, links, covers,
  timestamps, metrics, keyword, collection time, creator and comment state.
- Open source links in a new tab with safe rel attributes, provide broken-image
  fallback, and never render untrusted HTML.
- Do not use mock data to mask a failed API.

### Verification and rollout

- Run backend tests, frontend lint/tests/build, server shell syntax/tests, and
  skill validation before deployment.
- Deploy through isolated SSH stages, a verified SQLite backup, explicit
  `--allow-migrations`, markers, and the restricted helper.
- Validate Bilibili and Xiaohongshu first, then Zhihu/Weibo/Tieba, then
  independent Kuaishou modes. Do not run Douyin browser validation.
- A single platform/mode failure records an exact deferred state and does not
  block unrelated modes.
- Real comments validation uses one content and at most 10 comments; real
  sub-comment validation uses at most 5 replies.
- Pause only for QR/captcha/operator account action, new authorization or
  secret, irreversible data work, or new system authority.

### Documentation and next stage

- Update README, AGENTS, API/deployment/upstream/capability docs, and the
  repository-native server skill.
- Create but do not implement the planning task
  `intelligence-library-and-subscriptions`, covering subscriptions,
  scheduling, deduplication, labels, favorites, metric snapshots, creator
  monitoring, daily briefs, and trend analysis.

## Technical Approach

1. Use `crawler_tasks.crawler_type` as the persisted canonical mode column for
   compatibility, expose `mode` in the new API, and accept the legacy
   `crawler_type=search` request shape.
2. Add a content-mode migration that makes search-only task fields nullable,
   adds JSON-encoded target arrays and bounded count fields, and expands the
   mode check constraint without rewriting old task values.
3. Add a separate library-entity migration so task-contract rollback and
   library schema ownership remain reviewable.
4. Introduce typed task input and normalized content/creator/comment models,
   a dedicated library repository, and a transaction-scoped ingestion service.
5. Keep the Worker platform-agnostic: it asks the Adapter for arguments and
   expected entity files, then passes parsed normalized entities to the
   ingestion service.
6. Map standalone comments to a single-target upstream detail run with
   comments enabled and bounded. Use only reviewed, platform-scoped Runner
   seams for targeted sub-comments where the fixed upstream exposes a suitable
   client API; otherwise report an exact mode-level deferred state.
7. Capture public creator records through privacy-safe, process-local Adapter
   seams when the pinned teaching runtime intentionally makes its JSONL
   creator store a no-op. Never patch or persist third-party source code.

## Decision (ADR-lite)

**Context:** The existing database and API are search-only, while the pinned
upstream offers `search/detail/creator` plus comment flags. Its teaching build
also suppresses several creator-profile JSONL writes and has no uniform
standalone sub-comment CLI.

**Decision:** Preserve the pinned upstream, extend the reviewed repository
Runner through narrow platform-scoped seams, and make platform/mode support
truthful and independently deferrable. Split task-contract and library schema
changes, keep raw JSONL immutable, and make the application library the
idempotent source for normalized entities.

**Consequences:** The architecture supports all requested modes without
coupling API/Worker/UI to platform branches. Some modes may remain explicitly
deferred when the pinned upstream cannot perform a bounded target operation.
Future upstream updates remain an audited, isolated decision.

## Acceptance Criteria

- [ ] The production capability API returns a truthful 7 × 5 matrix.
- [ ] Five task modes enforce mode-specific fields and limits; legacy search
      tasks and request clients remain compatible.
- [ ] Adapters and Runner centralize platform behavior; Worker/API/UI do not
      accumulate platform conditionals.
- [ ] Safe migrations from `0003` preserve all 28 initial tasks and raw JSONL;
      a fresh database reaches head.
- [ ] Contents, creators, comments, links, and task provenance use tested
      constraints, indexes, idempotent upserts and null semantics.
- [ ] Task success requires parsed output and committed normalized entities;
      anomalous empty output fails closed.
- [ ] Library list/detail APIs and frontend views work without executing raw
      HTML or returning raw payloads by default.
- [ ] Backend tests, frontend lint/tests/build, shell checks, and production
      build pass.
- [ ] Each requested platform/mode has real production evidence or a precise
      deferred state; Bilibili/Xiaohongshu regressions pass.
- [ ] Production migration backup, revision, services, SNI health, task count,
      browser/D-state/resource recovery and clean worktree are recorded.
- [ ] Work commits are pushed and the next-stage planning task exists.

## Definition of Done

- All code, migrations, tests, docs, deployment effects, and rollback cautions
  are reviewed and committed.
- Production is on the final application commit with the database at the new
  Alembic head, both services active, no active crawler task, no browser
  residue, and a clean worktree.
- No capability is called production-verified without a recorded real task.
- The stage-six final report contains the complete evidence requested by the
  operator.

## Out of Scope

- Automatic MediaCrawler updates or edits to `/opt/mediacrawler`.
- Redis, Kafka, Elasticsearch, additional crawler concurrency, proxy pools,
  mass collection, or automatic publishing.
- Douyin browser production validation or capacity remediation.
- An MCP server.
- Scheduled subscriptions, tagging/favorites, historical metric snapshots,
  daily briefs, and trend analysis; these belong to the next planning task.

## Technical Notes

- Upstream audit: `research/upstream-content-mode-audit.md`.
- Production baseline: `research/production-baseline.md`.
- User-owned untracked `CLAUDE.md` is outside this task and must remain
  untouched and uncommitted.

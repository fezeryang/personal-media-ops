# Cross-platform research completion

## Goal

Complete the remaining Phase 8C work as one production-safe change: make the
Research Runtime select and verify multiple real platforms with deterministic
coverage goals, explain every query/content decision, preserve independent
evidence semantics, expose step-level usage and mixed billing semantics, and
recover safely across API/Worker/model/crawler failures. The existing 8C-1
quality foundation at revision `0012_research_quality_foundation` remains the
starting point; no unfinished Discovery Engine or autonomous user action work
is introduced.

## What I already know

* Local `main` was `07dbf85` and `origin/main` resolved to the same commit at
  session start; production was still on `f156017573af3f9ba5d72fcd6ba875c2ed11746b`.
* Production is healthy locally: API and Worker active, localhost health OK,
  no active crawler or research tasks, Alembic revision
  `0012_research_quality_foundation`, and SQLite `integrity_check=ok`.
* Production `.env` currently has
  `MEDIAOPS_ENABLED_PLATFORMS=bili,xhs,zhihu,wb,tieba,ks`; effective runtime
  search capability enables Bilibili, Xiaohongshu, Zhihu, Weibo and Tieba;
  Douyin is `deferred_resource_constrained` and Kuaishou search is
  `deferred_upstream_breakage`.
* MediaCrawler is clean at pinned commit
  `17f66121e0fcc40fc23958b995bec873d422667d`; the deployed Runner matches the
  repository Runner byte-for-byte.
* Production contains 16 research tasks. Thirteen explicitly stored only
  `bili`; three stored five platforms, but the completed multi-platform task
  actually crawled only Bilibili and Xiaohongshu. This proves the remaining
  issue is Runtime routing/coverage, not merely the deployment allow-list.
* The 8C-1 runtime already has deterministic query normalization, generic and
  historical duplicate gates, source-chain fields, four-way content counts,
  evidence occurrences, support types/strengths, rendered reports, and basic
  durable controls. Its query statuses are too narrow and its platform choice
  is round-robin rather than goal-driven.
* Current production AI records have distinct provider rows but no billing
  profile/provider-instance semantics; all 151 invocations are currently
  uncosted. MiniMax tool capability is tested, GLM tool capability is false,
  and DeepSeek is not tool-capable in the live records.
* The public production endpoint is owner-authenticated; unauthenticated
  capability probing correctly returns 401. Internal read-only registry
  inspection and the deployed environment provide the capability facts without
  bypassing authentication.

## Requirements

### Cross-platform routing and evidence strategy

* Preserve Bilibili as the baseline and restore Research search in this order:
  Zhihu, Weibo, Tieba, then Xiaohongshu when its login context is usable.
  Douyin and Kuaishou search remain explicitly deferred and never become
  fallback platforms.
* Research accepts and persists platform, query, requested count, reason,
  query type, parent query, source content/Finding, task ID, and expected
  evidence role for every search/crawl call. The tool enforces capability
  status, count caps, task scope, and the single global browser/crawler
  concurrency boundary.
* Add deterministic platform-specific query templates. Bilibili emphasizes
  demos/tutorials/workflows, Zhihu analysis and counter-arguments, Weibo
  current discussion/controversy, Tieba real problems/negative experience,
  and XHS practical usage/consumer feedback. The same query is not blindly
  copied across platforms.
* Persist platform plan vs actual platform results, including failure/deferred
  reasons and query-level result counts.

### Coverage, entities, scheduling, and decisions

* Add a durable Coverage Plan supporting target platform/entity/negative
  evidence/independent evidence/new content counts and a maximum single-entity
  evidence ratio. The default acceptance target is 3 platforms, 3 entities, 1
  negative/contradictory item, max 60%, 5 independent evidence items, and 5
  new contents.
* Persist entity evidence/query/new-content counts and coverage ratio. Once an
  entity is saturated, reduce its priority and schedule alternatives,
  competitors, and counterevidence.
* Extend query state to `generated`, `rejected_generic`, `rejected_duplicate`,
  `rejected_low_relevance`, `rejected_low_value`, `approved_pending`,
  `executing`, `completed`, `skipped_budget`, `skipped_saturation`,
  `skipped_low_marginal_value`, `superseded`, `failed`, and `cancelled`.
  Existing 8C-1 statuses migrate forward without losing history.
* Add deterministic priority components for relevance, specificity, novelty,
  noise, expected value, entity/platform diversity, negative evidence, and
  estimated resource cost. Every approved-but-unexecuted query is transitioned
  to a skipped/superseded/cancelled state with a reason.
* After each round persist new-content rate, new entities, independent
  evidence, duplicates, model token cost, pay-as-you-go cost, and crawl
  duration. Configurable consecutive-low-yield stopping requires two rounds
  below threshold plus no new entity and no new contradictory evidence.
* Separate collected results, new contents, candidate evidence, adopted
  evidence, and content decisions. Persist explicit non-adoption reasons:
  low relevance, repeated viewpoint, too short, missing body, marketing,
  unrelated entity, no factual increment, low source quality, or out of scope.

### Evidence quality and report constraints

* Keep independent evidence deduplicated by normalized `content_id`, increment
  occurrence counts, and retain all query/task provenance.
* Add first-version cross-platform repost detection using normalized title,
  body-summary hash, source URL, author, publication time, and bounded text
  similarity. Reposts are visible but do not increase independent evidence.
* Add/confirm source independence, content completeness, and evidence quality
  for every selected evidence item. Facts require direct evidence. Inferences
  require derivation, explicit counterevidence state, and no market-wide claim
  from one product. Opportunity findings list missing market-size, price,
  willingness-to-pay, competitor, retention, and user-count information where
  absent.
* Attempt at least one negative search for each core entity; absence is recorded
  as `counterevidence_status=not_found`, never as a positive claim.
* Reports expose Facts, Inferences, Contradictions, coverage shortfalls,
  collection/new/adopted/not-adopted counts, query source chains, and the
  precise end reason: target reached, budget exhausted, low marginal value,
  platform unavailable, no executable query, or user cancellation.

### Context and step-level usage

* Record usage for planning, initial query generation, query quality review,
  tool-result evaluation, entity extraction, evidence selection, finding
  generation, coverage review, and final report. Each record includes provider
  instance, vendor, model, billing mode, input/output/cached tokens, latency,
  fallback origin/reason, and invocation correlation.
* Implement a traceable Context Compactor that retains objective, coverage
  targets, entities, query-chain summaries, high-value evidence summaries,
  contradictory evidence, unresolved questions, budget state, content IDs,
  source URLs, platforms, publication times, and evidence roles while
  compressing repeated results, full history, low-value branches, and duplicate
  bodies. Persist compaction metrics.
* Use summary-first loading: library/search summaries first, full body only for
  selected candidates, then a deduplicated evidence packet for synthesis.

### Billing, budgets, routing, fallback, and structured output

* Model billing distinguishes vendor, provider instance, billing profile, and
  model. Support `subscription_fixed`, `pay_as_you_go`, `prepaid_balance`,
  `quota_bundle`, `relay`, and `unknown` without inheriting prices between
  provider instances.
* Support annual MiniMax and GLM subscription records with token/call/time/
  concurrency semantics and null marginal cost; optional amortization is
  explicitly labeled. DeepSeek official pay-as-you-go prices are versioned by
  input/output/cache/currency/effective time/source and remain unavailable
  until complete real pricing is configured. Relay providers persist their own
  metadata and do not silently enter tool routing.
* Resource budgets support input/output/total tokens, model calls, crawl tasks,
  runtime seconds, new contents, and pay-as-you-go amount/currency. Subscription
  providers are blocked by token/call/time/concurrency budgets, pay-as-you-go
  providers also by amount, and unknown-price usage reports null cost rather
  than zero.
* Provide deterministic route policies `prefer_subscription`, `prefer_payg`,
  `balanced`, `quality_first`, and `manual`. Tool calls require a tested
  tool-capable provider; default behavior prefers MiniMax for tools, GLM for
  ordinary analysis, and DeepSeek official for high-quality summary/fallback
  only when configured. A relay provider must pass structured and multi-turn
  tool tests before tool routing.
* Keep bounded retry/fallback behavior capability-aware. MiniMax is the tool
  route; DeepSeek may take over only for an equivalent tested capability or a
  summary step. Record the full fallback trajectory and never cross-model
  continue a stream after content has been emitted.
* Implement bounded structured-output degradation:
  native structured output → tool schema → strict JSON → one JSON repair →
  explicit failure. Apply it to plans, query candidates, entities, findings,
  coverage, and actions; never loop repairs.

### Runtime reliability and UI

* Add durable checkpoints and budget events so API/Research Runtime/Worker
  restarts resume completed work without repeating it, resetting budgets,
  duplicating evidence, or creating crawls after cancellation.
* Pause stops new model calls and crawler submissions while allowing an active
  short request to finish; Resume continues from the persisted safe checkpoint;
  Cancel stops new work, requests cancellation of an attached crawler, retains
  evidence/trace, and never auto-resumes.
* Add fault-injection tests for API/Runtime/Worker restart, model timeout,
  rate-limit/auth/tool-format errors, crawler/login timeout/cancel, SQLite
  transient lock, fallback success/failure, token/cost budgets, and all control
  semantics. No failure may leave a task permanently runnable or waiting.
* Upgrade the Research page with platform plan/results, entity coverage,
  query queue and skip reason, evidence/adoption/repost details, marginal
  yield, budget classifications, subscription vs payg/relay totals, model and
  fallback trace, controls, accurate errors, and 390px layout coverage.

## Acceptance Criteria

* [ ] Forward Alembic migration upgrades a populated 0012 database, preserves
  all existing research/query/Finding/evidence/invocation rows, passes
  integrity check, and has a reviewed fail-closed downgrade rationale.
* [ ] At least three real search-capable platforms participate in one bounded
  cross-platform research task, with two source-linked query expansion rounds;
  disabled/deferred platforms remain accurately labeled.
* [ ] A real acceptance task for the supplied personal-AI-workbench objective
  records the platform plan, actual platform/query/result counts, at least five
  new contents, three entities, one negative/contradictory evidence item, and
  five independent evidence items when the live sources provide them; any
  shortfall is reported with its real reason.
* [ ] Query and content decisions are fully explainable; no approved query or
  content remains without a terminal reason, and reposts do not inflate
  independent evidence.
* [ ] Coverage completion/stop reasons and single-entity concentration are
  deterministic, persisted, API-visible, and rendered by the frontend.
* [ ] Step usage, compaction metrics, provider-instance/billing semantics,
  budget gates, subscription null-cost semantics, official payg cost, and
  unknown-price semantics are API-visible and tested.
* [ ] Capability-aware fallback and one-pass structured-output degradation are
  implemented and tested without stream continuation or infinite repair.
* [ ] Pause/Resume/Cancel and restart recovery pass targeted failure-injection
  tests; the Worker remains single-concurrency and no Redis/Kafka/Elasticsearch
  is added.
* [ ] Backend pytest (with required coverage), frontend lint/test/build, and
  server shell syntax/tests pass. Production services remain healthy, crawler
  and research queues are empty after validation, and no browser residue is
  left behind.
* [ ] Changes are committed, pushed, deployed through the restricted release
  flow, verified against the target commit, and the final report includes the
  complete requested evidence and rollback cautions.

## Definition of Done

* Database, domain models, repository/service, API, Runtime, Worker,
  frontend, tests, documentation, migration/deployment impact, and production
  validation are updated as one traceable flow.
* All real-platform validation uses low-resource tasks, no comments or
  sub-comments, requested counts stay within the verified small range, and a
  QR/captcha/login action pauses for the user.
* No credentials, cookies, browser state, databases, logs, QR images, crawler
  output, or generated frontend assets are committed.

## Local implementation checkpoint

The database/domain/API/Runtime/frontend path is implemented locally and the
following gates pass before production validation: backend pytest with 392
tests and 86% total coverage, Ruff, Python compilation, frontend lint, 56
frontend tests with 90.05% coverage, frontend production build, server shell
syntax, and restricted release-script tests. The remaining unchecked criteria
are intentionally production-dependent and will only be marked after the
0013 deployment and bounded real-platform acceptance task.

## Technical Approach

Use one forward migration (`0013_cross_platform_research_completion`) with
small normalized tables for coverage plans, entity coverage, query metrics,
content decisions, budget events, step usage, and runtime checkpoints; extend
the existing AI provider/model tables with billing-profile and provider-instance
metadata plus versioned price rows. Keep the existing SQLite repository style
and `BEGIN IMMEDIATE` transitions. Add pure deterministic schedulers,
platform-strategy and context-compaction modules so Runtime orchestration stays
bounded and testable. Extend the existing ResearchToolService contract rather
than introducing more Agent abstractions. Add API response sections and typed
Zod schemas, then render the data in the existing Research page.

The Runtime will plan a per-platform queue, execute one platform/query at a
time through the existing ResearchToolService, checkpoint after every durable
step, and evaluate coverage/marginal yield before scheduling the next branch.
The crawler Worker remains the only browser owner. Model requests continue
through ModelGateway; billing and fallback audit data are recorded at the
gateway boundary.

## Decision (ADR-lite)

**Context**: 8C-1 has durable quality metadata but the next requirements cross
the database, Runtime, AI gateway, Worker, and frontend. Adding more Agent
abstractions would hide the actual coverage/cost/reliability gaps.

**Decision**: Add explicit durable records and pure policy modules at the
existing repository/service boundaries; use one migration and one bounded
Runtime state machine; keep all platform/provider capabilities fail-closed and
report shortfalls instead of fabricating results.

**Consequences**: The migration and API payload grow, but every stop, cost,
coverage, and evidence decision becomes inspectable and restartable. Existing
0012 tasks need legacy-compatible defaults, and real production coverage may
still fall short when a platform requires user login or yields no relevant
content; the report must expose that fact.

## Out of Scope

* Full Discovery Engine, recursive recommendations, creator relationship
  expansion, candidate review queues, feedback memory, multi-Agent runtime,
  MCP, Notion, knowledge graph, long-term unattended monitoring, automatic
  publishing, or automatic user actions.
* Douyin resource recovery, Kuaishou search upstream repair, new credentials,
  QR/captcha completion, root/system/Cloudflare/Nginx/sudoers/network changes.
* Redis, Kafka, Elasticsearch, crawler concurrency above one, automatic
  comments/sub-comments, or synthetic research data.

## Technical Notes

* Relevant specs: `.trellis/spec/backend/research-quality.md`,
  `.trellis/spec/backend/research-runtime-8c.md`,
  `.trellis/spec/backend/ai-model-gateway.md`,
  `.trellis/spec/backend/crawler-platforms.md`,
  `.trellis/spec/backend/database-guidelines.md`,
  `.trellis/spec/frontend/intelligence-workbench.md`,
  `.trellis/spec/frontend/research-center-8c.md`,
  `.trellis/spec/frontend/ai-model-center.md`, and
  `.trellis/spec/operations/server-deployment.md`.
* Baseline production anomaly: `.env` enables six platforms, but 13/16 stored
  research tasks explicitly selected only Bilibili; multi-platform rows stopped
  after Bilibili/XHS because the Runtime consumed its two-crawl round budget
  before reaching the remaining platform targets. This is an intentional
  routing/coverage bug to fix, not a reason to edit platform verification facts.
* External production health currently fails from the Codex observer with an
  OpenSSL `SSL_ERROR_SYSCALL`; this is recorded as an observer issue only and
  must be re-evaluated after helper/Nginx/SNI/local health gates during release.

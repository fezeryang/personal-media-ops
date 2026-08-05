# Phase 8C：跨平台研究、预算与 Runtime 可靠性

> **Status: completed — 2026-08-02.** The implementation, migration, bounded
> real-platform validation, recovery checks, quality gates, and production
> deployment are complete. The supplied live-source acceptance task reached
> the platform/entity/independent-evidence/new-content targets, while its
> negative-evidence target was truthfully recorded as unmet because the
> selected sources did not produce a qualifying negative item; this is a
> coverage shortfall, not a fabricated success. Phase 8C-1 remains archived;
> Discovery Engine work remains deferred to Phase 8D.

Phase 8C extends the Phase 8B Research Runtime without adding another Agent
abstraction. The durable path remains:

```text
SQLite / Alembic 0013
→ ResearchTaskRepository
→ Research API
→ one in-process Research Runtime
→ ModelGateway / ResearchToolService
→ one global crawler Worker
→ normalized library / Findings / frontend trace
```

## 生产平台边界

Research consumes `GET /api/crawler/capabilities` and validates the selected
`search` cell against `MEDIAOPS_ENABLED_PLATFORMS`. The recovery order is
`bili → zhihu → wb → tieba → xhs`; each failure is stored on its own platform
coverage row and does not silently downgrade another platform. `dy` remains
`deferred_resource_constrained`; `ks` search remains
`deferred_upstream_breakage`.

The 8C-1 Bilibili-only result was not caused by the production capability
configuration: production had six configured platforms and five verified
search cells. Existing task snapshots were Bilibili-only, while the previous
Runtime crawl-round logic stopped after its bounded branch budget. 8C now
persists a Coverage Plan and rotates one crawl at a time over the selected
platform snapshot.

## Coverage and query contract

`POST /api/research/tasks` accepts `coverage` and the extended budget fields:

```json
{
  "target_platform_count": 3,
  "target_entity_count": 3,
  "target_negative_evidence_count": 1,
  "max_single_entity_evidence_ratio": 0.6,
  "target_independent_evidence_count": 5,
  "target_new_content_count": 5
}
```

Every query is durable before execution. The canonical lifecycle is:

```text
generated | rejected_generic | rejected_duplicate | rejected_low_relevance
| rejected_low_value | approved_pending | executing | completed
| skipped_budget | skipped_saturation | skipped_low_marginal_value
| superseded | failed | cancelled
```

The legacy 8C-1 aliases remain readable for old tasks. An approved query that
does not run must carry `unexecuted_reason`; no query is left in an unexplained
approved state. Priority combines relevance, specificity, novelty, noise risk,
expected value, entity/platform diversity, negative-evidence bonus, and
estimated resource use. After each round the Runtime records new-content rate,
new-entity count, independent-evidence count, duplicate rate, model tokens,
pay-as-you-go cost, and crawl duration.

Two consecutive low-marginal rounds with no new entity and no negative evidence
stop the branch as `skipped_saturation` or `skipped_low_marginal_value`, using
the Coverage Plan threshold rather than a scattered constant.

## Platform-native evidence strategy

The first deterministic strategy is intentionally different by platform:

| Platform | Evidence emphasis |
| --- | --- |
| Bilibili | demonstrations, tutorials, long-form experience, workflows |
| Zhihu | analysis, demand discussion, product evaluation, counterpoints |
| Weibo | immediate releases, propagation, short-lived discussion, controversy |
| Tieba | real problems, negative experience, long-term feedback, failures |
| Xiaohongshu | usage experience, consumer decisions, scenarios, usability |

The same query is not copied mechanically to every platform. Saturated
entities receive a lower diversity bonus; alternatives, competitors and
negative queries are preferred. Reports must state when evidence is still
concentrated on one entity and must not call that a market-wide trend.
Entity concentration is calculated as the number of unique adopted,
non-repost `content_id` values mentioning the entity divided by the total
unique independent adopted evidence count. A content item mentioning several
entities is counted once for each matching entity, but it does not dilute the
single-entity ratio through a mention-sum denominator.

## Evidence decisions and provenance

Collected content, adopted evidence and rejected content are separate facts.
`research_content_decisions` records `adopted` or `not_adopted`, quality fields,
repost linkage and a reason such as `低相关`, `重复观点`, `内容过短`,
`正文缺失`, `营销内容`, `无实体关联`, `无事实增量`, or `来源质量不足`.

`finding_contents` remains one row per Finding/content pair. Repeated hits merge
in `evidence_occurrences`: independent evidence counts once by normalized
`content_id`, while occurrence count and query/crawler source arrays increase.
Cross-platform repost detection uses normalized title, text hash, URL, author,
publication time and bounded text similarity. A repost is not a second
independent source.

Facts require `direct` evidence. Inferences require a derivation,
`counterevidence_status`, and an explicit counterevidence explanation.
Contradictory evidence uses the `contradictory` role. A negative search that
finds nothing records `counterevidence_status=not_found`; it does not become
“没有缺点” or a positive quality claim.

## Context and usage trace

The Runtime loads summaries first, selects candidate content, loads full text
only through `get_content`, and sends a compact evidence packet to the model.
The packet preserves `content_id`, `source_url`, `platform`, `published_at`,
and `evidence_role`. `runtime_checkpoints` and `research_step_usage` retain
restart provenance and the following bounded steps:

```text
planning, initial_query_generation, query_quality_review,
tool_result_evaluation, entity_extraction, evidence_selection,
finding_generation, coverage_review, final_report
```

Each step stores provider instance, vendor, model, billing mode, input/output/
cached tokens, latency, fallback source/reason and optional cost metadata.
`context.compaction_stats` exposes candidate count, full-content count,
final-evidence count and compressed branches without putting complete history
back into every prompt.

## Billing and resource budget

Billing is modeled as four separate concepts: vendor, provider instance,
billing profile and model. `ai_billing_profiles` supports
`subscription_fixed`, `pay_as_you_go`, `prepaid_balance`, `quota_bundle`,
`relay`, and `unknown`. Provider price versions are scoped to a provider/model
instance and include input, output, cache-read, optional cache-write price,
currency, effective time and source.

MiniMax and GLM subscription calls record tokens, calls and latency but
`estimated_marginal_cost=null`, `estimated_cost_kind=not_applicable`; they are
not shown as zero or as uncosted. DeepSeek official is a separate pay-as-you-go
provider instance and is costed only when a complete price snapshot and token
usage exist. Relay providers never inherit official pricing. Unknown pricing
uses `estimated_cost=null` and `cost_budget_status=unavailable`.

`ResearchBudget` supports:

```text
max_input_tokens, max_output_tokens, max_total_tokens, max_model_calls,
max_crawl_tasks, max_runtime_seconds, max_new_contents, max_payg_amount,
currency, route_policy
```

Subscription routes are constrained by tokens, calls, time and concurrency;
pay-as-you-go routes additionally obey the amount budget. The first route policy
is deterministic: tool calls prefer a tested subscription-capable model,
ordinary analysis may use subscription GLM, quality/final-report work may use
DeepSeek official, and an unverified relay never enters tool routing.

## Fallback and structured output

Fallback is capability-aware. A tool request may move only to a model with
tested tool support; a text-only summary fallback must not be presented as an
equivalent multi-turn tool fallback. Once a stream has emitted content, it
fails instead of transparently continuing on another model. Invocation rows
record original provider/model, failure type, retry count, fallback provider/
model, handoff step and final status.

Structured parsing uses one finite chain:

```text
native structured output → tool schema → strict JSON → one JSON repair → failed
```

No infinite repair loop is allowed for plans, query candidates, entity
extraction, Findings, coverage review or proposed actions.

## Pause, resume, cancel and restart

Pause sets a durable flag. The Runtime stops new model/tool steps and new
crawler submissions while allowing an already-running short request to finish.
Resume claims from the persisted checkpoint; completed steps are not replayed.
Cancel sets `Cancelled`, requests cancellation of an attached crawler when
possible, retains findings/traces/budget events and never auto-resumes.
Transient SQLite `locked`/`busy` errors retry from the same checkpoint. API,
Worker and Runtime restarts reconcile orphan or waiting crawler rows and read
persisted usage/counters instead of resetting budgets.

## Migration and deployment

The forward migration is `0013_cross_platform_research_completion`, from
`0012_research_quality_foundation`. It adds coverage, entity/query metrics,
content decisions, budget events, step usage, checkpoints, provider billing
profiles/price versions and the required compatibility columns. It preserves
existing Research/Finding/Evidence rows and refuses downgrade when 8C data is
present.

Before production migration:

1. Run backend tests with coverage, frontend lint/test/build and shell syntax.
2. Run the reviewed SQLite backup and retain its SHA-256.
3. Dry-run the target commit and review the 0013 migration/downgrade guard.
4. Prepare a pushed local Release Candidate, then deploy with the reviewed
   release script and explicit
   `--release-candidate .release/rc.env --allow-migrations --execute`.
5. Verify Alembic head, `PRAGMA integrity_check`, API/Worker health, zero active
   crawler/research tasks and zero browser residue.

Do not restore or replace the production database automatically. Rollback is a
forward code fix; database restore is an irreversible administrative action.

## Scope exclusions

8C does not implement Discovery Engine traversal, creator relationship
expansion, candidate review queues, feedback memory, multi-Agent, MCP, Notion,
knowledge graph, long-term unattended monitoring, auto-publishing or automatic
user actions.

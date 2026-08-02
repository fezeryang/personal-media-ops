# Research Runtime 8C

## 1. Scope / Trigger

Apply this contract when changing cross-platform Research scheduling, coverage
plans, evidence decisions, Runtime checkpoints, step usage, mixed AI billing,
fallback behavior, or durable Pause / Resume / Cancel controls. This contract
starts at Alembic revision `0013_cross_platform_research_completion` and must
remain compatible with the `0012_research_quality_foundation` data already in
production.

## 2. Signatures

The authenticated Research API exposes task creation/detail and the existing
control endpoints:

```text
POST /api/research/tasks
GET  /api/research/tasks/{task_id}
POST /api/research/tasks/{task_id}/pause
POST /api/research/tasks/{task_id}/resume
POST /api/research/tasks/{task_id}/cancel
```

Task creation accepts `coverage`, `budget`, and `route_policy`. The detail
response includes `coverage`, `platform_coverage`, `entity_coverage`,
`queries`, `content_decisions`, `budget_events`, `step_usage`, and categorized
`consumption`.

The owner AI API exposes billing profiles and provider price versions through
`/api/ai/billing-profiles` and `/api/ai/provider-prices`. Providers carry a
vendor, provider-instance label, billing mode, and tool capability status.

Alembic `0013_cross_platform_research_completion` owns the additional billing,
coverage, query-metrics, content-decision, budget-event, step-usage, and
runtime-checkpoint tables. The Research tool accepts platform, query,
requested count, source-chain fields, task ID, and expected evidence role.

## 3. Contracts

Coverage is durable, not inferred from the final model response. A plan stores
target platform/entity/negative/independent-evidence/new-content counts and a
maximum single-entity evidence ratio. Platform records distinguish planned,
actual, production-verified, deferred, disabled, and failure reasons.

Every query has a lifecycle status and a terminal explanation. Approved work
must become `executing`, `completed`, `failed`, or a specific `skipped_*` /
`superseded` state. Marginal-yield metrics are recorded per round; two
consecutive low-yield rounds with no new entity and no new contradictory
evidence stop the branch using the configured threshold.

Content decisions distinguish collected, new, candidate, adopted, and not
adopted results. Reposts remain visible and preserve query/task provenance but
do not increase independent evidence. Evidence cards always retain
`content_id`, `source_url`, `platform`, `published_at`, and `evidence_role`.
Entity concentration uses unique adopted, non-repost content IDs over the
unique independent evidence denominator. A single content item may match more
than one entity, but entity mention multiplicity must not make a concentrated
study appear diverse.

Detail response projections must explicitly select the fields declared by
their Pydantic response models. Internal coverage row identifiers,
`research_task_id`, platform-set JSON, and audit timestamps must not leak into
an `extra="forbid"` API model; populated legacy and 8C rows must validate the
same as empty rows.

Numeric `research_budget_events.amount` and `estimated_cost` values must be
serialized as nullable decimal strings at the API boundary. SQLite numeric
affinity can return integers or floats even when writers store numeric text;
the frontend contract must not receive those raw values.

Step usage covers planning, query generation/review, tool evaluation, entity
extraction, evidence selection, finding generation, coverage review, and final
report. Each row records provider instance, vendor, model, billing mode,
tokens, latency, and fallback provenance. Context compaction must preserve
traceable evidence cards while reporting candidate, full-load, final, and
compressed counts.

Billing mode is attached to a provider instance and never inherited by model
name or another instance. Subscription usage has null marginal cost and is
shown as not applicable; pay-as-you-go cost is only estimated from a complete
versioned price; unknown or incomplete price remains unavailable, never zero.
Tool routes require a tested tool-capable provider. A fallback may take over
only when its capability matches the step; a streamed response cannot switch
models after content has been emitted. Structured output may degrade once in
the order native schema, tool schema, strict JSON, one repair, explicit fail.

Pause blocks new calls and crawler submissions, Resume uses the checkpoint, and
Cancel prevents new work, requests crawler cancellation, retains history, and
never auto-resumes. Restart recovery must not reset budgets or repeat completed
steps.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Platform is disabled/deferred or search is not production-verified | Do not submit; persist the platform reason |
| Approved query is not run | Transition it to a terminal skipped/superseded state with a reason |
| Entity exceeds concentration threshold | Lower its priority and schedule diversity/counterevidence queries |
| Repost or repeated content | Keep occurrence/provenance; count one independent item |
| Subscription usage | Record tokens/calls and null marginal cost |
| Missing payg price or usage | Set cost status to unavailable, never `0` |
| Tool fallback lacks tested capability | Fail explicitly or use a summary-only fallback |
| Pause/cancel checkpoint | No new model/crawler work after durable control is observed |
| SQLite busy/locked during recovery | Retry safely; do not mark the task terminal from a transient lock |
| Migration has existing 8C rows on downgrade | Refuse downgrade and preserve the database |

## 5. Good / Base / Bad Cases

- Good: a task plans Bilibili, Zhihu, Weibo, Tieba, or XHS according to the
  enabled capability matrix, records each result/failure, and reports actual
  platform and entity coverage.
- Base: an older 8C-1 task has only Bilibili and no new coverage rows; the API
  exposes its historical trajectory without inventing cross-platform results.
- Bad: the Runtime silently stops after two platforms, leaves `approved_pending`
  queries forever, calls DeepSeek as a tool fallback without capability proof,
  or renders subscription usage as zero currency.

## 6. Tests Required

- Migration upgrade from populated `0012`, row preservation, integrity check,
  and fail-closed downgrade.
- Platform planning/strategy, query lifecycle, source-chain persistence,
  marginal stop, entity concentration, negative evidence, repost detection,
  and adoption reasons.
- Step usage/compactor provenance, billing profile/price version, subscription
  null-cost, payg/unknown price, budget gates, fallback capability, and one-pass
  structured-output degradation.
- Pause/Resume/Cancel, API/Worker/Runtime restart, transient SQLite lock,
  timeout/rate-limit/auth/tool/crawler failures, and no duplicate evidence or
  crawler submission.
- Authenticated API and Research page rendering for platform plans, coverage,
  query skip reasons, evidence decisions, billing categories, fallback trace,
  controls, and 390px width.

## 7. Wrong vs Correct

### Wrong

```python
# The old round-robin budget silently makes Bilibili the only real platform.
for platform in platforms[:2]:
    await submit_search(platform, query)
```

### Correct

```python
plan = research.get_coverage_plan(task_id)
for platform in plan.platforms_needing_evidence:
    if not capabilities.can_search_production(platform):
        research.mark_platform_skipped(task_id, platform, "deferred_upstream_breakage")
        continue
    await submit_search(
        platform,
        query,
        research_task_id=task_id,
        expected_evidence_role="direct",
        reason="补足平台覆盖与反向证据",
    )
```

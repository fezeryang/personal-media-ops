# Research Runtime 8D-0

## 1. Scope / Trigger

Apply this contract when changing natural-language Research task creation,
Intent Contract persistence, execution-query planning, information utility,
discovery candidates, research memory, or Intent Alignment Review. This is a
new 8D-0 contract; the archived 8C contract remains historical and must not be
reopened or renamed.

## 2. Signatures

The authenticated Research API exposes the existing task/detail/control
surface plus the 8D-0 intent revision endpoint:

```text
POST /api/research/tasks
GET  /api/research/tasks/{task_id}
POST /api/research/tasks/{task_id}/intent/revise
POST /api/research/tasks/{task_id}/pause
POST /api/research/tasks/{task_id}/resume
POST /api/research/tasks/{task_id}/cancel
```

The runtime boundaries are separate and testable:

```python
build_default_intent(request, platforms) -> ResearchIntentContract
interpret_model_text(request, text, platforms) -> ResearchIntentContract
execution_query_directions(contract) -> list[dict[str, str]]
evaluate_query(..., record_type, query_role, intent_bound) -> QueryQuality
classify_information_utility(content, intent, ...) -> list[InformationUtilityAssessment]
```

Alembic revision `0014_research_intent_and_information_utility` owns:
`research_intents`, `research_intent_versions`,
`research_intent_assumptions`, `research_unknowns`,
`research_alignment_reviews`, `content_research_utilities`,
`research_entity_candidates`, `research_event_candidates`, and
`research_memory_items`. It also extends `research_queries` with
`record_type`, `gate_status`, `query_role`, `decision`, and `intent_id`.

## 3. Contracts

An Intent Contract preserves `original_request`, `original_intent`,
`interpreted_goal`, one stable `primary_intent`, zero or more stable
`secondary_intents`, `subject`, `known_entities`, `known_constraints`,
`unknowns_to_discover`, `time_scope`, `platform_preferences`,
`target_audience`, `evidence_requirements`,
`negative_evidence_requirements`, `exclusions`, `desired_output`,
`success_criteria`, `confidence`, `ambiguities`, `assumptions`, timestamps,
`version`, `intent_source`, and the current hypothesis/revision fields.

The stable intent enum is:
`discovery`, `verification`, `comparison`, `trend_tracking`,
`pain_point_research`, `competitor_scan`, `creator_scan`,
`content_opportunity`, `market_mapping`, `product_opportunity`, and
`monitoring`. Open semantic details live in the JSON fields; scheduling uses
only these stable enum values.

`record_type=user_goal` is an audit record for the user's natural-language
goal. It is accepted unless blank, meaningless, unsafe, or impossible to
convert. It must not be sent to a platform search adapter. Only
`record_type=execution_query` is normalized, deduplicated, scored for
specificity/noise, checked for platform support, and budgeted.

Execution query decisions are `allow`, `transform`, `hold`, or `reject`.
`hold` has a durable status such as `approved_pending`, `skipped_budget`,
`skipped_saturation`, `skipped_low_marginal_value`, or `superseded`.
Every execution query records its `query_role`, such as `seed_discovery`,
`entity_expansion`, `cross_platform_validation`, `counterevidence`,
`competitor_scan`, `trend_probe`, `creator_scan`, or `pain_point_probe`.

Planner output is not trusted as a query list. A malformed or unsupported JSON
object is discarded as planner output and falls back to deterministic
Intent-Contract directions; JSON field names must never become execution
queries. For a modern task, initial directions are transformed with the
selected platform's evidence strategy and platform label before historical
deduplication, so a valid direction is not lost solely because an earlier task
used the unbound base wording.

Information utility is multi-label and explainable. Valid labels are
`core_evidence`, `discovery_seed`, `background_context`, `event_signal`,
`counterevidence`, `memory_update`, `action_trigger`, `noise`, and
`duplicate`. A content item can be a seed and counterevidence at the same
time. Candidate entities remain `candidate_discovery`; they are not silently
added to monitoring.

Intent Alignment Review runs before terminal completion and records
`alignment_score`, covered and missing requirements, scope drift, a
recommended next step, and a review status. A task continues when budget is
available and a material gap remains; otherwise it reaches
`partial_completion` rather than claiming full completion.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Platform crawler fails | Record the platform/query failure as a coverage fact, then reuse the next held execution direction on the next eligible platform; rebind its platform-specific query text and normalized query while retaining old/new values in the execution trace |
| Platform crawler fails and no held/new direction remains | Enter Summarizing/`partial_completion` with an explicit gap; do not convert the platform failure into a generic candidate-rejection failure |
| Planner returns malformed/unsupported JSON | Ignore field names and free-form JSON fragments; use deterministic Intent-Contract directions |
| Historical deduplication removes a modern initial direction | Transform it with platform evidence strategy and platform binding before the gate; preserve the original direction in the plan audit |
| Blank/meaningless user goal | Reject task input with a validation error |
| User goal contains a broad word such as “工具” or “趋势” | Accept and interpret; never reject from a generic-term rule alone |
| Unbound seed execution query | Hold/reject with an Intent Contract binding reason |
| Entity expansion lacks parent query/source content | Reject as invalid expansion |
| Exact execution-query duplicate | Reject or mark duplicate while preserving audit history |
| Budget, cancellation, unsupported platform, or saturated branch | Persist the deterministic terminal/hold reason; do not call the adapter |
| Model response is malformed | Use strict JSON parsing, one bounded repair, then deterministic default intent |
| Intent confidence `< 0.45` | Persist one highest-value clarification question without blocking reasonable defaults elsewhere |
| Intent confidence `0.45–<0.75` | Continue with defaults and expose assumptions in the understanding card |
| Historical 8B/8C task | Create read-only `legacy_migrated` intent; do not re-run or rewrite old findings |
| Content is not final evidence but contains a new entity/fact | Preserve its seed, background, event, or memory utility reason |
| Alignment gap remains with budget | Continue the highest-value missing branch |
| Alignment gap remains without budget | Enter `partial_completion` with explicit missing requirements |
| Populated 8D-0 tables are downgraded | Refuse downgrade to prevent data loss |

## 5. Good / Base / Bad Cases

- Good: “最近有哪些值得关注的个人 AI 工具？” becomes a discovery
  contract with unknown product names, concrete bounded seed directions, and
  evidence plus counterevidence requirements.
- Base: an old task exposes a read-only legacy contract and historical query
  records without executing a new research round.
- Good: a product update with a limitation is retained as an event signal,
  counterevidence, memory update, and possibly core evidence when adopted.
- Bad: put the raw user goal through the execution-query generic-term gate,
  collapse the contract into `research_mode`, or discard a non-adopted item
  that is a useful discovery seed.

Platform crawler failure is a coverage fact, not an automatic Research
failure. The failed platform/query is recorded with its error, and a modern
task first reuses the next held execution direction on the next eligible
platform, rebuilding the platform-specific evidence strategy rather than
carrying the old platform's terms into the new query. If no held or newly valid direction remains, the task converges to
an auditable summary/`partial_completion` with an explicit coverage gap rather
than raising a generic “all research query candidates were rejected” failure.

## 6. Tests Required

- Intent unit tests assert primary/secondary intents, unknowns, time defaults,
  target audience, confidence bands, one-question clarification, model JSON
  repair/default behavior, and concrete query roles.
- Query-quality tests assert user-goal acceptance, intent-bound seed rules,
  exact duplicate/budget/platform gates, and hold/reject reasons.
- Utility tests assert multi-label counterevidence, discovery seed, event,
  memory, action, noise, duplicate, marketing, and adopted evidence paths.
- Migration tests upgrade a populated `0013` database, preserve tasks,
  findings, and audit queries, mark historical goals, and pass `integrity_check`.
- Repository/runtime tests assert versions, assumptions, unknowns, utility
  rows, candidates, events, memory, alignment review, partial completion, and
  no legacy re-execution.
- API/frontend tests assert the understanding card, revision boundary,
  detail schemas, utility counts, candidate/event cards, alignment review, and
  390px layout without synthetic values.

## 7. Wrong vs Correct

### Wrong

```python
if any(term in user_goal for term in GENERIC_TERMS):
    return reject("query is too generic")
```

### Correct

```python
intent = interpret_intent(user_goal)
directions = execution_query_directions(intent)
for direction in directions:
    evaluate_query(
        direction["query"],
        record_type="execution_query",
        query_role=direction["query_role"],
        intent_bound=True,
    )
```

# Phase 8D-0：研究意图理解与信息价值转化

Phase 8D-0 keeps the completed 8C runtime and adds a separate semantic layer:

```text
user goal
→ Intent Interpreter
→ Research Intent Contract
→ Research Planner
→ execution-query directions
→ library/crawler evidence
→ information utility
→ findings, discovery seeds, events, memory and actions
→ Intent Alignment Review
```

The user supplies a natural-language research goal. The user does not need to
know a product name, creator, competitor or platform-specific keyword first.
The original request is persisted as an immutable contract field; later
interpretations and owner revisions are versioned rather than silently
replacing it.

## Intent Contract

`research_intents` stores the current contract and
`research_intent_versions` stores every persisted version. The contract
contains:

```text
original_request, original_intent, interpreted_goal,
primary_intent, secondary_intents, subject,
known_entities, known_constraints, unknowns_to_discover,
time_scope, platform_preferences, target_audience,
evidence_requirements, negative_evidence_requirements,
exclusions, desired_output, success_criteria,
confidence, ambiguities, assumptions,
current_research_hypothesis, intent_revisions,
intent_source, clarification_question, version, timestamps
```

Stable scheduling enums include `discovery`, `verification`, `comparison`,
`trend_tracking`, `pain_point_research`, `competitor_scan`, `creator_scan`,
`content_opportunity`, `market_mapping`, `product_opportunity`, and
`monitoring`. Multiple secondary intents are retained. Deterministic defaults
cover time ranges, known entities and unknowns when the model is unavailable.
Low confidence produces one high-value clarification question, but a task can
still be created with the default contract.

## Goal/query boundary

`research_queries.record_type` separates `user_goal` from
`execution_query`. A user goal is retained for audit and has
`gate_status=not_applicable`; it is never sent to a platform search. Only
execution queries enter normalization, duplicate, specificity, noise, budget
and marginal-value gates. Query decisions are `allow`, `transform`, `hold` or
`reject`, and query roles include seed discovery, entity expansion,
cross-platform validation, counterevidence, competitor, trend, creator and
pain-point probes.

Historical 8B/8C tasks receive a read-only `legacy_migrated` intent projection
and are not re-planned. Historical goal rows are marked `user_goal` while
their audit history remains intact.

## Information utility

`content_research_utilities` is multi-label. A content item may be core
evidence, a discovery seed, background context, an event signal,
counterevidence, a memory update or an action trigger. Noise and duplicate
are explicit classifications, not an implicit “not in report” bucket.

`research_entity_candidates` and `research_event_candidates` retain source
content IDs and remain candidate records; they do not automatically create
monitoring subscriptions. `research_memory_items` stores confirmed facts,
inferences and observed entity updates with source query/content/finding
links.

Before summarization, `research_alignment_reviews` checks original intent,
unknowns, desired output, evidence gaps and scope drift. A task can remain in
research when budget allows, or finish as `partial_completion` when important
requirements remain unresolved.

## API and UI

The existing task endpoints now return the contract, plan, query roles,
utility rows, candidate entities, candidate events, memory items and the
latest alignment review. A task in `Draft` can revise its understanding via:

```text
POST /api/research/tasks/{task_id}/intent/revise
{"request":"..."}
```

The frontend creates from a natural-language goal, presents the research
understanding card before execution, and exposes assumptions, confidence,
unknowns, evidence/negative-evidence requirements, query roles, information
value counts, discovery candidates, event candidates and alignment status.

## Migration and rollout

Forward migration `0014_research_intent_and_information_utility` upgrades from
`0013_cross_platform_research_completion`. It preserves existing tasks,
findings, evidence, query history and JSONL. Before applying it to production,
back up SQLite, record the backup SHA-256, run the local quality gates, apply
Alembic with the reviewed migration gate, then verify the new head and
`PRAGMA integrity_check = ok`. The migration refuses a destructive downgrade
once 8D-0 rows exist.

8D-0 deliberately does not implement a complete Discovery Engine, automatic
traversal, knowledge graph, multi-agent orchestration, unattended monitoring,
feedback learning, Notion synchronization or automatic user actions.

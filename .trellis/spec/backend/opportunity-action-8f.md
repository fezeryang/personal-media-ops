# Opportunity & Action 8F

Apply this contract when changing Opportunity Signals, Opportunity Cards,
Validation Plans, owner-approved Actions, Outcomes, or outcome-derived Memory.

## Boundary

8F extends the existing Research/Discovery/Monitoring/Memory runtime. It does
not create a second research engine, a graph database, a CRM, a project
manager, or an automatic publishing path. `OpportunityRepository` references
existing owner-scoped source objects; it does not copy their facts into a new
knowledge graph.

## Evidence contract

An Opportunity source must retain `source_type`, `source_id`, optional
`evidence_id`/`content_id`/`finding_id`, role (`core`, `supporting`,
`counterevidence`, `background`), evidence kind (`direct`, `inference`,
`estimate`, `unknown`), source platform, independent group, and repost flag.
Single-source and repost-only input returns `needs_more_evidence`; it must not
be promoted by a score or by user feedback alone. A repeat analysis of the same
origin reuses the existing candidate instead of duplicating it.

## History and ownership

`opportunity_versions`, `opportunity_scores`, `validation_results`, Actions,
Outcomes, and `research_memory_items` are append-oriented. Validation changes
the Opportunity version and readiness; it does not overwrite earlier history.
Outcome Memory rows may have a null `research_task_id`, but must point back to
the Opportunity, Action, and Outcome. All API writes use `require_owner_session`
and therefore Owner Session plus CSRF/origin checks.

## Validation and Actions

Creating a Validation Plan is allowed only for a review-ready or more mature
Opportunity. The follow-up Research Task is independent and budgeted, receives
a new Intent Contract, and is created only by an explicit owner request.
Actions start at `proposed`; transitions are `proposed -> approved ->
in_progress -> completed` (or `abandoned`). An Outcome is rejected until the
Action is completed. External publishing, outreach, payment, third-party form
submission, and automatic business execution remain forbidden.

## Test obligations

Backend tests cover single-source rejection, repost/independence handling,
response-model validation, owner/CSRF boundaries, version history, follow-up
Research, Action transitions, Outcome -> Memory, and Research Space item
ownership. `tests/test_stage8f_opportunity.py` is the reference end-to-end
fixture. Do not use production data or synthetic production results in these
tests.

# Stage 8F Opportunity & Action

## Goal

Extend the existing Personal Media Ops research workbench so evidence from
Research, Discovery, Monitoring, and Memory can become an evidence-bound
Opportunity, a minimal Validation Plan, an owner-approved Action, and a
recorded Outcome that can update long-term memory. The feature must remain a
single-owner intelligence workbench, not a CRM, project manager, content
calendar, or automatic publishing system.

## What I already know

* Stage 8E is archived as `completed_with_data_limitation`; production runtime
  is `3faffc4`, with Prompt `v1 active / v2 candidate`.
* Existing foundations include Research Runtime, Findings/Evidence, Discovery
  Candidates/Feedback, Research Spaces, Memory, Monitoring Missions and the
  Prompt Registry.
* Existing repository patterns use SQLite repositories with short-lived
  connections, parameterized SQL, Alembic migrations, Pydantic `extra=forbid`
  boundaries, Owner Session + CSRF for writes, and Zod validation in the UI.
* Existing frontend navigation already has the canonical seven product areas;
  8F should enter primarily through AI工作台、发现收件箱和研究空间.
* Production data must not be mutated for a synthetic opportunity, change,
  notification, validation result, action, or outcome.

## Requirements

### Opportunity Intelligence

* Add a traceable Signal layer with the requested signal types, source/evidence
  IDs, platform/source/time, and Research/Discovery/Monitoring origin.
* Add four Opportunity types: `product_opportunity`, `business_opportunity`,
  `content_opportunity`, and `research_opportunity`.
* Keep Opportunity separate from Discovery Candidate. Support explicit
  materialization from evidence/candidates, but allow the correct result
  `no_opportunity_identified`.
* Persist Opportunity lifecycle, version history, readiness, transparent
  multi-dimensional scores, explanation, supporting/counter/background
  evidence, unknowns, and related Research/Monitoring/Space objects.
* Support owner feedback without equating acceptance with validation.

### Evidence and safety

* Every high-confidence signal/opportunity source must be traceable to an
  existing evidence/content/finding/change/candidate or an owner-selected
  object. A single marketing/repost source cannot become strong independent
  evidence.
* Preserve direct/inference/estimate/unknown labels and counterevidence.
* Use transparent deterministic scoring; user relevance only comes from
  explicit research goals, spaces, monitoring missions, or feedback.
* Never infer market size, guaranteed revenue, demand, or real-world outcomes.

### Validation and follow-up Research

* Support Validation Plan fields for hypothesis, target user, assumptions,
  unknowns, questions, evidence needed, cheapest test, success/failure
  criteria, effort, risk, and next decision.
* Owner confirmation is required before creating a follow-up Research Task.
  The follow-up has a new intent contract and bounded independent budget while
  retaining source Opportunity/Evidence references.
* Support validation results `supported`, `partially_supported`,
  `not_supported`, and `inconclusive`, with traceable evidence and history.

### Content Opportunity

* Use `opportunity.type=content_opportunity`; distinguish content gaps from
  popularity or unsupported "hot topic" claims.
* Show audience, user question, gap, evidence, counterevidence, saturation
  qualification, differentiation, timeliness, risk, and up to three evidence-
  bound angles. Do not publish automatically.

### Action and Outcome

* Add lightweight Actions with types `research`, `validate`, `prototype`,
  `interview`, `compare`, `write`, `review`, `monitor`, `manual_other` and
  statuses `proposed`, `approved`, `in_progress`, `completed`, `abandoned`.
* AI may propose; Owner must approve before a real-world action starts.
* Record Outcome fields including what happened, result, evidence, optional
  metrics, lesson, next step, and optional manually entered content metrics.
* Convert an Outcome into a traceable, historical Memory update using the
  existing Memory concept; never silently overwrite an older judgment.

### Product experience

* AI工作台 shows a small ranked set of opportunities, validation-in-progress,
  pending discoveries, important changes, and next-step suggestions; do not
  show crawler/token/technical dashboards on the first screen.
* Discovery Inbox supports upgrading a candidate to an Opportunity Candidate
  and displays opportunity source/type/readiness without becoming a second
  inbox.
* Research Space detail gains compact tabs/sections for Opportunities and
  Actions, reusing typed space items.
* Add an Opportunity Card/detail view with sticky summary and tabs for
  overview, evidence, validation, related research, actions/outcomes, and
  technical details.
* Provide meaningful empty, evidence-insufficient, counterevidence, pending,
  and failure states at 1440×900, 1280×720, and 390×844.

### Eval and operations

* Reuse the 8E Eval infrastructure and add 8F cases for strong multi-source
  pain, single marketing source, reposts, insufficient evidence, high
  competition, novel/weak demand, counterevidence, and content gap.
* Instrument evidence coverage, source independence, counterevidence,
  conversion, validation completion, feedback, follow-up, and action metrics;
  use `not_instrumented` where real data is unavailable.
* Add only the necessary Prompt Registry roles: Opportunity Analyst,
  Validation Planner, and Action Assistant.
* Deploy only after local implementation, automated tests/API integration,
  local visual checks, fixed RC push, production smoke, and bounded real
  acceptance. No 8G/8H is planned.

## Acceptance Criteria

* [ ] Alembic migration upgrades blank and populated databases and preserves
      existing 8E data; runtime head is synchronized.
* [ ] Backend APIs, repositories, services, and tests cover Signal,
      Opportunity, Evidence Pack, scoring/readiness, feedback, validation,
      follow-up research, content opportunities, actions, outcomes, and memory
      history with owner/CSRF boundaries.
* [ ] Frontend API schemas, pages, tabs, actions, loading/error/empty states,
      local fixtures, and responsive checks cover the complete loop.
* [ ] Existing Discovery/Research/Monitoring behavior remains compatible;
      no second Runtime or legacy first-class navigation is introduced.
* [ ] 8F Eval cases and recorded fixtures prove false-positive suppression and
      transparent `not_instrumented` handling.
* [ ] Local gate, backend tests, frontend lint/tests/build, and visual checks
      pass before release preparation.
* [ ] Production smoke and real business acceptance report either a real
      evidence-bound Opportunity or `no_opportunity_identified`; no synthetic
      validation/action/outcome is written.
* [ ] Stage report and Notion update document all 41 requested items and the
      final eight status dimensions; task is archived without creating 8G/8H.

## Definition of Done

* Tests cover new repository state transitions, API contracts, security, and
  cross-layer data flow.
* Frontend uses typed schemas and local fixture data for every required state.
* Release manifest records exact commit, gate, visual evidence, migration,
  backup, rollback, and previous production commit.
* Production remains healthy with no active crawler/research/monitoring leak.
* Remaining real-data or platform limitations are explicitly reported rather
  than converted into green claims.

## Out of Scope

* Automatic publishing, outreach, email, payments, ads, third-party forms,
  account registration, contracts, investments, or external push.
* CRM, sales pipeline, project management, Kanban, Sprint, multi-user owners,
  financial model, social analytics integration, MCP, Notion sync, graph
  database, open-ended multi-agent orchestration, 8G, and 8H.
* Automatic activation of Prompt versions or automatic long-running research.

## Technical Notes

* New persistence should use one forward Alembic revision after
  `0017_stage_8e`, likely with `opportunity_signals`, `opportunities`,
  `opportunity_sources`, `opportunity_scores`, `opportunity_feedback`,
  `validation_plans`, `validation_results`, `actions`, and `action_outcomes`.
  Reuse existing `research_spaces` typed items and add only the minimum allowed
  item types/foreign-key validation.
* Reuse existing `research_memory_items` through a traceable outcome-memory
  relation or an additive source reference; do not create a second generic
  memory store.
* The first implementation may use deterministic evidence aggregation and
  bounded prompt-role contracts; it must not require live model access for
  local fixtures or Recorded Eval.
* Relevant code paths: `backend/app/repositories/discovery.py`,
  `backend/app/repositories/monitoring.py`, `backend/app/repositories/research.py`,
  `backend/app/services/ai/prompt_registry.py`, `backend/app/api/research.py`,
  `frontend/src/pages/overview-page.tsx`,
  `frontend/src/pages/discovery-inbox-page.tsx`, and
  `frontend/src/pages/research-spaces-page.tsx`.

## Research References

* [`research/8f-architecture.md`](research/8f-architecture.md) — repository
  inspection and convergence decisions for extending the existing Runtime.

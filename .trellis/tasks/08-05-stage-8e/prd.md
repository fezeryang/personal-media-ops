# Stage 8E — AI Behavior System and Proactive Monitoring

## Goal

Deliver the complete 8E product loop in one continuous release:

```text
user monitoring goal → confirmed Monitoring Mission → bounded scheduled/manual run
→ memory/baseline comparison → evidence-bound meaningful change → event update
→ attention decision → Discovery Inbox + in-app notification → feedback/memory update
```

The implementation must extend the existing Research Runtime, Model Gateway,
Evidence/Finding/Entity/Event/Memory, Discovery Inbox, and single-concurrency
Worker. It must not create a second research runtime or restore legacy
subscriptions/creator-watch as primary product surfaces.

## Scope

1. Establish a fixed, answer-independent AI Eval Dataset, recorded-task replay,
   metric ledger, baseline report, Product Constitution, role/tool contracts,
   Prompt Registry with active/candidate/rollback versions, and bounded admin
   activation/rollback APIs.
2. Implement a tiered Context Builder and wire the existing Context Compactor
   into real Runtime model calls. Preserve evidence/content IDs, source/time,
   fact-vs-inference labels, unresolved questions, reverse evidence, and query
   lineage. Add query semantic-drift checks, early stopping, and at most one
   bounded Alignment Review research backflow.
3. Add the owner-confirmed Monitoring Mission model and API. Support topic,
   entity, creator, event, research question, and query targets; manual,
   daily, weekly, and bounded custom schedules; mission/run/platform state
   separation; per-run/daily budgets, locks, backoff, pause/resume/archive,
   missed-run recovery, and reuse of the existing crawler queue/Worker.
4. Add baseline creation, change classifications, source independence/repost
   handling, event aggregation, reversible evidence-bound Memory Updates, and
   no-change/duplicate/cooldown suppression.
5. Add attention levels and owner-scoped in-app notifications. Monitoring
   changes enter the existing Discovery Inbox with `source_type=monitoring`;
   raw run/tool detail remains on the mission.
6. Add canonical Monitoring Missions navigation, two-step creation/understanding
   card, tabbed mission detail, run/change/baseline views, AI Workbench change
   summary, prompt read-only/admin view, responsive states, and tests at
   1440×900, 1280×720, and 390×844.

## Product and safety boundaries

- Monitoring is never created by AI without explicit owner confirmation.
- No automatic scope expansion, publishing, commercial action, external
  notifications, MCP/Notion sync, graph database, Redis/Kafka/Celery cluster,
  or minute-level schedules.
- Facts require evidence IDs; inferences are labelled; missing evidence stays
  unknown. Reposts do not count as independent evidence.
- Search verification never implies detail/creator/comment verification.
- Platform/login limitations remain explicit (`blocked_by_platform`) and are
  not replaced with synthetic data.
- Prompt activation/rollback requires Owner Session, Origin, CSRF, and an
  explicit user operation. Model code never self-activates a prompt.
- Existing legacy subscription/creator-watch rows are preserved; reliable
  records may be mapped as `legacy_imported`, while uncertain rows remain
  read-only archive data.

## Cross-layer contracts

Database → repository → service/runtime → authenticated API/Pydantic models →
Worker/scheduler → typed frontend API/Zod → pages/hooks → tests and deployment
must preserve nulls, UTC timestamps, owner scope, IDs, evidence lineage, and
explicit failure states. Schema changes use a forward Alembic migration and
existing-data/integrity tests. Production startup remains fail-closed at the
current migration head.

Minimum APIs include `/api/monitoring/missions`, mission detail/control/run,
mission runs/changes/baseline, `/api/notifications`, `/api/ai/prompts`, and
`/api/ai/evals`, plus the existing Discovery Inbox integration. Exact response
models must reject undeclared internal fields.

## Acceptance criteria

- Fixed Eval Dataset covers exploration, pain points, comparison, trends,
  verification, creator/product/event monitoring, negative feedback,
  opportunity signals, insufficient evidence, and unavailable platforms;
  baseline and candidate comparisons are recorded without fabricated scores.
- Context tiers, compaction provenance, drift/early-stop decisions, and one
  bounded alignment backflow are visible in tests and Runtime trace.
- Prompt versions, role/tool contracts, active/candidate selection, and safe
  rollback are persisted and covered by auth/CSRF/API tests.
- A confirmed mission can create a first baseline, run once, return an honest
  meaningful change or `no_meaningful_change`, aggregate updates, suppress
  duplicates, and update the existing Inbox/notification surfaces.
- Pause/resume, lock exclusion, bounded schedule, backoff, platform failure,
  and resource budget behavior are deterministic and tested.
- Desktop/mobile UI has no horizontal overflow; empty, failure, login-limited,
  running, changed, and no-change states are visible and honest.
- Local gate, backend tests, frontend lint/test/build, visual evidence,
  Release Candidate push, deployment, production smoke, and small real
  business validation are completed before archive. Platform captcha/QR may
  remain `completed_with_platform_limitation` only for the affected platform.

## Out of scope

8F opportunity/action cards and auto-verification/publishing, external pushes,
complex multi-agent orchestration, full knowledge graph, collaboration, MCP,
Notion synchronization, and future 8G/8H planning.

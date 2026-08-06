# Monitoring Mission and AI Governance 8E

## 1. Scope / Trigger

This contract applies to the Stage 8E cross-layer flow for AI governance,
Monitoring Missions, baseline comparison, change delivery, and in-product
notifications. It is triggered by changes to migration `0017_stage_8e`, the
`/api/monitoring`, `/api/notifications`, or `/api/ai/prompts` and
`/api/ai/evals` routes, the existing Research Runtime bridge, or the frontend
monitoring views.

The mission service is not a second crawler or research runtime. A mission
with platforms creates a bounded existing `research_tasks` row and stores its
ID in `monitoring_runs.research_task_id`; the existing single-concurrency
Worker remains authoritative for platform execution.

## 2. Signatures

### API

- `GET/POST /api/monitoring/missions`
- `GET/PATCH /api/monitoring/missions/{id}`
- `POST /api/monitoring/missions/{id}/confirm`
- `POST /api/monitoring/missions/{id}/run`
- `POST /api/monitoring/missions/{id}/pause`
- `POST /api/monitoring/missions/{id}/resume`
- `POST /api/monitoring/missions/{id}/archive`
- `GET /api/monitoring/missions/{id}/runs`
- `GET /api/monitoring/missions/{id}/changes`
- `GET /api/monitoring/missions/{id}/baseline`
- `GET /api/notifications`
- `POST /api/notifications/{id}/read|defer|ignore`
- `GET /api/ai/prompts`, `GET /api/ai/evals`
- `POST /api/ai/prompts/{key}/activate|rollback`

### Database

Migration `0017_stage_8e` adds Prompt Registry/Eval tables, monitoring
missions, targets, runs, run queries, baselines, changes, change sources,
memory updates, notifications, and four governance columns on existing
invocations plus query lineage columns on existing research queries.

### Service

`MonitoringService.run_once(owner_id, mission_id, trigger)` claims one run,
creates a baseline on first execution, and either compares local library
content or links an existing Research Task. `reconcile_linked_runs()` is
called by the existing Worker and persists terminal changes, memory updates,
and notifications. A linked Research Task in `AwaitingReview` is already
result-ready for monitoring reconciliation; the Research Center may still
wait for Owner review before changing that task to `Done`, but the monitoring
run must not remain `running` behind that separate UI workflow.

When the bridge creates a Research Task, it must persist the deterministic
default Intent Contract before waking the Runtime. This keeps a broad
monitoring goal on the modern intent/planner path; otherwise the Runtime
mistakes the task for a legacy task and can reject it for lacking three model
generated terms before its deterministic execution directions are available.
The deterministic directions must include at least three bounded seeds for a
wide negative-feedback goal so the monitoring run does not depend on the model
inventing enough planner terms.

## 3. Contracts

### Request/response

- Mission creation starts as `draft`; only an explicit Owner-confirmed action
  makes it `active`.
- Mission lifecycle states are `draft`, `active`, `paused`, `running`,
  `waiting_platform`, `waiting_login`, `completed_run`, `degraded`, `failed`,
  and `archived`. Run status is stored separately.
- A first run reports `baseline_created` and does not call all baseline
  content a new change.
- Changes contain type, fingerprint, explanation, first/latest timestamps,
  evidence/source counts, independent-source and repost counts, attention
  level, and unresolved questions.
- `monitoring` discovery items use the existing Discovery Inbox response
  contract; raw queries/tool traces remain in Mission detail.
- Eval cases have no golden answer. Missing measurement is the literal
  `not_instrumented`, never an estimated percentage.
- Every Model Gateway invocation records `prompt_key`, `prompt_version`,
  `context_version`, and `tool_contract_version`.

### Environment and resources

No new queue, cache, database, or browser pool is permitted. SQLite locking,
the existing Worker, its one-browser invariant, and bounded mission budgets
are required. Platform login/captcha remains an explicit `waiting_login` or
`blocked_by_platform` result.

## 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Create without a non-empty goal | Reject with the normal Pydantic/API validation error. |
| Run a draft mission | Reject; require explicit confirmation first. |
| Run a paused/archived mission | Reject and leave the mission unchanged. |
| Concurrent run claim | SQLite `BEGIN IMMEDIATE` returns the existing active run; never create a duplicate. |
| Platform task waiting for login | Keep mission durable; set run/mission waiting state and do not synthesize changes. |
| Scheduled failure | Record run failure/backoff and keep the mission schedulable with bounded exponential backoff. |
| Mission list response | Return only `MonitoringMissionSummary` fields; detail-only targets, rules, failure counters, and last error must not leak into the summary response because API models use `extra="forbid"`. |
| Broad negative-feedback mission | Provide complaint, counterevidence, and replacement-need directions before planning; a short model response must not degrade a valid mission for lacking three terms. |
| Same fingerprint or repost in a later run | Merge/deduplicate; do not create a second notification. |
| Low-confidence or no meaningful change | Store the comparison when useful, suppress notification according to attention policy. |
| Prompt activation/rollback without Owner Session or CSRF | Reject before mutation. AI/runtime code cannot activate versions. |
| Downgrade with any Stage 8E row | Refuse downgrade; backup and explicit data review are required. |

## 5. Good / Base / Bad Cases

- Good: confirm a mission, create its baseline, bridge a platform run through
  Research Runtime, reconcile new evidence, merge reposts, and expose one
  Inbox item plus one notification.
- Base: run a library-only mission with no meaningful difference; return
  `no_meaningful_change` and do not notify.
- Bad: treat every fetched row as a new change, count syndicated copies as
  independent sources, or create a long-lived mission from a legacy
  subscription without user confirmation.

## 6. Tests Required

- Migration test upgrades a blank database through `0017_stage_8e` and checks
  the head and required tables.
- Domain tests cover first baseline, change types, independent source/repost
  counts, event fingerprint merging, memory update fields, notification
  deduplication, lock, pause/resume, and scheduled backoff.
- API tests cover Owner/CSRF, two-step confirmation, CRUD, linked Research
  Task reconciliation in both `Done` and result-ready `AwaitingReview` states
  (including the initial Intent Contract), prompt listing/eval replay,
  activation and rollback.
- Full backend regression and frontend lint/test/build are release gates.

## 7. Wrong vs Correct

### Wrong

```python
for item in fetched_items:
    notify_user("New information", item)
```

### Correct

```python
comparison = compare_baseline(baseline, fetched_items)
persist_change(comparison)
if should_notify(comparison) and not already_notified(comparison.fingerprint):
    create_notification(comparison)
```

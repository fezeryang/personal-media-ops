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
- Recorded Eval replay uses the fixed server-side fixture only; it is a
  governance comparison artifact, not product evidence or a live research
  result. A zero rate is meaningful data when the metric is a rate where zero
  is the desired outcome (for example, scope drift or duplicate rate).

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

## 8. Candidate Prompt and Recorded Eval Replay

### 1. Scope / Trigger

This contract applies when adding or changing Prompt Registry candidates or
the bounded offline Eval replay path. It prevents a candidate review action
from becoming a live model call, crawler run, or automatic Prompt activation.

### 2. Signatures

- `POST /api/ai/evals/replay`
- `AIRepository.replay_recorded_fixture(prompt_key, prompt_version)`
- `candidate_prompt_specs()` returns the intentionally bounded candidate set.

### 3. Contracts

- Request JSON is exactly `{ "prompt_key": string, "prompt_version": string }`.
  The key is lowercase `a-z0-9_`; the version is bounded to
  `A-Za-z0-9._-`.
- The endpoint returns `run_id`, `prompt_key`, `prompt_version`,
  `context_version`, `recorded_task_id`, `case_count`, and `status_counts`.
- The fixed fixture uses `recorded_task_id=stage-8e-recorded-fixture` and
  `context_version=ctx-v1`; it evaluates every fixed case, instruments the
  two recorded cases, and leaves the others `not_instrumented`.
- The endpoint requires Owner Session and CSRF. It writes Eval run/result
  rows only; it never fetches a platform or calls a model.
- `intent_interpreter:v2` is seeded as `candidate` during governance-default
  initialization. Initialization must not re-add it as a candidate after an
  explicit activation; activation and rollback remain user actions.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Anonymous or missing Owner Session | Reject before repository access. |
| Missing/invalid CSRF | Return the normal `403` CSRF error and do not write Eval rows. |
| Unknown Prompt key/version | Return `404`; do not create a run. |
| Prompt status not `active` or `candidate` | Return `409`; do not create a run. |
| Missing fixture metric | Store `not_instrumented`; never infer a ratio. |
| Zero scope drift, duplicate rate, or error-inference rate | Treat as a valid zero, not a failure. |
| Zero intent consistency or fact-evidence binding | Mark that case `failed`. |

### 5. Good / Base / Bad Cases

- Good: run the fixed fixture for active v1 and candidate v2, compare at
  least two instrumented cases, and keep production active v1 until an Owner
  explicitly activates a quality-approved candidate.
- Base: replay produces passed results for the two fixture cases and
  `not_instrumented` for the remaining fixed dataset without claiming live
  research quality.
- Bad: accept a recorded response from the request body, re-crawl a platform
  during replay, or treat every zero-valued metric as a failed case.

### 6. Tests Required

- Repository/API test asserts replay writes one completed run with all fixed
  cases, at least two passed results, and no live research task.
- API test asserts missing/invalid CSRF returns `403`.
- Foundation test asserts valid zero drift/error rates classify as passed and
  missing metrics remain `not_instrumented`.
- Governance test asserts the candidate is present before explicit activation
  and is not automatically reactivated afterward.

### 7. Wrong vs Correct

#### Wrong

```python
response = request.json()["recorded_response"]
return run_model_or_crawler(response)
```

#### Correct

```python
return repository.replay_recorded_fixture(
    prompt_key=payload.prompt_key,
    prompt_version=payload.prompt_version,
)
```

# Research detail budget-event response format

## Goal

Fix the authenticated Research detail page's second data-loading failure. The
HTTP 500 caused by entity coverage has been removed, but the same production
payload is rejected by the frontend schema because `budget_events[].amount` is
serialized as a JSON number while the frontend contract requires a string.
Normalize this API boundary without changing stored billing history or
weakening the frontend validation contract.

## What I already know

* A production reconstruction of both supplied tasks
  `0fe13920-34b8-48ee-971b-36bf42ba0462` and
  `fdf25155-4e10-493e-884b-a40e071b0c68` shows integer budget-event amounts.
* The frontend `budgetEventSchema` expects `amount: z.string().nullable()` and
  `estimated_cost: z.string().nullable()`.
* SQLite numeric affinity returns integer/float values even when the writer
  stores numeric strings; the API currently exposes the raw SQLite values from
  `research_budget_events`.
* The repository already has `_decimal()` for stable nullable numeric-string
  serialization and the database must not be rewritten.

## Requirements

* Normalize `budget_events.amount` and `budget_events.estimated_cost` at the
  backend API projection boundary using the existing decimal serializer.
* Preserve null as null and preserve non-negative numeric precision.
* Add an authenticated Research detail regression test with a numeric budget
  event, asserting HTTP 200 and string JSON values.
* Keep the frontend schema strict and unchanged; do not add a permissive parse
  that hides future API contract drift.
* Deploy without a migration and verify both real task detail payloads through
  the production response model and frontend-compatible field types.

## Acceptance Criteria

* [ ] Numeric `amount` and `estimated_cost` serialize as strings in the detail
  response; null values remain null.
* [ ] Both supplied production task shapes pass the frontend-compatible API
  contract check.
* [ ] Backend and frontend quality gates pass.
* [ ] Production API/Worker remain healthy; no research, crawler, browser, or
  database rows are modified.

## Definition of Done

* Root cause and response boundary are documented.
* Regression test passes locally and remotely.
* Code is committed, pushed, deployed, and verified.
* The unrelated `08-02-ux` planning task and pre-existing `CLAUDE.md` remain
  untouched.

## Out of Scope

* Changing `frontend/src/api/research.ts` schemas.
* Rewriting historical budget events or changing billing semantics.
* Database migrations, database restore, crawler changes, or UX redesign.

## Technical Notes

* Projection: `backend/app/repositories/research.py`.
* API route/model: `backend/app/api/research.py` and
  `backend/app/models/research.py`.
* Frontend contract: `frontend/src/api/research.ts`.
* Relevant specs: `.trellis/spec/backend/research-runtime-8c.md`,
  `.trellis/spec/backend/error-handling.md`, and
  `.trellis/spec/frontend/research-center-8c.md`.

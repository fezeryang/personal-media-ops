# Research task detail HTTP 500 fix

## Goal

Restore the authenticated Research task detail page for Phase 8C tasks. A
request for the supplied AI research task currently returns HTTP 500, so the
frontend cannot render coverage, entities, evidence, budget, or runtime trace
data. Fix the backend response contract without changing stored research
results or weakening the frontend's typed validation.

## What I already know

* The affected task is `0fe13920-34b8-48ee-971b-36bf42ba0462`; the related
  task `fdf25155-4e10-493e-884b-a40e071b0c68` fails in the same way.
* Production is running commit `d7a530aa673c90cb826f631e88217e46e681035f`
  with API and Worker active and database revision
  `0013_cross_platform_research_completion`.
* The frontend requests `/api/research/tasks/{task_id}` and displays the
  server error directly; no mock fallback is involved.
* Production repository reconstruction of the exact endpoint response shows
  `ResearchTaskDetail` validation fails on every populated `entity_coverage`
  item because the repository returns database bookkeeping fields (`id`,
  `research_task_id`, `created_at`, `updated_at`) while the Pydantic response
  model has `extra="forbid"` and intentionally exposes only the stable UI
  fields.
* The same mismatch affects both supplied research tasks; no database repair
  is required.

## Requirements

* Make the repository/API boundary return exactly the fields declared by
  `ResearchEntityCoverage`, preserving all user-visible entity counts and
  concentration data.
* Add a regression test that loads populated 8C entity coverage through the
  actual Research detail response model and proves both supplied task shapes
  are compatible.
* Audit the other populated 8C detail sections for the same database-row
  leakage and cover any discovered response-contract mismatch in tests.
* Preserve authenticated access, HTTP error semantics, existing database rows,
  and frontend behavior. Do not modify production data directly.
* Deploy through the reviewed release flow and verify the exact task detail
  endpoint returns a valid response after activation.

## Acceptance Criteria

* [ ] `ResearchTaskDetail.model_validate(_detail(repository.get(...)))` passes
  for both supplied production task shapes using a populated temporary SQLite
  fixture.
* [ ] Backend API tests cover populated entity coverage and legacy/empty
  coverage compatibility.
* [ ] Frontend lint/test/build remain green without schema weakening.
* [ ] Production task detail requests return HTTP 200 for both supplied IDs;
  no task, finding, evidence, or content row is rewritten.
* [ ] API, Worker, crawler queue, browser state, database revision, and
  production worktree remain healthy after deployment.

## Definition of Done

* Root cause documented and regression test committed.
* Backend quality gates and the relevant frontend gates pass.
* Production backup exists before release; no migration is expected.
* Code is committed, pushed, deployed, and verified against the target commit.
* The pre-existing untracked `CLAUDE.md` remains untouched and uncommitted.

## Out of Scope

* Rewriting or deleting research results, findings, evidence, entities, or
  database rows.
* Changing the Phase 8C frontend feature scope, billing semantics, or crawler
  behavior.
* Adding mock data, relaxing Pydantic `extra="forbid"`, or bypassing auth.
* Database migration, downgrade, restore, or system/Nginx changes.

## Technical Notes

* Backend route: `backend/app/api/research.py`.
* Response contracts: `backend/app/models/research.py`.
* Repository projection: `backend/app/repositories/research.py`.
* Existing 8C specs: `.trellis/spec/backend/research-runtime-8c.md` and
  `.trellis/spec/frontend/research-center-8c.md`.
* Operational verification follows `.agents/skills/mediaops-server/` and
  `docs/deployment.md`.

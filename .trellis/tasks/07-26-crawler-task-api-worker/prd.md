# Implement crawler task API and worker

## Goal

Add a lightweight, production-oriented task layer around the already deployed
MediaCrawler installation. FastAPI accepts and exposes Bilibili search tasks;
a separate single-instance worker claims tasks from SQLite and launches the
fixed external runner without modifying or copying MediaCrawler.

## Requirements

### Persistence

* Use Python's standard-library SQLite driver; default database path is
  `/var/lib/mediaops/mediaops.db`, overridable by `MEDIAOPS_DATABASE_PATH`.
* Create `crawler_tasks` idempotently with UUID IDs and all fields listed by
  the user.
* Restrict statuses to `pending`, `running`, `waiting_login`, `succeeded`,
  `failed`, and `cancelled`.
* Use parameterized SQL and atomic transactions for task claiming.

### API

* Add create/list/detail/log/qrcode/results/cancel endpoints under
  `/api/crawler/tasks`.
* Accept only `platform=bili`, `crawler_type=search`, non-empty keywords, and
  `requested_count` from 1 through 20.
* Force `login_type=qrcode`; do not accept commands, paths, cookies, scripts,
  concurrency, comment flags, or other launcher controls.
* Return `201` for creation, `404` for unknown tasks, and `409` for invalid
  cancellation state.
* List tasks newest first.
* Log access supports either byte `offset` or line `tail`, with bounded output.
* QR access returns only the task's validated configured PNG path or a clear
  `404` while unavailable.
* Results are streamed line by line from `.jsonl` files in the task's validated
  output directory and support `offset` plus bounded `limit`.

### Worker

* Run independently as `python -m app.workers.crawler_worker`.
* On startup, mark stale `running` and `waiting_login` tasks failed with an
  abnormal-interruption message.
* Enforce a single worker using an OS file lock derived from the database path,
  in addition to atomic SQLite claim semantics.
* Claim one oldest pending task at a time.
* Create deterministic per-task output, log, and QR paths from the UUID.
* Invoke only configured fixed Python and runner paths with
  `asyncio.create_subprocess_exec`; never use a shell.
* Pass only service-generated flags for Bilibili search, QR login, count,
  output, QR path, concurrency=1, and disabled comments.
* Explicitly build child `PATH` using `MEDIAOPS_NODE_BINARY` or
  `MEDIAOPS_NODE_BIN_DIR`.
* Merge stdout/stderr, append logs as lines arrive, detect the QR file, and
  move `running -> waiting_login -> running` when log activity resumes.
* Poll `cancel_requested`, terminate then kill on timeout, and persist
  `cancelled`.
* Count valid JSONL lines after successful exit; persist failure details for a
  non-zero exit or execution error.

### Configuration and deployment

* Support every environment variable listed in the user request.
* Add a non-root systemd worker example using backend `.venv`, working
  directory, environment file, and restart policy.
* Expand `.gitignore` for database, QR, browser profile, output, and runtime
  artifacts.
* Update README, `docs/api-contract.md`, and `docs/deployment.md`.

### Testing

* Tests use temporary SQLite/filesystem paths and fake runner processes only.
* Cover creation, validation, single claim, success, failure, cancellation,
  JSONL pagination, path traversal, concurrency exclusion, and the existing
  health endpoint.
* `cd backend && uv sync && uv run pytest` passes.

## Acceptance Criteria

* [ ] The schema initializes automatically and idempotently at the configured path.
* [ ] API request models expose no process or filesystem controls.
* [ ] Only one worker instance and one crawler subprocess can run at a time.
* [ ] Task state, PID, timestamps, counts, and errors are persisted correctly.
* [ ] Log, QR, and result endpoints cannot escape configured task paths.
* [ ] Tests never contact Bilibili or start MediaCrawler.
* [ ] `/api/health` remains unchanged.
* [ ] Documentation lists initialization, environment, worker, and systemd steps.
* [ ] Changes are committed and pushed to `main`.

## Definition of Done

* Tests and import/startup checks pass on Python 3.11.
* Security review confirms parameterized SQL, allow-listed inputs, safe path
  resolution, fixed executables, argument arrays, and no `shell=True`.
* The lockfile, documentation, environment example, and systemd unit are
  committed; runtime data and credentials are not.

## Technical Approach

Use a small repository/service split:

* `app/db.py` owns SQLite connection setup and schema initialization.
* `app/repositories/crawler_tasks.py` owns parameterized task persistence and
  atomic claiming.
* `app/api/crawler.py` owns Pydantic request/response contracts and safe
  filesystem responses.
* `app/workers/crawler_worker.py` owns the single-worker lock and process
  lifecycle.

SQLite uses WAL mode and short transactions. Claiming is a conditional
`UPDATE ... WHERE status='pending'` inside `BEGIN IMMEDIATE`, so a second
claimer cannot receive the same task. The OS lock prevents two long-running
worker loops from being active against one database.

The runner command contract is an explicit, service-owned argument array:

```text
<MEDIACRAWLER_PYTHON> <MEDIACRAWLER_RUNNER>
  --platform bili
  --crawler-type search
  --keywords <validated keywords>
  --login-type qrcode
  --requested-count <1..20>
  --output-dir <generated task directory>
  --qrcode-path <generated task PNG>
  --max-concurrency-num 1
  --enable-comments false
```

## Decision (ADR-lite)

**Context**: The server is memory constrained and the job must survive API
process restarts without Redis, Celery, containers, or a separate database.

**Decision**: Persist jobs in SQLite, use one polling worker, combine an OS file
lock with transactional claiming, and launch a fixed external adapter using a
strict argument array.

**Consequences**: The design is simple to operate and deterministic, but is
intentionally single-host and single-job. Horizontal scaling and retry policy
are out of scope.

## Out of Scope

* Platforms other than Bilibili and crawler types other than keyword search.
* Redis, Celery, Docker, PostgreSQL, browser automation inside this repository,
  AI analysis, automatic publishing, frontend changes, retries, scheduling,
  authentication, and multi-host workers.
* Changes to `/opt/mediacrawler` or storage of cookies/browser profiles in Git.

## Technical Notes

* Existing ASGI path remains `app.main:app`.
* Existing health response remains exactly compatible.
* Production paths are defaults only; tests override every writable location.

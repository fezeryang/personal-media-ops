# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

The backend uses standard-library `sqlite3` for lightweight task metadata.
Database paths come from `Settings`; API input never controls a database path.
Every repository method opens its own short-lived connection. Alembic owns
schema history; runtime startup verifies the current revision and never
silently migrates.

---

## Query Patterns

All user-derived values use `?` parameters. SQL interpolation is limited to
compile-time constants such as schema status literals and internal assignment
fragments. Multi-step state transitions use `BEGIN IMMEDIATE`.

---

## Migrations

Versioned revisions live under `backend/migrations/`. Run:

```bash
MEDIAOPS_DATABASE_PATH=/path/to/mediaops.db uv run alembic upgrade head
```

`0001_legacy_tasks` creates a blank database or adopts the exact legacy column
set. `0002_multiplatform_tasks` rebuilds the table with the
`bili/xhs/dy` platform constraint while copying every column. Keep
`app.database_migrations.HEAD_REVISION` synchronized with the Alembic script
head; a regression test compares them.

`app.db.initialize_database()` is a schema check plus WAL setup, not a DDL
initializer. Back up production SQLite before any migration.

---

## Naming Conventions

Use lowercase plural table names and `snake_case` columns/indexes. Timestamps
are UTC ISO-8601 strings. SQLite booleans are `INTEGER` constrained to `0/1`.

---

## Common Mistakes

Do not claim a pending task with an unguarded `SELECT` followed by a later
update. Use the repository's `BEGIN IMMEDIATE` claim method, which also refuses
to claim while any task is `running` or `waiting_login`.

## Scenario: Crawler task persistence and claiming

### 1. Scope / Trigger

This contract applies when creating, claiming, cancelling, recovering, or
completing crawler tasks.

### 2. Signatures

* Table: `crawler_tasks`
* Migration: `uv run alembic upgrade head`
* Runtime verifier: `initialize_database(database_path: Path) -> None`
* Claim: `CrawlerTaskRepository.claim_next() -> dict | None`
* Worker command: `python -m app.workers.crawler_worker`

### 3. Contracts

`crawler_tasks` contains UUID `id`, platform/type/keyword/login inputs, bounded
requested and actual counts, status, generated paths, PID, error text,
timestamps, and `cancel_requested`. Status is one of `pending`, `running`,
`waiting_login`, `succeeded`, `failed`, or `cancelled`.

`MEDIAOPS_DATABASE_PATH` defaults to `/var/lib/mediaops/mediaops.db`.
The database must be at `HEAD_REVISION` before API or Worker startup.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Schema is absent or unversioned | Runtime raises `DatabaseMigrationRequired` |
| Blank database is upgraded | Alembic creates the current schema |
| Legacy Bilibili table is upgraded | Existing row values are preserved |
| Non-Bilibili rows exist during `0002` downgrade | Downgrade fails before rebuild |
| Active task exists | `claim_next()` returns `None` |
| Pending task exists and no active task | Oldest pending task becomes `running` atomically |
| Worker restarts with active tasks | Active tasks become `failed` with interruption text |
| Cancelling a terminal task | Repository raises `TaskNotCancellableError` |

### 5. Good/Base/Bad Cases

* Good: back up, run Alembic, then start code that requires the new head.
* Base: an empty queue returns `None` without an error.
* Bad: application startup creates or changes tables, or code ships without a
  matching revision.

### 6. Tests Required

Repository tests must assert one-task claiming, concurrent claimer exclusion,
interrupted-task recovery, terminal cancellation conflicts, and persisted
timestamps/statuses. Migration tests must cover blank and legacy databases,
row preservation, platform constraints, script-head synchronization, and
downgrade refusal. API tests must use temporary SQLite files.

### 7. Wrong vs Correct

Wrong:

```python
connection.execute("ALTER TABLE crawler_tasks ADD COLUMN new_value TEXT")
# Runtime code is not the schema migration mechanism.
```

Correct:

```bash
uv run alembic revision -m "add new value"
uv run alembic upgrade head
```

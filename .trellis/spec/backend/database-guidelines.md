# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

The backend uses standard-library `sqlite3` for lightweight task metadata.
Database paths come from `Settings`; API input never controls a database path.
Every repository method opens its own short-lived connection.

---

## Query Patterns

All user-derived values use `?` parameters. SQL interpolation is limited to
compile-time constants such as schema status literals and internal assignment
fragments. Multi-step state transitions use `BEGIN IMMEDIATE`.

---

## Migrations

`app.db.initialize_database()` creates parent directories and applies
idempotent `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`
statements. Back up the SQLite file before adding future schema migrations.

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
* Initializer: `initialize_database(database_path: Path) -> None`
* Claim: `CrawlerTaskRepository.claim_next() -> dict | None`
* Worker command: `python -m app.workers.crawler_worker`

### 3. Contracts

`crawler_tasks` contains UUID `id`, platform/type/keyword/login inputs, bounded
requested and actual counts, status, generated paths, PID, error text,
timestamps, and `cancel_requested`. Status is one of `pending`, `running`,
`waiting_login`, `succeeded`, `failed`, or `cancelled`.

`MEDIAOPS_DATABASE_PATH` defaults to `/var/lib/mediaops/mediaops.db`.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Schema is absent | Initializer creates table and index |
| Active task exists | `claim_next()` returns `None` |
| Pending task exists and no active task | Oldest pending task becomes `running` atomically |
| Worker restarts with active tasks | Active tasks become `failed` with interruption text |
| Cancelling a terminal task | Repository raises `TaskNotCancellableError` |

### 5. Good/Base/Bad Cases

* Good: one short transaction claims one pending UUID.
* Base: an empty queue returns `None` without an error.
* Bad: SQL concatenates keywords or a second worker starts another active task.

### 6. Tests Required

Repository tests must assert one-task claiming, concurrent claimer exclusion,
interrupted-task recovery, terminal cancellation conflicts, and persisted
timestamps/statuses. API tests must use temporary SQLite files.

### 7. Wrong vs Correct

Wrong:

```python
row = connection.execute("SELECT id FROM crawler_tasks WHERE status='pending'")
# Another worker can select the same row here.
```

Correct:

```python
connection.execute("BEGIN IMMEDIATE")
# Check active tasks, select one pending row, and conditionally update it
# before committing.
```

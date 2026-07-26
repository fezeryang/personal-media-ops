# SQLite Migration Strategy

## Decision

Use Alembic as the versioned migration mechanism while keeping application
queries on the standard-library `sqlite3` module.

Official Alembic documentation describes it as a lightweight migration tool
for SQLAlchemy and documents SQLite's required move-and-copy workflow for
constraint changes:

- <https://alembic.sqlalchemy.org/en/latest/>
- <https://alembic.sqlalchemy.org/en/latest/batch.html>
- <https://alembic.sqlalchemy.org/en/latest/api/commands.html>

## Required Revisions

1. A baseline revision creates the legacy Bilibili-only `crawler_tasks` table
   on a blank database. On an existing database it validates the expected
   legacy columns before adopting it.
2. A second revision rebuilds `crawler_tasks` with the same columns and data,
   changing only the platform check from `platform = 'bili'` to
   `platform IN ('bili', 'xhs', 'dy')`.

The existing table has an unnamed SQLite `CHECK`, so the migration should use
an explicit table definition rather than trusting reflected unnamed
constraints.

## Runtime Policy

- API and Worker startup verify that the database is at Alembic head; they do
  not silently mutate production schema.
- Tests and first-time setup explicitly run `upgrade head`.
- Production sequence is backup, pull/dependency sync, tests/build, Alembic
  upgrade, restricted release, and health verification.
- The deploy script requires an explicit migration opt-in when migration or
  schema paths changed.

## Compatibility and Rollback

- Existing UUIDs, Bilibili rows, timestamps, statuses, paths, counts, and
  indexes are copied unchanged.
- The expanded constraint is backward-compatible with the old application,
  which continues to create only Bilibili rows.
- Code rollback should use a reviewed revert/known-good forward deployment
  without downgrading the expanded constraint.
- A database downgrade is allowed only when no XHS or Douyin rows exist.
- Production restore requires the pre-migration SQLite backup, stopped
  writers, and separate authorization.

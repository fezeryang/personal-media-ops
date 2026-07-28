# Database Schema Audit

## Observed State

Production is at Alembic revision:

```text
0002_multiplatform_tasks
```

The actual production `crawler_tasks` table includes:

```sql
CONSTRAINT ck_tasks_platform
CHECK (platform IN ('bili','xhs','dy'))
```

This is a real persistence constraint, not documentation-only metadata.
Inserting `zhihu`, `wb`, `tieba`, or `ks` is impossible without a forward
migration.

## Existing Migration Behavior

- `0001_legacy_tasks` creates or adopts the legacy Bilibili-only table.
- `0002_multiplatform_tasks` rebuilds `crawler_tasks`, preserves every column,
  and expands the platform constraint to Bilibili, Xiaohongshu, and Douyin.
- Runtime startup verifies `HEAD_REVISION`; it does not execute migrations.
- The `0002` downgrade refuses to proceed when non-Bilibili rows exist.

## Required Migration

Create:

```text
0003_remaining_platforms
```

It will rebuild the table with:

```sql
CHECK (
  platform IN ('bili','xhs','dy','zhihu','wb','tieba','ks')
)
```

The copy must preserve all columns, task IDs, status values, counts, paths,
errors, timestamps, and cancellation flags. It must not read or rewrite JSONL
files.

The downgrade will first refuse if any `zhihu`, `wb`, `tieba`, or `ks` row
exists. Only then may it rebuild the `0002` constraint. This avoids destructive
loss or implicit platform coercion.

## Required Verification

- Upgrade a blank database to the new head.
- Upgrade an existing `0002` database containing Bilibili, Xiaohongshu, and
  Douyin rows and assert byte-for-byte field preservation.
- Accept all seven platform codes and reject unknown values.
- Keep completed task statuses and result paths unchanged.
- Assert migration-script head and runtime `HEAD_REVISION` match.
- Assert downgrade refusal when any new-platform row exists.

Production deployment requires a verified SQLite backup and the explicit
`--allow-migrations` gate. The application must not start against `0002` after
the code's runtime head becomes `0003`.

# SQLite scheduling and DST research

## Sources

- Python 3.11 `zoneinfo` and `datetime` documentation, including `fold`
  behavior:
  <https://docs.python.org/3.11/library/zoneinfo.html> and
  <https://docs.python.org/3.11/library/datetime.html>.
- Existing single-concurrency and recovery contracts:
  `backend/app/workers/crawler_worker.py`,
  `backend/app/repositories/crawler_tasks.py`,
  `backend/app/db.py`, and `AGENTS.md`.

## Compared approaches

### External cron/systemd timers per subscription

- Creates configuration outside Git/database truth and requires new privileged
  system management for every schedule.
- Makes pause/edit/audit/idempotency harder and violates the no-independent-
  process direction.

### APScheduler inside API or Worker

- Can model recurrence but adds a dependency/job store abstraction for five
  simple schedules.
- Running it in the API risks duplicate schedulers with multiple processes;
  running it in the Worker still requires application-owned run/task
  transactions and recovery logic.

### Small database coordinator in the existing Worker (selected)

- The Worker already has a host-wide file lock and is the only process allowed
  to launch crawler browsers.
- A monotonic poll deadline keeps the scheduler query low frequency while task
  polling remains responsive.
- `BEGIN IMMEDIATE`, unique scheduled slots, persisted next-run timestamps,
  and normal crawler task rows make the state restart-safe without a broker.

## Atomic scheduling contract

1. Begin an immediate SQLite transaction.
2. Select enabled records with `next_run_at <= now`.
3. Revalidate platform/mode capability.
4. Insert a run with unique `(owner object, scheduled_for)`.
5. Insert all ordinary crawler tasks and normalized run/task links in platform
   order.
6. Advance `next_run_at` from the recorded schedule slot, not wall-clock
   completion time.
7. Commit, then let the existing FIFO `claim_next()` and Worker lock execute
   one browser process at a time.

If the process restarts, queued tasks remain. The current Worker already marks
interrupted active tasks failed; reconciliation closes the owning automation
run, and the unique scheduled slot prevents rescheduling the same occurrence.

## DST policy

- Schedule definitions are local wall-clock rules stored with an IANA zone;
  materialized `scheduled_for` and all audit timestamps are UTC.
- For a candidate wall time, create both `fold=0` and `fold=1` variants and
  round-trip each through UTC.
- If both round-trip and offsets differ, the time is ambiguous; select
  `fold=0` so the repeated wall time runs once at its first occurrence.
- If neither round-trips, the time is nonexistent; advance minute-by-minute to
  the first valid local time.
- Persist the resulting UTC occurrence and enforce a unique constraint. Clock
  rollback or duplicate polling cannot create a second run.

## Failure and load policy

- Automatic frequency is never less than six hours.
- Failure delay is `min(6h * 2^(consecutive_failures-1), 24h)` and is applied
  as a lower bound on the next nominal occurrence.
- One run queues small per-platform counts and no automatic comments.
- Creator watch is bounded to five items and uses only verified creator modes.
- Trend/brief work is local SQLite aggregation and does not start a browser or
  add another service.

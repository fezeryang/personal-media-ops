# Subscriptions and low-resource scheduling

Keyword subscriptions turn verified search adapters into recurring,
incremental intelligence collection. Creator watchlist entries use the same
queue for verified creator-mode checks.

## Subscription contract

A subscription stores a name, query, one or more platform/count pairs,
enabled state, schedule type/configuration, IANA timezone, run timestamps,
failure state, and the next materialized UTC execution time. Accepted schedule
types are:

```text
manual
every_6_hours
daily
weekdays
weekly
```

Clients submit a bounded typed configuration, not a cron expression.
`daily`, `weekdays`, and `weekly` use a local `HH:MM`; weekly also uses a
0–6 Monday-first weekday. Automatic intervals shorter than six hours are not
available.

Only enabled platforms whose exact `search` mode is
`production_verified` can be selected. This explicitly excludes disabled and
deferred modes, Douyin, and Kuaishou search. Changing the platform capability
later causes a due invalid subscription to be disabled rather than generating
an endless failure loop.

## Scheduler architecture

The existing Worker owns one low-cost coordinator loop; no Redis, Celery,
broker, or per-subscription process is created. Every automation poll:

1. reconciles queued/running subscription and watch runs with crawler tasks;
2. selects due UTC slots inside `BEGIN IMMEDIATE`;
3. inserts a unique `(subscription_id, scheduled_for)` run;
4. creates normal pending crawler tasks in platform order;
5. advances `next_run_at` with an exact compare-and-update.

The crawler queue and Worker lock remain the only browser execution path, so
the global browser concurrency stays one. A restart can reconcile generated
tasks and terminal states. Re-reading the same due slot cannot create a second
run. Failed recurring runs use bounded exponential delay: 6, 12, then at most
24 hours.

## Timezone and DST behavior

All stored timestamps are UTC with a `Z` suffix. Schedules retain an IANA
timezone. A nonexistent local time in a DST spring-forward gap advances to the
first valid minute; an ambiguous fall-back time uses `fold=0`, so it runs once.
The resolved UTC slot is persisted before execution, preventing server clock
changes or restarts from repeating it.

## Incremental results

Each platform task links back to a `subscription_run`. Library upsert reports:

```text
new_content_count
existing_content_count
changed_content_count
```

New means no prior `(platform, source_content_id)` existed. Existing content
is never counted as new; metric changes are tracked independently. Run detail
returns platform/task order, status, counts, errors, duration timestamps, and
the associated task IDs.

## Creator watchlist and briefs

Watchlist items support `every_6_hours`, `daily`, and `weekly`, with at most
five contents per check. They reuse verified creator mode and normal crawler
tasks. Pause/resume changes only future scheduling; already generated tasks
retain explicit ownership.

A per-owner brief schedule can generate one deterministic brief daily. Its UTC
slot uses the same atomic claim pattern. The Worker calculates the matching
24-hour trend window before generating the brief.

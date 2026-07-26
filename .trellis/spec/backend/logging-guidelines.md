# Logging Guidelines

> How logging is done in this project.

---

## Overview

Crawler stdout and stderr are merged and appended in real time to one
service-generated log file per task. API log access is bounded and validates
the stored path against the configured task path.

---

## Log Levels

The external runner owns crawler line content. Worker lifecycle failures are
stored in `error_message`; systemd/journald records worker process failures.

---

## Structured Logging

Crawler log files are plain UTF-8-compatible text at
`<MEDIAOPS_LOG_ROOT>/crawler/{task_id}.log`.

---

## What to Log

Preserve runner stdout/stderr in arrival order. Persist PID, state transitions,
exit code failures, completion time, and interruption recovery in SQLite.

---

## What NOT to Log

Do not log cookies, browser profile data, environment variables, command
credentials, or QR image bytes. Never accept a caller-provided log path.

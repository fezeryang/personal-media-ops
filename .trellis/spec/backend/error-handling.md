# Error Handling

> How errors are handled in this project.

---

## Overview

FastAPI uses HTTP status codes and short `detail` messages. Worker failures are
persisted on the task and must never leave a claimed task active indefinitely.

---

## Error Types

Use domain errors for expected state conflicts, such as
`TaskNotCancellableError` and `WorkerAlreadyRunning`. Convert them at the API or
CLI boundary.

---

## Error Handling Patterns

Catch expected errors narrowly. The crawler worker is a deliberate process
boundary: it catches unexpected execution errors only to persist a failed task
with `finished_at`, then continues polling.

---

## API Error Responses

Use HTTP 404 for missing tasks/files, 409 for task-state or stored-path
conflicts, and FastAPI's 422 validation response for invalid request/query
fields. Do not expose tracebacks, SQL text, or file contents in errors.

---

## Common Mistakes

Never return HTTP 200 for a missing QR code, never silently accept cancellation
of terminal tasks, and never leave a non-zero subprocess exit as `running`.

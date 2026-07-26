# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

Backend code targets Python 3.11 and is managed with uv. Ruff, compile checks,
pytest, and at least 80% application coverage form the quality gate.

---

## Forbidden Patterns

* `shell=True`, shell command strings, and caller-controlled executables/paths.
* SQL built from user input.
* Reading an entire crawler result file into memory.
* Tests that contact MediaCrawler, Bilibili, or production paths.

---

## Required Patterns

* Pydantic allow lists with `extra="forbid"` at API boundaries.
* Parameter arrays with `asyncio.create_subprocess_exec`.
* Resolved-path containment checks before file reads.
* Temporary SQLite and filesystem roots in tests.

---

## Testing Requirements

Run `uv run pytest` for every change. New worker behavior requires fake-runner
tests for success, failure, cancellation, and relevant state transitions.
Concurrency changes require an actual competing-claimer or lock test.

---

## Code Review Checklist

Run:

```bash
uv sync
uv run ruff check .
uv run python -m compileall -q app tests
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

Review process arguments, SQL placeholders, path containment, task state
transitions, ignored runtime data, and compatibility of `/api/health`.

## Test Environment Diagnostic

FastAPI synchronous routes use AnyIO worker threads. If pytest hangs, first run
a minimal `asyncio` `call_soon_threadsafe()` probe. In the managed Codex
sandbox, socket wakeups may be blocked even when application code is correct.
If the minimal probe fails in-sandbox and passes outside it, run the unchanged
test suite in the approved unsandboxed environment; do not replace
`TestClient`, pin unrelated packages, or rewrite production code to mask the
execution-environment restriction.

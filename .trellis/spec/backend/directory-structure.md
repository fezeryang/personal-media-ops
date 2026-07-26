# Directory Structure

> How backend code is organized in this project.

---

## Overview

<!--
Document your project's backend directory structure here.

Questions to answer:
- How are modules/packages organized?
- Where does business logic live?
- Where are API endpoints defined?
- How are utilities and helpers organized?
-->

The Python project root is `backend/`. Application code is under `backend/app`,
with HTTP route modules in `app/api` and environment-backed shared settings in
`app/core`. Integration tests are under `backend/tests`.

---

## Directory Layout

```
backend/
├── app/
│   ├── api/
│   ├── crawler/
│   ├── models/
│   ├── core/
│   ├── repositories/
│   ├── workers/
│   ├── db.py
│   └── main.py
├── migrations/
│   └── versions/
├── tests/
├── alembic.ini
├── pyproject.toml
└── .env.example
scripts/crawler/
└── run_mediacrawler.py
deploy/systemd/
└── mediaops-api.service.example
```

---

## Module Organization

<!-- How should new features/modules be organized? -->

Keep the API contract close to its route in `app/api/<resource>.py`; mount
routers from `app/main.py`. Keep configuration parsing in `app/core/config.py`.
Keep Pydantic request/response contracts in `app/models`, platform Adapters and
the registry in `app/crawler`, parameterized SQLite access in
`app/repositories`, runtime schema checks in `app/db.py`, Alembic revisions in
`migrations/versions`, and independently executable workers in `app/workers`.
The reviewed external-process bridge lives in `scripts/crawler`; it is not
MediaCrawler core source.

---

## Naming Conventions

<!-- File and folder naming rules -->

Use lowercase `snake_case` for Python modules and test files. The ASGI object
must remain importable as `app.main:app`.

---

## Examples

<!-- Link to well-organized modules as examples -->

Examples: `backend/app/api/health.py` exposes `GET /api/health`;
`backend/app/api/crawler.py` exposes crawler task resources; and
`backend/app/workers/crawler_worker.py` runs separately from FastAPI.

## Scenario: Minimal health API contract

### 1. Scope / Trigger

This contract applies to the initial backend skeleton and any deployment that
uses the example systemd unit.

### 2. Signatures

* ASGI application: `app.main:app`
* HTTP endpoint: `GET /api/health`
* Development command: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`

### 3. Contracts

The endpoint returns HTTP 200 and the JSON fields `status`, `service`, and
`version`, with values `ok`, `personal-media-ops-api`, and `0.1.0`.
`FRONTEND_ORIGINS` is optional and is parsed as a comma-separated list of
explicit origins. An unset value produces no allowed origins.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| `GET /api/health` | HTTP 200 with the fixed health payload |
| `FRONTEND_ORIGINS` unset or empty | CORS allows no browser origin |
| `FRONTEND_ORIGINS` contains comma-separated origins | Only those exact origins are configured |
| Any other method at `/api/health` | FastAPI returns HTTP 405 |

### 5. Good/Base/Bad Cases

* Good: `FRONTEND_ORIGINS=https://app.example.com`
* Base: empty `FRONTEND_ORIGINS` for server-only deployments
* Bad: `FRONTEND_ORIGINS=*` or an undocumented production domain

### 6. Tests Required

`backend/tests/test_health.py` must assert HTTP 200 and exact equality of all
three response fields. Configuration changes must add assertions for origin
allow-list behavior.

### 7. Wrong vs Correct

Wrong: `allow_origins=["*"]` or mounting the router without the `/api` prefix.

Correct: configure `CORSMiddleware` from `Settings.frontend_origins` and mount
the health router with `prefix="/api"`.

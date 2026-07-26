# Initialize minimal FastAPI backend

## Goal

Create the first deployable backend skeleton for `personal-media-ops`, suitable
for Ubuntu 22.04 on an Alibaba Cloud server. This phase intentionally provides
only a health endpoint and configuration plumbing; it does not introduce any
database, queue, crawler, browser automation, or AI integration.

## What I already know

* The repository root is currently only Trellis project scaffolding and has no application code.
* The backend will live under `backend/` and use Python 3.11, FastAPI, uv, and Uvicorn.
* The required ASGI import path is `app.main:app`.
* The required endpoint is `GET /api/health` with a fixed JSON response.
* CORS must be configured from `FRONTEND_ORIGINS`; no wildcard production origin is allowed.
* Deployment documentation must include a systemd service example.
* The repository must not contain `.env`, runtime data, logs, cookies, or database files.

## Assumptions

* `backend/` is the Python project root; `backend/app` is the import package and `backend/tests` contains pytest tests.
* `FRONTEND_ORIGINS` accepts a comma-separated list of origins and defaults to an empty list.
* The service example runs from the checked-out backend directory and uses an environment file supplied by the operator.
* Git is initialized at the repository root and the existing GitHub origin is `git@github.com:fezeryang/personal-media-ops.git`.

## Requirements

* Add `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/health.py`, `backend/app/core/__init__.py`, and `backend/app/core/config.py`.
* Add `backend/tests/test_health.py`.
* Add `backend/pyproject.toml` configured for Python 3.11, FastAPI, Uvicorn, pytest, and HTTPX test support only.
* Add `backend/.env.example` without secrets.
* Add root `README.md` documenting the project, local setup, development command, health endpoint, environment variable, and deployment example.
* Add `deploy/systemd/mediaops-api.service.example`.
* Return exactly `{ "status": "ok", "service": "personal-media-ops-api", "version": "0.1.0" }` from `GET /api/health`.
* Ensure `cd backend && uv sync && uv run pytest` passes.
* Do not install Redis, Celery, MediaCrawler, Playwright, AI SDKs, or a database dependency.
* Commit the implementation and push `main` to the configured GitHub origin after verification.

## Acceptance Criteria

* [ ] `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` starts the app from `backend/`.
* [ ] `GET /api/health` returns HTTP 200 and the required JSON body.
* [ ] CORS origins are read from `FRONTEND_ORIGINS`, with no wildcard default.
* [ ] `cd backend && uv sync && uv run pytest` succeeds.
* [ ] No forbidden dependencies or runtime artifacts are tracked.
* [ ] Changes are committed on `main` and pushed to GitHub.

## Definition of Done

* Tests pass and the resulting file layout is documented.
* Configuration and deployment examples contain no secrets.
* Git diff is reviewed before commit and the final commit hash is reported.

## Out of Scope

* Database models, migrations, persistence, Redis, Celery, crawlers, Playwright, AI SDKs, authentication, and business APIs.
* Production reverse proxy, TLS, monitoring, or cloud provisioning.

## Technical Notes

* Relevant project guidance: `.trellis/spec/backend/index.md` and its backend guideline files; these are currently scaffolding placeholders.
* Existing repository guidance: `AGENTS.md` requires environment variables for secrets and a reviewed diff before commits/pushes.

# Repository Guidelines

These rules apply to the entire repository. More specific `AGENTS.md` files may
add local rules, but may not weaken the safety requirements below.

## Product and Current Scope

**Personal Media Ops**（个人互联网情报与内容运营平台）是用户自己的互联网信息获取、
整理、分析与内容运营基础设施，不是普通爬虫面板。

Current capabilities are Bilibili keyword collection, FastAPI APIs, SQLite task
metadata, a single-concurrency Worker, external MediaCrawler integration, a
React workbench, log/QR/result views, and same-origin Nginx deployment. Never
present unfinished modules or synthetic data as working product behavior.

## End-to-End Agent Workflow

Own product outcomes across the whole stack. For each requirement, trace and
implement the necessary flow:

```text
database → domain model → backend service → API → Worker → frontend
         → tests → documentation → deployment impact
```

Do not ask the user to coordinate frontend and backend work. Before modifying
code:

1. Read the relevant code, tests, and documentation.
2. Confirm real API and data-model contracts.
3. Decide whether a database migration is required.
4. Identify Worker and production-deployment effects.
5. Provide a short implementation plan.

Git is the only source of truth for code. Never leave production-only edits
uncommitted or edit generated JS/CSS on the server.

## Repository Structure

- `backend/`: Python 3.11 FastAPI app, SQLite repository, Worker, and pytest.
- `frontend/`: React/Vite/TypeScript workbench and Vitest tests.
- `docs/`: API, deployment, agent workflow, and server operations.
- `deploy/systemd/`: reviewed service-unit examples; installation needs root.
- `scripts/server/`: guarded SSH diagnostics, logs, backup, and deployment.
- `infra/`: non-secret SSH and infrastructure examples.
- `.agents/skills/`: repository-native Codex skills, including
  `mediaops-server`.
- `.trellis/`: workflow, project specs, task records, and developer journal.

## Engineering and Security Rules

- Do not mask API failures with Mock data or silently swallow exceptions.
- Do not use TypeScript `any` to bypass contracts.
- Never commit passwords, Cookies, private keys, tokens, `.env`, databases,
  logs, QR codes, browser state, or crawler output.
- Do not copy or modify MediaCrawler core code; integrate through adapters.
- Keep crawler concurrency at one unless the user explicitly approves a
  capacity change.
- Do not add automatic publishing without user approval.
- Do not run destructive database work without a verified backup.
- Never use `git reset --hard`, delete the production database, clear
  `/var/lib/mediaops`, or clear `/var/log/mediaops`.
- Do not test unverified changes directly in production.

## Local Quality Gates

Backend:

```bash
cd backend
uv sync --frozen
uv run pytest
```

Frontend:

```bash
cd frontend
npm ci --include=dev
npm run lint
npm run test
npm run build
```

Before deployment, all commands above must pass. Confirm Git status and scan
for accidental data, logs, QR images, credentials, and generated runtime files.

## Database Changes

Schema changes require a migration mechanism and a production backup. Never
change only a model or initializer while claiming migration support. Migrations
must preserve existing data, and deployment docs must specify backup,
migration, application, and rollback order.

This repository currently has no formal migration tool; it only applies
idempotent initial SQLite DDL. Establishing versioned migrations is the next
database-infrastructure task before the first schema change.

## Production Operations

Use `$mediaops-server` and `scripts/server/`. Default to read-only diagnosis.
Before any mutation, state the target host, target commit, worktree state, and
planned actions. Back up SQLite before database-affecting deployment.

Do not edit production repository files, `/opt/mediacrawler`, browser login
state, systemd, Nginx, or BaoTa configuration unless the task explicitly
requires it. Do not restart every service without evidence. Prefer diagnosis
and the smallest verified repair. If root access is unavailable, never request
an interactive sudo password; provide exact root commands and report
“code prepared, production operation pending.”

## Completion Report

Every completed task must report:

- what was implemented;
- major files changed;
- whether the database changed;
- whether the backend changed;
- whether the frontend changed;
- whether the Worker was affected;
- whether deployment was affected;
- tests executed and their results;
- production-build result;
- remaining work;
- commit hash and push status;
- final worktree status;
- production deployment commands;
- rollback cautions.

<!-- TRELLIS:START -->
# Trellis Instructions

This project is managed by Trellis. Read `.trellis/workflow.md`,
`.trellis/spec/`, `.trellis/tasks/`, and `.trellis/workspace/` as directed by
the active workflow. Repository skills live under `.agents/skills/`. Prefer
available Trellis commands over manual task bookkeeping.

Managed by Trellis. Edits inside this block may be overwritten by a future
`trellis update`.
<!-- TRELLIS:END -->

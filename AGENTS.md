# Repository Guidelines

These rules apply to the entire repository. More specific `AGENTS.md` files may
add local rules, but may not weaken the safety requirements below.

## Product and Current Scope

**Personal Media Ops**（个人互联网情报与内容运营平台）是用户自己的互联网信息获取、
整理、分析与内容运营基础设施，不是普通爬虫面板。

Current capabilities are a seven-platform, mode-level Adapter registry; five
explicit task modes (`search`, `detail`, `creator`, `comments`,
`sub_comments`); versioned SQLite task and library entities; a
single-concurrency Worker; external pinned MediaCrawler integration; FastAPI
task/library APIs; React task, capability, content, creator, comment, QR, log,
and provenance views; and same-origin Nginx deployment. Platform × mode
statuses are independent facts. Search verification must never imply detail,
creator, or comment verification. Douyin remains resource-deferred and
Kuaishou search remains upstream-deferred until a recorded real task proves
otherwise. Never present unfinished modules or synthetic data as working
product behavior.

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
- `scripts/crawler/`: reviewed MediaCrawler Runner adapter; not third-party
  MediaCrawler source.
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
- Run the local quality gates before using production for the explicitly
  authorized small real-platform validation.

## Agent Autonomy and Pause Boundary

Once the user authorizes an end-to-end product or rollout outcome, own the
normal engineering loop without asking the user to choose technical steps:

```text
collect evidence → inspect real state → resume from the last safe checkpoint
→ fix → test → commit → push → deploy → verify → continue
```

An SSH exit code, missing EOF, transient network/package-source failure,
test/build/service/helper failure, Adapter/Runner mismatch, or the need for a
new fix commit is not by itself a reason to pause. Each individual stage
remains fail-closed, but the Agent must diagnose it, preserve completed work,
apply an in-scope repair, and resume instead of treating one command result as
the whole system state. Do not repeat a verified migration or restore a
database merely because deployment transport failed later.

Pause only when progress requires:

- the user to scan a QR code, solve a captcha, approve an account prompt, or
  act in an external console;
- a new secret, account, token, license, paid service, or third-party grant;
- an irreversible data operation such as database replacement, destructive
  downgrade, result deletion, or browser-login-state deletion; or
- authority outside the installed boundary, such as sudoers/root-shell,
  firewall/user, Cloudflare, security-group, domain, or shared system
  infrastructure changes.

Targeted non-secret production configuration changes explicitly required by
the active task, such as `MEDIAOPS_ENABLED_PLATFORMS`, may be performed
autonomously. Back up the file with restrictive permissions, change only the
named variable, never print the complete file, and report only the variable
name plus its non-secret value.

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

Alembic is the formal migration mechanism under `backend/migrations/`. Runtime
startup verifies that SQLite is at the current head and must not silently
upgrade it. New schema changes require a forward migration, an existing-data
test, and a reviewed downgrade or explicit irreversible-migration rationale.

## Production Operations

Use `$mediaops-server` and `scripts/server/`. Start with read-only diagnosis,
then continue with the smallest authorized mutation needed to reach the
already-approved outcome.
Before any mutation, state the target host, target commit, worktree state, and
planned actions. Back up SQLite before database-affecting deployment.
Deployments containing migration/schema paths require the explicit
`--allow-migrations` gate; never add that flag without reviewing migration and
rollback behavior.

Do not edit production repository files, `/opt/mediacrawler`, browser login
state, systemd, Nginx, or BaoTa configuration unless the task explicitly
requires it. Do not restart every service without evidence. Prefer diagnosis
and the smallest verified repair. Reconnect after transport anomalies and
compare commits, markers, database revision, processes, and health before
deciding which stage remains. Routine privileged release work must use only
the reviewed `/usr/local/sbin/mediaops-release` subcommands through `sudo -n`.
Never request an interactive sudo password, seek a root shell, or automatically
install/overwrite the helper or sudoers.

For the stage-four rollout authorized on 2026-07-26, the reproduced
Codex-observer failure at the external Beaver/WAF boundary (`403`, `525`, or a
TLS reset) is non-blocking only when the restricted helper and Nginx checks
pass, both application services are active, localhost `/api/health` passes,
and the production server can validate the public hostname and certificate via
an SNI loopback request. Record the external observer failure in the final
report. This exception does not permit ignoring a different public failure, an
origin-side failure, or any failed database, test, build, migration, helper,
service, Nginx, or SNI gate.

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

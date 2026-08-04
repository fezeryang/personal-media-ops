# Repository Guidelines

These rules apply to the entire repository. More specific `AGENTS.md` files may
add local rules, but may not weaken the safety requirements below.

## Product and Current Scope

**Personal Media Ops**（个人互联网情报与内容运营平台）是用户自己的互联网信息获取、
整理、分析与内容运营基础设施，不是普通爬虫面板。

Current capabilities are a single-owner authenticated intelligence workbench;
scoped API keys and a stable Agent API v1; keyword subscriptions and
low-resource scheduling; tags, favorites, ordered collections, creator
watchlists, metric snapshots, deterministic trend signals and daily briefs;
a seven-platform, mode-level Adapter registry; five explicit task modes
(`search`, `detail`, `creator`, `comments`, `sub_comments`); a
single-concurrency Worker; external pinned MediaCrawler integration; and
same-origin Nginx deployment. Platform × mode
statuses are independent facts. Search verification must never imply detail,
creator, or comment verification. Douyin remains resource-deferred and
Kuaishou search remains upstream-deferred until a recorded real task proves
otherwise. Bilibili and Zhihu content modes are production-verified; Weibo
and Tieba detail/creator/comments are production-verified; Kuaishou
detail/comments are production-verified while creator is upstream-deferred;
Xiaohongshu signed-target modes are login-context-deferred. Never present
unfinished modules or synthetic data as working product behavior.

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

## Phase 8D Authentication and Production Acceptance

The user's normal production workflow in Windows Chrome is valid. A missing
Owner session in a WSL temporary Playwright profile is an automation-context
failure, not evidence that the user failed to log in or that the production
server cannot continue. Never treat that condition as a product-authentication
failure or repeatedly ask the user to log in.

### Ownership boundaries

Keep the two authentication domains separate:

- **Windows browser**: view the production frontend, complete an Owner login,
  scan a third-party platform QR code, solve a captcha, make one explicit
  confirmation, and perform the final visual product check.
- **Production server**: run the Research Runtime and single-concurrency
  Crawler Worker, persist platform login state, generate and score Discovery
  candidates, apply feedback, associate Research Spaces, recover state, and
  provide the authoritative database, API, task, and log evidence.
- **Codex**: develop, deploy when authorized, start bounded tasks through the
  official application path, wait for server execution, inspect formal API and
  server evidence, repair real defects, and write the acceptance report.

Codex must not read or export Windows Chrome cookies, session tokens, browser
state, or profile files; take over the user's daily browser; connect to a
Chrome debugging port; or create a test backdoor. Do not start a new WSL
temporary browser merely because it has no Owner cookie. Do not mix the
Personal Media Ops Owner Workbench session with Bilibili, Zhihu, Xiaohongshu,
Weibo, Tieba, or other platform login state.

### Human intervention boundary

User intervention is limited to an actual visual authentication or approval
requirement. When one occurs:

1. Tell the user the exact production frontend page to open.
2. Show the login page, QR code, captcha, or confirmation entry through the
   production frontend.
3. The user completes only the scan, login, captcha, or one explicit
   confirmation in their Windows browser.
4. After the user replies `已完成`, resume from the existing checkpoint and
   verify the corresponding server session, platform login state, task state,
   database rows, and formal API response.

Never ask the user to configure WSL, create a Playwright profile, connect
remote debugging, copy or export cookies/browser state, provide a session
token, execute server commands, install a plugin, or handle CSRF manually.
Do not restart a browser or repeat a login after the user has completed the
required visual action. If no real login, QR, captcha, or confirmation is
needed, continue the server-side acceptance autonomously.

### 8D acceptance status and path

The current Phase 8D status is:

```text
implementation: complete
automated_tests: passed
production_deployment: passed
remaining: real production tasks and product-experience acceptance
authentication_intervention: only when actually required, through the
  Windows production frontend for one scan, login, captcha, or confirmation
```

Remaining acceptance must use the existing application and server flow:

```text
Windows frontend visual action (only when required)
  → user replies "已完成"
  → server Owner/platform state verification
  → Research Runtime / Crawler Worker execution
  → formal API, database, task, and log validation
  → frontend visual result check
```

The absence of an Owner cookie in a newly created WSL temporary profile is
not a remaining product defect and is not a reason to rerun the whole suite.
Preserve the current task checkpoint and continue from the last verified
server state. Platform QR login is completed by the user through the
production frontend and then persisted by the server MediaCrawler Worker;
Owner confirmation is completed through the normal frontend and business API.

## Production Data Loading and Login-QR Acceptance

An authenticated page showing `数据加载失败` or `请求失败（HTTP 500）` is a
blocking production defect, even when `/api/health`, systemd, and the public
homepage are healthy. Every production acceptance involving Research or
crawler login must exercise the real authenticated API contracts, including:

- `/api/research/tasks`;
- `/api/research/tasks/{id}` and `/api/research/tasks/{id}/events` for every
  acceptance task;
- `/api/crawler/tasks/{id}` and `/api/crawler/tasks/{id}/qrcode` for every
  crawler task that is `waiting_login`.

The detail endpoint must be validated with populated nested data, especially
information utilities, entity/event candidates, memory items, alignment
reviews, queries, and evidence. Before release, locally validate the exact
repository payload through its Pydantic response model; a database row that
loads but cannot satisfy the response model is an API failure. Do not claim
acceptance from a successful list request alone.

For a `waiting_login` task, the QR endpoint must return HTTP 200 with
`image/png`, the QR file must exist at the bounded task path, and the UI must
poll it until login or a terminal state. If the task has already timed out or
left `waiting_login`, the absence of a QR is expected and must be reported as
an explicit terminal/login failure; it is not evidence that login succeeded.
Never delete or silently reuse browser login state to make this check pass.
Any 500, missing nested response field, stale QR state, or mismatch between
task status and QR availability requires a regression test and a new
production verification before the stage can be marked complete.

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

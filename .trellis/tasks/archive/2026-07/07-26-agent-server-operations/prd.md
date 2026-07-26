# Establish Agent and Server Operations

## Goal

Turn the repository into the durable source of truth for end-to-end product
engineering and production operations. Expand the root `AGENTS.md`, add one
auto-discovered `mediaops-server` Codex skill, create guarded SSH/diagnostic/
backup/deploy scripts, and document the operating model without changing the
product or production server.

## Requirements

- Refactor the existing root `AGENTS.md` in place and preserve one Trellis
  managed block.
- Define product scope, end-to-end agent responsibilities, engineering and
  production safety rules, real project layout, verification commands,
  migration policy, and mandatory completion reports.
- Use `.agents/skills/mediaops-server/` as the single skill source because this
  repository's Codex session auto-discovers project skills there.
- Build the skill with `SKILL.md`, `agents/openai.yaml`,
  `references/server-inventory.md`, `references/deployment.md`, and a small
  script dispatcher.
- Add `infra/ssh/config.example`; never add a key, password, token, Cookie, or
  production `.env`.
- Add guarded Bash tools under `scripts/server/`: `connect.sh`, `status.sh`,
  `healthcheck.sh`, `logs.sh`, `backup.sh`, and `deploy.sh`.
- Every public script uses `set -Eeuo pipefail`, supports `--help`, validates
  arguments, defaults `MEDIAOPS_SSH_HOST` to `mediaops-prod`, uses BatchMode,
  and fails clearly.
- Diagnostics are read-only. Backup and deployment default to dry-run and
  require explicit `--execute`.
- Deployment uses `git pull --ff-only`, records old/target commits, backs up
  SQLite, runs all backend/frontend gates, and never requests an interactive
  sudo password.
- Root-only deployment work is gated behind explicit `--root-stage` and
  `sudo -n`; otherwise output exact commands and report production work as
  pending.
- Update `README.md` and `docs/deployment.md`; add
  `docs/agent-workflow.md` and `docs/server-operations.md`.
- State honestly that no formal migration tool exists and make establishing
  one the next database infrastructure task.

## Acceptance Criteria

- [ ] `AGENTS.md` covers the entire repository and all requested reporting and
      production-operation rules.
- [ ] `mediaops-server` validates with the official skill validator and is
      automatically discoverable from the repository.
- [ ] Inventory contains the supplied hostnames, paths, services, Node,
      MediaCrawler, storage, and URL facts but no credentials.
- [ ] All required scripts exist, are executable, pass `bash -n`, and expose
      useful `--help`.
- [ ] Script dry-runs do not connect or mutate production.
- [ ] Missing SSH alias is reported once; no production connection is
      attempted in this task.
- [ ] ShellCheck is run if installed; absence is reported rather than hidden.
- [ ] Backend pytest, frontend lint/test/build, path checks, and secret scans
      pass.
- [ ] Changes are reviewed, committed, and pushed to `main`; the final worktree
      is clean.

## Definition of Done

- Documentation and scripts agree on server paths and privilege boundaries.
- No product behavior, database schema, frontend, backend, Worker, systemd
  unit, Nginx config, or production host is modified.
- Deployment and rollback caveats are explicit.
- The task is archived and session work is recorded after the work commit.

## Technical Approach

Create one repository-native skill using the official `skill-creator`
initializer. Keep reusable command implementation in `scripts/server/`; the
skill dispatcher calls those scripts rather than copying them. Share safe SSH
defaults and validation through `scripts/server/lib/common.bash`.

Use remote `bash -s` scripts with fixed paths and validated scalar arguments.
Separate read-only commands, mediaops-writable phases, and privileged phases.
Use consistent SQLite backup through Python's `sqlite3.Connection.backup`,
metadata, and SHA-256 checksums. Do not automate rollback or sudoers changes.

## Decision (ADR-lite)

**Context**: The repository needs one skill source that Codex can discover
without user-level installation or duplicated copies.

**Decision**: Store `mediaops-server` under `.agents/skills/`, the project-level
path already surfaced by the current Codex environment. Do not create a
parallel `skills/` or user-level copy.

**Consequences**: Opening Codex in this repository makes the skill available.
Other harnesses may use their own skill discovery, but this task does not
duplicate the source to support them.

## Out of Scope

- Product features, API changes, database schema changes, or migrations
- Production deployment, service restarts, Nginx/systemd/sudoers changes
- Database restore or destructive cleanup automation
- Editing `/opt/mediacrawler`
- Installing SSH keys or modifying the user's SSH configuration

## Technical Notes

- Current production services: `mediaops-api` and
  `mediaops-crawler-worker`.
- Existing database initialization uses idempotent SQLite DDL, not a migration
  framework.
- Existing deployment docs point Nginx at the application build directory;
  supplied production inventory uses `/www/wwwroot/ops.fezern8n.com` and is
  authoritative for this task.
- Current `ssh -G mediaops-prod` resolves to hostname `mediaops-prod`, so the
  alias is not configured and no SSH connection is authorized.
- Research: `research/skill-layout.md`.

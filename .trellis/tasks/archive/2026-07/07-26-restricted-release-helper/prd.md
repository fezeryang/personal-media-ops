# Integrate Restricted Production Release Helper

## Goal

Replace direct privileged deployment commands with the reviewed
`/usr/local/sbin/mediaops-release` v1 boundary. Keep a repository source for
the helper and exact sudoers allowlist, update the production deployment
orchestrator and Skill, and verify everything locally without performing a real
release.

## Requirements

- Keep `mediaops-prod` as the default SSH alias and honor
  `MEDIAOPS_SSH_HOST`.
- Keep deployment dry-run by default; require `--execute` for production
  mutation and support explicit `--dry-run` and `--target-ref`.
- Resolve `origin/main`, require the requested target to match it, reject dirty
  worktrees and non-fast-forward updates, and print old/target commits.
- Report target host, current commit, target commit, migration detection,
  backup state, tests, and the helper subcommand before mutation.
- Back up SQLite before pulling code. Never back up or print `.env`, cookies,
  QR codes, browser state, or SSH credentials.
- Run `uv sync --frozen`, backend pytest, `npm ci --include=dev`, frontend
  lint/test/build, then call exactly:
  `sudo -n /usr/local/sbin/mediaops-release finalize`.
- Never call `finalize` if any sync, test, or build stage fails.
- Run internal and public health checks after helper success and record the
  deployment only after all checks pass.
- Report the exact failed stage and never describe partial activation as a
  successful deployment.
- Store the reviewed helper source at `infra/release/mediaops-release` and its
  exact command allowlist at `infra/sudoers/mediaops-release.example`.
- Remove the obsolete sudoers example that grants direct rsync, systemctl, and
  Nginx commands.
- Do not install or overwrite the production helper or sudoers from deployment
  code.
- Update the repository-level `mediaops-server` Skill, operations code-spec,
  README, and deployment/operations documentation.

## Acceptance Criteria

- [x] Helper `version` prints `1`.
- [x] Helper `status` reports host/action/app root/version, API/Worker states,
      frontend build/publication presence, Nginx validation, and API health.
- [x] Helper accepts only the documented eight subcommands and rejects extra
      arguments.
- [x] Sudoers example permits only exact helper/subcommand pairs.
- [x] `deploy.sh --help` documents `--target-ref`, `--dry-run`, and
      `--execute`.
- [x] Dry-run does not connect to production or invoke the helper.
- [x] Invalid target refs, dirty worktrees, non-fast-forward updates, migration
      paths, and failed gates stop before `finalize`.
- [x] Full deployment uses only the restricted helper for root work.
- [x] Bash syntax, Skill validation, backend tests, frontend lint/test/build,
      path checks, and secret/artifact scans pass.
- [x] No real production publish/restart/reload/finalize is run in this task.

## Definition of Done

- The helper source, sudoers source, deployment script, Skill, code-spec, and
  operator docs agree.
- No backend, frontend, database, Worker, systemd, Nginx, installed helper,
  installed sudoers, or production runtime state is changed.
- Changes are committed and pushed to `main`; the worktree is clean.

## Technical Approach

Use a fixed-path, root-only Bash helper with no environment-driven privileged
paths. The non-root deploy script owns Git, backup, dependencies, tests, and
build. It invokes only helper `finalize` after every gate succeeds. The helper
owns static synchronization, service restart, Nginx check/reload, and local
verification. Both layers use strict mode, bounded input validation, explicit
stage output, and non-interactive sudo.

`--target-ref` resolves a commit after fetching `origin/main`; deployment
continues only when that commit equals `origin/main`, preserving the
fast-forward-only main release policy while allowing a caller to pin the
expected SHA.

## Decision (ADR-lite)

**Context**: The old deploy script directly allowed rsync, systemctl, and Nginx
through sudo, creating a wider privileged surface.

**Decision**: Use one reviewed v1 helper and exact sudoers subcommand entries.
Do not let deployment install or modify either source on production.

**Consequences**: Privileged behavior is narrow and auditable. Changes to the
helper require a separate human-reviewed installation before deployment code
may depend on a new helper version.

## Out of Scope

- Real production publication or application restart
- Installing/updating `/usr/local/sbin/mediaops-release`
- Installing/updating sudoers
- Database migration or restore
- Backend, frontend, Worker, systemd, or Nginx configuration changes
- Automatic rollback

## Technical Notes

- Production repository was already clean at
  `85cc1bb83f3a743316dd4609393e84efa7a81fa8`.
- Server-side `bash -n scripts/server/*.sh` passed before implementation.
- Helper v1 `version` and `status` succeeded; no state-changing helper command
  was invoked.
- See `research/helper-v1-observation.md`.

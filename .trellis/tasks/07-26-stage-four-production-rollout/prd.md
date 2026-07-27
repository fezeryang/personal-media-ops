# Stage Four Production Rollout Health-Check Exception

## Goal

Continue the end-to-end stage four production rollout at the fixed initial
target commit `ee22c771e5e52c8d6d78dbf8e74586ed65a40e0d`, while recording a
narrow operator-approved exception for the already diagnosed external
Beaver/WAF health-check failure.

The rollout is outcome-authorized: recoverable engineering, transport,
test/build, service, Helper, Adapter, Runner, and API/UI failures are diagnosed
and repaired autonomously through commit, push, resumable deployment, and real
verification. A failed command is not by itself a user pause condition.

## Requirements

- Add a repository rule explaining that the known external observer failure
  (`403`/`525`/TLS reset from the Codex execution environment) does not by
  itself block this rollout.
- Do not turn the exception into permission to ignore arbitrary public health
  failures.
- Continue requiring clean Git state, target identity, SQLite backup,
  Alembic verification, backend/frontend quality gates, restricted helper
  success, active services, valid Nginx configuration, localhost API health,
  and a public-hostname SNI check from the production server.
- Run the initial deployment at the user-fixed target commit.
- Keep `MEDIAOPS_ENABLED_PLATFORMS=bili` during the initial deployment.
- Run a real Bilibili regression before enabling Xiaohongshu.
- Enable and validate Xiaohongshu, then Douyin, one at a time, with global
  browser concurrency fixed at one.
- Pause only for QR-code scanning, external-console work, destructive database
  risk, abnormal migration/worktree/target state, insufficient controlled
  permissions, failed gates or real collection, or unauthorized sensitive
  configuration changes.
- Never print `.env`, cookies, browser storage, or login-state contents.
- Resume from verified commits, markers, migrations, backups, and process
  state after an interrupted deployment; never repeat a verified migration or
  restore the database solely because a later transport stage failed.
- Pause only for user QR/captcha/account actions, a new secret or external
  grant, an irreversible data operation, or authority outside the existing
  SSH/restricted-helper boundary.
- Permit targeted, backed-up, non-secret updates to
  `MEDIAOPS_ENABLED_PLATFORMS` without printing any other `.env` content.
- Make the deploy script recognize the approved external-observer exception
  only after helper/Nginx/services/localhost and production SNI loopback pass.

## Acceptance Criteria

- [ ] `AGENTS.md` contains the narrow health-check exception.
- [ ] Initial production deployment reaches the fixed target commit.
- [ ] SQLite backup and checksum are recorded.
- [ ] Alembic reaches `0002_multiplatform_tasks` without losing legacy tasks.
- [ ] Backend pytest and frontend lint/test/build pass during deployment.
- [ ] API, Worker, helper, Nginx, localhost health, and production-server SNI
      health checks pass.
- [ ] Bilibili regression succeeds with real results.
- [ ] Xiaohongshu and Douyin are enabled and production-verified only after
      their own real successful tasks.
- [ ] Any QR-code wait reports the task ID and task-detail URL.
- [ ] Code and task bookkeeping are committed and pushed, and the final
      worktree state is reported.
- [ ] Agent autonomy and pause-boundary rules are synchronized across
      `AGENTS.md`, the production Skill, deployment references, and docs.
- [ ] The external-observer fallback is regression-tested and records its
      non-blocking result without masking arbitrary public/origin failures.

## Definition of Done

- All authorized production stages have completed or the workflow has paused
  at an explicitly allowed blocking condition with exact evidence.
- Database, backend, frontend, Worker, deployment, tests, build, commits,
  push status, worktree state, and rollback cautions are reported.

## Technical Approach

Document the exception in `AGENTS.md` as an evidence-based observer exception.
Use the existing `scripts/server/deploy.sh`, restricted release helper, API
contracts, and single-concurrency Worker. Use bounded SSH and read-only
diagnostics around each production mutation. Do not bypass failed application,
database, build, helper, Nginx, localhost, or production-origin SNI checks.

## Decision (ADR-lite)

**Context:** The application, helper, Nginx, TLS certificate, and localhost
public-hostname SNI checks pass, while the current Codex observer is blocked by
the external Beaver/WAF path.

**Decision:** Treat only that reproduced observer-specific failure as
non-blocking for this rollout, as explicitly authorized by the operator.

**Consequences:** The final report must state that independent external health
was not proven from the Codex network. A different public failure or an origin
failure remains blocking.

## Out of Scope

- Changing Cloudflare, BaoTa/Beaver WAF, Nginx, system networking, systemd, or
  sudoers.
- Database restoration or destructive downgrade.
- Editing `/opt/mediacrawler` core code.
- Increasing crawler concurrency, enabling comments, sub-comments, or proxies.
- Large-scale collection or automatic publishing.

## Technical Notes

- Initial server commit observed:
  `0a23f47f3b6931fa0cdfe1bb17cf448324176b58`.
- Initial target commit:
  `ee22c771e5e52c8d6d78dbf8e74586ed65a40e0d`.
- Required operational contract:
  `.trellis/spec/operations/server-deployment.md`.
- Deployment references:
  `docs/deployment.md`, `docs/server-operations.md`, and
  `.agents/skills/mediaops-server/references/deployment.md`.

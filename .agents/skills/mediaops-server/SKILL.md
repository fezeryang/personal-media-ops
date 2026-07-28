---
name: mediaops-server
description: Operate Personal Media Ops production safely through bounded SSH diagnostics and the restricted mediaops-release helper. Use for service checks, logs, unreachable API or idle Worker diagnosis, GitHub/server revision comparison, SQLite backup preparation, controlled application builds, restricted releases, post-deployment verification, and rollback preparation.
---

# MediaOps Server Operations

Operate `mediaops-prod` with evidence-first commands. Never claim success
without command output and verification.

## Load Context

1. Read [references/server-inventory.md](references/server-inventory.md).
2. For backup, build, release, failure, or rollback work, also read
   [references/deployment.md](references/deployment.md).
3. Read root `AGENTS.md` and the relevant repository deployment docs.
4. State the target, operation class, and whether it mutates production.

Use `MEDIAOPS_SSH_HOST`, defaulting to `mediaops-prod`. Use BatchMode and a
connection timeout. Never embed the IP in scripts, request a password, read a
private key, or log in as root.

## Classify the Operation

### Read-only diagnosis

Use `connect`, `status`, `healthcheck`, or bounded `logs`. Treat permission
failure as unknown, not as proof that a service or file is absent.

```bash
.agents/skills/mediaops-server/scripts/run-server-tool.sh status
.agents/skills/mediaops-server/scripts/run-server-tool.sh healthcheck --with-ssh
```

### Application build

Run Git sync, `uv sync --frozen`, backend pytest, frontend `npm ci`, lint, test,
and build as `mediaops`. This is preparation, not a successful release.

### Database backup

Run `scripts/server/backup.sh --execute` before pull or migration. Back up only
SQLite and non-secret deployment metadata. Never back up `.env`, cookies, QR
codes, browser state, crawler results, or SSH material.

### Restricted release

Routine privileged activation is available only through:

```bash
sudo -n /usr/local/sbin/mediaops-release <allowed-subcommand>
```

The full deploy script may call only `finalize`, and only after all tests and
the build and any explicitly authorized Alembic migration pass. Never call
direct privileged rsync, systemctl, or Nginx commands. Never install or
overwrite the helper or sudoers automatically.

### Root boundary

The repository files under `infra/release/` and `infra/sudoers/` are reviewed
sources for a human administrator. They do not grant Codex a root shell or
arbitrary sudo. Do not probe commands outside the allowlist or bypass it.

## Required Pre-release Report

Before a real release, report:

- target server;
- current commit;
- target commit/ref;
- whether database migration or schema paths exist;
- whether migration execution has explicit `--allow-migrations` authorization;
- whether SQLite backup has completed;
- exact backend/frontend tests to run;
- helper path and subcommand.

Start with a no-connection dry-run:

```bash
scripts/server/deploy.sh --target-ref <origin-main-sha> --dry-run
```

An explicit user request to complete the production rollout authorizes the
normal release/retry loop; do not ask again for each non-destructive stage. A
real release uses:

```bash
scripts/server/deploy.sh --target-ref <origin-main-sha> --execute
```

If and only if the reviewed diff contains a compatible Alembic migration, use:

```bash
scripts/server/deploy.sh \
  --target-ref <origin-main-sha> \
  --allow-migrations \
  --execute
```

## Post-release Verification

After helper success, verify the localhost API and public frontend/API routes.
Compare repository commit, build marker, and published marker. Record old/new
commits only after all checks pass. For content-mode releases, also verify the
exact Alembic head, `/api/crawler/capabilities` has seven platforms × five
modes, `/api/library/stats` responds, old task counts remain intact, and the
library tables exist before creating any real mode task. A successful process
exit without normalized library entities and task provenance is not a
successful collection.

## Failure Handling

- Keep each stage fail-closed, report its exact failure, and immediately
  inspect real remote state before deciding what remains.
- Treat SSH 255, missing EOF, or a lost session as transport evidence, not
  proof the remote stage failed. Reconnect, compare the stage marker, commit,
  build/published markers, processes, and database revision, then resume from
  the nearest safe checkpoint.
- For fixable test/build/service/helper/Adapter/Runner failures within the
  authorized outcome, diagnose, edit the repository, add tests, commit, push,
  redeploy, and verify without asking the user to select the repair.
- Never rerun a verified migration or restore a database solely because a
  later stage or connection failed.
- The recorded Codex-observer `403`, `525`, or TLS/connection failure is
  non-blocking only after helper/Nginx/services/localhost checks and a
  production-server SNI loopback all pass. Record the exception.
- Never describe preparation or partial activation as success; report success
  only from the composite state.

Pause only for user QR/captcha/account actions, new secrets or third-party
grants, irreversible data operations, or authority outside the existing
helper/SSH boundary. Targeted non-secret configuration changes explicitly
required by the task may proceed without another approval; back up the file,
change only the named variable, and never print the full file.

## Rollback Preparation

Retain the pre-release SQLite backup and old commit. Prefer a reviewed Git
revert or known-good forward deployment. Before downgrading, confirm the
migration permits it with current data. Database restore requires stopped
writers and separate authorization. Never use `git reset --hard`, delete
`/var/lib/mediaops`, clear logs, or modify `/opt/mediacrawler`.

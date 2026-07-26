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

A separately authorized real release uses:

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
commits only after all checks pass.

## Failure Handling

- Stop on a dirty worktree, target mismatch, non-fast-forward update,
  unauthorized migration/schema path, backup failure, failed
  test/build/migration, helper failure, or health failure.
- Report the exact failed stage.
- Never describe code preparation or partial helper execution as success.
- Inspect evidence before retrying; do not restart every service blindly.

## Rollback Preparation

Retain the pre-release SQLite backup and old commit. Prefer a reviewed Git
revert or known-good forward deployment. Before downgrading, confirm the
migration permits it with current data. Database restore requires stopped
writers and separate authorization. Never use `git reset --hard`, delete
`/var/lib/mediaops`, clear logs, or modify `/opt/mediacrawler`.

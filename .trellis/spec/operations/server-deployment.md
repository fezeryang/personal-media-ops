# Server Deployment Contract

## 1. Scope / Trigger

Apply this contract when adding or changing production diagnostics, logs,
backup, deployment, SSH inventory, privilege boundaries, or server paths.
`AGENTS.md` defines safety policy; `.agents/skills/mediaops-server/` supplies
operator context; `scripts/server/` is the executable source of truth.

## 2. Signatures

```text
connect.sh [--host SSH_ALIAS]
status.sh [--host SSH_ALIAS]
healthcheck.sh [--base-url URL] [--with-ssh] [--host SSH_ALIAS]
logs.sh SOURCE [--lines 1..5000] [--follow] [--host SSH_ALIAS]
backup.sh [--host SSH_ALIAS] [--dry-run | --execute]
deploy.sh [--host SSH_ALIAS] [--commit SHA] [--dry-run | --execute] [--root-stage]
```

`SOURCE` is exactly one of `--api`, `--worker`, `--nginx-access`,
`--nginx-error`, or `--task UUID`.

## 3. Contracts

- `MEDIAOPS_SSH_HOST` defaults to the SSH alias `mediaops-prod`.
- SSH uses `BatchMode=yes` and `ConnectTimeout=10`.
- Backup and deployment are dry-run by default.
- Deployment always targets `origin/main`, uses `git pull --ff-only`, and
  rejects a dirty production worktree.
- Backup uses SQLite's backup API, integrity checking, metadata, and SHA-256.
- Non-root deployment runs all backend and frontend quality gates.
- Root work is explicit through `--root-stage` and `sudo -n`; scripts never
  prompt for a password.
- Static output flows from `/opt/personal-media-ops/frontend/dist/` to
  `/www/wwwroot/ops.fezern8n.com/`.
- The build writes the target commit to `.mediaops-release`; status compares it
  with the checked-out repository commit.

## 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Invalid SSH alias characters | Exit 2 before SSH |
| Alias not configured | Report missing config/key prerequisite once |
| Invalid commit | Exit 2 before SSH |
| Non-UUID task log request | Exit 2 before SSH |
| More than 5000 log lines | Exit 2 before SSH |
| `--dry-run` with `--execute` | Exit 2 |
| `--root-stage` without `--execute` | Exit 2 |
| Dirty production worktree | Stop before backup or pull |
| Missing/unwritable backup root | Stop and print the exact root preparation command |
| Nonzero test/build command | Stop before activation |
| Missing restricted sudo | Stop without a password prompt; production remains pending |
| Failed post-release health check | Return nonzero and do not report success |

## 5. Good / Base / Bad Cases

- Good: `deploy.sh --commit <sha>` prints host, target, phases, and root commands
  without connecting.
- Base: `deploy.sh --commit <sha> --execute` backs up, fast-forwards, validates,
  builds, then reports root activation as pending.
- Bad: accepting a caller-provided command, file path, service name, log path,
  or SSH password.

## 6. Tests Required

- `bash -n` succeeds for every public script and shared library.
- Every public script returns help successfully.
- Backup and deployment dry-runs succeed with an unresolvable host.
- Conflicting execution modes and root-without-execute fail before SSH.
- Task-log path traversal is rejected before SSH.
- The official Skill validator succeeds.
- Backend pytest and frontend lint/test/build remain green.
- Repository scans find no private key, `.env`, database, log, QR, or runtime
  data artifacts.

## 7. Wrong vs Correct

### Wrong

```bash
ssh mediaops@47.105.36.220 'cd /opt/personal-media-ops && git reset --hard'
sudo systemctl restart mediaops-api
```

This bypasses the alias, destroys worktree state, skips backup and tests, and
may prompt for a password.

### Correct

```bash
scripts/server/deploy.sh --commit <origin-main-sha>
scripts/server/deploy.sh --commit <origin-main-sha> --execute
```

Only add `--root-stage` after the target, commit, command list, and restricted
sudo policy have been explicitly reviewed.

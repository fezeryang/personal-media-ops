# Server Deployment Contract

## 1. Scope / Trigger

Apply this contract to production diagnostics, backup, Git sync, application
build, restricted release, post-release verification, or rollback preparation.
`scripts/server/` is the non-root orchestration source;
`infra/release/mediaops-release` is the reviewed privileged source.

## 2. Signatures

```text
connect.sh [--host SSH_ALIAS]
status.sh [--host SSH_ALIAS]
healthcheck.sh [--base-url URL] [--with-ssh] [--host SSH_ALIAS]
logs.sh SOURCE [--lines 1..5000] [--follow] [--host SSH_ALIAS]
backup.sh [--host SSH_ALIAS] [--dry-run | --execute]
deploy.sh [--host SSH_ALIAS] [--target-ref REF] [--allow-migrations]
          [--dry-run | --execute]
mediaops-release {version|status|publish-frontend|restart-services|nginx-check|nginx-reload|verify|finalize}
```

`SOURCE` is exactly one of `--api`, `--worker`, `--nginx-access`,
`--nginx-error`, or `--task UUID`.

## 3. Contracts

- `MEDIAOPS_SSH_HOST` defaults to `mediaops-prod`; SSH is non-interactive.
- Dry-run makes no SSH connection. Execute requires an explicit flag.
- `--target-ref` must resolve to `origin/main`; updates are fast-forward only.
- Migration/schema paths stop deployment unless the reviewed release receives
  explicit `--allow-migrations`.
- SQLite backup completes before pull.
- Backend sync/pytest and frontend ci/lint/test/build complete before helper
  invocation.
- Authorized migrations run `uv run alembic upgrade head` after backup and all
  tests/builds, then verify runtime schema head before helper invocation.
- The deploy script calls only
  `sudo -n /usr/local/sbin/mediaops-release finalize` for privileged work.
- Helper version is `1`; its paths, services, binaries, and subcommands are
  fixed.
- The installed helper may intentionally be `root:root 0750`; `mediaops` does
  not need direct read or execute permission. Validate availability only with
  `sudo -n /usr/local/sbin/mediaops-release version`, which exercises the
  reviewed sudoers entry without weakening the helper mode.
- Helper and sudoers sources are never installed by deployment code.
- Success is recorded only after internal and public checks pass.

## 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Invalid host or target-ref | Exit before SSH |
| `--dry-run` with `--execute` | Exit 2 |
| Dirty/non-main server worktree | Stop before backup/pull |
| Target differs from `origin/main` | Stop before backup/pull |
| Target is non-fast-forward | Stop before backup/pull |
| Migration/schema path detected without opt-in | Report paths and stop |
| Authorized Alembic migration fails | Stop before `finalize` |
| Missing helper or helper version not `1` | Stop before backup/pull |
| Helper is not directly executable by `mediaops`, but `sudo -n ... version` returns `1` | Continue; this is the expected restricted-permission model |
| `sudo -n ... version` fails | Report the controlled helper entry as unavailable and stop before backup/pull |
| Backup failure | Stop before pull |
| Target changes after backup | Stop before pull |
| Test/build failure | Do not invoke `finalize` |
| Helper failure | Report restricted-release stage; never claim success |
| Health failure | Report failed stage; never record success |
| Extra/unknown helper argument | Exit 2 |
| Helper mutation invoked without root | Exit 3 |

## 5. Good / Base / Bad Cases

- Good: `deploy.sh --target-ref <sha> --allow-migrations --dry-run` prints
  migration authorization, gates, and helper subcommand without SSH.
- Base: `--execute` backs up, fast-forwards, tests/builds, calls `finalize`,
  verifies, then prints old/new commits.
- Good: a `root:root 0750` installed helper passes preflight through its exact
  `sudo -n ... version` allowlist entry even though `[[ -x helper ]]` is false
  for `mediaops`.
- Bad: direct sudo rsync/systemctl/Nginx, arbitrary helper arguments, helper
  installation, password prompts, or reporting partial activation as success.

## 6. Tests Required

- Bash syntax passes for public scripts, embedded remote Bash/Python, helper,
  and script tests.
- Release script tests cover dry-run, invalid args, helper version/allowlist,
  no direct root commands, no direct-user helper executability assumption, and
  gate ordering before `finalize`.
- Official Skill validation passes.
- Backend pytest and frontend lint/test/build remain green.
- Secret/artifact scans find no private keys, `.env`, database, logs, QR codes,
  cookies, or runtime output.
- Real `finalize`, publish, restart, and reload are never used for local
  verification.

## 7. Wrong vs Correct

### Wrong

```bash
[[ -x /usr/local/sbin/mediaops-release ]]
sudo systemctl restart mediaops-api
sudo /www/server/nginx/sbin/nginx -s reload
```

### Correct

```bash
sudo -n /usr/local/sbin/mediaops-release version
scripts/server/deploy.sh --target-ref <origin-main-sha> --dry-run
scripts/server/deploy.sh \
  --target-ref <origin-main-sha> \
  --allow-migrations \
  --execute
```

The second command is a real release and requires explicit user authorization.

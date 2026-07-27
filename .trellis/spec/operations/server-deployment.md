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
          [--resume] [--dry-run | --execute]
mediaops-release {version|status|publish-frontend|restart-services|nginx-check|nginx-reload|verify|finalize}
command -v xvfb-run
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
- Deployment runs as isolated stages (`preflight`, `backup`, `git-sync`,
  `runner-sync`, `backend-test`, `frontend-build`, `migrate`, `finalize`,
  `verify`), each in its own SSH session; long-running stages add SSH
  keepalives. The
  marker-tracked stages (`backup` through `finalize`) append
  `<stage>=done <utc-timestamp>` to
  `/var/lib/mediaops/deploy-state/<target-commit>.stages` only after remote
  success; `preflight` and `verify` are not marker-tracked.
- `runner-sync` (between `git-sync` and `backend-test`) installs the reviewed
  repository runner `scripts/crawler/run_mediacrawler.py` to
  `/var/lib/mediaops/bin/run_mediacrawler.py` — the copy the Worker actually
  executes via `MEDIACRAWLER_RUNNER`; unsynced drift caused a real production
  Xiaohongshu argparse failure. It runs as `mediaops` without sudo, hard-fails
  on a missing source, is a no-op (`runner_sync=unchanged`) when the installed
  copy is byte-identical, and otherwise takes a UTC-timestamped
  `install -m 750` backup, installs the new copy, purges
  `/var/lib/mediaops/bin/__pycache__`, and logs `runner_sync=updated` with the
  new file's sha256.
- `--resume` skips stages already marked done for the same target commit;
  `preflight` and `verify` always run. A non-resume execute run clears the
  target commit's marker file first, so stale markers from earlier attempts
  cannot satisfy the exit-255 recheck. Stages are idempotent and individually
  re-runnable.
- An SSH exit of 255 triggers exactly one reconnect to recheck the remote
  stage marker; a `done` marker means the stage completed remotely, otherwise
  that attempt fails. A failed attempt does not itself require a user pause:
  the Agent inspects commits, markers, migrations, processes, and health,
  repairs within the authorized scope, and resumes from the nearest verified
  checkpoint.
- The deploy script normally calls only
  `sudo -n /usr/local/sbin/mediaops-release finalize` for privileged work.
  When the deployed helper v1 finalize fails but both `.mediaops-release`
  markers already equal the target commit (the known immutable `.user.ini`
  rsync failure), the script may complete activation with the individually
  allowlisted `restart-services`, `nginx-reload`, and `verify` subcommands;
  a marker mismatch aborts instead.
- Helper version is `1`; its paths, services, binaries, and subcommands are
  fixed.
- The installed helper may intentionally be `root:root 0750`; `mediaops` does
  not need direct read or execute permission. Validate availability only with
  `sudo -n /usr/local/sbin/mediaops-release version`, which exercises the
  reviewed sudoers entry without weakening the helper mode.
- Helper and sudoers sources are never installed by deployment code.
- Before enabling `dy`, the operator must confirm that `xvfb-run` is available
  on the production host. Installing `xvfb` is an administrator-owned system
  change and is outside `deploy.sh` and the restricted helper. The reviewed
  Runner exits explicitly when a headful run has neither `DISPLAY` nor
  `xvfb-run`.
- `MEDIAOPS_ENABLED_PLATFORMS` is non-secret targeted configuration. An
  authorized rollout may back up `.env` with restrictive permissions and
  replace only that variable without printing any other value.
- Success is recorded only after internal checks and either the direct public
  checks pass or the exact approved external-observer exception passes.
  The exception accepts only Codex-side `403`, `525`, or connection/TLS
  failure, then requires helper status, Nginx, both services, localhost API,
  and certificate-valid public-hostname SNI loopback checks from production.
  Deployment records store `external_observer=passed|failed-nonblocking`.

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
| Test/build failure | Do not invoke `finalize`; fix/test/commit/push and resume without a technical user pause |
| Stage SSH exit 255 with remote `done` marker | Warn and continue |
| Stage SSH exit 255 without remote marker | Fail that attempt with the stage name, inspect real state, then repair/resume |
| Helper finalize failure with both release markers at target | Complete via allowlisted `restart-services`/`nginx-reload`/`verify` |
| Helper failure without marker parity | Report restricted-release stage; never claim success |
| Direct public check returns `403`, `525`, or connection/TLS failure; production helper/SNI loopback passes | Record `external_observer=failed-nonblocking` and complete |
| Approved observer failure but helper/SNI loopback fails | Fail verify; never record success |
| Direct public check returns any other HTTP or invalid payload | Fail verify; never use the observer exception |
| `dy` enablement requested without `xvfb-run` | Do not enable `dy`; report the administrator prerequisite |
| Xvfb wrapper returns without `DISPLAY` | Runner fails explicitly; never claim a runnable Douyin task |
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
- Good: check `command -v xvfb-run` read-only before an approved `dy`
  enablement, then validate one real task with global concurrency still at one.
- Good: after a Codex-side TLS reset, recheck helper status and
  `--resolve <host>:443:127.0.0.1` routes on production, record the observer
  result, and continue only when every origin-side gate passes.
- Bad: direct sudo rsync/systemctl/Nginx, arbitrary helper arguments, helper
  installation, password prompts, or reporting partial activation as success.
- Bad: silently install system packages from deployment automation or enable
  `dy` while its required virtual-display executable is absent.
- Bad: treat one SSH/public-check exit code as the whole deployment state, or
  let an arbitrary public HTTP 500 use the observer exception.

## 6. Tests Required

- Bash syntax passes for public scripts, embedded remote Bash/Python, helper,
  and script tests.
- Release script tests cover dry-run, invalid args, helper version/allowlist,
  no direct root commands, no direct-user helper executability assumption, and
  gate ordering before `finalize`.
- Stubbed (never real SSH) execute-path tests cover `--resume` stage
  skipping, exit-255 marker recovery, the `runner-sync` marker, ordering
  between `git-sync` and `backend-test`, and resume skip, the non-resume
  stale-marker reset, the
  finalize `.user.ini` fallback, the helper rsync protect/exclude filter, and
  that dry-run never invokes SSH.
- Stubbed observer tests assert that a connection/TLS failure plus successful
  production SNI loopback completes with `failed-nonblocking`, a failed SNI
  loopback aborts, and HTTP 500 never enters the exception.
- Official Skill validation passes.
- Backend pytest and frontend lint/test/build remain green.
- Runner unit tests assert Xvfb re-exec, missing-Xvfb failure, wrapped-without-
  `DISPLAY` failure, and legacy missing-`--headless` compatibility.
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
scripts/server/deploy.sh --execute || wait-for-user
```

### Correct

```bash
sudo -n /usr/local/sbin/mediaops-release version
ssh -o BatchMode=yes mediaops-prod 'command -v xvfb-run'
scripts/server/deploy.sh --target-ref <origin-main-sha> --dry-run
scripts/server/deploy.sh \
  --target-ref <origin-main-sha> \
  --allow-migrations \
  --execute
# On a recoverable failure: inspect remote markers/state, fix, commit, push,
# then rerun with --resume from the verified checkpoint.
```

The `--execute` deployment command is a real release and requires explicit
user authorization.

# Restricted Deployment Reference

## Privilege Model

The SSH user is `mediaops`. It owns Git sync, dependency installation, tests,
frontend build, SQLite backup, and health checks.

The only routine privileged entry point is:

```text
/usr/local/sbin/mediaops-release
```

Installed helper version: `1`.

Exact subcommands:

```text
version
status
publish-frontend
restart-services
nginx-check
nginx-reload
verify
finalize
```

Use `sudo -n`; never request a password or root shell. The full orchestrator
normally calls only `finalize`; the reviewed `.user.ini` fallback below is the
sole exception and uses only allowlisted subcommands. Repository sources are:

```text
infra/release/mediaops-release
infra/sudoers/mediaops-release.example
```

They require separate human review and installation. Deployment code must
never copy or overwrite the installed helper or sudoers.

## Standard Sequence

Deployment runs as isolated stages, each in its own SSH session; long-running
stages add SSH keepalives. Marker-tracked stages (`backup` through `finalize`)
append `<stage>=done <utc-timestamp>` to
`/var/lib/mediaops/deploy-state/<target-commit>.stages` after remote success;
`--resume` skips stages already recorded for the same target commit
(`preflight` and `verify` always run), while a non-resume execute run clears
the target commit's marker file first.

1. `preflight`: confirm SSH identity, main branch, clean worktree; fetch
   `origin/main`; resolve `--target-ref`; require the target to equal
   `origin/main` and be a fast-forward; detect migration/schema paths and stop
   unless `--allow-migrations` was explicitly supplied after migration and
   rollback review; record old and target commits, tests, helper version, and
   `finalize`.
2. `backup`: back up SQLite with `scripts/server/backup.sh --execute`.
3. `git-sync`: re-fetch, ensure the target did not change, run
   `git pull --ff-only origin main`, and confirm HEAD equals the target.
4. `runner-sync`: install the reviewed repository runner
   `scripts/crawler/run_mediacrawler.py` to
   `/var/lib/mediaops/bin/run_mediacrawler.py`, the copy the Worker actually
   executes (`MEDIACRAWLER_RUNNER`); unsynced drift here caused a real
   production Xiaohongshu argparse failure. Runs as `mediaops` without sudo;
   no-op when byte-identical, otherwise a UTC-timestamped `install -m 750`
   backup, the new copy, and a `__pycache__` purge.
5. `backend-test`: run `uv sync --frozen` and backend pytest.
6. `frontend-build`: run frontend `npm ci --include=dev`, lint, test, build,
   and write the target commit to `frontend/dist/.mediaops-release`.
7. `migrate` (authorized schema changes only): run
   `uv run alembic upgrade head` against the fixed production SQLite path and
   verify the database is at head.
8. `finalize`: invoke `sudo -n /usr/local/sbin/mediaops-release finalize`.
9. `verify`: verify the localhost API, the public frontend, health API, and
   SPA route; record success and print old/new commits.

If a stage's SSH invocation exits 255 (transport error), the orchestrator
reconnects once and rechecks the remote stage marker; a `done` marker means
the stage completed remotely and the deployment continues. A missing marker
fails that attempt, after which the Agent diagnoses real remote state, repairs
the script or application when needed, and resumes from the nearest verified
checkpoint instead of pausing for technical direction.

If the deployed helper v1 `finalize` fails but both the published and built
`.mediaops-release` markers already equal the target commit (the known
immutable BaoTa `.user.ini` rsync exit-23 failure), the orchestrator completes
activation with the individually allowlisted `restart-services`,
`nginx-reload`, and `verify` subcommands; a marker mismatch aborts instead.

## Helper Responsibilities

- `publish-frontend`: synchronize the fixed build directory to the fixed
  static root.
- `restart-services`: restart only `mediaops-api` and
  `mediaops-crawler-worker`.
- `nginx-check`: run the fixed BaoTa Nginx configuration test.
- `nginx-reload`: validate, then reload the fixed Nginx binary.
- `verify`/`status`: check services, build/publication presence, Nginx, and
  local API health.
- `finalize`: publish, restart, check, reload, verify, then report success.

The helper accepts no arbitrary paths, services, commands, environment-derived
privileged paths, or extra arguments.

## Backup and Migration

The backup uses SQLite's backup API, integrity checking, metadata, and SHA-256
under `/var/backups/mediaops`. It excludes `.env`, cookies, QR codes, SSH
material, virtual environments, caches, and crawler results.

Alembic revisions under `backend/migrations/` are the versioned migration
source. Application startup verifies head and does not auto-upgrade. A change
under migration/alembic/SQL paths, `backend/app/db.py`, or backend models
requires a reviewed migration plan, backup, and explicit
`--allow-migrations`. The deploy script runs migrations only after backend
tests and frontend build succeed, and before `finalize`.

## Failure, Recovery, and Rollback

Every stage is fail-closed. A failed test/build prevents `finalize`. A helper or
health failure may mean production is partially activated; inspect commits,
markers, services, database revision, and health before retrying. Under an
authorized rollout, fixable failures are handled through repository changes,
tests, commits, push, and resumable redeployment without asking the user to
choose the technical recovery.

The known external Codex-observer `403`, `525`, or TLS/connection failure may be
recorded as non-blocking only when helper/Nginx checks, both services, localhost
health, and a certificate-valid public-hostname SNI loopback from production
all pass. Other public or origin failures remain failures.

Retain the old commit and backup. Prefer a reviewed Git revert or known-good
forward commit. A database downgrade is allowed only when its revision
explicitly supports current production data. Never use `git reset --hard`.
Database restore requires stopped writers, explicit authorization, ownership
validation, integrity checks, and post-restore health checks.

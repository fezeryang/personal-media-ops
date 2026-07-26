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
calls only `finalize`. Repository sources are:

```text
infra/release/mediaops-release
infra/sudoers/mediaops-release.example
```

They require separate human review and installation. Deployment code must
never copy or overwrite the installed helper or sudoers.

## Standard Sequence

1. Confirm SSH identity, main branch, and clean worktree.
2. Fetch `origin/main`; resolve `--target-ref`.
3. Require the target to equal `origin/main` and be a fast-forward.
4. Detect migration/schema paths. Stop because this repository has no formal
   migration framework.
5. Record old and target commits, tests, helper version, and `finalize`.
6. Back up SQLite with `scripts/server/backup.sh --execute`.
7. Re-fetch and ensure the target did not change.
8. Run `git pull --ff-only origin main`.
9. Run `uv sync --frozen` and backend pytest.
10. Run frontend `npm ci --include=dev`, lint, test, and build.
11. Write the target commit to `frontend/dist/.mediaops-release`.
12. Invoke `sudo -n /usr/local/sbin/mediaops-release finalize`.
13. Verify the localhost API.
14. Verify the public frontend, health API, and SPA route.
15. Record success and print old/new commits.

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

The application currently has no versioned migration tool. A change under
migration/alembic/SQL paths, `backend/app/db.py`, or backend models stops the
automated release pending a reviewed migration plan and backup.

## Failure and Rollback

Every stage is fail-closed. A failed test/build prevents `finalize`. A helper or
health failure may mean production is partially activated; report failure and
inspect before retrying.

Retain the old commit and backup. Prefer a reviewed Git revert or known-good
forward commit. Never use `git reset --hard`. Database restore requires stopped
writers, explicit authorization, ownership validation, integrity checks, and
post-restore health checks.

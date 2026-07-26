# Controlled Deployment Reference

## Safety Boundary

Run read-only diagnostics first. Before production modification, print and
confirm:

- SSH target alias and resolved host;
- current server commit and clean worktree;
- target `origin/main` commit;
- database and backup paths;
- non-root and root actions.

Never use an interactive sudo password. If `sudo -n` is not authorized, finish
the non-root stage and provide the administrator command list.

## Standard Sequence

Use `scripts/server/deploy.sh`; do not reproduce the sequence ad hoc.

1. Preflight SSH, paths, tools, branch, and worktree.
2. Resolve and confirm the exact `origin/main` commit.
3. Back up SQLite with `scripts/server/backup.sh --execute`.
4. Run `git pull --ff-only origin main`.
5. Run `uv sync --frozen` and `uv run pytest` in `backend/`.
6. Run `npm ci --include=dev --cache "$HOME/.npm-cache"`, lint, tests, and
   production build in `frontend/`.
7. Synchronize `frontend/dist/` to `/www/wwwroot/ops.fezern8n.com/`.
8. Restart `mediaops-api` and `mediaops-crawler-worker`.
9. Validate and reload BaoTa Nginx.
10. Check the public frontend, public health endpoint, SPA task route, and local
    API.
11. Record old commit, target commit, timestamp, and result.

Steps 7-9 require root or reviewed restricted sudo. The deploy tool is dry-run
by default. `--execute` performs backup and code preparation.
`--execute --root-stage` also attempts the root stage with `sudo -n`.

## Backup and Database Rules

The backup tool uses SQLite's backup API and runs an integrity check. It stores
the database copy, Git commit, UTC timestamp, and SHA-256 checksums under
`/var/backups/mediaops`.

It excludes `.env`, cookies, QR codes, private keys, virtual environments,
caches, and crawler result data.

The repository currently initializes its SQLite schema in application code and
does not have a formal migration framework. Do not claim otherwise. Establish a
migration mechanism before a future schema change, make migrations compatible
with existing data, back up production first, and document release order.

## Recovery Boundary

Do not automatically restore a backup or remove a database. A restore requires
a reviewed plan, stopped writers, explicit authorization, file ownership
verification, and post-restore integrity and application health checks.

Prefer a reviewed Git revert or a known-good release commit for code rollback.
Never use `git reset --hard` on production.

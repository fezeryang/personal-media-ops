#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"

DEPLOY_STAGE="argument-validation"

deployment_failure() {
    local exit_code="$1"
    local line_number="$2"
    trap - ERR
    printf 'ERROR: deployment failed stage=%s exit=%s line=%s\n' \
        "$DEPLOY_STAGE" "$exit_code" "$line_number" >&2
    printf 'ERROR: deployment_success=no; production may be partially prepared or activated—inspect before retrying\n' >&2
    exit "$exit_code"
}

deployment_abort() {
    local message="$1"
    local exit_code="${2:-3}"
    printf 'ERROR: deployment failed stage=%s: %s\n' \
        "$DEPLOY_STAGE" "$message" >&2
    printf 'ERROR: deployment_success=no; do not treat partial preparation or activation as a successful release\n' >&2
    exit "$exit_code"
}

trap 'deployment_failure "$?" "$LINENO"' ERR

usage() {
    cat <<'EOF'
Usage: deploy.sh [--host SSH_ALIAS] [--target-ref REF] [--allow-migrations] [--dry-run | --execute]

Run a controlled deployment of GitHub main through the restricted release helper.

Options:
  --host SSH_ALIAS  SSH config alias (default: MEDIAOPS_SSH_HOST or mediaops-prod)
  --target-ref REF  Expected origin/main commit or ref (default: origin/main)
  --allow-migrations
                    Permit reviewed Alembic migrations after backup and tests
  --dry-run          Print the deployment plan without connecting (default)
  --execute          Back up, pull, test, build, finalize, and verify
  -h, --help         Show this help

Dry-run never connects to production. Execute mode never installs or modifies
the release helper or sudoers and never reads .env, cookies, QR codes, browser
state, or SSH private keys.
EOF
}

print_plan() {
    cat <<'EOF'
Phases:
  confirm SSH identity and production worktree
  fetch origin/main and resolve the target ref
  reject non-fast-forward updates and unauthorized database migrations
  record the old commit
  create a consistent SQLite backup
  git pull --ff-only origin main
  uv sync --frozen
  backend pytest
  npm ci --include=dev
  frontend lint
  frontend test
  frontend build
  uv run alembic upgrade head (only for explicitly authorized migrations)
  restricted release helper finalize
  internal API health check
  public frontend and API health checks
  record and print old/new commits
EOF
}

record_deployment() {
    local ssh_host="$1"
    local old_commit="$2"
    local target_commit="$3"

    mediaops_ssh "$ssh_host" "bash -s -- ${old_commit} ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
old_commit="$1"
target_commit="$2"
record_path="/var/lib/mediaops/deployments.log"

if [[ -w "$(dirname -- "$record_path")" ]] &&
   { [[ ! -e "$record_path" ]] || [[ -w "$record_path" ]]; }; then
    printf '%s result=succeeded old_commit=%s target_commit=%s user=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$old_commit" \
        "$target_commit" \
        "$(id -un)" >> "$record_path"
else
    printf 'WARNING: deployment record is not writable: %s\n' "$record_path" >&2
fi
REMOTE
}

host_override=""
target_ref="origin/main"
execute=false
dry_run=false
allow_migrations=false

while (($# > 0)); do
    case "$1" in
        --host)
            mediaops_require_value "$1" "${2:-}"
            host_override="$2"
            shift 2
            ;;
        --target-ref)
            mediaops_require_value "$1" "${2:-}"
            target_ref="$2"
            shift 2
            ;;
        --execute)
            execute=true
            shift
            ;;
        --allow-migrations)
            allow_migrations=true
            shift
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            mediaops_die "unknown argument: $1"
            ;;
    esac
done

host="$(mediaops_resolve_host "$host_override")"
mediaops_validate_host "$host"
mediaops_validate_target_ref "$target_ref"
if [[ "$execute" == true && "$dry_run" == true ]]; then
    mediaops_die "--dry-run and --execute are mutually exclusive"
fi

mediaops_stage "Deployment plan"
printf 'Target server: %s\n' "$host"
printf 'Repository: %s\n' "$MEDIAOPS_APP_ROOT"
printf 'Target ref: %s\n' "$target_ref"
printf 'Current commit: inspect during execute preflight\n'
printf 'Target commit: resolve during execute preflight\n'
printf 'Database migration: inspect during execute preflight\n'
if [[ "$allow_migrations" == true ]]; then
    printf 'Migration authorization: granted\n'
else
    printf 'Migration authorization: required when detected\n'
fi
printf 'Database backup: required before pull\n'
printf 'Tests: uv sync --frozen; backend pytest; frontend npm ci, lint, test, build\n'
printf 'Helper path: %s\n' "$MEDIAOPS_RELEASE_HELPER"
printf 'Helper subcommand: finalize\n'
print_plan

if [[ "$execute" != true ]]; then
    printf 'Dry run only. No SSH connection or production mutation was attempted.\n'
    exit 0
fi

DEPLOY_STAGE="ssh-preflight"
mediaops_require_ssh "$host"

DEPLOY_STAGE="fetch-and-target-validation"
preflight="$(
    mediaops_ssh "$host" \
        "bash -s -- ${target_ref} ${allow_migrations}" <<'REMOTE'
set -Eeuo pipefail
target_ref="$1"
allow_migrations="$2"
repository="/opt/personal-media-ops"
node_bin_dir="/www/server/nodejs/v22.22.3/bin"
release_helper="/usr/local/sbin/mediaops-release"
export PATH="${node_bin_dir}:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

[[ "$(id -un)" == "mediaops" ]] || {
    printf 'ERROR: expected remote user mediaops, found: %s\n' "$(id -un)" >&2
    exit 2
}
[[ -d "${repository}/.git" ]] || {
    printf 'ERROR: repository not found: %s\n' "$repository" >&2
    exit 2
}
[[ "$(git -C "$repository" branch --show-current)" == "main" ]] || {
    printf 'ERROR: production repository is not on main\n' >&2
    exit 2
}
[[ -z "$(git -C "$repository" status --porcelain)" ]] || {
    printf 'ERROR: production worktree is not clean\n' >&2
    git -C "$repository" status --short >&2
    exit 3
}

command -v git >/dev/null
command -v uv >/dev/null
[[ -x "${node_bin_dir}/node" && -x "${node_bin_dir}/npm" ]] || {
    printf 'ERROR: fixed Node/npm runtime is unavailable: %s\n' "$node_bin_dir" >&2
    exit 2
}
[[ -x "$release_helper" ]] || {
    printf 'ERROR: restricted release helper is unavailable: %s\n' "$release_helper" >&2
    exit 2
}
[[ -d "${repository}/backend" && -d "${repository}/frontend" ]] || {
    printf 'ERROR: backend or frontend directory is missing\n' >&2
    exit 2
}

git -C "$repository" fetch origin main
old_commit="$(git -C "$repository" rev-parse HEAD)"
main_target="$(git -C "$repository" rev-parse origin/main)"
target_commit="$(
    git -C "$repository" rev-parse --verify "${target_ref}^{commit}" 2>/dev/null
)" || {
    printf 'ERROR: target ref does not resolve to a commit: %s\n' "$target_ref" >&2
    exit 2
}

[[ "$target_commit" == "$main_target" ]] || {
    printf 'ERROR: target ref %s resolves to %s, but origin/main is %s\n' \
        "$target_ref" "$target_commit" "$main_target" >&2
    exit 3
}
git -C "$repository" merge-base --is-ancestor "$old_commit" "$target_commit" || {
    printf 'ERROR: target is not a fast-forward of current HEAD\n' >&2
    exit 3
}

changed_paths="$(git -C "$repository" diff --name-only "$old_commit" "$target_commit")"
migration_paths="$(
    grep -E \
        '(^|/)(migrations?|alembic)(/|$)|\.sql$|^backend/app/db\.py$|^backend/app/models/' \
        <<<"$changed_paths" || true
)"
migration_state="no"
if [[ -n "$migration_paths" ]]; then
    migration_state="yes"
fi

helper_version="$(sudo -n "$release_helper" version)"
[[ "$helper_version" == "1" ]] || {
    printf 'ERROR: expected release helper version 1, found: %s\n' "$helper_version" >&2
    exit 3
}

printf 'remote_user=%s\n' "$(id -un)"
printf 'remote_host=%s\n' "$(hostname)"
printf 'worktree=clean\n'
printf 'old_commit=%s\n' "$old_commit"
printf 'target_commit=%s\n' "$target_commit"
printf 'target_ref=%s\n' "$target_ref"
printf 'database_migration=%s\n' "$migration_state"
printf 'migration_authorized=%s\n' "$allow_migrations"
printf 'database_backup=pending\n'
printf 'tests=backend-pytest,frontend-lint,frontend-test,frontend-build\n'
printf 'helper_version=%s\n' "$helper_version"
printf 'helper_subcommand=finalize\n'

if [[ "$migration_state" == "yes" && "$allow_migrations" != "true" ]]; then
    printf 'ERROR: database migration or schema paths require --allow-migrations after review:\n%s\n' \
        "$migration_paths" >&2
    exit 4
fi
REMOTE
)"

printf '%s\n' "$preflight"
old_commit="$(awk -F= '$1 == "old_commit" {print $2}' <<<"$preflight")"
target_commit="$(awk -F= '$1 == "target_commit" {print $2}' <<<"$preflight")"
migration_state="$(awk -F= '$1 == "database_migration" {print $2}' <<<"$preflight")"
migration_authorized="$(
    awk -F= '$1 == "migration_authorized" {print $2}' <<<"$preflight"
)"
helper_version="$(awk -F= '$1 == "helper_version" {print $2}' <<<"$preflight")"
mediaops_validate_full_commit "$old_commit"
mediaops_validate_full_commit "$target_commit"
if [[ "$migration_state" == "yes" && "$migration_authorized" != "true" ]]; then
    deployment_abort "database migration was not explicitly authorized"
fi
[[ "$helper_version" == "1" ]] ||
    deployment_abort "release helper version validation did not pass"

mediaops_stage "Confirmed production deployment"
printf 'Target server: %s\n' "$host"
printf 'Current commit: %s\n' "$old_commit"
printf 'Target commit: %s\n' "$target_commit"
printf 'Database migration: %s\n' "$migration_state"
printf 'Migration authorization: %s\n' "$migration_authorized"
printf 'Database backup: pending\n'
printf 'Tests: backend pytest; frontend lint, test, build\n'
printf 'Helper call after all gates: finalize\n'

DEPLOY_STAGE="sqlite-backup"
backup_output="$("${SCRIPT_DIR}/backup.sh" --host "$host" --execute)"
printf '%s\n' "$backup_output"
printf 'Database backup: completed\n'

DEPLOY_STAGE="git-sync-and-build"
mediaops_ssh "$host" \
    "bash -s -- ${target_commit} ${migration_state} ${migration_authorized}" <<'REMOTE'
set -Eeuo pipefail
target_commit="$1"
migration_state="$2"
migration_authorized="$3"
repository="/opt/personal-media-ops"
node_bin_dir="/www/server/nodejs/v22.22.3/bin"
database_path="/var/lib/mediaops/mediaops.db"
remote_stage="initialization"
export PATH="${node_bin_dir}:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

remote_failure() {
    local exit_code="$1"
    local line_number="$2"
    trap - ERR
    printf 'ERROR: remote deployment failed stage=%s exit=%s line=%s\n' \
        "$remote_stage" "$exit_code" "$line_number" >&2
    exit "$exit_code"
}
trap 'remote_failure "$?" "$LINENO"' ERR

remote_stage="worktree-recheck"
[[ -z "$(git -C "$repository" status --porcelain)" ]] || {
    printf 'ERROR: worktree became dirty after preflight\n' >&2
    exit 3
}

remote_stage="target-recheck"
git -C "$repository" fetch origin main
resolved_target="$(git -C "$repository" rev-parse origin/main)"
[[ "$resolved_target" == "$target_commit" ]] || {
    printf 'ERROR: origin/main changed after preflight: expected %s, found %s\n' \
        "$target_commit" "$resolved_target" >&2
    exit 3
}
git -C "$repository" merge-base --is-ancestor HEAD "$target_commit" || {
    printf 'ERROR: target is no longer a fast-forward\n' >&2
    exit 3
}

remote_stage="git-pull"
git -C "$repository" pull --ff-only origin main
[[ "$(git -C "$repository" rev-parse HEAD)" == "$target_commit" ]] || {
    printf 'ERROR: repository did not reach target commit\n' >&2
    exit 3
}

remote_stage="backend-dependency-sync"
(
    cd -- "${repository}/backend"
    uv sync --frozen
)

remote_stage="backend-pytest"
(
    cd -- "${repository}/backend"
    uv run pytest
)

remote_stage="frontend-npm-ci"
(
    cd -- "${repository}/frontend"
    npm ci --include=dev --cache "${HOME}/.npm-cache"
)

remote_stage="frontend-lint"
(
    cd -- "${repository}/frontend"
    npm run lint
)

remote_stage="frontend-test"
(
    cd -- "${repository}/frontend"
    npm run test
)

remote_stage="frontend-build"
(
    cd -- "${repository}/frontend"
    npm run build
)

[[ -f "${repository}/frontend/dist/index.html" ]] || {
    printf 'ERROR: frontend build did not create dist/index.html\n' >&2
    exit 3
}

if [[ "$migration_state" == "yes" ]]; then
    [[ "$migration_authorized" == "true" ]] || {
        printf 'ERROR: migration stage reached without authorization\n' >&2
        exit 4
    }
    remote_stage="database-migration"
    (
        cd -- "${repository}/backend"
        MEDIAOPS_DATABASE_PATH="$database_path" uv run alembic upgrade head
        MEDIAOPS_DATABASE_PATH="$database_path" uv run python -c \
            'from app.core.config import settings; from app.database_migrations import require_database_current; require_database_current(settings.database_path)'
    )
fi

printf '%s\n' "$target_commit" > "${repository}/frontend/dist/.mediaops-release"
printf 'remote_build=completed\n'
REMOTE

DEPLOY_STAGE="restricted-release-finalize"
mediaops_stage "Restricted production activation"
printf 'Helper path: %s\n' "$MEDIAOPS_RELEASE_HELPER"
printf 'Helper subcommand: finalize\n'
mediaops_ssh "$host" 'sudo -n /usr/local/sbin/mediaops-release finalize'

DEPLOY_STAGE="internal-health-check"
mediaops_stage "Internal API health check"
internal_health="$(
    mediaops_ssh "$host" \
        'curl -fsS --max-time 10 http://127.0.0.1:8000/api/health'
)"
grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"$internal_health" &&
    grep -Eq '"service"[[:space:]]*:[[:space:]]*"personal-media-ops-api"' <<<"$internal_health" ||
    deployment_abort "internal API returned an invalid health payload"
printf '%s\n' "$internal_health"

DEPLOY_STAGE="public-health-check"
"${SCRIPT_DIR}/healthcheck.sh" --host "$host"

DEPLOY_STAGE="deployment-record"
record_deployment "$host" "$old_commit" "$target_commit"

DEPLOY_STAGE="complete"
mediaops_stage "Deployment succeeded"
printf 'Old commit: %s\n' "$old_commit"
printf 'New commit: %s\n' "$target_commit"
printf 'Database migration: %s\n' "$migration_state"
printf 'Migration authorization: %s\n' "$migration_authorized"
printf 'Database backup: completed\n'
printf 'Helper subcommand: finalize\n'
printf 'Deployment success: yes\n'
printf 'Rollback preparation: retain the pre-deployment backup and use a reviewed Git revert; never use git reset --hard\n'

#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
    cat <<'EOF'
Usage: deploy.sh [--host SSH_ALIAS] [--commit SHA] [--dry-run | --execute] [--root-stage]

Prepare and optionally complete a controlled deployment of GitHub main.

Options:
  --host SSH_ALIAS  SSH config alias (default: MEDIAOPS_SSH_HOST or mediaops-prod)
  --commit SHA       Require origin/main to resolve to this 7-40 character SHA
  --dry-run          Print the deployment plan without connecting (default)
  --execute          Run backup, pull, dependency sync, tests, and frontend build
  --root-stage       Also run the reviewed root stage through non-interactive sudo
  -h, --help         Show this help

Without --execute, this is a dry run and makes no connection or server changes.
Without --root-stage, --execute stops after code preparation and prints the exact
commands that an authorized administrator must run.
EOF
}

print_phases() {
    cat <<'EOF'
Phases:
  preflight
  confirm target commit
  database backup
  git pull --ff-only
  backend dependency sync and tests
  frontend dependency install, lint, tests, and build
  static file synchronization
  application service restart
  Nginx validation and reload
  public and local health checks
  deployment record
EOF
}

print_root_commands() {
    cat <<'EOF'
Root stage commands pending human authorization:
  sudo -n /usr/bin/rsync --archive --delete --no-owner --no-group /opt/personal-media-ops/frontend/dist/ /www/wwwroot/ops.fezern8n.com/
  sudo -n /usr/bin/systemctl restart mediaops-api mediaops-crawler-worker
  sudo -n /www/server/nginx/sbin/nginx -t
  sudo -n /www/server/nginx/sbin/nginx -s reload
EOF
}

record_deployment() {
    local ssh_host="$1"
    local old_commit="$2"
    local target_commit="$3"
    local result="$4"

    mediaops_ssh "$ssh_host" "bash -s -- ${old_commit} ${target_commit} ${result}" <<'REMOTE'
set -Eeuo pipefail
old_commit="$1"
target_commit="$2"
result="$3"
record_path="/var/lib/mediaops/deployments.log"

if [[ -w "$(dirname -- "$record_path")" ]] &&
   { [[ ! -e "$record_path" ]] || [[ -w "$record_path" ]]; }; then
    printf '%s result=%s old_commit=%s target_commit=%s user=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$result" \
        "$old_commit" \
        "$target_commit" \
        "$(id -un)" >> "$record_path"
else
    printf 'WARNING: deployment record is not writable: %s\n' "$record_path" >&2
fi
REMOTE
}

host_override=""
requested_commit=""
execute=false
dry_run=false
root_stage=false

while (($# > 0)); do
    case "$1" in
        --host)
            mediaops_require_value "$1" "${2:-}"
            host_override="$2"
            shift 2
            ;;
        --commit)
            mediaops_require_value "$1" "${2:-}"
            requested_commit="$2"
            shift 2
            ;;
        --execute)
            execute=true
            shift
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        --root-stage)
            root_stage=true
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
if [[ -n "$requested_commit" ]]; then
    mediaops_validate_commit "$requested_commit"
fi
if [[ "$execute" == true && "$dry_run" == true ]]; then
    mediaops_die "--dry-run and --execute are mutually exclusive"
fi
if [[ "$root_stage" == true && "$execute" != true ]]; then
    mediaops_die "--root-stage requires --execute"
fi

mediaops_stage "Deployment plan"
printf 'Target server: %s\n' "$host"
printf 'Repository: %s\n' "$MEDIAOPS_APP_ROOT"
printf 'Branch: origin/main\n'
if [[ -n "$requested_commit" ]]; then
    printf 'Required target commit: %s\n' "$requested_commit"
else
    printf 'Required target commit: resolve origin/main during preflight\n'
fi
print_phases

if [[ "$execute" != true ]]; then
    printf 'Dry run only. No SSH connection or production mutation was attempted.\n'
    print_root_commands
    exit 0
fi

mediaops_require_ssh "$host"
mediaops_stage "Read-only preflight"

preflight="$(
    mediaops_ssh "$host" 'bash -s' <<'REMOTE'
set -Eeuo pipefail
repository="/opt/personal-media-ops"
node_bin_dir="/www/server/nodejs/v22.22.3/bin"
export PATH="${node_bin_dir}:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

[[ -d "${repository}/.git" ]] || {
    printf 'ERROR: repository not found: %s\n' "$repository" >&2
    exit 2
}

branch="$(git -C "$repository" branch --show-current)"
[[ "$branch" == "main" ]] || {
    printf 'ERROR: expected branch main, found: %s\n' "${branch:-detached}" >&2
    exit 2
}

[[ -z "$(git -C "$repository" status --porcelain)" ]] || {
    printf 'ERROR: production worktree is not clean\n' >&2
    git -C "$repository" status --short >&2
    exit 3
}

command -v git >/dev/null
command -v uv >/dev/null
[[ -x "${node_bin_dir}/node" ]] || {
    printf 'ERROR: Node binary not found: %s/node\n' "$node_bin_dir" >&2
    exit 2
}
[[ -x "${node_bin_dir}/npm" ]] || {
    printf 'ERROR: npm binary not found: %s/npm\n' "$node_bin_dir" >&2
    exit 2
}
[[ -d "${repository}/backend" && -d "${repository}/frontend" ]] || {
    printf 'ERROR: backend or frontend directory is missing\n' >&2
    exit 2
}

old_commit="$(git -C "$repository" rev-parse HEAD)"
target_commit="$(git -C "$repository" ls-remote origin refs/heads/main | awk 'NR == 1 {print $1}')"
[[ "$target_commit" =~ ^[0-9a-f]{40}$ ]] || {
    printf 'ERROR: could not resolve origin/main\n' >&2
    exit 2
}

printf 'old_commit=%s\n' "$old_commit"
printf 'target_commit=%s\n' "$target_commit"
printf 'remote_user=%s\n' "$(id -un)"
printf 'remote_host=%s\n' "$(hostname)"
REMOTE
)"

printf '%s\n' "$preflight"
old_commit="$(awk -F= '$1 == "old_commit" {print $2}' <<<"$preflight")"
target_commit="$(awk -F= '$1 == "target_commit" {print $2}' <<<"$preflight")"
mediaops_validate_full_commit "$old_commit"
mediaops_validate_full_commit "$target_commit"

if [[ -n "$requested_commit" && "$target_commit" != "$requested_commit"* ]]; then
    mediaops_die "origin/main resolved to ${target_commit}, not requested ${requested_commit}"
fi

mediaops_stage "Confirmed production change"
printf 'Target server: %s\n' "$host"
printf 'Old commit: %s\n' "$old_commit"
printf 'Target commit: %s\n' "$target_commit"
printf 'Actions: backup database; fast-forward main; run all backend/frontend gates; build dist\n'
if [[ "$root_stage" == true ]]; then
    printf 'Root stage: enabled through sudo -n; no password prompt will be used\n'
else
    printf 'Root stage: disabled; static sync, service restart, and Nginx reload will remain pending\n'
fi

"${SCRIPT_DIR}/backup.sh" --host "$host" --execute

mediaops_stage "Pulling and validating application code"
mediaops_ssh "$host" "bash -s -- ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
target_commit="$1"
repository="/opt/personal-media-ops"
node_bin_dir="/www/server/nodejs/v22.22.3/bin"
export PATH="${node_bin_dir}:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

[[ -z "$(git -C "$repository" status --porcelain)" ]] || {
    printf 'ERROR: worktree became dirty after preflight\n' >&2
    exit 3
}

git -C "$repository" pull --ff-only origin main
current_commit="$(git -C "$repository" rev-parse HEAD)"
[[ "$current_commit" == "$target_commit" ]] || {
    printf 'ERROR: expected commit %s, found %s\n' "$target_commit" "$current_commit" >&2
    exit 3
}

(
    cd -- "${repository}/backend"
    uv sync --frozen
    uv run pytest
)

(
    cd -- "${repository}/frontend"
    npm ci --include=dev --cache "${HOME}/.npm-cache"
    npm run lint
    npm run test
    npm run build
)

[[ -f "${repository}/frontend/dist/index.html" ]] || {
    printf 'ERROR: frontend build did not create dist/index.html\n' >&2
    exit 3
}
printf '%s\n' "$target_commit" > "${repository}/frontend/dist/.mediaops-release"
REMOTE

if [[ "$root_stage" != true ]]; then
    record_deployment "$host" "$old_commit" "$target_commit" "code-prepared-root-pending"
    mediaops_stage "Code preparation complete; production activation pending"
    print_root_commands
    printf 'After an authorized administrator runs the commands, verify with:\n'
    printf '  %q --host %q --with-ssh\n' "${SCRIPT_DIR}/healthcheck.sh" "$host"
    printf 'Rollback note: keep the backup and deploy a reviewed Git revert or known-good commit; do not use git reset --hard.\n'
    exit 3
fi

mediaops_stage "Running authorized root stage"
mediaops_ssh "$host" 'bash -s' <<'REMOTE'
set -Eeuo pipefail

sudo -n /usr/bin/rsync \
    --archive \
    --delete \
    --no-owner \
    --no-group \
    /opt/personal-media-ops/frontend/dist/ \
    /www/wwwroot/ops.fezern8n.com/

sudo -n /usr/bin/systemctl restart mediaops-api mediaops-crawler-worker
sudo -n /www/server/nginx/sbin/nginx -t
sudo -n /www/server/nginx/sbin/nginx -s reload
REMOTE

mediaops_stage "Post-deployment health checks"
"${SCRIPT_DIR}/healthcheck.sh" --host "$host" --with-ssh
record_deployment "$host" "$old_commit" "$target_commit" "succeeded"

mediaops_stage "Deployment complete"
printf 'Deployed commit: %s\n' "$target_commit"
printf 'Database backup was created before code changes.\n'
printf 'Rollback note: use the backup only after stopping writers and following a reviewed restore plan.\n'

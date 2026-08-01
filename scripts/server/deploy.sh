#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"

readonly DEPLOY_STATE_DIR="/var/lib/mediaops/deploy-state"

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
Usage: deploy.sh [--host SSH_ALIAS] [--target-ref REF] [--allow-migrations]
                 [--resume] [--dry-run | --execute]

Run a controlled, staged deployment of GitHub main through the restricted
release helper. Every stage uses its own short-lived SSH connection and records
a completion marker on the server, so an interrupted deployment can be resumed.

Options:
  --host SSH_ALIAS  SSH config alias (default: MEDIAOPS_SSH_HOST or mediaops-prod)
  --target-ref REF  Expected origin/main commit or ref (default: origin/main)
  --allow-migrations
                    Permit reviewed Alembic migrations after backup and tests
  --resume           Skip stages already recorded as done on the server for the
                     same target commit (preflight and verify always run)
  --dry-run          Print the deployment plan without connecting (default)
  --execute          Back up, pull, test, build, finalize, and verify

Dry-run never connects to production. Execute mode never installs or modifies
the release helper or sudoers and never reads .env, cookies, QR codes, browser
state, or SSH private keys.
EOF
}

print_plan() {
    cat <<'EOF'
Stages (each in its own SSH session, recorded in /var/lib/mediaops/deploy-state/<target-commit>.stages):
  preflight: confirm SSH identity, worktree, target ref, migration authorization, helper version
  backup: create a consistent SQLite backup
  git-sync: fetch origin/main and git pull --ff-only to the fixed target commit
  model-gateway-key: create or verify the fixed 32-byte gateway master key
                     with directory mode 0700 and file mode 0600
  runner-sync: install the reviewed MediaCrawler runner copy the Worker executes
               (/var/lib/mediaops/bin/run_mediacrawler.py), backing up any
               differing installed copy first
  backend-test: uv sync --frozen; backend pytest
  frontend-build: npm ci; frontend lint, test, build; write the frontend release marker
  migrate: uv run alembic upgrade head (only for explicitly authorized migrations)
  finalize: restricted release helper finalize (marker-verified fallback for the
            deployed helper's known .user.ini publish failure)
  verify: internal API health, public health checks, deployment record

Transport hardening:
  long-running stages use SSH keepalives (ServerAliveInterval=15, CountMax=8)
  an SSH exit of 255 triggers one reconnect to recheck the remote stage marker
  --resume skips stages already marked done for the same target commit
  without --resume, execute clears the target commit's stage markers first
EOF
}

# --- stage marker helpers -----------------------------------------------

resume_markers=""

load_resume_markers() {
    resume_markers="$(
        mediaops_ssh "$host" \
            "cat -- '${DEPLOY_STATE_DIR}/${target_commit}.stages' 2>/dev/null || true"
    )"
}

stage_recorded_locally() {
    local stage="$1"
    [[ -n "$resume_markers" ]] && grep -q "^${stage}=done" <<<"$resume_markers"
}

stage_done_remotely() {
    local stage="$1"
    mediaops_ssh "$host" \
        "grep -q -- '^${stage}=done' '${DEPLOY_STATE_DIR}/${target_commit}.stages'"
}

# A non-resume execute run starts from a clean marker file so a stale marker
# from an earlier attempt can never satisfy the exit-255 marker recheck for a
# stage that genuinely failed in this run.
reset_stage_markers() {
    mediaops_ssh "$host" \
        "bash -s -- reset-stage-markers ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
state_dir="/var/lib/mediaops/deploy-state"
mkdir -p -- "$state_dir"
: > "${state_dir}/${target_commit}.stages"
REMOTE
}

write_stage_marker() {
    local stage="$1"
    mediaops_ssh "$host" \
        "bash -s -- write-stage-marker ${target_commit} ${stage}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
stage="$2"
state_dir="/var/lib/mediaops/deploy-state"
mkdir -p -- "$state_dir"
printf '%s=done %s\n' "$stage" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
REMOTE
}

# Run one marker-tracked stage: honor --resume, and treat an SSH transport
# error (exit 255) as recoverable when the remote marker proves completion.
run_marker_stage() {
    local stage="$1"
    local runner="$2"
    DEPLOY_STAGE="$stage"
    mediaops_stage "Stage: ${stage}"
    if [[ "$resume" == true ]] && stage_recorded_locally "$stage"; then
        mediaops_info "resume: stage already completed for ${target_commit}; skipping: ${stage}"
        return 0
    fi
    local status=0
    "$runner" || status=$?
    if ((status == 255)); then
        mediaops_warn "stage=${stage} SSH exited 255 (transport error); reconnecting once to recheck the remote stage marker"
        if stage_done_remotely "$stage"; then
            mediaops_warn "SSH transport anomaly, stage completed remotely: ${stage}"
            status=0
        fi
    fi
    ((status == 0)) ||
        deployment_abort "stage did not complete: ${stage}" "$status"
}

# --- stage runners (pipeline order) --------------------------------------

stage_backup() {
    "${SCRIPT_DIR}/backup.sh" --host "$host" --execute &&
        write_stage_marker backup
}

stage_git_sync() {
    mediaops_ssh_long "$host" "bash -s -- git-sync ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
repository="/opt/personal-media-ops"
state_dir="/var/lib/mediaops/deploy-state"

[[ -z "$(git -C "$repository" status --porcelain)" ]] || {
    printf 'ERROR: worktree became dirty after preflight\n' >&2
    exit 3
}

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
git -C "$repository" pull --ff-only origin main
[[ "$(git -C "$repository" rev-parse HEAD)" == "$target_commit" ]] || {
    printf 'ERROR: repository did not reach target commit\n' >&2
    exit 3
}
mkdir -p -- "$state_dir"
printf 'git-sync=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
printf 'git_sync=completed\n'
REMOTE
}

# The model gateway master key is deliberately outside the repository,
# database, environment file, logs, and database-backup tree. Production's
# mediaops user owns /var/lib/mediaops, so this stage needs no root helper.
# Existing key material is never read or replaced; malformed state fails shut.
stage_model_gateway_key() {
    mediaops_ssh "$host" "bash -s -- model-gateway-key ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
secret_dir="/var/lib/mediaops/secrets"
key_file="${secret_dir}/model-gateway-master.key"
state_dir="/var/lib/mediaops/deploy-state"

[[ "$(id -un)" == "mediaops" ]] || {
    printf 'ERROR: model gateway key stage requires the mediaops user\n' >&2
    exit 2
}
if [[ -e "$secret_dir" && ( ! -d "$secret_dir" || -L "$secret_dir" ) ]]; then
    printf 'ERROR: model gateway secret directory is not a real directory\n' >&2
    exit 3
fi
mkdir -p -- "$secret_dir"
[[ "$(stat -c '%U' -- "$secret_dir")" == "mediaops" ]] || {
    printf 'ERROR: model gateway secret directory owner is invalid\n' >&2
    exit 3
}
chmod 700 -- "$secret_dir"

key_state="present"
if [[ -e "$key_file" ]]; then
    [[ -f "$key_file" && ! -L "$key_file" ]] || {
        printf 'ERROR: model gateway key is not a regular file\n' >&2
        exit 3
    }
    [[ "$(stat -c '%U' -- "$key_file")" == "mediaops" ]] || {
        printf 'ERROR: model gateway key owner is invalid\n' >&2
        exit 3
    }
    [[ "$(stat -c '%s' -- "$key_file")" == "32" ]] || {
        printf 'ERROR: model gateway key length is invalid\n' >&2
        exit 3
    }
else
    KEY_FILE="$key_file" python3 - <<'PY'
import os

path = os.environ["KEY_FILE"]
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
if hasattr(os, "O_NOFOLLOW"):
    flags |= os.O_NOFOLLOW
descriptor = os.open(path, flags, 0o600)
try:
    written = os.write(descriptor, os.urandom(32))
    if written != 32:
        raise RuntimeError("short write while creating gateway key")
    os.fsync(descriptor)
finally:
    os.close(descriptor)
PY
    key_state="created"
fi
chmod 600 -- "$key_file"
mkdir -p -- "$state_dir"
printf 'model-gateway-key=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
printf 'model_gateway_master_key=%s directory_mode=0700 file_mode=0600\n' \
    "$key_state"
REMOTE
}

# The Worker executes the reviewed runner COPY at
# /var/lib/mediaops/bin/run_mediacrawler.py (settings default and production
# MEDIACRAWLER_RUNNER), not the repository file. Sync it on every deployment so
# the installed copy can never drift from the repository version again.
stage_runner_sync() {
    mediaops_ssh "$host" "bash -s -- runner-sync ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
src="/opt/personal-media-ops/scripts/crawler/run_mediacrawler.py"
dst="/var/lib/mediaops/bin/run_mediacrawler.py"
state_dir="/var/lib/mediaops/deploy-state"

[[ -f "$src" ]] || {
    printf 'ERROR: reviewed runner source is missing from the repository: %s\n' \
        "$src" >&2
    exit 3
}
mkdir -p -- /var/lib/mediaops/bin
if [[ -f "$dst" ]] && cmp -s -- "$src" "$dst"; then
    printf 'runner_sync=unchanged\n'
else
    if [[ -f "$dst" ]]; then
        install -m 750 -- "$dst" "${dst}.backup-$(date -u +%Y%m%dT%H%M%SZ)"
    fi
    install -m 750 -- "$src" "$dst"
    rm -rf -- /var/lib/mediaops/bin/__pycache__
    printf 'runner_sync=updated sha256=%s\n' \
        "$(sha256sum -- "$dst" | awk '{print $1}')"
fi
mkdir -p -- "$state_dir"
printf 'runner-sync=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
REMOTE
}

stage_backend_test() {
    mediaops_ssh_long "$host" "bash -s -- backend-test ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
repository="/opt/personal-media-ops"
state_dir="/var/lib/mediaops/deploy-state"
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

cd -- "${repository}/backend"
uv sync --frozen
uv run pytest
mkdir -p -- "$state_dir"
printf 'backend-test=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
printf 'backend_test=completed\n'
REMOTE
}

stage_frontend_build() {
    mediaops_ssh_long "$host" "bash -s -- frontend-build ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
repository="/opt/personal-media-ops"
node_bin_dir="/www/server/nodejs/v22.22.3/bin"
state_dir="/var/lib/mediaops/deploy-state"
export PATH="${node_bin_dir}:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

cd -- "${repository}/frontend"
npm ci --include=dev --cache "${HOME}/.npm-cache"
npm run lint
npm run test
npm run build
[[ -f "${repository}/frontend/dist/index.html" ]] || {
    printf 'ERROR: frontend build did not create dist/index.html\n' >&2
    exit 3
}
printf '%s\n' "$target_commit" > "${repository}/frontend/dist/.mediaops-release"
mkdir -p -- "$state_dir"
printf 'frontend-build=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
printf 'frontend_build=completed\n'
REMOTE
}

stage_migrate() {
    mediaops_ssh_long "$host" "bash -s -- migrate ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
repository="/opt/personal-media-ops"
database_path="/var/lib/mediaops/mediaops.db"
state_dir="/var/lib/mediaops/deploy-state"
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"

cd -- "${repository}/backend"
MEDIAOPS_DATABASE_PATH="$database_path" uv run alembic upgrade head
MEDIAOPS_DATABASE_PATH="$database_path" uv run python -c \
    'from app.core.config import settings; from app.database_migrations import require_database_current; require_database_current(settings.database_path)'
mkdir -p -- "$state_dir"
printf 'migrate=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
printf 'database_migration=completed\n'
REMOTE
}

stage_finalize() {
    mediaops_ssh_long "$host" "bash -s -- finalize ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
state_dir="/var/lib/mediaops/deploy-state"

sudo -n /usr/local/sbin/mediaops-release finalize
mkdir -p -- "$state_dir"
printf 'finalize=done %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "${state_dir}/${target_commit}.stages"
REMOTE
}

# Compare the published and built frontend release markers against the target
# commit without touching any sensitive file.
finalize_marker_parity() {
    mediaops_ssh "$host" "bash -s -- verify-publish-marker ${target_commit}" <<'REMOTE'
set -Eeuo pipefail
shift
target_commit="$1"
published_marker="/www/wwwroot/ops.fezern8n.com/.mediaops-release"
built_marker="/opt/personal-media-ops/frontend/dist/.mediaops-release"
published_commit="missing"
built_commit="missing"
if [[ -r "$published_marker" ]]; then
    published_commit="$(tr -d '[:space:]' < "$published_marker")"
fi
if [[ -r "$built_marker" ]]; then
    built_commit="$(tr -d '[:space:]' < "$built_marker")"
fi
printf 'published_release=%s\n' "$published_commit"
printf 'built_release=%s\n' "$built_commit"
if [[ "$published_commit" == "$target_commit" &&
      "$built_commit" == "$target_commit" ]]; then
    printf 'release_marker_parity=match\n'
else
    printf 'release_marker_parity=mismatch\n'
fi
REMOTE
}

# The deployed helper v1 aborts finalize when rsync cannot unlink the
# immutable BaoTa .user.ini file, even though the publish itself completed.
# If both release markers already equal the target commit, finish the
# activation with the individually allowlisted helper subcommands instead.
wait_for_fallback_api() {
    local attempt
    for attempt in $(seq 1 20); do
        if mediaops_ssh "$host" \
            'curl -fsS --max-time 10 http://127.0.0.1:8000/api/health'; then
            mediaops_info "fallback API readiness confirmed on attempt ${attempt}"
            return 0
        fi
        sleep 1
    done
    return 1
}

finalize_fallback() {
    local finalize_status="$1"
    local parity

    mediaops_warn "helper finalize failed (exit=${finalize_status}); checking published release markers before any fallback"
    parity="$(finalize_marker_parity)" ||
        deployment_abort "could not inspect release markers after helper finalize failure" "$finalize_status"
    printf '%s\n' "$parity"
    grep -q '^release_marker_parity=match$' <<<"$parity" ||
        deployment_abort "helper finalize failed and release markers do not match target ${target_commit}; production may be partially activated" "$finalize_status"

    mediaops_warn "finalize fallback: publish already matches the target commit; completing activation with individual helper subcommands"
    mediaops_ssh "$host" 'sudo -n /usr/local/sbin/mediaops-release restart-services' ||
        deployment_abort "fallback restart-services did not succeed"
    wait_for_fallback_api ||
        deployment_abort "fallback API did not become ready after restart-services"
    mediaops_ssh "$host" 'sudo -n /usr/local/sbin/mediaops-release nginx-reload' ||
        deployment_abort "fallback nginx-reload did not succeed"
    mediaops_ssh "$host" 'sudo -n /usr/local/sbin/mediaops-release verify' ||
        deployment_abort "fallback verify did not succeed"
    write_stage_marker finalize ||
        deployment_abort "could not record the finalize stage marker after fallback"
    mediaops_info "finalize fallback succeeded: restart-services, nginx-reload, and verify completed individually"
}

run_finalize_stage() {
    DEPLOY_STAGE="finalize"
    mediaops_stage "Stage: finalize"
    printf 'Helper path: %s\n' "$MEDIAOPS_RELEASE_HELPER"
    printf 'Helper subcommand: finalize\n'
    if [[ "$resume" == true ]] && stage_recorded_locally finalize; then
        mediaops_info "resume: stage already completed for ${target_commit}; skipping: finalize"
        return 0
    fi
    local status=0
    stage_finalize || status=$?
    if ((status == 255)); then
        mediaops_warn "stage=finalize SSH exited 255 (transport error); reconnecting once to recheck the remote stage marker"
        if stage_done_remotely finalize; then
            mediaops_warn "SSH transport anomaly, stage completed remotely: finalize"
            status=0
        fi
    fi
    if ((status != 0)); then
        finalize_fallback "$status"
    fi
}

record_deployment() {
    local ssh_host="$1"
    local old_commit="$2"
    local target_commit="$3"
    local external_observer="$4"

    mediaops_ssh "$ssh_host" \
        "bash -s -- record-deployment ${old_commit} ${target_commit} ${external_observer}" <<'REMOTE'
set -Eeuo pipefail
shift
old_commit="$1"
target_commit="$2"
external_observer="$3"
record_path="/var/lib/mediaops/deployments.log"

if [[ -w "$(dirname -- "$record_path")" ]] &&
   { [[ ! -e "$record_path" ]] || [[ -w "$record_path" ]]; }; then
    printf '%s result=succeeded old_commit=%s target_commit=%s external_observer=%s user=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$old_commit" \
        "$target_commit" \
        "$external_observer" \
        "$(id -un)" >> "$record_path"
else
    printf 'WARNING: deployment record is not writable: %s\n' "$record_path" >&2
fi
REMOTE
}

verify_server_sni_loopback() {
    mediaops_ssh "$host" \
        "bash -s -- verify-sni-loopback ${MEDIAOPS_PUBLIC_URL#https://}" <<'REMOTE'
set -Eeuo pipefail
shift
public_host="$1"

[[ "$public_host" =~ ^[A-Za-z0-9.-]+$ ]] || {
    printf 'ERROR: invalid public host for SNI loopback verification\n' >&2
    exit 3
}

sudo -n /usr/local/sbin/mediaops-release status

check_sni_route() {
    local label="$1"
    local path="$2"
    local require_health_json="$3"
    local response
    local status
    local body

    response="$(
        curl -sS -L --max-time 15 \
            --resolve "${public_host}:443:127.0.0.1" \
            -w $'\n%{http_code}' \
            "https://${public_host}${path}"
    )"
    status="${response##*$'\n'}"
    body="${response%$'\n'*}"
    [[ "$status" =~ ^2[0-9][0-9]$ ]] || {
        printf 'ERROR: sni_%s=http-%s\n' "$label" "$status" >&2
        return 1
    }
    if [[ "$require_health_json" == "yes" ]]; then
        grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"$body" &&
            grep -Eq '"service"[[:space:]]*:[[:space:]]*"personal-media-ops-api"' <<<"$body" ||
            {
                printf 'ERROR: sni_%s=invalid-health-payload\n' "$label" >&2
                return 1
            }
    fi
    printf 'sni_%s=ok http=%s host=%s\n' "$label" "$status" "$public_host"
}

check_sni_route frontend / no
check_sni_route public_api /api/health yes
check_sni_route crawler_route /crawler/tasks no
REMOTE
}

host_override=""
target_ref="origin/main"
execute=false
dry_run=false
allow_migrations=false
resume=false

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
        --resume)
            resume=true
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
if [[ "$resume" == true ]]; then
    printf 'Resume mode: enabled (stages already marked done for the target commit are skipped)\n'
else
    printf 'Resume mode: disabled\n'
fi
printf 'Stage markers: %s/<target-commit>.stages\n' "$DEPLOY_STATE_DIR"
print_plan

if [[ "$execute" != true ]]; then
    printf 'Dry run only. No SSH connection or production mutation was attempted.\n'
    exit 0
fi

DEPLOY_STAGE="ssh-preflight"
mediaops_require_ssh "$host"

DEPLOY_STAGE="preflight"
preflight="$(
    mediaops_ssh "$host" \
        "bash -s -- preflight ${target_ref} ${allow_migrations}" <<'REMOTE'
set -Eeuo pipefail
shift
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

if ! helper_version="$(sudo -n "$release_helper" version)"; then
    printf 'ERROR: restricted release helper is unavailable through sudo -n: %s\n' \
        "$release_helper" >&2
    exit 2
fi
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

if [[ "$resume" == true ]]; then
    DEPLOY_STAGE="resume-state"
    load_resume_markers
    if [[ -n "$resume_markers" ]]; then
        mediaops_info "resume: completed stages recorded for ${target_commit}:"
        printf '%s\n' "$resume_markers"
    else
        mediaops_info "resume: no completed stages recorded for ${target_commit}"
    fi
else
    DEPLOY_STAGE="stage-state"
    reset_stage_markers
    mediaops_info "non-resume run: cleared stage markers for ${target_commit}"
fi

run_marker_stage backup stage_backup
printf 'Database backup: completed\n'

run_marker_stage git-sync stage_git_sync
run_marker_stage model-gateway-key stage_model_gateway_key
run_marker_stage runner-sync stage_runner_sync
run_marker_stage backend-test stage_backend_test
run_marker_stage frontend-build stage_frontend_build

if [[ "$migration_state" == "yes" ]]; then
    [[ "$migration_authorized" == "true" ]] ||
        deployment_abort "migration stage reached without authorization" 4
    run_marker_stage migrate stage_migrate
else
    mediaops_info "migrate: no database migration detected; stage skipped"
fi

run_finalize_stage

DEPLOY_STAGE="verify"
mediaops_stage "Stage: verify"
internal_health="$(
    mediaops_ssh "$host" \
        'curl -fsS --max-time 10 http://127.0.0.1:8000/api/health'
)"
grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"$internal_health" &&
    grep -Eq '"service"[[:space:]]*:[[:space:]]*"personal-media-ops-api"' <<<"$internal_health" ||
    deployment_abort "internal API returned an invalid health payload"
printf '%s\n' "$internal_health"

external_observer_status="passed"
public_health_status=0
public_health_output=""
public_health_output="$(
    "${SCRIPT_DIR}/healthcheck.sh" --host "$host" 2>&1
)" || public_health_status=$?
printf '%s\n' "$public_health_output"
if ((public_health_status != 0)); then
    if ! grep -Eq \
        '^(frontend|public_api|crawler_route)=(connection-failed|http-(403|525))[[:space:]]' \
        <<<"$public_health_output"; then
        deployment_abort \
            "public health check failed outside the approved external-observer exception" \
            "$public_health_status"
    fi
    mediaops_warn \
        "external observer could not validate the public route; checking helper, Nginx, services, localhost API, and the public hostname/certificate through production SNI loopback"
    verify_server_sni_loopback ||
        deployment_abort \
            "external observer failed and production SNI loopback verification did not pass" \
            "$public_health_status"
    external_observer_status="failed-nonblocking"
    mediaops_warn \
        "external observer failure recorded as non-blocking after production SNI loopback verification passed"
fi

DEPLOY_STAGE="deployment-record"
record_deployment \
    "$host" \
    "$old_commit" \
    "$target_commit" \
    "$external_observer_status"

DEPLOY_STAGE="complete"
mediaops_stage "Deployment succeeded"
printf 'Old commit: %s\n' "$old_commit"
printf 'New commit: %s\n' "$target_commit"
printf 'Database migration: %s\n' "$migration_state"
printf 'Migration authorization: %s\n' "$migration_authorized"
printf 'Database backup: completed\n'
printf 'Helper subcommand: finalize\n'
printf 'External observer: %s\n' "$external_observer_status"
printf 'Deployment success: yes\n'
printf 'Rollback preparation: retain the pre-deployment backup and use a reviewed Git revert; never use git reset --hard\n'

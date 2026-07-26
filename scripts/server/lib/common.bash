#!/usr/bin/env bash

readonly MEDIAOPS_DEFAULT_SSH_HOST="mediaops-prod"
readonly MEDIAOPS_APP_ROOT="/opt/personal-media-ops"
readonly MEDIAOPS_BACKEND_ROOT="${MEDIAOPS_APP_ROOT}/backend"
readonly MEDIAOPS_FRONTEND_ROOT="${MEDIAOPS_APP_ROOT}/frontend"
readonly MEDIAOPS_FRONTEND_DIST="${MEDIAOPS_FRONTEND_ROOT}/dist"
readonly MEDIAOPS_STATIC_ROOT="/www/wwwroot/ops.fezern8n.com"
readonly MEDIAOPS_DATABASE="/var/lib/mediaops/mediaops.db"
readonly MEDIAOPS_BACKUP_ROOT="/var/backups/mediaops"
readonly MEDIAOPS_NGINX="/www/server/nginx/sbin/nginx"
readonly MEDIAOPS_NODE_BIN="/www/server/nodejs/v22.22.3/bin"
readonly MEDIAOPS_PUBLIC_URL="https://ops.fezern8n.com"
readonly MEDIAOPS_API_SERVICE="mediaops-api"
readonly MEDIAOPS_WORKER_SERVICE="mediaops-crawler-worker"

readonly -a MEDIAOPS_SSH_OPTIONS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
)

mediaops_error() {
  local exit_code="$1"
  local line_number="$2"
  printf 'ERROR: command failed (exit=%s, line=%s)\n' \
    "$exit_code" "$line_number" >&2
  return "$exit_code"
}

mediaops_enable_error_trap() {
  trap 'mediaops_error "$?" "$LINENO"' ERR
}

mediaops_stage() {
  printf '\n==> %s\n' "$1"
}

mediaops_info() {
  printf 'INFO: %s\n' "$1"
}

mediaops_warn() {
  printf 'WARN: %s\n' "$1" >&2
}

mediaops_die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit "${2:-2}"
}

mediaops_require_command() {
  command -v "$1" >/dev/null 2>&1 ||
    mediaops_die "required command not found: $1"
}

mediaops_require_value() {
  local option="$1"
  local value="${2:-}"
  [[ -n "$value" && "$value" != --* ]] ||
    mediaops_die "${option} requires a value"
}

mediaops_resolve_host() {
  local explicit_host="${1:-}"
  printf '%s\n' "${explicit_host:-${MEDIAOPS_SSH_HOST:-$MEDIAOPS_DEFAULT_SSH_HOST}}"
}

mediaops_validate_host() {
  local host="$1"
  [[ "$host" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
    mediaops_die "invalid SSH host alias: $host"
}

mediaops_validate_lines() {
  local lines="$1"
  [[ "$lines" =~ ^[1-9][0-9]*$ ]] ||
    mediaops_die "--lines must be a positive integer"
  ((lines <= 5000)) || mediaops_die "--lines must not exceed 5000"
}

mediaops_validate_commit() {
  local commit="$1"
  [[ "$commit" =~ ^[0-9a-fA-F]{7,40}$ ]] ||
    mediaops_die "--commit must be a 7-40 character hexadecimal Git commit"
}

mediaops_validate_full_commit() {
  local commit="$1"
  [[ "$commit" =~ ^[0-9a-fA-F]{40}$ ]] ||
    mediaops_die "expected a full 40-character Git commit, received: $commit"
}

mediaops_validate_uuid() {
  local task_id="$1"
  [[ "$task_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$ ]] ||
    mediaops_die "--task requires a canonical UUID"
}

mediaops_ssh() {
  local host="$1"
  shift
  ssh "${MEDIAOPS_SSH_OPTIONS[@]}" "$host" "$@"
}

mediaops_require_ssh_alias() {
  local host="$1"
  mediaops_require_command ssh
  local config
  local resolved_host
  local resolved_user
  local local_user

  if ! config="$(ssh -G "$host" 2>/dev/null)"; then
    mediaops_die "could not resolve SSH configuration for '${host}'"
  fi
  resolved_host="$(awk '$1 == "hostname" {print $2; exit}' <<<"$config")"
  resolved_user="$(awk '$1 == "user" {print $2; exit}' <<<"$config")"
  local_user="$(id -un)"

  if [[ -z "$resolved_host" || -z "$resolved_user" ]] ||
    [[ "$resolved_host" == "$host" && "$resolved_user" == "$local_user" ]]; then
    mediaops_die "SSH alias '${host}' is not configured; copy infra/ssh/config.example into ~/.ssh/config and install the private key locally"
  fi
}

mediaops_require_ssh() {
  local host="$1"
  mediaops_require_ssh_alias "$host"
  if ! ssh "${MEDIAOPS_SSH_OPTIONS[@]}" "$host" true >/dev/null 2>&1; then
    mediaops_die "non-interactive SSH failed for '${host}'; check SSH config, key permissions, and network access"
  fi
}

#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
  cat <<'EOF'
Usage: healthcheck.sh [--base-url URL] [--with-ssh] [--host SSH_ALIAS]

Check the public frontend, public API health, SPA task route, and optionally
the localhost API over SSH.

Options:
  --base-url URL    Public base URL (default: https://ops.fezern8n.com)
  --with-ssh        Also check http://127.0.0.1:8000/api/health over SSH
  --host SSH_ALIAS  Override MEDIAOPS_SSH_HOST (default: mediaops-prod)
  -h, --help        Show this help
EOF
}

base_url="${MEDIAOPS_PUBLIC_URL}"
host_override=""
with_ssh=0

while (($# > 0)); do
  case "$1" in
    --base-url)
      mediaops_require_value "$1" "${2:-}"
      base_url="${2%/}"
      shift 2
      ;;
    --with-ssh)
      with_ssh=1
      shift
      ;;
    --host)
      mediaops_require_value "$1" "${2:-}"
      host_override="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      mediaops_die "unknown option: $1"
      ;;
  esac
done

[[ "$base_url" =~ ^https?://[A-Za-z0-9._:-]+$ ]] ||
  mediaops_die "--base-url must be an HTTP(S) origin without a path"
mediaops_require_command curl

check_http() {
  local label="$1"
  local url="$2"
  local require_health_json="$3"
  local response
  local status
  local body

  if ! response="$(curl -sS -L --max-time 15 -w $'\n%{http_code}' "$url")"; then
    printf '%s=connection-failed url=%s\n' "$label" "$url" >&2
    return 1
  fi
  status="${response##*$'\n'}"
  body="${response%$'\n'*}"
  if [[ ! "$status" =~ ^2[0-9][0-9]$ ]]; then
    printf '%s=http-%s url=%s\n' "$label" "$status" "$url" >&2
    return 1
  fi
  if [[ "$require_health_json" == "yes" ]]; then
    grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"$body" &&
      grep -Eq '"service"[[:space:]]*:[[:space:]]*"personal-media-ops-api"' <<<"$body" &&
      grep -Eq '"version"[[:space:]]*:' <<<"$body" || {
        printf '%s=invalid-health-payload url=%s\n' "$label" "$url" >&2
        return 1
      }
  fi
  printf '%s=ok http=%s url=%s\n' "$label" "$status" "$url"
}

mediaops_stage "Public health checks"
check_http frontend "${base_url}" no
check_http public_api "${base_url}/api/health" yes
check_http crawler_route "${base_url}/crawler/tasks" no

if ((with_ssh)); then
  host="$(mediaops_resolve_host "$host_override")"
  mediaops_validate_host "$host"
  mediaops_require_ssh_alias "$host"
  mediaops_stage "Local API over SSH"
  mediaops_info "target=${host}"
  local_health="$(mediaops_ssh "$host" \
    'curl -fsS --max-time 10 http://127.0.0.1:8000/api/health')"
  grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"$local_health" &&
    grep -Eq '"service"[[:space:]]*:[[:space:]]*"personal-media-ops-api"' <<<"$local_health" ||
    mediaops_die "localhost API returned an invalid health payload"
  printf 'local_api=ok\n%s\n' "$local_health"
fi

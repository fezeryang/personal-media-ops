#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
  cat <<'EOF'
Usage: status.sh [--host SSH_ALIAS]

Run a read-only production status survey: Git, services, port 8000, API,
Nginx config, disk, memory, failed task count, and static frontend presence.

Options:
  --host SSH_ALIAS  Override MEDIAOPS_SSH_HOST (default: mediaops-prod)
  -h, --help        Show this help
EOF
}

host_override=""
while (($# > 0)); do
  case "$1" in
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

host="$(mediaops_resolve_host "$host_override")"
mediaops_validate_host "$host"
mediaops_require_ssh_alias "$host"

mediaops_stage "Production status"
mediaops_info "target=${host}"
mediaops_info "mode=read-only"

mediaops_ssh "$host" 'bash -s' <<'REMOTE'
set -Eeuo pipefail

APP_ROOT="/opt/personal-media-ops"
BACKEND_ROOT="${APP_ROOT}/backend"
DATABASE="/var/lib/mediaops/mediaops.db"
STATIC_INDEX="/www/wwwroot/ops.fezern8n.com/index.html"
STATIC_RELEASE="/www/wwwroot/ops.fezern8n.com/.mediaops-release"
NGINX="/www/server/nginx/sbin/nginx"
repository_commit=""

section() {
  printf '\n-- %s --\n' "$1"
}

permission_or_failure() {
  local label="$1"
  local output="$2"
  if grep -Eqi 'permission denied|access denied|not permitted|authentication is required' <<<"$output"; then
    printf '%s=permission-denied\n' "$label"
  else
    printf '%s=failed\n%s\n' "$label" "$output"
  fi
}

service_status() {
  local service="$1"
  local output
  if output="$(systemctl is-active "$service" 2>&1)"; then
    printf '%s=%s\n' "$service" "$output"
  else
    local exit_code=$?
    if grep -Eqi 'permission denied|access denied|not permitted|authentication is required' <<<"$output"; then
      printf '%s=permission-denied\n' "$service"
    elif ((exit_code == 3)); then
      printf '%s=%s\n' "$service" "${output:-inactive}"
    else
      printf '%s=unavailable\n%s\n' "$service" "$output"
    fi
  fi
}

section "Identity"
printf 'user=%s\n' "$(whoami)"
printf 'hostname=%s\n' "$(hostname)"
printf 'time=%s\n' "$(date -Is)"

section "Git"
if [[ -d "${APP_ROOT}/.git" ]]; then
  repository_commit="$(git -C "$APP_ROOT" rev-parse HEAD)"
  printf 'commit=%s\n' "$repository_commit"
  printf 'branch=%s\n' "$(git -C "$APP_ROOT" branch --show-current)"
  git_state="$(git -C "$APP_ROOT" status --porcelain)"
  if [[ -z "$git_state" ]]; then
    printf 'worktree=clean\n'
  else
    printf 'worktree=dirty\n%s\n' "$git_state"
  fi
else
  printf 'repository=missing\n'
fi

section "systemd"
if command -v systemctl >/dev/null 2>&1; then
  service_status mediaops-api
  service_status mediaops-crawler-worker
else
  printf 'systemd=unavailable\n'
fi

section "Port 8000"
if command -v ss >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | awk '$4 ~ /:8000$/ {found=1} END {exit !found}'; then
    printf 'port_8000=listening\n'
  else
    printf 'port_8000=not-listening-or-permission-denied\n'
  fi
else
  printf 'port_check=ss-unavailable\n'
fi

section "Local API"
if command -v curl >/dev/null 2>&1; then
  if health="$(curl -fsS --max-time 10 http://127.0.0.1:8000/api/health 2>&1)"; then
    printf 'api_health=ok\n%s\n' "$health"
  else
    printf 'api_health=failed\n%s\n' "$health"
  fi
else
  printf 'api_health=curl-unavailable\n'
fi

section "Nginx"
if [[ ! -x "$NGINX" ]]; then
  printf 'nginx=missing-or-not-executable\n'
elif nginx_output="$("$NGINX" -t 2>&1)"; then
  printf 'nginx_config=ok\n%s\n' "$nginx_output"
else
  permission_or_failure nginx_config "$nginx_output"
fi

section "Static frontend"
if [[ -f "$STATIC_INDEX" ]]; then
  if [[ -r "$STATIC_INDEX" ]]; then
    printf 'static_index=present\n'
    printf 'static_index_modified=%s\n' "$(stat -c %y "$STATIC_INDEX")"
    if command -v sha256sum >/dev/null 2>&1; then
      printf 'static_index_sha256=%s\n' "$(sha256sum "$STATIC_INDEX" | awk '{print $1}')"
    fi
  else
    printf 'static_index=permission-denied\n'
  fi
else
  printf 'static_index=missing\n'
fi
if [[ ! -e "$STATIC_RELEASE" ]]; then
  printf 'static_release=missing\n'
elif [[ ! -r "$STATIC_RELEASE" ]]; then
  printf 'static_release=permission-denied\n'
else
  static_commit="$(tr -d '[:space:]' < "$STATIC_RELEASE")"
  if [[ "$static_commit" =~ ^[0-9a-f]{40}$ ]]; then
    printf 'static_commit=%s\n' "$static_commit"
    if [[ -n "$repository_commit" && "$static_commit" == "$repository_commit" ]]; then
      printf 'static_version=matches-repository\n'
    elif [[ -n "$repository_commit" ]]; then
      printf 'static_version=mismatch\n'
    else
      printf 'static_version=repository-unknown\n'
    fi
  else
    printf 'static_release=invalid\n'
  fi
fi

section "Failed crawler tasks"
if [[ ! -e "$DATABASE" ]]; then
  printf 'failed_tasks=database-missing\n'
elif [[ ! -r "$DATABASE" ]]; then
  printf 'failed_tasks=permission-denied\n'
elif [[ ! -x "${BACKEND_ROOT}/.venv/bin/python" ]]; then
  printf 'failed_tasks=backend-python-missing\n'
else
  "${BACKEND_ROOT}/.venv/bin/python" - "$DATABASE" <<'PY'
import sqlite3
import sys
from datetime import UTC, datetime, timedelta

database = sys.argv[1]
cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
try:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM crawler_tasks
        WHERE status = 'failed' AND created_at >= ?
        """,
        (cutoff,),
    ).fetchone()[0]
except (OSError, sqlite3.Error) as error:
    print(f"failed_tasks_last_24h=read-failed:{error}")
else:
    print(f"failed_tasks_last_24h={count}")
finally:
    if "connection" in locals():
        connection.close()
PY
fi

section "Disk"
df -h "$APP_ROOT" /var/lib/mediaops /var/log/mediaops 2>&1 || true

section "Memory"
if command -v free >/dev/null 2>&1; then
  free -h
else
  awk '/MemTotal|MemAvailable/ {print}' /proc/meminfo
fi
REMOTE

#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
  cat <<'EOF'
Usage: status.sh [--host SSH_ALIAS] [--research-task UUID]

Run a read-only production status survey: Git, services, port 8000, API,
Nginx config, disk, memory, failed task count, and static frontend presence.

Options:
  --host SSH_ALIAS  Override MEDIAOPS_SSH_HOST (default: mediaops-prod)
  --research-task UUID
                    Add read-only Research detail, crawler, and schema checks
  -h, --help        Show this help
EOF
}

host_override=""
research_task_id=""
while (($# > 0)); do
  case "$1" in
    --host)
      mediaops_require_value "$1" "${2:-}"
      host_override="$2"
      shift 2
      ;;
    --research-task)
      mediaops_require_value "$1" "${2:-}"
      mediaops_validate_uuid "$2"
      research_task_id="$2"
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

mediaops_ssh "$host" "bash -s -- ${research_task_id}" <<'REMOTE'
set -Eeuo pipefail

APP_ROOT="/opt/personal-media-ops"
BACKEND_ROOT="${APP_ROOT}/backend"
DATABASE="/var/lib/mediaops/mediaops.db"
RESEARCH_TASK_ID="${1:-}"
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

if [[ -n "$RESEARCH_TASK_ID" ]]; then
  section "Research acceptance (read-only)"
  if [[ ! -x "${BACKEND_ROOT}/.venv/bin/python" ]]; then
    printf 'research_acceptance=backend-python-missing\n'
  else
    "${BACKEND_ROOT}/.venv/bin/python" - "$DATABASE" "$RESEARCH_TASK_ID" <<'PY'
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, "/opt/personal-media-ops/backend")

from app.api.research import _detail
from app.models.research import ResearchTaskDetail
from app.repositories.research import ResearchTaskRepository

database_path, task_id = sys.argv[1:3]
database_uri = f"file:{quote(database_path, safe='/')}?mode=ro"

with sqlite3.connect(database_uri, uri=True) as connection:
    connection.row_factory = sqlite3.Row
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    head = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    task_row = connection.execute(
        "SELECT user_id, status, current_round FROM research_tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    print(f"database_integrity={integrity}")
    print(f"alembic_head={head['version_num'] if head else 'missing'}")
    print(f"research_task_present={'yes' if task_row else 'no'}")
    if task_row is not None:
        print(f"research_task_status={task_row['status']}")
        print(f"research_task_round={task_row['current_round']}")
        crawler_rows = connection.execute(
            """
            SELECT id, status, actual_count, qrcode_path
            FROM crawler_tasks
            WHERE research_task_id = ?
            ORDER BY created_at, id
            """,
            (task_id,),
        ).fetchall()
        print(f"crawler_task_count={len(crawler_rows)}")
        for row in crawler_rows:
            qrcode_exists = Path(str(row["qrcode_path"])).is_file()
            print(
                "crawler_task="
                f"{row['id']} status={row['status']} actual_count={row['actual_count']} "
                f"qrcode_file={'present' if qrcode_exists else 'absent'}"
            )

        repository = ResearchTaskRepository(Path(database_path))
        task = repository.get(
            user_id=str(task_row["user_id"]),
            task_id=task_id,
            detail=True,
        )
        if task is None:
            raise SystemExit("research_detail_repository=missing")
        validated = ResearchTaskDetail.model_validate(_detail(task))
        print("research_detail_model=valid")
        print(f"research_findings={len(validated.findings)}")
        print(f"research_events={len(validated.events)}")
        print(f"research_queries={len(validated.queries)}")
        print(f"research_utilities={len(validated.information_utilities or [])}")
        print(f"research_unknowns={len(validated.unknowns or [])}")
        print(f"research_memory_items={len(validated.memory_items or [])}")
        print(f"research_discovery_seeds={len(validated.discovery_seeds or [])}")
        print(f"research_discovery_candidates={len(validated.discovery_candidates or [])}")

    aggregate_queries = (
        ("research_task_total", "SELECT COUNT(*) FROM research_tasks"),
        (
            "research_active_tasks",
            """
            SELECT COUNT(*) FROM research_tasks
            WHERE status IN (
              'Draft', 'Planning', 'Researching', 'WaitingCrawl',
              'WaitingLogin', 'Summarizing', 'BudgetExceeded'
            )
            """,
        ),
        (
            "crawler_active_tasks",
            "SELECT COUNT(*) FROM crawler_tasks WHERE status IN ('pending', 'running', 'waiting_login')",
        ),
        ("discovery_runs", "SELECT COUNT(*) FROM research_discovery_runs"),
        ("discovery_candidates", "SELECT COUNT(*) FROM research_discovery_candidates"),
        ("discovery_feedback", "SELECT COUNT(*) FROM research_discovery_feedback"),
        ("research_spaces", "SELECT COUNT(*) FROM research_spaces"),
        ("research_space_items", "SELECT COUNT(*) FROM research_space_items"),
    )
    for label, query in aggregate_queries:
        print(f"{label}={connection.execute(query).fetchone()[0]}")
PY
  fi
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

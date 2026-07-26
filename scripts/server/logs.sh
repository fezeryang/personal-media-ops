#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
  cat <<'EOF'
Usage: logs.sh SOURCE [--lines N] [--follow] [--host SSH_ALIAS]

Read a bounded production log. Exactly one SOURCE is required:
  --api                 mediaops-api journal
  --worker              mediaops-crawler-worker journal
  --nginx-access        BaoTa Nginx access log
  --nginx-error         BaoTa Nginx error log
  --task UUID           One crawler task log

Options:
  --lines N             Number of lines (default: 200, maximum: 5000)
  --follow              Explicitly continue following after the initial lines
  --host SSH_ALIAS      Override MEDIAOPS_SSH_HOST (default: mediaops-prod)
  -h, --help            Show this help
EOF
}

mode=""
task_id=""
lines=200
follow=0
host_override=""

while (($# > 0)); do
  case "$1" in
    --api | --worker | --nginx-access | --nginx-error)
      [[ -z "$mode" ]] || mediaops_die "choose exactly one log source"
      mode="${1#--}"
      shift
      ;;
    --task)
      [[ -z "$mode" ]] || mediaops_die "choose exactly one log source"
      mediaops_require_value "$1" "${2:-}"
      mode="task"
      task_id="$2"
      shift 2
      ;;
    --lines)
      mediaops_require_value "$1" "${2:-}"
      lines="$2"
      shift 2
      ;;
    --follow)
      follow=1
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

[[ -n "$mode" ]] || mediaops_die "choose one log source; see --help"
mediaops_validate_lines "$lines"
if [[ "$mode" == "task" ]]; then
  mediaops_validate_uuid "$task_id"
fi

host="$(mediaops_resolve_host "$host_override")"
mediaops_validate_host "$host"
mediaops_require_ssh_alias "$host"

mediaops_stage "Production logs"
mediaops_info "target=${host}"
mediaops_info "source=${mode}, lines=${lines}, follow=${follow}"

mediaops_ssh "$host" "bash -s -- ${mode} ${lines} ${follow} ${task_id}" <<'REMOTE'
set -Eeuo pipefail

mode="$1"
lines="$2"
follow="$3"
task_id="${4:-}"

read_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    printf 'ERROR: log does not exist: %s\n' "$path" >&2
    exit 4
  fi
  if [[ ! -r "$path" ]]; then
    printf 'ERROR: permission denied reading log: %s\n' "$path" >&2
    exit 3
  fi
  if [[ "$follow" == "1" ]]; then
    exec tail -n "$lines" -f -- "$path"
  fi
  tail -n "$lines" -- "$path"
}

read_journal() {
  local unit="$1"
  local probe
  probe="$(journalctl -u "$unit" -n 1 --no-pager 2>&1 || true)"
  if grep -Eqi 'permission denied|not seeing messages|access denied' <<<"$probe"; then
    printf 'ERROR: permission denied reading journal for %s\n' "$unit" >&2
    exit 3
  fi
  if [[ "$follow" == "1" ]]; then
    exec journalctl -u "$unit" -n "$lines" -f
  fi
  journalctl -u "$unit" -n "$lines" --no-pager
}

case "$mode" in
  api)
    read_journal mediaops-api
    ;;
  worker)
    read_journal mediaops-crawler-worker
    ;;
  nginx-access)
    read_file /www/wwwlogs/ops.fezern8n.com.log
    ;;
  nginx-error)
    read_file /www/wwwlogs/ops.fezern8n.com.error.log
    ;;
  task)
    read_file "/var/log/mediaops/crawler/${task_id}.log"
    ;;
  *)
    printf 'ERROR: unsupported log source\n' >&2
    exit 2
    ;;
esac
REMOTE

#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
  cat <<'EOF'
Usage: connect.sh [--host SSH_ALIAS]

Validate non-interactive SSH access and print read-only server identity facts.

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

mediaops_stage "SSH connection check"
mediaops_info "target=${host}"
mediaops_info "mode=read-only, BatchMode=yes, ConnectTimeout=10"

mediaops_ssh "$host" '
set -eu
printf "remote_user=%s\n" "$(whoami)"
printf "hostname=%s\n" "$(hostname)"
printf "time=%s\n" "$(date -Is)"
if test -r /etc/os-release; then
  . /etc/os-release
  printf "os=%s\n" "${PRETTY_NAME:-unknown}"
else
  printf "os=unknown\n"
fi
'

#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../../../.." && pwd)"

usage() {
    cat <<'EOF'
Usage: run-server-tool.sh TOOL [TOOL_OPTIONS...]

Dispatch to one canonical repository server tool.

Tools:
  connect
  status
  healthcheck
  logs
  backup
  deploy

Examples:
  run-server-tool.sh status
  run-server-tool.sh healthcheck --with-ssh
  run-server-tool.sh logs --worker --lines 200
  run-server-tool.sh deploy --commit abcdef1
EOF
}

if (($# == 0)); then
    usage >&2
    exit 2
fi

case "$1" in
    -h|--help)
        usage
        exit 0
        ;;
    connect|status|healthcheck|logs|backup|deploy)
        tool="$1"
        shift
        ;;
    *)
        printf 'ERROR: unsupported tool: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
esac

tool_path="${REPOSITORY_ROOT}/scripts/server/${tool}.sh"
if [[ ! -x "$tool_path" ]]; then
    printf 'ERROR: canonical server tool is not executable: %s\n' "$tool_path" >&2
    exit 2
fi

exec "$tool_path" "$@"

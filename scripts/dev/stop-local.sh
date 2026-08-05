#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_ROOT="${REPOSITORY_ROOT}/.local-dev"

stop_pid_file() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] || return 0
    local pid
    pid="$(tr -d '[:space:]' < "$pid_file")"
    if [[ "$pid" =~ ^[2-9][0-9]*$ ]] && kill -0 "$pid" 2>/dev/null; then
        printf 'Stopping local process pid=%s\n' "$pid"
        kill "$pid" 2>/dev/null || true
        for _ in $(seq 1 20); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.1
        done
        if kill -0 "$pid" 2>/dev/null; then
            printf 'ERROR: local process did not stop cleanly: %s\n' "$pid" >&2
            return 1
        fi
    fi
    rm -f -- "$pid_file"
}

stop_pid_file "${LOCAL_ROOT}/frontend.pid"
stop_pid_file "${LOCAL_ROOT}/api.pid"
printf 'Local services stopped. Local data remains under %s.\n' "$LOCAL_ROOT"

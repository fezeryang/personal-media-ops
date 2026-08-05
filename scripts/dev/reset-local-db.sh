#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_ROOT="${REPOSITORY_ROOT}/.local-dev"

if [[ -f "${LOCAL_ROOT}/api.pid" || -f "${LOCAL_ROOT}/frontend.pid" ]]; then
    printf 'ERROR: stop local services before resetting the local database.\n' >&2
    exit 2
fi

rm -f -- "${LOCAL_ROOT}/mediaops.db" "${LOCAL_ROOT}/mediaops.db-shm" \
    "${LOCAL_ROOT}/mediaops.db-wal"
printf 'Reset only the local SQLite database under %s.\n' "$LOCAL_ROOT"

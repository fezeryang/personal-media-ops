#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_ROOT="${REPOSITORY_ROOT}/.local-dev"
LOG_ROOT="${LOCAL_ROOT}/logs"
BACKEND_ROOT="${REPOSITORY_ROOT}/backend"
BACKEND_PYTHON="${BACKEND_ROOT}/.venv/bin/python"

if [[ ! -x "$BACKEND_PYTHON" ]]; then
    printf 'ERROR: local backend environment is missing: %s\n' "$BACKEND_PYTHON" >&2
    printf 'Run the documented local dependency setup, then retry.\n' >&2
    exit 2
fi
if [[ ! -x "${REPOSITORY_ROOT}/frontend/node_modules/.bin/vite" ]]; then
    printf 'ERROR: local frontend dependencies are missing. Run npm ci in frontend.\n' >&2
    exit 2
fi

mkdir -p -- "$LOG_ROOT" "${LOCAL_ROOT}/crawler-output" "${LOCAL_ROOT}/qrcodes" \
    "${LOCAL_ROOT}/browser-data" "${LOCAL_ROOT}/secrets"

for pid_file in "${LOCAL_ROOT}/api.pid" "${LOCAL_ROOT}/frontend.pid"; do
    if [[ -f "$pid_file" ]]; then
        pid="$(tr -d '[:space:]' < "$pid_file")"
        if [[ "$pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$pid" 2>/dev/null; then
            printf 'ERROR: local service is already running (pid=%s, file=%s)\n' "$pid" "$pid_file" >&2
            printf 'Run scripts/dev/stop-local.sh first.\n' >&2
            exit 3
        fi
        rm -f -- "$pid_file"
    fi
done

database_path="${LOCAL_ROOT}/mediaops.db"
local_env=(
    "PATH=${PATH}"
    "NO_PROXY=127.0.0.1,localhost"
    "no_proxy=127.0.0.1,localhost"
    "PYTHONPATH=${BACKEND_ROOT}"
    "FRONTEND_ORIGINS=http://127.0.0.1:5173"
    "MEDIAOPS_DATABASE_PATH=${database_path}"
    "MEDIAOPS_OUTPUT_ROOT=${LOCAL_ROOT}/crawler-output"
    "MEDIAOPS_LOG_ROOT=${LOCAL_ROOT}/logs"
    "MEDIAOPS_QRCODE_ROOT=${LOCAL_ROOT}/qrcodes"
    "MEDIAOPS_MODEL_GATEWAY_MASTER_KEY_PATH=${LOCAL_ROOT}/secrets/model-gateway-master.key"
    "MEDIAOPS_ENABLED_PLATFORMS=bili"
    "MEDIAOPS_AI_PROVIDER=disabled"
    "MEDIAOPS_SECURE_SESSION_COOKIE=false"
)

printf '==> Preparing local SQLite database\n'
(
    cd -- "$BACKEND_ROOT"
    env -i "${local_env[@]}" "$BACKEND_PYTHON" -m alembic upgrade head
)

printf '==> Starting local FastAPI: http://127.0.0.1:8000\n'
(
    cd -- "$BACKEND_ROOT"
    exec env -i "${local_env[@]}" "$BACKEND_PYTHON" -m uvicorn app.main:app \
        --host 127.0.0.1 --port 8000
) >"${LOG_ROOT}/api.log" 2>&1 &
api_pid=$!
printf '%s\n' "$api_pid" >"${LOCAL_ROOT}/api.pid"

printf '==> Starting local Vite: http://127.0.0.1:5173\n'
(
    cd -- "${REPOSITORY_ROOT}/frontend"
    exec env -i "PATH=${PATH}" VITE_LOCAL_FIXTURES=true npm run dev -- \
        --host 127.0.0.1 --port 5173
) >"${LOG_ROOT}/frontend.log" 2>&1 &
frontend_pid=$!
printf '%s\n' "$frontend_pid" >"${LOCAL_ROOT}/frontend.pid"

for attempt in $(seq 1 30); do
    if curl -fsS --max-time 2 http://127.0.0.1:8000/api/health >/dev/null 2>&1 &&
        curl -fsS --max-time 2 http://127.0.0.1:5173/__local/fixtures >/dev/null 2>&1; then
        printf '\nLocal services are ready.\n'
        printf '  API:      http://127.0.0.1:8000\n'
        printf '  Frontend: http://127.0.0.1:5173\n'
        printf '  Fixtures: http://127.0.0.1:5173/__local/fixtures\n'
        printf '  Logs:     %s\n' "$LOG_ROOT"
        exit 0
    fi
    if ! kill -0 "$api_pid" 2>/dev/null || ! kill -0 "$frontend_pid" 2>/dev/null; then
        printf 'ERROR: local service exited during startup. Inspect %s.\n' "$LOG_ROOT" >&2
        exit 4
    fi
    sleep 1
done

printf 'ERROR: local services did not become ready. Inspect %s.\n' "$LOG_ROOT" >&2
exit 5

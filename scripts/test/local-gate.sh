#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_ROOT="${REPOSITORY_ROOT}/backend"
FRONTEND_ROOT="${REPOSITORY_ROOT}/frontend"
BACKEND_PYTHON="${BACKEND_ROOT}/.venv/bin/python"
BACKEND_PYTEST="${BACKEND_ROOT}/.venv/bin/pytest"
GATE_TMP=""
TEST_TIMEOUT_SECONDS="${MEDIAOPS_LOCAL_TEST_TIMEOUT_SECONDS:-900}"

fail() {
    printf 'ERROR: local gate failed: %s\n' "$1" >&2
    exit 1
}

stage() {
    printf '\n==> %s\n' "$1"
}

cleanup() {
    if [[ -n "$GATE_TMP" && -d "$GATE_TMP" ]]; then
        rm -rf -- "$GATE_TMP"
    fi
}
trap cleanup EXIT

cd -- "$REPOSITORY_ROOT"
[[ "$TEST_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] ||
    fail "MEDIAOPS_LOCAL_TEST_TIMEOUT_SECONDS must be a positive integer"
command -v timeout >/dev/null 2>&1 || fail "timeout is required for bounded local gates"
[[ -x "$BACKEND_PYTHON" && -x "$BACKEND_PYTEST" ]] ||
    fail "backend/.venv is missing; install the pinned local backend environment"
command -v npm >/dev/null 2>&1 || fail "npm is required"
[[ -x "${FRONTEND_ROOT}/node_modules/.bin/vite" ]] ||
    fail "frontend/node_modules is missing; run npm ci --include=dev"

stage "backend dependencies and tests"
backend_test_status=0
if command -v uv >/dev/null 2>&1; then
    timeout --foreground "$TEST_TIMEOUT_SECONDS" bash -c \
        "cd -- '$BACKEND_ROOT' && uv sync --frozen && uv run pytest" ||
        backend_test_status=$?
else
    timeout --foreground "$TEST_TIMEOUT_SECONDS" bash -c \
        "cd -- '$BACKEND_ROOT' && '$BACKEND_PYTHON' -m pytest" ||
        backend_test_status=$?
fi
if ((backend_test_status == 124)); then
    fail "backend tests exceeded ${TEST_TIMEOUT_SECONDS}s; inspect the named local test instead of waiting indefinitely"
fi
((backend_test_status == 0)) || exit "$backend_test_status"

stage "temporary SQLite migration and current-head check"
GATE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/mediaops-local-gate.XXXXXX")"
local_db="${GATE_TMP}/mediaops.db"
local_env=(
    "PATH=${PATH}"
    "NO_PROXY=127.0.0.1,localhost"
    "no_proxy=127.0.0.1,localhost"
    "PYTHONPATH=${BACKEND_ROOT}"
    "MEDIAOPS_DATABASE_PATH=${local_db}"
    "MEDIAOPS_OUTPUT_ROOT=${GATE_TMP}/crawler-output"
    "MEDIAOPS_LOG_ROOT=${GATE_TMP}/logs"
    "MEDIAOPS_QRCODE_ROOT=${GATE_TMP}/qrcodes"
    "MEDIAOPS_MODEL_GATEWAY_MASTER_KEY_PATH=${GATE_TMP}/model-gateway-master.key"
    "MEDIAOPS_ENABLED_PLATFORMS=bili"
    "MEDIAOPS_AI_PROVIDER=disabled"
    "MEDIAOPS_SECURE_SESSION_COOKIE=false"
)
(
    cd -- "$BACKEND_ROOT"
    env -i "${local_env[@]}" "$BACKEND_PYTHON" -m alembic upgrade head
    env -i "${local_env[@]}" "$BACKEND_PYTHON" -c \
        'from pathlib import Path; from app.database_migrations import require_database_current; require_database_current(Path(__import__("os").environ["MEDIAOPS_DATABASE_PATH"]))'
)

stage "frontend lint, tests, and build"
frontend_status=0
timeout --foreground "$TEST_TIMEOUT_SECONDS" bash -c \
    "cd -- '$FRONTEND_ROOT' && npm ci --include=dev && npm run lint && npm run test && npm run build" ||
    frontend_status=$?
if ((frontend_status == 124)); then
    fail "frontend lint/test/build exceeded ${TEST_TIMEOUT_SECONDS}s"
fi
((frontend_status == 0)) || exit "$frontend_status"

stage "shell syntax and release-script checks"
mapfile -t shell_files < <(
    find "$REPOSITORY_ROOT/scripts" "$REPOSITORY_ROOT/infra" \
        -type f \( -name '*.sh' -o -name '*.bash' \) -print | sort
)
(( ${#shell_files[@]} > 0 )) || fail "no shell files were discovered"
bash -n "${shell_files[@]}"
"${REPOSITORY_ROOT}/scripts/server/tests/test_release_scripts.sh"

stage "local visual checks at required viewports"
"${REPOSITORY_ROOT}/scripts/test/local-visual.sh"

stage "local-only safety and repository hygiene"
if rg -n --fixed-strings \
    -e 'ops.fezern8n.com' \
    -e 'mediaops-prod' \
    -e '--execute' \
    --glob '!local-gate.sh' \
    "${REPOSITORY_ROOT}/scripts/dev" "${REPOSITORY_ROOT}/scripts/test" "${REPOSITORY_ROOT}/scripts/release"; then
    fail "local scripts contain a production host or execute flag"
fi
git diff --check || fail "whitespace errors are present in the worktree"
while IFS= read -r -d '' tracked_path; do
    case "$tracked_path" in
        *.env|*.db|*.sqlite|*.sqlite3|*cookies*|*browser_data*|*qrcodes*|*qr*.png|*.pem|*.key)
            [[ "$tracked_path" == *.env.example ]] || fail "sensitive artifact is tracked: $tracked_path"
            ;;
    esac
done < <(git ls-files -z)

printf '\nlocal_test_status=passed\n'
printf 'local_visual_status=passed\n'
printf 'local_gate=passed\n'

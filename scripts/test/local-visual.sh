#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
FRONTEND_ROOT="${REPOSITORY_ROOT}/frontend"
EVIDENCE_ROOT="${REPOSITORY_ROOT}/docs/evidence"
PORT="${MEDIAOPS_LOCAL_VISUAL_PORT:-5174}"
URL="http://127.0.0.1:${PORT}/__local/fixtures"

[[ -x "${FRONTEND_ROOT}/node_modules/.bin/vite" ]] || {
    printf 'ERROR: frontend dependencies are required for local visual checks.\n' >&2
    exit 2
}

chrome_bin=""
for candidate in /usr/bin/google-chrome /usr/bin/chromium /snap/bin/chromium; do
    if [[ -x "$candidate" ]]; then
        chrome_bin="$candidate"
        break
    fi
done
[[ -n "$chrome_bin" ]] || {
    printf 'ERROR: no local headless Chromium/Chrome was found.\n' >&2
    exit 2
}

mkdir -p -- "$EVIDENCE_ROOT"
temporary_root="$(mktemp -d "${TMPDIR:-/tmp}/mediaops-local-visual.XXXXXX")"
server_pid=""
cleanup() {
    if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
        kill "$server_pid" 2>/dev/null || true
    fi
    rm -rf -- "$temporary_root"
}
trap cleanup EXIT

(
    cd -- "$FRONTEND_ROOT"
    exec env -i "PATH=${PATH}" NO_PROXY=127.0.0.1,localhost \
        no_proxy=127.0.0.1,localhost VITE_LOCAL_FIXTURES=true npm run dev -- \
        --host 127.0.0.1 --port "$PORT"
) >"${temporary_root}/vite.log" 2>&1 &
server_pid=$!

for _ in $(seq 1 30); do
    if curl -fsS --max-time 2 "$URL" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
curl -fsS --max-time 5 "$URL" >/dev/null || {
    printf 'ERROR: local fixture page did not become reachable.\n' >&2
    sed -n '1,120p' "${temporary_root}/vite.log" >&2 || true
    exit 3
}

browser_data="${temporary_root}/browser-data"
for viewport in 1440x900 1280x720 390x844; do
    output="${EVIDENCE_ROOT}/local-fixtures-${viewport}.png"
    timeout 30 "$chrome_bin" --headless=new --no-sandbox --disable-gpu \
        --user-data-dir="$browser_data" --window-size="$viewport" \
        --virtual-time-budget=3000 --screenshot="$output" "$URL" >/dev/null
    [[ -s "$output" ]] || {
        printf 'ERROR: Chrome did not produce visual evidence for %s.\n' "$viewport" >&2
        exit 4
    }
done

printf 'local_visual_status=passed\n'
printf 'evidence_path=%s\n' "$EVIDENCE_ROOT"

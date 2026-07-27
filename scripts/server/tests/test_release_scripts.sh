#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
DEPLOY="${REPOSITORY_ROOT}/scripts/server/deploy.sh"
COMMON="${REPOSITORY_ROOT}/scripts/server/lib/common.bash"
HELPER="${REPOSITORY_ROOT}/infra/release/mediaops-release"
SUDOERS="${REPOSITORY_ROOT}/infra/sudoers/mediaops-release.example"

usage() {
    cat <<'EOF'
Usage: test_release_scripts.sh

Run local, non-production checks for the deploy script, restricted helper
source, and sudoers source. This test never connects to a server.
EOF
}

if (($# > 0)); then
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: unknown argument: %s\n' "$1" >&2
            exit 2
            ;;
    esac
fi

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

assert_contains() {
    local text="$1"
    local expected="$2"
    grep -Fq -- "$expected" <<<"$text" ||
        fail "expected output to contain: ${expected}"
}

assert_rejects() {
    if "$@" >/dev/null 2>&1; then
        fail "command unexpectedly succeeded: $*"
    fi
}

[[ -x "$DEPLOY" ]] || fail "deploy script is not executable"
[[ -x "$HELPER" ]] || fail "release helper source is not executable"
[[ -f "$SUDOERS" ]] || fail "release sudoers source is missing"

bash -n "$DEPLOY" "$HELPER" "$COMMON"

dry_run_output="$(
    "$DEPLOY" \
        --host deliberately-unresolvable-mediaops \
        --target-ref 0123456789abcdef0123456789abcdef01234567 \
        --dry-run
)"
assert_contains "$dry_run_output" "Target server: deliberately-unresolvable-mediaops"
assert_contains "$dry_run_output" "Target ref: 0123456789abcdef0123456789abcdef01234567"
assert_contains "$dry_run_output" "Database migration: inspect during execute preflight"
assert_contains "$dry_run_output" "Migration authorization: required when detected"
assert_contains "$dry_run_output" "Database backup: required before pull"
assert_contains "$dry_run_output" "Helper subcommand: finalize"
assert_contains "$dry_run_output" "runner-sync: install the reviewed MediaCrawler runner copy the Worker executes"
assert_contains "$dry_run_output" "Dry run only"

migration_dry_run_output="$(
    "$DEPLOY" \
        --host deliberately-unresolvable-mediaops \
        --target-ref 0123456789abcdef0123456789abcdef01234567 \
        --allow-migrations \
        --dry-run
)"
assert_contains "$migration_dry_run_output" "Migration authorization: granted"
assert_contains "$migration_dry_run_output" "uv run alembic upgrade head"

assert_rejects "$DEPLOY" --dry-run --execute
assert_rejects "$DEPLOY" --target-ref '../main' --dry-run
assert_rejects "$DEPLOY" --root-stage

[[ "$("$HELPER" version)" == "1" ]] ||
    fail "helper version output must be exactly 1"
grep -Fq -- "--exclude='.user.ini'" "$HELPER" ||
    fail "helper rsync must exclude .user.ini from transfer"
grep -Fq -- "--filter='protect .user.ini'" "$HELPER" ||
    fail "helper rsync must protect .user.ini from --delete"
assert_rejects "$HELPER" unknown
assert_rejects "$HELPER" version extra
assert_rejects "$HELPER" publish-frontend

readonly -a allowed_subcommands=(
    version
    status
    publish-frontend
    restart-services
    nginx-check
    nginx-reload
    verify
    finalize
)

sudoers_entries="$(
    grep -Ec '^[[:space:]]+/usr/local/sbin/mediaops-release ' "$SUDOERS"
)"
[[ "$sudoers_entries" -eq "${#allowed_subcommands[@]}" ]] ||
    fail "sudoers must contain exactly eight helper command entries"
for subcommand in "${allowed_subcommands[@]}"; do
    grep -Fq "/usr/local/sbin/mediaops-release ${subcommand}" "$SUDOERS" ||
        fail "sudoers is missing helper subcommand: ${subcommand}"
done
if grep -Eq '/usr/local/sbin/mediaops-release[[:space:]]+\*' "$SUDOERS"; then
    fail "sudoers must not use a helper argument wildcard"
fi

if grep -Eq \
    'sudo -n (/usr/bin/rsync|/usr/bin/systemctl|/www/server/nginx/sbin/nginx)' \
    "$DEPLOY"; then
    fail "deploy script contains a direct privileged command"
fi

if grep -Fq '[[ -x "$release_helper" ]]' "$DEPLOY"; then
    fail "deploy script must not require direct helper execution by mediaops"
fi
grep -Fq 'sudo -n "$release_helper" version' "$DEPLOY" ||
    fail "deploy script must validate helper availability through sudo -n"

finalize_line="$(
    grep -nF 'sudo -n /usr/local/sbin/mediaops-release finalize' "$DEPLOY" |
        cut -d: -f1
)"
[[ "$finalize_line" =~ ^[0-9]+$ ]] ||
    fail "deploy script must call helper finalize exactly once"

for gate in 'uv run pytest' 'npm run lint' 'npm run test' 'npm run build'; do
    gate_line="$(grep -nF "$gate" "$DEPLOY" | head -n 1 | cut -d: -f1)"
    [[ "$gate_line" =~ ^[0-9]+$ && "$gate_line" -lt "$finalize_line" ]] ||
        fail "gate must appear before helper finalize: ${gate}"
done

migration_line="$(
    grep -nF 'uv run alembic upgrade head' "$DEPLOY" |
        tail -n 1 |
        cut -d: -f1
)"
[[ "$migration_line" =~ ^[0-9]+$ && "$migration_line" -lt "$finalize_line" ]] ||
    fail "Alembic upgrade must appear before helper finalize"
grep -Fq -- '--allow-migrations' "$DEPLOY" ||
    fail "deploy script must require explicit migration authorization"

# The ssh stub does not capture heredoc bodies, so the runner-sync remote
# logic (unchanged detection, pre-overwrite backup, fixed mode, cache purge)
# is asserted against the deploy script source.
grep -Fq 'dst="/var/lib/mediaops/bin/run_mediacrawler.py"' "$DEPLOY" ||
    fail "runner-sync must target the installed Worker runner copy"
grep -Fq 'src="/opt/personal-media-ops/scripts/crawler/run_mediacrawler.py"' \
    "$DEPLOY" ||
    fail "runner-sync must copy the reviewed repository runner"
grep -Fq 'cmp -s -- "$src" "$dst"' "$DEPLOY" ||
    fail "runner-sync must skip byte-identical installed runners"
grep -Fq 'install -m 750 -- "$dst" "${dst}.backup-' "$DEPLOY" ||
    fail "runner-sync must back up a differing installed runner before overwrite"
grep -Fq 'install -m 750 -- "$src" "$dst"' "$DEPLOY" ||
    fail "runner-sync must install the runner with fixed mode 750"
grep -Fq 'rm -rf -- /var/lib/mediaops/bin/__pycache__' "$DEPLOY" ||
    fail "runner-sync must purge the stale runner bytecode cache"
if grep -F 'bash -s -- runner-sync' "$DEPLOY" | grep -q 'sudo'; then
    fail "runner-sync must not use sudo; the destination is mediaops-owned"
fi

if grep -Eq \
    '(cp|install|rsync).*/usr/local/sbin/mediaops-release|/etc/sudoers' \
    "$DEPLOY"; then
    fail "deploy script must not install the helper or sudoers"
fi

# --- stubbed execute-path tests (no real SSH or network, ever) -----------

STUB_ROOT="$(mktemp -d)"
trap 'rm -rf "$STUB_ROOT"' EXIT
STUB_BIN="${STUB_ROOT}/bin"
mkdir -p -- "$STUB_BIN"
readonly TARGET_COMMIT="0123456789abcdef0123456789abcdef01234567"

cat > "${STUB_BIN}/ssh" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail

state="${MEDIAOPS_STUB_STATE:?MEDIAOPS_STUB_STATE is required}"
log="${state}/ssh.log"
markers="${state}/markers"
mkdir -p -- "$state"
touch -- "$log" "$markers"

if [[ "${1:-}" == "-G" ]]; then
    printf 'hostname 203.0.113.10\nuser mediaops\n'
    exit 0
fi

host=""
command_string=""
while (($# > 0)); do
    case "$1" in
        -o)
            shift 2
            ;;
        *)
            if [[ -z "$host" ]]; then
                host="$1"
            elif [[ -z "$command_string" ]]; then
                command_string="$1"
            else
                command_string="${command_string} $1"
            fi
            shift
            ;;
    esac
done
printf '%s\n' "$command_string" >> "$log"

read -ra words <<<"$command_string"

mark_done() {
    printf '%s=done 2026-07-26T00:00:00Z\n' "$1" >> "$markers"
}

consume_stdin() {
    cat >/dev/null
}

run_stage() {
    local stage="$1"
    consume_stdin
    if [[ "$stage" == "${MEDIAOPS_STUB_FAIL_STAGE:-}" ]]; then
        if [[ "${MEDIAOPS_STUB_FAIL_COMPLETES:-0}" == "1" ]]; then
            mark_done "$stage"
        fi
        exit "${MEDIAOPS_STUB_FAIL_CODE:-1}"
    fi
    mark_done "$stage"
    printf 'stub_stage=%s\n' "$stage"
    exit 0
}

case "$command_string" in
    true)
        exit 0
        ;;
    "bash -s")
        consume_stdin
        printf 'Backup created: /var/backups/mediaops/stub\n'
        printf 'Checksum file: /var/backups/mediaops/stub/SHA256SUMS\n'
        exit 0
        ;;
    "bash -s -- preflight "*)
        consume_stdin
        printf 'remote_user=mediaops\n'
        printf 'remote_host=stub-host\n'
        printf 'worktree=clean\n'
        printf 'old_commit=fedcba9876543210fedcba9876543210fedcba98\n'
        printf 'target_commit=%s\n' "${words[4]}"
        printf 'target_ref=%s\n' "${words[4]}"
        printf 'database_migration=%s\n' "${MEDIAOPS_STUB_MIGRATION:-no}"
        printf 'migration_authorized=%s\n' "${words[5]}"
        printf 'database_backup=pending\n'
        printf 'tests=backend-pytest,frontend-lint,frontend-test,frontend-build\n'
        printf 'helper_version=1\n'
        printf 'helper_subcommand=finalize\n'
        exit 0
        ;;
    "bash -s -- git-sync "*)
        run_stage git-sync
        ;;
    "bash -s -- runner-sync "*)
        run_stage runner-sync
        ;;
    "bash -s -- backend-test "*)
        run_stage backend-test
        ;;
    "bash -s -- frontend-build "*)
        run_stage frontend-build
        ;;
    "bash -s -- migrate "*)
        run_stage migrate
        ;;
    "bash -s -- finalize "*)
        run_stage finalize
        ;;
    "bash -s -- write-stage-marker "*)
        consume_stdin
        mark_done "${words[5]}"
        exit 0
        ;;
    "bash -s -- reset-stage-markers "*)
        consume_stdin
        : > "$markers"
        exit 0
        ;;
    "bash -s -- verify-publish-marker "*)
        consume_stdin
        printf 'published_release=stub\n'
        printf 'built_release=stub\n'
        printf 'release_marker_parity=%s\n' "${MEDIAOPS_STUB_PARITY:-match}"
        exit 0
        ;;
    "bash -s -- verify-sni-loopback "*)
        consume_stdin
        if [[ "${MEDIAOPS_STUB_SNI_FAIL:-0}" == "1" ]]; then
            printf 'sni_frontend=failed\n' >&2
            exit 22
        fi
        printf 'api=active\n'
        printf 'worker=active\n'
        printf 'sni_frontend=ok http=200 host=ops.example.test\n'
        printf 'sni_public_api=ok http=200 host=ops.example.test\n'
        printf 'sni_crawler_route=ok http=200 host=ops.example.test\n'
        exit 0
        ;;
    "bash -s -- record-deployment "*)
        consume_stdin
        exit 0
        ;;
    "cat -- '/var/lib/mediaops/deploy-state/"*)
        cat -- "$markers"
        exit 0
        ;;
    "grep -q -- "*)
        if [[ "$command_string" =~ \^([a-z-]+)=done ]]; then
            if grep -q "^${BASH_REMATCH[1]}=done" "$markers"; then
                exit 0
            fi
        fi
        exit 1
        ;;
    "curl -fsS --max-time 10 http://127.0.0.1:8000/api/health")
        printf '{"status": "ok", "service": "personal-media-ops-api", "version": "stub"}\n'
        exit 0
        ;;
    "sudo -n /usr/local/sbin/mediaops-release restart-services")
        exit 0
        ;;
    "sudo -n /usr/local/sbin/mediaops-release nginx-reload")
        exit 0
        ;;
    "sudo -n /usr/local/sbin/mediaops-release verify")
        exit 0
        ;;
    *)
        printf 'stub-ssh: unhandled command: %s\n' "$command_string" >&2
        exit 97
        ;;
esac
STUB
chmod +x "${STUB_BIN}/ssh"

cat > "${STUB_BIN}/curl" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
state="${MEDIAOPS_STUB_STATE:?MEDIAOPS_STUB_STATE is required}"
mkdir -p -- "$state"
printf 'curl %s\n' "$*" >> "${state}/curl.log"
case "${MEDIAOPS_STUB_CURL_MODE:-ok}" in
    ok)
        printf '{"status": "ok", "service": "personal-media-ops-api", "version": "stub"}\n200\n'
        ;;
    connection-failed)
        printf 'curl: simulated TLS reset\n' >&2
        exit 35
        ;;
    http-403)
        printf 'blocked\n403\n'
        ;;
    http-500)
        printf 'origin failure\n500\n'
        ;;
    *)
        printf 'unknown stub curl mode\n' >&2
        exit 2
        ;;
esac
STUB
chmod +x "${STUB_BIN}/curl"

bash -n "${STUB_BIN}/ssh" "${STUB_BIN}/curl"

stub_state_reset() {
    local state="$1"
    mkdir -p -- "$state"
    : > "${state}/markers"
    : > "${state}/ssh.log"
    : > "${state}/curl.log"
}

run_stubbed_deploy() {
    local state="$1"
    shift
    PATH="${STUB_BIN}:${PATH}" MEDIAOPS_STUB_STATE="$state" \
        MEDIAOPS_STUB_CURL_MODE="${MEDIAOPS_STUB_CURL_MODE:-ok}" \
        MEDIAOPS_STUB_SNI_FAIL="${MEDIAOPS_STUB_SNI_FAIL:-0}" \
        "$DEPLOY" \
        --host stub-mediaops \
        --target-ref "$TARGET_COMMIT" \
        "$@" 2>&1
}

# 1. Dry-run must never invoke ssh or curl, even with the stubs on PATH.
state_dry="${STUB_ROOT}/state-dry"
stub_state_reset "$state_dry"
stub_dry_output="$(run_stubbed_deploy "$state_dry" --dry-run)"
assert_contains "$stub_dry_output" "Dry run only"
if [[ -s "${state_dry}/ssh.log" ]]; then
    fail "dry-run must not invoke ssh"
fi
if [[ -s "${state_dry}/curl.log" ]]; then
    fail "dry-run must not invoke curl"
fi

# 2. A full staged execute run succeeds and records every stage marker.
state_ok="${STUB_ROOT}/state-ok"
stub_state_reset "$state_ok"
execute_output="$(run_stubbed_deploy "$state_ok" --execute)"
assert_contains "$execute_output" "Deployment succeeded"
assert_contains "$execute_output" "New commit: ${TARGET_COMMIT}"
for stage in backup git-sync runner-sync backend-test frontend-build finalize; do
    grep -q "^${stage}=done" "${state_ok}/markers" ||
        fail "stage marker missing after execute: ${stage}"
done
if grep -qF "bash -s -- migrate" "${state_ok}/ssh.log"; then
    fail "migrate stage must not run without detected migrations"
fi

# runner-sync must run between git-sync and backend-test.
git_sync_line="$(
    grep -nF "bash -s -- git-sync" "${state_ok}/ssh.log" | head -n 1 | cut -d: -f1
)"
runner_sync_line="$(
    grep -nF "bash -s -- runner-sync" "${state_ok}/ssh.log" | head -n 1 | cut -d: -f1
)"
backend_test_line="$(
    grep -nF "bash -s -- backend-test" "${state_ok}/ssh.log" | head -n 1 | cut -d: -f1
)"
[[ "$git_sync_line" =~ ^[0-9]+$ &&
   "$runner_sync_line" =~ ^[0-9]+$ &&
   "$backend_test_line" =~ ^[0-9]+$ &&
   "$git_sync_line" -lt "$runner_sync_line" &&
   "$runner_sync_line" -lt "$backend_test_line" ]] ||
    fail "runner-sync must run between git-sync and backend-test"

# 3. --resume skips stages already marked done for the same target commit.
state_resume="${STUB_ROOT}/state-resume"
stub_state_reset "$state_resume"
{
    printf 'backup=done 2026-07-26T00:00:00Z\n'
    printf 'git-sync=done 2026-07-26T00:00:00Z\n'
    printf 'runner-sync=done 2026-07-26T00:00:00Z\n'
    printf 'backend-test=done 2026-07-26T00:00:00Z\n'
} > "${state_resume}/markers"
resume_output="$(run_stubbed_deploy "$state_resume" --execute --resume)"
assert_contains "$resume_output" "skipping: backup"
assert_contains "$resume_output" "skipping: git-sync"
assert_contains "$resume_output" "skipping: runner-sync"
assert_contains "$resume_output" "skipping: backend-test"
assert_contains "$resume_output" "Deployment succeeded"
if grep -qx "bash -s" "${state_resume}/ssh.log"; then
    fail "resume must not rerun the completed backup stage"
fi
if grep -qF "bash -s -- git-sync" "${state_resume}/ssh.log"; then
    fail "resume must not rerun the completed git-sync stage"
fi
if grep -qF "bash -s -- runner-sync" "${state_resume}/ssh.log"; then
    fail "resume must not rerun the completed runner-sync stage"
fi
if grep -qF "bash -s -- backend-test" "${state_resume}/ssh.log"; then
    fail "resume must not rerun the completed backend-test stage"
fi
grep -qF "bash -s -- frontend-build" "${state_resume}/ssh.log" ||
    fail "resume must still run stages without a done marker"

# 4. SSH exit 255 with a completed remote marker is a transport anomaly.
state_255="${STUB_ROOT}/state-255"
stub_state_reset "$state_255"
transport_output="$(
    MEDIAOPS_STUB_FAIL_STAGE=frontend-build \
    MEDIAOPS_STUB_FAIL_CODE=255 \
    MEDIAOPS_STUB_FAIL_COMPLETES=1 \
        run_stubbed_deploy "$state_255" --execute
)"
assert_contains "$transport_output" \
    "SSH transport anomaly, stage completed remotely: frontend-build"
assert_contains "$transport_output" "Deployment succeeded"

# 5. SSH exit 255 without a remote marker still fails with the stage name.
state_255_fail="${STUB_ROOT}/state-255-fail"
stub_state_reset "$state_255_fail"
if transport_fail_output="$(
    MEDIAOPS_STUB_FAIL_STAGE=frontend-build \
    MEDIAOPS_STUB_FAIL_CODE=255 \
        run_stubbed_deploy "$state_255_fail" --execute
)"; then
    fail "deployment must fail when SSH dies and the stage marker is absent"
fi
assert_contains "$transport_fail_output" "stage did not complete: frontend-build"

# 5b. A stale marker from an earlier attempt must not satisfy the exit-255
# recheck in a non-resume run: execute clears the marker file first.
state_stale="${STUB_ROOT}/state-stale"
stub_state_reset "$state_stale"
printf 'frontend-build=done 2026-07-25T00:00:00Z\n' > "${state_stale}/markers"
if stale_output="$(
    MEDIAOPS_STUB_FAIL_STAGE=frontend-build \
    MEDIAOPS_STUB_FAIL_CODE=255 \
        run_stubbed_deploy "$state_stale" --execute
)"; then
    fail "a stale stage marker must not mask a failed stage in a non-resume run"
fi
assert_contains "$stale_output" "stage did not complete: frontend-build"

# 6. Finalize fallback: helper v1 fails but release markers match the target.
state_fallback="${STUB_ROOT}/state-fallback"
stub_state_reset "$state_fallback"
fallback_output="$(
    MEDIAOPS_STUB_FAIL_STAGE=finalize \
    MEDIAOPS_STUB_FAIL_CODE=23 \
    MEDIAOPS_STUB_PARITY=match \
        run_stubbed_deploy "$state_fallback" --execute
)"
assert_contains "$fallback_output" "finalize fallback succeeded"
assert_contains "$fallback_output" "Deployment succeeded"
for subcommand in restart-services nginx-reload verify; do
    grep -qF "sudo -n /usr/local/sbin/mediaops-release ${subcommand}" \
        "${state_fallback}/ssh.log" ||
        fail "finalize fallback must invoke helper subcommand: ${subcommand}"
done
grep -q "^finalize=done" "${state_fallback}/markers" ||
    fail "finalize fallback must record the finalize stage marker"

# 7. Finalize fallback aborts when the release markers do not match.
state_mismatch="${STUB_ROOT}/state-mismatch"
stub_state_reset "$state_mismatch"
if mismatch_output="$(
    MEDIAOPS_STUB_FAIL_STAGE=finalize \
    MEDIAOPS_STUB_FAIL_CODE=23 \
    MEDIAOPS_STUB_PARITY=mismatch \
        run_stubbed_deploy "$state_mismatch" --execute
)"; then
    fail "deployment must fail when finalize fails and markers do not match"
fi
assert_contains "$mismatch_output" "release markers do not match"
if grep -qF "mediaops-release restart-services" "${state_mismatch}/ssh.log"; then
    fail "fallback must not restart services when markers do not match"
fi

# 8. Authorized migrations run the migrate stage; unauthorized ones abort.
state_migration="${STUB_ROOT}/state-migration"
stub_state_reset "$state_migration"
migration_output="$(
    MEDIAOPS_STUB_MIGRATION=yes \
        run_stubbed_deploy "$state_migration" --execute --allow-migrations
)"
assert_contains "$migration_output" "Deployment succeeded"
grep -qF "bash -s -- migrate" "${state_migration}/ssh.log" ||
    fail "authorized migration must run the migrate stage"
grep -q "^migrate=done" "${state_migration}/markers" ||
    fail "authorized migration must record the migrate stage marker"

state_unauthorized="${STUB_ROOT}/state-unauthorized"
stub_state_reset "$state_unauthorized"
if unauthorized_output="$(
    MEDIAOPS_STUB_MIGRATION=yes \
        run_stubbed_deploy "$state_unauthorized" --execute
)"; then
    fail "deployment must fail when a migration is detected without --allow-migrations"
fi
assert_contains "$unauthorized_output" "not explicitly authorized"
if grep -qF "bash -s -- migrate" "${state_unauthorized}/ssh.log"; then
    fail "unauthorized migration must never reach the migrate stage"
fi

# 9. The known external observer failure is non-blocking only when production
# helper/SNI loopback verification succeeds.
state_observer="${STUB_ROOT}/state-observer"
stub_state_reset "$state_observer"
observer_output="$(
    MEDIAOPS_STUB_CURL_MODE=connection-failed \
        run_stubbed_deploy "$state_observer" --execute
)"
assert_contains "$observer_output" \
    "external observer failure recorded as non-blocking"
assert_contains "$observer_output" "External observer: failed-nonblocking"
grep -qF "bash -s -- verify-sni-loopback" "${state_observer}/ssh.log" ||
    fail "observer transport failure must trigger production SNI loopback"

# 10. The exception never hides a failed production SNI loopback.
state_sni_fail="${STUB_ROOT}/state-sni-fail"
stub_state_reset "$state_sni_fail"
if sni_fail_output="$(
    MEDIAOPS_STUB_CURL_MODE=http-403 \
    MEDIAOPS_STUB_SNI_FAIL=1 \
        run_stubbed_deploy "$state_sni_fail" --execute
)"; then
    fail "deployment must fail when observer and production SNI checks both fail"
fi
assert_contains "$sni_fail_output" \
    "production SNI loopback verification did not pass"

# 11. An arbitrary public HTTP failure is not an observer exception.
state_public_500="${STUB_ROOT}/state-public-500"
stub_state_reset "$state_public_500"
if public_500_output="$(
    MEDIAOPS_STUB_CURL_MODE=http-500 \
        run_stubbed_deploy "$state_public_500" --execute
)"; then
    fail "deployment must fail on a public HTTP 500"
fi
assert_contains "$public_500_output" \
    "failed outside the approved external-observer exception"
if grep -qF "bash -s -- verify-sni-loopback" \
    "${state_public_500}/ssh.log"; then
    fail "public HTTP 500 must not use the observer exception"
fi

printf 'release_script_tests=passed\n'

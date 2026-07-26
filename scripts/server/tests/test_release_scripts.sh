#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
DEPLOY="${REPOSITORY_ROOT}/scripts/server/deploy.sh"
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

bash -n "$DEPLOY" "$HELPER"

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

if grep -Eq \
    '(cp|install|rsync).*/usr/local/sbin/mediaops-release|/etc/sudoers' \
    "$DEPLOY"; then
    fail "deploy script must not install the helper or sudoers"
fi

printf 'release_script_tests=passed\n'

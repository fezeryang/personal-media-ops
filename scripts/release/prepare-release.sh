#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_GATE="${REPOSITORY_ROOT}/scripts/test/local-gate.sh"

usage() {
    cat <<'EOF'
Usage: prepare-release.sh [--output FILE]
                          [--allow-unrelated-dirty PATH]

Run the local gate and write a non-secret Release Candidate manifest. The
manifest identifies one pushed commit and may only allow explicitly named,
pre-existing task-unrelated dirty paths.
EOF
}

output="${REPOSITORY_ROOT}/.release/rc.env"
declare -a allowed_dirty=()
while (($# > 0)); do
    case "$1" in
        --output)
            [[ -n "${2:-}" && "$2" != --* ]] || { printf 'ERROR: --output requires a value\n' >&2; exit 2; }
            output="$2"
            shift 2
            ;;
        --allow-unrelated-dirty)
            [[ -n "${2:-}" && "$2" != --* ]] || { printf 'ERROR: --allow-unrelated-dirty requires a path\n' >&2; exit 2; }
            allowed_dirty+=("$2")
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: unknown argument: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

cd -- "$REPOSITORY_ROOT"
printf '==> Running local gate before creating Release Candidate\n'
"$LOCAL_GATE"

release_commit="$(git rev-parse HEAD)"
origin_commit="$(git rev-parse origin/main 2>/dev/null || true)"
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || {
    printf 'ERROR: HEAD is not a full commit hash\n' >&2
    exit 3
}
[[ "$origin_commit" == "$release_commit" ]] || {
    printf 'ERROR: HEAD is not equal to origin/main; push the commit before preparing RC\n' >&2
    printf '       HEAD=%s origin/main=%s\n' "$release_commit" "${origin_commit:-missing}" >&2
    exit 3
}

matches_allowed() {
    local candidate="$1"
    local allowed
    for allowed in "${allowed_dirty[@]}"; do
        [[ "$candidate" == "$allowed" ]] && return 0
    done
    return 1
}

declare -a dirty_paths=()
while IFS= read -r status_line; do
    [[ -n "$status_line" ]] || continue
    dirty_paths+=("${status_line:3}")
done < <(git status --porcelain=v1 --untracked-files=all)
for path in "${dirty_paths[@]}"; do
    matches_allowed "$path" || {
        printf 'ERROR: worktree contains unapproved dirty path: %s\n' "$path" >&2
        printf 'Use --allow-unrelated-dirty only for a known pre-existing path outside this release.\n' >&2
        exit 4
    }
done

migration_paths="$(git diff --name-only "${release_commit}^" "$release_commit" | grep -E \
    '(^|/)(migrations?|alembic)(/|$)|\.sql$|^backend/app/db\.py$|^backend/app/models/' || true)"
migration_state="no"
[[ -n "$migration_paths" ]] && migration_state="yes"

mkdir -p -- "$(dirname -- "$output")"
{
    printf 'release_manifest_version=1\n'
    printf 'release_candidate_status=ready\n'
    printf 'release_commit=%s\n' "$release_commit"
    printf 'origin_main=%s\n' "$origin_commit"
    printf 'local_gate_status=passed\n'
    printf 'local_visual_status=passed\n'
    printf 'migration_state=%s\n' "$migration_state"
    printf 'migration_paths=%s\n' "${migration_paths//$'\n'/,}"
    printf 'previous_production_commit=pending_server_preflight\n'
    printf 'worktree_status=%s\n' "$(if ((${#dirty_paths[@]} == 0)); then printf clean; else printf unrelated_dirty_allowed; fi)"
    printf 'unrelated_dirty_paths=%s\n' "$(IFS=,; printf '%s' "${dirty_paths[*]:-}")"
    printf 'visual_evidence=docs/evidence/local-fixtures-1440x900.png,docs/evidence/local-fixtures-1280x720.png,docs/evidence/local-fixtures-390x844.png,docs/evidence/local-opportunity-1440x900.png,docs/evidence/local-opportunity-1280x720.png,docs/evidence/local-opportunity-390x844.png\n'
    printf 'prepared_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >"$output"
chmod 600 -- "$output"
printf 'Release Candidate prepared: %s\n' "$output"
printf 'release_commit=%s\n' "$release_commit"
printf 'release_candidate_status=ready\n'

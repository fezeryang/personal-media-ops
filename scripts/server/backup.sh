#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.bash
source "${SCRIPT_DIR}/lib/common.bash"
mediaops_enable_error_trap

usage() {
    cat <<'EOF'
Usage: backup.sh [--host SSH_ALIAS] [--dry-run | --execute]

Create a consistent SQLite backup on the production server.

Options:
  --host SSH_ALIAS  SSH config alias (default: MEDIAOPS_SSH_HOST or mediaops-prod)
  --dry-run          Print the backup plan without connecting (default)
  --execute         Perform the backup. Without this flag, print the plan only.
  -h, --help        Show this help.

The backup contains the SQLite database, deployment metadata, and checksums.
It excludes .env files, credentials, QR codes, virtual environments, caches,
and crawler result data.
EOF
}

host_override=""
execute=false
dry_run=false

while (($# > 0)); do
    case "$1" in
        --host)
            mediaops_require_value "$1" "${2:-}"
            host_override="$2"
            shift 2
            ;;
        --execute)
            execute=true
            shift
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            mediaops_die "unknown argument: $1"
            ;;
    esac
done

host="$(mediaops_resolve_host "$host_override")"
mediaops_validate_host "$host"
if [[ "$execute" == true && "$dry_run" == true ]]; then
    mediaops_die "--dry-run and --execute are mutually exclusive"
fi

mediaops_stage "Backup plan"
printf 'Target server: %s\n' "$host"
printf 'Database: %s\n' "$MEDIAOPS_DATABASE"
printf 'Backup root: %s\n' "$MEDIAOPS_BACKUP_ROOT"
printf 'Included: consistent SQLite copy, Git commit, timestamp, SHA-256 checksum\n'
printf 'Excluded: .env, cookies, QR codes, SSH keys, caches, virtual environments, crawler results\n'

if [[ "$execute" != true ]]; then
    printf 'Dry run only. Re-run with --execute to create the backup.\n'
    exit 0
fi

mediaops_require_ssh "$host"
mediaops_stage "Creating production backup"

mediaops_ssh "$host" 'bash -s' <<'REMOTE'
set -Eeuo pipefail

database_path="/var/lib/mediaops/mediaops.db"
backup_root="/var/backups/mediaops"
repository="/opt/personal-media-ops"
backend_python="/opt/personal-media-ops/backend/.venv/bin/python"

if [[ ! -f "$database_path" ]]; then
    printf 'ERROR: database does not exist: %s\n' "$database_path" >&2
    exit 2
fi

if [[ ! -r "$database_path" ]]; then
    printf 'ERROR: database is not readable by %s: %s\n' "$(id -un)" "$database_path" >&2
    exit 3
fi

if [[ ! -x "$backend_python" ]]; then
    printf 'ERROR: backend Python is unavailable: %s\n' "$backend_python" >&2
    exit 2
fi

if [[ ! -d "$backup_root" || ! -w "$backup_root" ]]; then
    printf 'ERROR: backup root is missing or not writable by %s: %s\n' "$(id -un)" "$backup_root" >&2
    printf 'Root preparation required:\n' >&2
    printf '  sudo install -d -o mediaops -g mediaops -m 0750 %s\n' "$backup_root" >&2
    exit 3
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${timestamp}"
suffix=0
while [[ -e "$backup_dir" ]]; do
    suffix=$((suffix + 1))
    backup_dir="${backup_root}/${timestamp}-${suffix}"
done

umask 077
mkdir -- "$backup_dir"
backup_database="${backup_dir}/mediaops.db"

"$backend_python" - "$database_path" "$backup_database" <<'PY'
import sqlite3
import sys
from urllib.parse import quote

source_path, destination_path = sys.argv[1:3]
source_uri = f"file:{quote(source_path, safe='/')}?mode=ro"

with sqlite3.connect(source_uri, uri=True) as source:
    with sqlite3.connect(destination_path) as destination:
        source.backup(destination)
        result = destination.execute("PRAGMA integrity_check").fetchone()

if result is None or result[0] != "ok":
    raise SystemExit(f"SQLite integrity check failed: {result!r}")
PY

git_commit="unknown"
if [[ -d "${repository}/.git" ]]; then
    git_commit="$(git -C "$repository" rev-parse HEAD 2>/dev/null || printf 'unknown')"
fi

{
    printf 'environment=mediaops-prod\n'
    printf 'created_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'created_by=%s\n' "$(id -un)"
    printf 'source_database=%s\n' "$database_path"
    printf 'git_commit=%s\n' "$git_commit"
} > "${backup_dir}/metadata.txt"

(
    cd -- "$backup_dir"
    sha256sum mediaops.db metadata.txt > SHA256SUMS
)

printf 'Backup created: %s\n' "$backup_dir"
printf 'Checksum file: %s/SHA256SUMS\n' "$backup_dir"
printf 'Database SHA-256: %s\n' "$(sha256sum "${backup_dir}/mediaops.db" | awk '{print $1}')"
REMOTE

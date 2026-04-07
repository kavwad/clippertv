#!/usr/bin/env bash
# Weekly Clipper CSV ingestion wrapper for launchd.
#
# Usage: ./clippertv-ingest.sh [--dry-run]
#
# Requires:
#   - uv (https://docs.astral.sh/uv/)
#   - .env in REPO_DIR with TURSO_DATABASE_URL, TURSO_AUTH_TOKEN, ENCRYPTION_KEY

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/ingest-$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "Starting Clipper CSV ingestion"
log "Repo: ${REPO_DIR}"

cd "$REPO_DIR"

EXTRA_ARGS=()
if [[ "${1:-}" == "--dry-run" ]]; then
    EXTRA_ARGS+=(--dry-run)
    log "Dry-run mode"
fi

uv run clippertv-ingest --days 30 "${EXTRA_ARGS[@]}" -v 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

if [[ $EXIT_CODE -eq 0 ]]; then
    log "Ingestion completed successfully"
    [[ -n "$HEALTHCHECK_URL" ]] && curl -fsS -m 10 "$HEALTHCHECK_URL" > /dev/null || true
else
    log "Ingestion failed with exit code ${EXIT_CODE}"
    [[ -n "$HEALTHCHECK_URL" ]] && curl -fsS -m 10 "$HEALTHCHECK_URL/fail" > /dev/null || true
fi

# Prune logs older than 90 days
find "$LOG_DIR" -name 'ingest-*.log' -mtime +90 -delete 2>/dev/null || true

exit "$EXIT_CODE"

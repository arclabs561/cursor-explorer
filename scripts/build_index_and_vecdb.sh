#!/usr/bin/env bash
set -euo pipefail

JOB="build_index_and_vecdb"
REPO="/Users/henry/Documents/dev/devdev"
source "$(dirname "$0")/lib.sh"

cd "$REPO"

# Load local env if present
if [[ -f "$REPO/scripts/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO/scripts/.env"
  set +a
fi

# Also load repo-level .env if present
if [[ -f "$REPO/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO/.env"
  set +a
fi
# Optional user-level env files
if [[ -f "$HOME/.cursor-explorer.env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.cursor-explorer.env"
fi
if [[ -f "$HOME/.cursor_explorer.env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.cursor_explorer.env"
fi

export PYTHONPATH="$REPO/src"
: "${LLM_LOG_PATH:=$REPO/logs/llm_usage.jsonl}"

mkdir -p "$REPO/logs" "$REPO/.locks"
LOG_FILE="${LOG_FILE:-$REPO/logs/$JOB.$(date -u '+%Y%m%dT%H%M%SZ').log}"

find_uv

INDEX_JSONL="${INDEX_JSONL:-$REPO/cursor_index.jsonl}"
VEC_DB="${VEC_DB:-$REPO/cursor_vec.db}"
LIMIT_COMPOSERS="${LIMIT_COMPOSERS:-200}"
MAX_TURNS="${MAX_TURNS:-50}"

if ! acquire_lock "$JOB"; then
  log "already running, skipping"
  exit 0
fi
trap release_lock EXIT

run_index() {
  PYTHONPATH="$REPO/src" "$UV_BIN" run python -m cursor_explorer \
    index "$INDEX_JSONL" --limit-composers "$LIMIT_COMPOSERS" --max-turns "$MAX_TURNS" \
    --trace-meta job="$JOB" --trace-meta runner=script
}

run_vec() {
  PYTHONPATH="$REPO/src" "$UV_BIN" run python -m cursor_explorer \
    vec-db-index "$VEC_DB" "$INDEX_JSONL" \
    --trace-meta job="$JOB" --trace-meta runner=script
}

log "index step starting"
if ! retry 3 15 run_index; then
  log "index step failed after retries"
  notify error "Index step failed"
  exit 1
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  log "OPENAI_API_KEY not set; skipping vec-db-index step"
else
  log "vec-db-index step starting"
  if ! retry 3 15 run_vec; then
    log "vec-db-index step failed after retries"
    notify error "Vec DB index step failed"
    exit 1
  fi
fi
log "completed successfully"
notify ok "Completed successfully"



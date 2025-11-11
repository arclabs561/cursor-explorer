#!/usr/bin/env bash
set -euo pipefail

JOB="agent_query_fuzzer"
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

FUZZ_SEED="${FUZZ_SEED:-prompt injection and code-exec}"
FUZZ_STEPS="${FUZZ_STEPS:-5}"

# Require OpenAI key for agent runs
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  log "ERROR: OPENAI_API_KEY not set. Provide it via $REPO/scripts/.env or $REPO/.env"
  notify error "Missing OPENAI_API_KEY"
  exit 2
fi

if ! acquire_lock "$JOB"; then
  log "already running, skipping"
  exit 0
fi
trap release_lock EXIT

run_cmd() {
  PYTHONPATH="$REPO/src" "$UV_BIN" run python -m cursor_explorer \
    fuzz-agent --seed "$FUZZ_SEED" --steps "$FUZZ_STEPS" \
    --trace-meta job="$JOB" --trace-meta runner=script
}

log "starting"
if retry 3 15 run_cmd; then
  log "completed successfully"
  notify ok "Completed successfully"
else
  log "failed after retries"
  notify error "Failed after retries"
  exit 1
fi



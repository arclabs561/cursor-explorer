#!/usr/bin/env bash
set -euo pipefail

# Common helpers for job scripts

# Default repo path; can be overridden by environment
REPO="${REPO:-/Users/henry/Documents/dev/devdev}"
LOG_DIR="${LOG_DIR:-$REPO/logs}"

log() {
  local line
  line="[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] ${JOB:-job}: $*"
  if [[ -n "${LOG_FILE:-}" ]]; then
    echo "$line" | tee -a "$LOG_FILE"
  else
    echo "$line"
  fi
}

# Optional Slack-compatible webhook notification
notify() {
  local level="$1"; shift || true
  local text="$*"
  local url="${SLACK_WEBHOOK_URL:-${NOTIFY_WEBHOOK_URL:-}}"
  if [[ -z "$url" ]]; then
    return 0
  fi
  # escape quotes for JSON
  local esc
  esc="$(echo "$text" | sed 's/"/\\"/g')"
  local payload
  payload=$(printf '{"text":"[%s] %s: %s"}' "$level" "${JOB:-job}" "$esc")
  curl -s -X POST -H 'Content-type: application/json' --data "$payload" "$url" >/dev/null || true
}

find_uv() {
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
  elif [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
  elif [[ -x "/opt/homebrew/bin/uv" ]]; then
    UV_BIN="/opt/homebrew/bin/uv"
  else
    log "uv not found in PATH; install uv or adjust PATH"
    exit 127
  fi
}

acquire_lock() {
  local name="$1"
  LOCKDIR="$REPO/.locks/${name}.lock"
  if mkdir "$LOCKDIR" 2>/dev/null; then
    return 0
  else
    return 1
  fi
}

release_lock() {
  if [[ -n "${LOCKDIR:-}" && -d "$LOCKDIR" ]]; then
    rmdir "$LOCKDIR" || true
  fi
}

retry() {
  local attempts="$1"; shift
  local sleep_base="$1"; shift
  local n=1
  while true; do
    if "$@"; then
      return 0
    fi
    if [[ $n -ge $attempts ]]; then
      return 1
    fi
    sleep $((sleep_base * n))
    n=$((n + 1))
  done
}



#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_NAME="${APP_NAME:-quant-ai}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
PIP_BIN="${PIP_BIN:-$VENV_DIR/bin/pip}"
HEALTHCHECK_SCRIPT="${HEALTHCHECK_SCRIPT:-$APP_DIR/scripts/server_healthcheck.sh}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:5000/healthz}"

log() {
    printf '[rollback] %s\n' "$1"
}

fail() {
    printf '[rollback] ERROR: %s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

main() {
    require_command git
    require_command systemctl
    [[ $# -eq 1 ]] || fail "usage: bash scripts/server_rollback.sh <commit>"
    [[ -x "$PIP_BIN" ]] || fail "missing pip executable: $PIP_BIN"
    [[ -x "$HEALTHCHECK_SCRIPT" ]] || fail "missing healthcheck script: $HEALTHCHECK_SCRIPT"

    local target_commit="$1"
    cd "$APP_DIR"

    log "rolling back to $target_commit"
    git reset --hard "$target_commit"

    log "installing dependencies"
    "$PIP_BIN" install -r requirements.txt

    log "restarting service $APP_NAME"
    systemctl restart "$APP_NAME"

    log "running healthcheck"
    APP_NAME="$APP_NAME" HEALTHCHECK_URL="$HEALTHCHECK_URL" bash "$HEALTHCHECK_SCRIPT"

    log "rollback finished at $(date -Iseconds)"
}

main "$@"

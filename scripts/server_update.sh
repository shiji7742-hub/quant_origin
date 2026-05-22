#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_NAME="${APP_NAME:-quant-ai}"
REMOTE_NAME="${REMOTE_NAME:-quant-origin}"
BRANCH_NAME="${BRANCH_NAME:-main}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
PIP_BIN="${PIP_BIN:-$VENV_DIR/bin/pip}"
HEALTHCHECK_SCRIPT="${HEALTHCHECK_SCRIPT:-$APP_DIR/scripts/server_healthcheck.sh}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:5000/healthz}"

log() {
    printf '[update] %s\n' "$1"
}

fail() {
    printf '[update] ERROR: %s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

main() {
    require_command git
    require_command systemctl
    [[ -x "$PIP_BIN" ]] || fail "missing pip executable: $PIP_BIN"
    [[ -x "$HEALTHCHECK_SCRIPT" ]] || fail "missing healthcheck script: $HEALTHCHECK_SCRIPT"

    cd "$APP_DIR"

    local old_commit
    old_commit="$(git rev-parse HEAD)"
    log "old_commit=$old_commit"
    log "fetching $REMOTE_NAME/$BRANCH_NAME"
    git fetch "$REMOTE_NAME"
    git checkout "$BRANCH_NAME"
    git reset --hard "$REMOTE_NAME/$BRANCH_NAME"

    local new_commit
    new_commit="$(git rev-parse HEAD)"
    log "new_commit=$new_commit"

    log "installing dependencies"
    "$PIP_BIN" install -r requirements.txt

    log "restarting service $APP_NAME"
    systemctl restart "$APP_NAME"

    log "running healthcheck"
    APP_NAME="$APP_NAME" HEALTHCHECK_URL="$HEALTHCHECK_URL" bash "$HEALTHCHECK_SCRIPT"

    log "update finished at $(date -Iseconds)"
    log "rollback if needed: APP_DIR=$APP_DIR APP_NAME=$APP_NAME VENV_DIR=$VENV_DIR HEALTHCHECK_URL=$HEALTHCHECK_URL bash scripts/server_rollback.sh $old_commit"
}

main "$@"

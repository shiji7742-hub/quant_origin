#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-quant-ai}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:5000/healthz}"
CURL_BIN="${CURL_BIN:-curl}"

log() {
    printf '[healthcheck] %s\n' "$1"
}

fail() {
    printf '[healthcheck] ERROR: %s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

main() {
    require_command systemctl
    require_command "$CURL_BIN"

    local service_state
    service_state="$(systemctl is-active "$APP_NAME" || true)"
    [[ "$service_state" == "active" ]] || fail "service $APP_NAME is not active: $service_state"

    local payload
    payload="$("$CURL_BIN" --fail --silent --show-error "$HEALTHCHECK_URL")"
    printf '%s' "$payload" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' || fail "health endpoint is not ok"

    log "service $APP_NAME is active"
    log "health endpoint ok: $HEALTHCHECK_URL"
}

main "$@"

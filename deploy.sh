#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="${APP_NAME:-quant-ai}"
APP_USER="${APP_USER:-$(id -un)}"
APP_GROUP="${APP_GROUP:-$(id -gn)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
WORKERS="${WORKERS:-2}"
SERVICE_TEMPLATE="$APP_DIR/deploy/quant-ai.service"
SERVICE_TARGET="${SERVICE_TARGET:-/etc/systemd/system/${APP_NAME}.service}"
SKIP_SERVICE_INSTALL="${SKIP_SERVICE_INSTALL:-0}"

log() {
    printf '[deploy] %s\n' "$1"
}

fail() {
    printf '[deploy] ERROR: %s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

install_python_env() {
    require_command "$PYTHON_BIN"

    if [[ ! -d "$VENV_DIR" ]]; then
        log "creating virtualenv at $VENV_DIR"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi

    log "installing Python dependencies"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" gunicorn
}

ensure_env_file() {
    if [[ -f "$APP_DIR/.env" ]]; then
        return
    fi

    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    log "created $APP_DIR/.env from template"
    log "edit .env before exposing the service publicly"
}

install_service() {
    require_command systemctl
    [[ -f "$SERVICE_TEMPLATE" ]] || fail "missing service template: $SERVICE_TEMPLATE"

    if [[ "${EUID}" -ne 0 ]]; then
        fail "run with sudo/root to install the systemd service, or set SKIP_SERVICE_INSTALL=1"
    fi

    log "installing systemd unit to $SERVICE_TARGET"

    sed \
        -e "s|__APP_USER__|$APP_USER|g" \
        -e "s|__APP_GROUP__|$APP_GROUP|g" \
        -e "s|__APP_DIR__|$APP_DIR|g" \
        -e "s|__VENV_DIR__|$VENV_DIR|g" \
        -e "s|__WORKERS__|$WORKERS|g" \
        -e "s|__HOST__|$HOST|g" \
        -e "s|__PORT__|$PORT|g" \
        "$SERVICE_TEMPLATE" > "$SERVICE_TARGET"

    systemctl daemon-reload
    systemctl enable --now "$APP_NAME"
    systemctl restart "$APP_NAME"

    log "service status"
    systemctl status "$APP_NAME" --no-pager
}

print_summary() {
    log "app_dir=$APP_DIR"
    log "venv_dir=$VENV_DIR"
    log "listen=$HOST:$PORT"
    log "workers=$WORKERS"
    log "test with: curl http://$HOST:$PORT/login"
    log "day-2 updates use: bash scripts/server_update.sh"
}

main() {
    install_python_env
    ensure_env_file

    if [[ "$SKIP_SERVICE_INSTALL" == "1" ]]; then
        log "skipping systemd installation"
        print_summary
        exit 0
    fi

    install_service
    print_summary
}

main "$@"

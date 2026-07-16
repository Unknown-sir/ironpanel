#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
BASE=${IRONPANEL_TGPROXY_DIR:-/opt/ironpanel-telegram-proxy}
REPO=${IRONPANEL_TGPROXY_REPO:-https://github.com/Unknown-sir/JSMTProxy.git}
RUNTIME="$BASE/ironpanel"
CONFIG="$RUNTIME/config.json"
USAGE="$RUNTIME/usage.json"
PORT=${IRONPANEL_TGPROXY_PORT:-${TELEGRAM_PROXY_BASE:-6969}}
MODE="${1:---install-only}"
log(){ echo "[IronPanel Telegram Proxy] $*"; }

if [[ "$MODE" == "--status" ]]; then
  echo "Base: $BASE"
  echo "Runtime: $RUNTIME"
  echo "Repo: $REPO"
  echo "Port: $PORT"
  command -v node || command -v nodejs || true
  [[ -f "$CONFIG" ]] && cat "$CONFIG" || true
  systemctl status ironpanel-tgproxy.service --no-pager || true
  systemctl list-units 'ironpanel-tgproxy.service' 'ironpanel-tgproxy-*.service' --all --no-pager || true
  exit 0
fi

install_packages(){
  log "Installing NodeJS/Git dependencies"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm git ca-certificates curl || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y nodejs npm git ca-certificates curl || true
  fi
  if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then
    ln -sf "$(command -v nodejs)" /usr/bin/node || true
  fi
  if ! command -v node >/dev/null 2>&1; then
    echo "NodeJS is not installed. Install nodejs/npm and rerun this repair." >&2
    exit 1
  fi
}

install_source(){
  mkdir -p "$BASE" "$RUNTIME"
  if command -v git >/dev/null 2>&1; then
    if [[ ! -d "$BASE/JSMTProxy/.git" ]]; then
      rm -rf "$BASE/JSMTProxy"
      log "Cloning JSMTProxy from $REPO"
      git clone --depth=1 "$REPO" "$BASE/JSMTProxy" || log "Warning: clone failed; IronPanel wrapper can still run if node is installed."
    else
      log "Updating JSMTProxy source"
      git -C "$BASE/JSMTProxy" fetch --depth=1 origin master || true
      git -C "$BASE/JSMTProxy" reset --hard origin/master || true
    fi
  fi
  if [[ -f "$BASE/JSMTProxy/mtproxy.js" ]]; then
    node --check "$BASE/JSMTProxy/mtproxy.js" >/dev/null 2>&1 || log "Warning: upstream mtproxy.js check failed; using IronPanel wrapper."
  fi
}

install_wrapper_and_service(){
  mkdir -p "$RUNTIME"
  if [[ -f "$APP_DIR/scripts/ironpanel_mtproxy.js" ]]; then
    node --check "$APP_DIR/scripts/ironpanel_mtproxy.js" >/dev/null 2>&1 || { echo "ironpanel_mtproxy.js failed node --check" >&2; exit 1; }
    cp -f "$APP_DIR/scripts/ironpanel_mtproxy.js" "$RUNTIME/ironpanel_mtproxy.js"
    chmod 755 "$RUNTIME/ironpanel_mtproxy.js"
  elif [[ ! -f "$RUNTIME/ironpanel_mtproxy.js" ]]; then
    echo "IronPanel MTProxy wrapper not found at $APP_DIR/scripts/ironpanel_mtproxy.js" >&2
    exit 1
  fi
  if [[ ! -f "$CONFIG" ]]; then
    cat > "$CONFIG" <<JSON
{
  "port": ${PORT},
  "mode": "single-port-multi-secret",
  "users": []
}
JSON
  fi
  [[ -f "$USAGE" ]] || echo '{"updated_at": null, "users": {}}' > "$USAGE"
  cat > /etc/systemd/system/ironpanel-tgproxy.service <<SERVICE
[Unit]
Description=IronPanel shared Telegram MTProto proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$RUNTIME
Environment=IRONPANEL_TGPROXY_CONFIG=$CONFIG
Environment=IRONPANEL_TGPROXY_USAGE=$USAGE
ExecStart=/usr/bin/node $RUNTIME/ironpanel_mtproxy.js
Restart=always
RestartSec=3
LimitNOFILE=81920

[Install]
WantedBy=multi-user.target
SERVICE
  systemctl daemon-reload || true
  systemctl disable --now ironpanel-tgproxy-*.service >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/ironpanel-tgproxy-*.service >/dev/null 2>&1 || true
  systemctl enable --now ironpanel-tgproxy.service >/dev/null 2>&1 || true
  ufw allow "${PORT}/tcp" >/dev/null 2>&1 || true
  iptables -C INPUT -p tcp --dport "$PORT" -m comment --comment ironpanel-tgproxy-shared -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport "$PORT" -m comment --comment ironpanel-tgproxy-shared -j ACCEPT || true
}

sync_from_app(){
  if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
    log "Syncing IronPanel Telegram Proxy users and restarting service"
    (cd "$APP_DIR" && "$APP_DIR/.venv/bin/python" - <<'PYAPP'
from run import app
from app.services.provisioning import sync_all_users
with app.app_context():
    sync_all_users(restart=True)
PYAPP
) || true
  fi
}

install_packages
install_source
install_wrapper_and_service

case "$MODE" in
  --sync)
    sync_from_app
    ;;
  --restart)
    systemctl restart ironpanel-tgproxy.service || true
    ;;
  --install-only|*)
    # Core/service is installed and enabled. User secrets are written by
    # IronPanel sync_user/sync_all_users, or by rerunning this script with --sync.
    ;;
esac

if systemctl is-active --quiet ironpanel-tgproxy.service; then
  log "Core is active: ironpanel-tgproxy.service"
else
  log "Core installed but service is not active yet. Check: journalctl -u ironpanel-tgproxy.service -n 80 --no-pager"
fi
log "Done"

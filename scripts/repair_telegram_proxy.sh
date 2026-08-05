#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
BASE=${IRONPANEL_TGPROXY_DIR:-/opt/ironpanel-telegram-proxy}
REPO=${IRONPANEL_TGPROXY_REPO:-https://github.com/Unknown-sir/JSMTProxy.git}
RUNTIME="$BASE/ironpanel"
CONFIG="$RUNTIME/config.json"
USAGE="$RUNTIME/usage.json"
LOG_FILE=${IRONPANEL_TGPROXY_LOG:-/var/log/ironpanel-tgproxy.log}
PORT=${IRONPANEL_TGPROXY_PORT:-}
MODE="${1:---install-only}"
NODE_BIN=""
log(){ echo "[IronPanel Telegram Proxy] $*"; }

resolve_configured_port(){
  local candidate="${IRONPANEL_TGPROXY_PORT:-}"
  if [[ -z "$candidate" && -f /etc/ironpanel/ironpanel.env && -x "$APP_DIR/.venv/bin/python" ]]; then
    candidate=$(cd "$APP_DIR" && set -a && . /etc/ironpanel/ironpanel.env >/dev/null 2>&1 && set +a && "$APP_DIR/.venv/bin/python" - <<'PYPORT' 2>/dev/null || true
import os, sqlite3
p=os.environ.get('DATABASE_URL','')
if p.startswith('sqlite:///'):
    db=p.replace('sqlite:///','',1)
else:
    db='/etc/ironpanel/ironpanel.db'
try:
    con=sqlite3.connect(db); cur=con.cursor()
    cur.execute("select value from app_setting where key='port_telegram_proxy_base'")
    row=cur.fetchone()
    if row and row[0]: print(str(row[0]).strip())
except Exception:
    pass
PYPORT
)
  fi
  if [[ -z "$candidate" && -f "$CONFIG" ]]; then
    candidate=$(python3 - <<PYPORT 2>/dev/null || true
import json
try:
    print(json.load(open('$CONFIG')).get('port',''))
except Exception:
    pass
PYPORT
)
  fi
  if [[ -z "$candidate" && -n "${TELEGRAM_PROXY_BASE:-}" ]]; then
    candidate="$TELEGRAM_PROXY_BASE"
  fi
  PORT="${candidate:-6969}"
}

normalize_port(){
  resolve_configured_port
  if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then PORT=6969; fi
  if (( PORT < 1024 || PORT > 60000 )); then PORT=6969; fi
}

find_node(){
  NODE_BIN="$(command -v node || true)"
  if [[ -z "$NODE_BIN" ]]; then NODE_BIN="$(command -v nodejs || true)"; fi
  if [[ -z "$NODE_BIN" ]]; then
    echo "NodeJS runtime was not found." >&2
    return 1
  fi
  export NODE_BIN
}

if [[ "$MODE" == "--status" || "$MODE" == "--diagnose" ]]; then
  normalize_port
  echo "Base: $BASE"
  echo "Runtime: $RUNTIME"
  echo "Repo: $REPO"
  echo "Port: $PORT"
  echo "Node: $(command -v node || command -v nodejs || true)"
  echo "Config: $CONFIG"
  [[ -f "$CONFIG" ]] && cat "$CONFIG" || true
  echo "--- service"
  systemctl status ironpanel-tgproxy.service --no-pager || true
  echo "--- old units"
  systemctl list-units 'ironpanel-tgproxy.service' 'ironpanel-tgproxy-*.service' --all --no-pager || true
  echo "--- port listeners"
  ss -ltnp 2>/dev/null | grep -E ":${PORT}\b" || true
  echo "--- wrapper log"
  tail -120 "$LOG_FILE" 2>/dev/null || true
  echo "--- journal"
  journalctl -u ironpanel-tgproxy.service -n 120 --no-pager 2>/dev/null || true
  exit 0
fi

install_packages(){
  log "Installing NodeJS/Git dependencies"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y || true
    # NodeSource nodejs already includes npm and conflicts with Ubuntu npm on some servers.
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs git ca-certificates curl iproute2 || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y nodejs git ca-certificates curl iproute || true
  fi
  if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then
    ln -sf "$(command -v nodejs)" /usr/bin/node || true
  fi
  find_node || { echo "NodeJS is not installed. Install nodejs/npm and rerun this repair." >&2; exit 1; }
  local ver
  ver="$($NODE_BIN -v 2>/dev/null || true)"
  log "Node runtime: $NODE_BIN $ver"
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
}

stop_old_services(){
  log "Stopping old Telegram proxy services"
  systemctl stop ironpanel-tgproxy.service >/dev/null 2>&1 || true
  systemctl disable --now ironpanel-tgproxy-*.service >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/ironpanel-tgproxy-*.service >/dev/null 2>&1 || true
  pkill -f "$RUNTIME/ironpanel_mtproxy.js" >/dev/null 2>&1 || true
  systemctl daemon-reload || true
}

rebuild_safe_config(){
  mkdir -p "$RUNTIME"
  normalize_port
  if [[ -f "$CONFIG" ]]; then
    if ! python3 - <<PY >/dev/null 2>&1
import json
json.load(open('$CONFIG'))
PY
    then
      cp -f "$CONFIG" "$CONFIG.broken.$(date +%s)" || true
      rm -f "$CONFIG"
    fi
  fi
  if [[ ! -f "$CONFIG" ]]; then
    cat > "$CONFIG" <<JSON
{
  "port": ${PORT},
  "mode": "single-port-multi-secret",
  "users": []
}
JSON
  else
    python3 - <<PY
import json
from pathlib import Path
p=Path('$CONFIG')
data=json.loads(p.read_text() or '{}')
data['port']=int(${PORT})
data.setdefault('mode','single-port-multi-secret')
users=data.get('users')
if not isinstance(users, list): data['users']=[]
p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
PY
  fi
  [[ -f "$USAGE" ]] || echo '{"updated_at": null, "users": {}}' > "$USAGE"
  touch "$LOG_FILE" || true
}

install_wrapper_and_service(){
  mkdir -p "$RUNTIME"
  find_node
  if [[ -f "$APP_DIR/scripts/ironpanel_mtproxy.js" ]]; then
    "$NODE_BIN" --check "$APP_DIR/scripts/ironpanel_mtproxy.js" >/dev/null 2>&1 || { echo "ironpanel_mtproxy.js failed node --check" >&2; exit 1; }
    cp -f "$APP_DIR/scripts/ironpanel_mtproxy.js" "$RUNTIME/ironpanel_mtproxy.js"
    chmod 755 "$RUNTIME/ironpanel_mtproxy.js"
  elif [[ ! -f "$RUNTIME/ironpanel_mtproxy.js" ]]; then
    echo "IronPanel MTProxy wrapper not found at $APP_DIR/scripts/ironpanel_mtproxy.js" >&2
    exit 1
  fi
  rebuild_safe_config
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
Environment=IRONPANEL_TGPROXY_LOG=$LOG_FILE
ExecStartPre=$NODE_BIN --check $RUNTIME/ironpanel_mtproxy.js
ExecStart=$NODE_BIN $RUNTIME/ironpanel_mtproxy.js
Restart=always
RestartSec=3
LimitNOFILE=81920
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
SERVICE
  systemctl daemon-reload || true
  ufw allow "${PORT}/tcp" >/dev/null 2>&1 || true
  iptables -C INPUT -p tcp --dport "$PORT" -m comment --comment ironpanel-tgproxy-shared -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport "$PORT" -m comment --comment ironpanel-tgproxy-shared -j ACCEPT || true
}

sync_from_app(){
  if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
    log "Syncing IronPanel Telegram Proxy users"
    (cd "$APP_DIR" && "$APP_DIR/.venv/bin/python" - <<'PYAPP'
from run import app
from app.services.provisioning import sync_all_users
with app.app_context():
    sync_all_users(restart=True)
PYAPP
) || true
  fi
}

start_service(){
  log "Starting ironpanel-tgproxy.service"
  systemctl enable ironpanel-tgproxy.service >/dev/null 2>&1 || true
  systemctl restart ironpanel-tgproxy.service || true
  sleep 1
  if systemctl is-active --quiet ironpanel-tgproxy.service; then
    log "Core is active: ironpanel-tgproxy.service"
  else
    log "Core failed to start. Recent details:"
    journalctl -u ironpanel-tgproxy.service -n 80 --no-pager 2>/dev/null || true
    tail -80 "$LOG_FILE" 2>/dev/null || true
    exit 1
  fi
}

install_packages
install_source
stop_old_services
install_wrapper_and_service

case "$MODE" in
  --sync)
    sync_from_app
    ;;
  --restart)
    ;;
  --install-only|*)
    ;;
esac

start_service
log "Done"

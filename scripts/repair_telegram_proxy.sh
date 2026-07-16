#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
BASE=${IRONPANEL_TGPROXY_DIR:-/opt/ironpanel-telegram-proxy}
REPO=${IRONPANEL_TGPROXY_REPO:-https://github.com/Unknown-sir/JSMTProxy.git}
# If invoked by the panel, IRONPANEL_TGPROXY_REPO can be set from AppSetting.telegram_proxy_repo.
mkdir -p "$BASE"
log(){ echo "[IronPanel Telegram Proxy] $*"; }

if [[ "${1:-}" == "--status" ]]; then
  echo "Base: $BASE"
  echo "Repo: $REPO"
  command -v node || command -v nodejs || true
  systemctl list-units 'ironpanel-tgproxy.service' 'ironpanel-tgproxy-*.service' --all --no-pager || true
  exit 0
fi


log "Installing NodeJS/Git dependencies"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm git ca-certificates || true
elif command -v yum >/dev/null 2>&1; then
  yum install -y nodejs npm git ca-certificates || true
fi

if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then
  ln -sf "$(command -v nodejs)" /usr/bin/node || true
fi

if [[ ! -d "$BASE/JSMTProxy/.git" ]]; then
  rm -rf "$BASE/JSMTProxy"
  log "Cloning JSMTProxy from $REPO"
  git clone --depth=1 "$REPO" "$BASE/JSMTProxy"
else
  log "Updating JSMTProxy source"
  git -C "$BASE/JSMTProxy" fetch --depth=1 origin master || true
  git -C "$BASE/JSMTProxy" reset --hard origin/master || true
fi

if [[ ! -f "$BASE/JSMTProxy/mtproxy.js" ]]; then
  echo "mtproxy.js was not found in JSMTProxy source" >&2
  exit 1
fi

# Validate the upstream script. If node cannot parse it on this system, keep the
# source but mark the issue in logs so admin can update the repo or node version.
node --check "$BASE/JSMTProxy/mtproxy.js" >/dev/null 2>&1 || log "Warning: node --check failed for upstream mtproxy.js; try updating NodeJS or repository."

if [[ -f "$APP_DIR/scripts/ironpanel_mtproxy.js" ]]; then
  node --check "$APP_DIR/scripts/ironpanel_mtproxy.js" >/dev/null 2>&1 || { echo "ironpanel_mtproxy.js failed node --check" >&2; exit 1; }
fi

if [[ "${1:-}" == "--sync" || "${1:-}" == "--install-only" ]]; then
  systemctl daemon-reload || true
fi

if [[ "${1:-}" == "--sync" ]]; then
  log "Re-syncing IronPanel users and Telegram proxy services"
  if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
    (cd "$APP_DIR" && "$APP_DIR/.venv/bin/python" - <<'PYAPP'
from run import app
from app.services.provisioning import sync_all_users
with app.app_context():
    sync_all_users(restart=True)
PYAPP
) || true
  fi
fi

log "Done"

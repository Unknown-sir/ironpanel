#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
VENV=${VENV:-$APP_DIR/.venv}
LOG=${LOG:-/var/log/ironpanel-cisco-auth-repair.log}
if [[ $EUID -ne 0 ]]; then
  echo '[IronPanel] repair_cisco_auth.sh must run as root' >&2
  exit 2
fi
if [[ -f /etc/ironpanel/ironpanel.env ]]; then
  set -a
  # shellcheck disable=SC1091
  . /etc/ironpanel/ironpanel.env
  set +a
fi
cd "$APP_DIR"
mkdir -p /etc/ocserv /etc/ironpanel /var/log
log(){ printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }
run_sync(){
  "$VENV/bin/python" - <<'PY'
from app import create_app
from app.services.provisioning import sync_all_users
app = create_app()
with app.app_context():
    sync_all_users(restart=True)
PY
}
log 'Repairing ocserv runtime before rebuilding users'
if [[ -x "$APP_DIR/scripts/repair_ocserv.sh" ]]; then
  bash "$APP_DIR/scripts/repair_ocserv.sh"
fi
log 'Rebuilding Cisco/Ocserv auth from IronPanel users with native ocpasswd format'
run_sync
if [[ -x "$APP_DIR/scripts/repair_ocserv.sh" ]]; then
  bash "$APP_DIR/scripts/repair_ocserv.sh"
fi
run_sync
conf_path=$(awk -F'passwd=' '/plain\[passwd=/{gsub(/[]" ]/,"",$2); print $2; exit}' /etc/ocserv/ocserv.conf 2>/dev/null || true)
[[ -n "$conf_path" ]] || conf_path=/etc/ocserv/ocpasswd

# v19.9.16: keep Cisco/AnyConnect independent from session hook failures.
sed -i   -e '/^connect-script[[:space:]]*=.*ocserv_session_hook\.sh/d'   -e '/^disconnect-script[[:space:]]*=.*ocserv_session_hook\.sh/d'   /etc/ocserv/ocserv.conf 2>/dev/null || true
grep -q 'plain\[passwd=/etc/ocserv/ocpasswd\]' /etc/ocserv/ocserv.conf 2>/dev/null || { log "ERROR: ocserv.conf still does not use /etc/ocserv/ocpasswd"; exit 6; }
users=$(grep -c '^[^#[:space:]][^:]*:' "$conf_path" 2>/dev/null || true)
log "Cisco/Ocserv auth ready: auth=$conf_path users=$users"
systemctl restart ocserv
systemctl status ocserv --no-pager -n 20 || true

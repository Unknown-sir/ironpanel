#!/usr/bin/env bash
set -euo pipefail
LOG=${LOG:-/var/log/ironpanel-openvpn-repair.log}
APP_DIR=${APP_DIR:-/opt/ironpanel}
PY="$APP_DIR/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
mkdir -p "$(dirname "$LOG")" /etc/openvpn/server /var/log/openvpn
exec > >(tee -a "$LOG") 2>&1

echo "[$(date -Is)] IronPanel OpenVPN repair started"
cd "$APP_DIR"

# Rewrite OpenVPN runtime config from panel settings. This is intentionally
# lightweight: no full core install and no all-service restart.
"$PY" - <<'PY'
from app import create_app
from app.services.provisioning import apply_runtime_configs, sync_all_users, openvpn_transport, openvpn_port
app=create_app()
with app.app_context():
    apply_runtime_configs()
    sync_all_users(restart=False)
    print(f"OpenVPN target: proto={openvpn_transport()} port={openvpn_port()}")
PY

# If older Ocserv was still bound to the same TCP port, stop/reload it before
# starting OpenVPN. apply_runtime_configs() may already have moved Ocserv away.
systemctl stop ocserv >/dev/null 2>&1 || true

if command -v openvpn >/dev/null 2>&1; then
  openvpn --config /etc/openvpn/server/server.conf --test-crypto >/dev/null 2>&1 || true
fi

systemctl daemon-reload || true
systemctl enable openvpn-server@server >/dev/null 2>&1 || true
systemctl restart openvpn-server@server
sleep 1
systemctl restart ocserv >/dev/null 2>&1 || true

echo "--- openvpn status ---"
systemctl status openvpn-server@server --no-pager -l || true

echo "--- listeners ---"
ss -lntup | grep -E 'openvpn|:1194|:1195' || true

echo "[$(date -Is)] IronPanel OpenVPN repair finished"

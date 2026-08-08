#!/usr/bin/env bash
set -euo pipefail
LOG=${LOG:-/var/log/ironpanel-openvpn-repair.log}
APP_DIR=${APP_DIR:-/opt/ironpanel}
PY="$APP_DIR/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
mkdir -p "$(dirname "$LOG")" /etc/openvpn/server /var/log/openvpn
exec > >(tee -a "$LOG") 2>&1

echo "[$(date -Is)] IronPanel OpenVPN repair started"

PREREQ="$APP_DIR/scripts/install_protocol_prerequisites.sh"
if [[ ! -x "$PREREQ" ]]; then
  echo "[IronPanel] missing prerequisite installer: $PREREQ" >&2
  exit 20
fi
APP_DIR="$APP_DIR" ETC_DIR=${ETC_DIR:-/etc/ironpanel} bash "$PREREQ" --ensure-openvpn

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

# If Ocserv is enabled by the effective license/settings and was still bound to
# the same TCP port, stop/reload it before starting OpenVPN. Free/Beginner repair
# must not accidentally wake a paid-only daemon.
OCSERV_ACTIVE=$("$PY" - <<'PYOC'
from app import create_app
from app.services.provisioning import active_protocols
app=create_app()
with app.app_context():
    print('1' if 'ocserv' in active_protocols() else '0')
PYOC
)
if [[ "$OCSERV_ACTIVE" == "1" ]]; then systemctl stop ocserv >/dev/null 2>&1 || true; fi

if ! command -v openvpn >/dev/null 2>&1; then
  echo '[IronPanel] openvpn binary is missing' >&2
  exit 21
fi
for required in /etc/openvpn/server/server.conf /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt /etc/openvpn/server/server.key /etc/openvpn/server/dh.pem /etc/openvpn/server/tls-crypt.key; do
  [[ -s "$required" ]] || { echo "[IronPanel] required OpenVPN file is missing: $required" >&2; exit 22; }
done
openssl x509 -in /etc/openvpn/server/ca.crt -noout >/dev/null 2>&1 || { echo '[IronPanel] invalid OpenVPN CA certificate' >&2; exit 22; }
openssl x509 -in /etc/openvpn/server/server.crt -noout >/dev/null 2>&1 || { echo '[IronPanel] invalid OpenVPN server certificate' >&2; exit 22; }
openssl pkey -in /etc/openvpn/server/server.key -noout >/dev/null 2>&1 || { echo '[IronPanel] invalid OpenVPN server private key' >&2; exit 22; }
openssl dhparam -in /etc/openvpn/server/dh.pem -check -noout >/dev/null 2>&1 || { echo '[IronPanel] invalid OpenVPN DH parameters' >&2; exit 22; }

systemctl daemon-reload || true
systemctl enable openvpn-server@server >/dev/null 2>&1 || true
systemctl reset-failed openvpn-server@server >/dev/null 2>&1 || true
systemctl restart openvpn-server@server
sleep 1
systemctl is-active --quiet openvpn-server@server || { journalctl -u openvpn-server@server -n 80 --no-pager >&2 || true; exit 23; }
if [[ "$OCSERV_ACTIVE" == "1" ]]; then systemctl restart ocserv >/dev/null 2>&1 || true; fi

echo "--- openvpn status ---"
systemctl status openvpn-server@server --no-pager -l || true

echo "--- listeners ---"
ss -lntup | grep -E 'openvpn|:1194|:1195' || true

echo "[$(date -Is)] IronPanel OpenVPN repair finished"

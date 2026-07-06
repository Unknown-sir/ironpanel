#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash upgrade.sh"; exit 1; fi
APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ "${1:-}" == "--restart-only" ]]; then
  systemctl daemon-reload
  systemctl restart ironpanel
  echo "Ironpanel restarted."
  exit 0
fi
mkdir -p "$APP_DIR" "$ETC_DIR"
systemctl stop ironpanel 2>/dev/null || true
rsync -a --delete --exclude '.venv' --exclude 'ironpanel.db' "$SRC_DIR/" "$APP_DIR/"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel >/dev/null
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
if [[ ! -f "$ETC_DIR/ironpanel.env" ]]; then
  SECRET=$(openssl rand -hex 32); API_KEY=$(openssl rand -hex 32)
  PUBLIC_HOST=$(curl -fsS4 https://api.ipify.org || hostname -I | awk '{print $1}')
  cat > "$ETC_DIR/ironpanel.env" <<ENV
IRONPANEL_SECRET_KEY=$SECRET
IRONPANEL_API_KEY=$API_KEY
IRONPANEL_PUBLIC_HOST=$PUBLIC_HOST
IRONPANEL_PORT=8080
IRONPANEL_CONFIG_ROOT=$ETC_DIR
DATABASE_URL=sqlite:///$ETC_DIR/ironpanel.db
ENV
fi
set -a; . "$ETC_DIR/ironpanel.env"; set +a
cd "$APP_DIR"
"$APP_DIR/.venv/bin/flask" --app run.py upgrade-db
PANEL_PORT_DB=$("$APP_DIR/.venv/bin/python" - <<'PY' || true
import os, sqlite3
p=os.environ.get('DATABASE_URL','')
if p.startswith('sqlite:///'):
    db=p.replace('sqlite:///','',1)
    try:
        con=sqlite3.connect(db); cur=con.cursor()
        cur.execute("select value from app_setting where key='port_panel'")
        row=cur.fetchone(); print(row[0] if row else '')
    except Exception: pass
PY
)
if [[ -n "${PANEL_PORT_DB:-}" ]]; then
  if grep -q '^IRONPANEL_PORT=' "$ETC_DIR/ironpanel.env"; then sed -i "s/^IRONPANEL_PORT=.*/IRONPANEL_PORT=$PANEL_PORT_DB/" "$ETC_DIR/ironpanel.env"; else echo "IRONPANEL_PORT=$PANEL_PORT_DB" >> "$ETC_DIR/ironpanel.env"; fi
fi

PORT_EXPORTS=$("$APP_DIR/.venv/bin/python" - <<'PY' || true
import os, sqlite3
p=os.environ.get('DATABASE_URL','')
vals={'OPENVPN_UDP':'1194','OPENVPN_TCP':'1195','OPENVPN_PROTO':'udp','OCSERV_PORT':'8443','OCSERV_TCP':'8443','OCSERV_UDP':'8443','WIREGUARD_PORT':'51820','OCSERV_TRANSPORT':'tcp_udp','WIREGUARD_TRANSPORT':'udp','L2TP_TRANSPORT':'udp'}
mapk={'OPENVPN_UDP':'port_openvpn_udp','OPENVPN_TCP':'port_openvpn_tcp','OPENVPN_PROTO':'openvpn_transport','OCSERV_PORT':'port_ocserv_tcp','OCSERV_TCP':'port_ocserv_tcp','OCSERV_UDP':'port_ocserv_udp','WIREGUARD_PORT':'port_wireguard_udp','OCSERV_TRANSPORT':'ocserv_transport','WIREGUARD_TRANSPORT':'wireguard_transport','L2TP_TRANSPORT':'l2tp_transport'}
if p.startswith('sqlite:///'):
    db=p.replace('sqlite:///','',1)
    try:
        con=sqlite3.connect(db); cur=con.cursor()
        for env,k in mapk.items():
            cur.execute('select value from app_setting where key=?',(k,)); row=cur.fetchone()
            if row and row[0]: vals[env]=str(row[0])
    except Exception: pass
print(' '.join(f'{k}={v}' for k,v in vals.items()))
PY
)
export ETC_DIR IRONPANEL_PUBLIC_HOST
if [[ -x "$APP_DIR/scripts/install_vpn_core.sh" ]]; then
  env $PORT_EXPORTS ETC_DIR="$ETC_DIR" PUBLIC_HOST="${IRONPANEL_PUBLIC_HOST:-}" bash "$APP_DIR/scripts/install_vpn_core.sh"
fi
"$APP_DIR/.venv/bin/python" - <<'PYSYNC' || true
from app import create_app
from app.services.provisioning import sync_all_users
app=create_app()
with app.app_context():
    sync_all_users(restart=True)
PYSYNC
cat > /etc/systemd/system/ironpanel.service <<SERVICE
[Unit]
Description=Ironpanel VPN Management Panel
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ETC_DIR/ironpanel.env
ExecStart=$APP_DIR/.venv/bin/gunicorn -k gthread -w 2 -b 0.0.0.0:\${IRONPANEL_PORT} run:app
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
SERVICE

cat > /etc/systemd/system/ironpanel-usage-sync.service <<USAGESERVICE
[Unit]
Description=Ironpanel VPN Traffic Usage Sync
After=network.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ETC_DIR/ironpanel.env
ExecStart=$APP_DIR/.venv/bin/flask --app run.py sync-usage
User=root
USAGESERVICE

cat > /etc/systemd/system/ironpanel-usage-sync.timer <<USAGETIMER
[Unit]
Description=Run Ironpanel VPN Traffic Usage Sync every minute

[Timer]
OnBootSec=60s
OnUnitActiveSec=60s
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
USAGETIMER
systemctl daemon-reload
systemctl enable --now ironpanel
systemctl enable --now ironpanel-usage-sync.timer >/dev/null 2>&1 || true
systemctl restart ironpanel
cat <<INFO
Ironpanel upgraded.
VPN cores installed/updated: OpenVPN, WireGuard, Ocserv/Cisco AnyConnect, StrongSwan/IPsec, xl2tpd/L2TP.
Panel port: ${PANEL_PORT_DB:-$IRONPANEL_PORT}
Open: http://${IRONPANEL_PUBLIC_HOST}:${PANEL_PORT_DB:-$IRONPANEL_PORT}
INFO

#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash install.sh"; exit 1; fi
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" && "$ARCH" != "amd64" ]]; then echo "Only x86_64/amd64 is supported by this installer."; exit 1; fi
. /etc/os-release || true
if [[ "${ID:-ubuntu}" != "ubuntu" ]]; then echo "Ubuntu 22.04/24.04 recommended. Continuing in 5s..."; sleep 5; fi

read -rp "Admin username [admin]: " ADMIN_USER; ADMIN_USER=${ADMIN_USER:-admin}
read -rsp "Admin password [auto-generate]: " ADMIN_PASS; echo; ADMIN_PASS=${ADMIN_PASS:-$(openssl rand -base64 14)}
read -rp "Panel port [8080]: " PANEL_PORT; PANEL_PORT=${PANEL_PORT:-8080}
read -rp "Public hostname/IP [auto-detect]: " PUBLIC_HOST; PUBLIC_HOST=${PUBLIC_HOST:-$(curl -fsS4 https://api.ipify.org || hostname -I | awk '{print $1}')}
read -rp "Tunnel host/IP for client configs [empty = use public host]: " TUNNEL_HOST; TUNNEL_HOST=${TUNNEL_HOST:-}
LICENSE_SERVER="http://license.skyshield.space:8002"
read -rp "Ironpanel license key [empty = enter later]: " LICENSE_KEY; LICENSE_KEY=${LICENSE_KEY:-}
read -rp "OpenVPN transport tcp/udp [udp]: " OPENVPN_PROTO; OPENVPN_PROTO=${OPENVPN_PROTO:-udp}; OPENVPN_PROTO=$(echo "$OPENVPN_PROTO"|tr A-Z a-z); [[ "$OPENVPN_PROTO" == "tcp" ]] || OPENVPN_PROTO=udp
read -rp "OpenVPN UDP port [1194]: " OPENVPN_UDP; OPENVPN_UDP=${OPENVPN_UDP:-1194}
read -rp "OpenVPN TCP port [1195]: " OPENVPN_TCP; OPENVPN_TCP=${OPENVPN_TCP:-1195}
read -rp "Ocserv TCP/UDP port [8443]: " OCSERV_PORT; OCSERV_PORT=${OCSERV_PORT:-8443}
read -rp "WireGuard UDP port [51820]: " WIREGUARD_PORT; WIREGUARD_PORT=${WIREGUARD_PORT:-51820}

APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
mkdir -p "$APP_DIR" "$ETC_DIR" "$ETC_DIR/profiles"
rsync -a --delete ./ "$APP_DIR/"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nginx openssl curl rsync sqlite3 qrencode iptables-persistent ca-certificates

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
SECRET=$(openssl rand -hex 32)
API_KEY=$(openssl rand -hex 32)
cat > "$ETC_DIR/ironpanel.env" <<ENV
IRONPANEL_SECRET_KEY=$SECRET
IRONPANEL_API_KEY=$API_KEY
IRONPANEL_PUBLIC_HOST=$PUBLIC_HOST
IRONPANEL_TUNNEL_HOST=$TUNNEL_HOST
IRONPANEL_PORT=$PANEL_PORT
IRONPANEL_CONFIG_ROOT=$ETC_DIR
DATABASE_URL=sqlite:///$ETC_DIR/ironpanel.db
ENV
chmod 600 "$ETC_DIR/ironpanel.env"

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

# Always install/repair the real VPN core daemons. OpenVPN is installed here.
env ETC_DIR="$ETC_DIR" PUBLIC_HOST="$PUBLIC_HOST" OPENVPN_PROTO="$OPENVPN_PROTO" OPENVPN_UDP="$OPENVPN_UDP" OPENVPN_TCP="$OPENVPN_TCP" OCSERV_PORT="$OCSERV_PORT" OCSERV_TCP="$OCSERV_PORT" OCSERV_UDP="$OCSERV_PORT" WIREGUARD_PORT="$WIREGUARD_PORT" bash "$APP_DIR/scripts/install_vpn_core.sh"

cd "$APP_DIR"
set -a; . "$ETC_DIR/ironpanel.env"; set +a
"$APP_DIR/.venv/bin/flask" --app run.py init-db --admin-user "$ADMIN_USER" --admin-pass "$ADMIN_PASS"
"$APP_DIR/.venv/bin/python" - <<PYSET
import os
from app import create_app
from app.core.extensions import db
from app.core.models import AppSetting
app=create_app()
settings={
 "public_host": os.environ.get("IRONPANEL_PUBLIC_HOST",""),
 "tunnel_host": os.environ.get("IRONPANEL_TUNNEL_HOST",""),
 "openvpn_transport": "$OPENVPN_PROTO",
 "port_panel": os.environ.get("IRONPANEL_PORT","8080"),
 "port_openvpn_udp": "$OPENVPN_UDP",
 "port_openvpn_tcp": "$OPENVPN_TCP",
 "port_ocserv_tcp": "$OCSERV_PORT",
 "port_ocserv_udp": "$OCSERV_PORT",
 "port_wireguard_udp": "$WIREGUARD_PORT",
 "license_server_url": "$LICENSE_SERVER",
 "license_key": "$LICENSE_KEY",
 "ocserv_transport": "tcp_udp",
 "wireguard_transport": "udp",
 "l2tp_transport": "udp",
}
with app.app_context():
    for k,v in settings.items():
        row=AppSetting.query.filter_by(key=k).first()
        if not row: db.session.add(AppSetting(key=k,value=v))
        else: row.value=v
    db.session.commit()
PYSET

chmod +x "$APP_DIR/scripts/"*.sh "$APP_DIR/scripts/"*.py 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now ironpanel >/dev/null 2>&1 || true
systemctl enable --now ironpanel-usage-sync.timer >/dev/null 2>&1 || true
systemctl restart ironpanel
cat <<INFO

Ironpanel installed.
VPN cores: OpenVPN, WireGuard, Ocserv/Cisco AnyConnect, StrongSwan/IPsec and xl2tpd/L2TP are installed/updated automatically.
OpenVPN: ${OPENVPN_PROTO}/$( [[ "$OPENVPN_PROTO" == "tcp" ]] && echo "$OPENVPN_TCP" || echo "$OPENVPN_UDP" )
URL: http://$PUBLIC_HOST:$PANEL_PORT
Admin username: $ADMIN_USER
Admin password: $ADMIN_PASS
Global API key: $API_KEY
License server: $LICENSE_SERVER
License key: ${LICENSE_KEY:-not set}
Config: $ETC_DIR
INFO

#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash install.sh"; exit 1; fi
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" && "$ARCH" != "amd64" ]]; then echo "Only x86_64/amd64 is supported by this installer."; exit 1; fi
. /etc/os-release || true
if [[ "${ID:-ubuntu}" != "ubuntu" ]]; then echo "Ubuntu 22.04/24.04 recommended. Continuing in 5s..."; sleep 5; fi

install_certbot_safe() {
  echo "Installing isolated Certbot for Auto SSL..."
  apt-get update >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y snapd ca-certificates python3-venv python3-pip >/dev/null 2>&1 || true
  systemctl enable --now snapd.socket >/dev/null 2>&1 || true
  systemctl start snapd.service >/dev/null 2>&1 || true
  if command -v snap >/dev/null 2>&1; then
    snap install core >/dev/null 2>&1 || snap refresh core >/dev/null 2>&1 || true
    snap install --classic certbot >/dev/null 2>&1 || true
    ln -sf /snap/bin/certbot /usr/local/bin/certbot >/dev/null 2>&1 || true
  fi
  if ! /snap/bin/certbot --version >/dev/null 2>&1 && ! /usr/local/bin/certbot --version >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-openssl python3-cryptography >/dev/null 2>&1 || true
  fi
}


read -rp "Admin username [admin]: " ADMIN_USER; ADMIN_USER=${ADMIN_USER:-admin}
read -rsp "Admin password [auto-generate]: " ADMIN_PASS; echo; ADMIN_PASS=${ADMIN_PASS:-$(openssl rand -base64 14)}
read -rp "Panel port [8080]: " PANEL_PORT; PANEL_PORT=${PANEL_PORT:-8080}
read -rp "Public hostname/IP [auto-detect]: " PUBLIC_HOST; PUBLIC_HOST=${PUBLIC_HOST:-$(curl -fsS4 https://api.ipify.org || hostname -I | awk '{print $1}')}
read -rp "Tunnel host/IP for client configs [empty = use public host]: " TUNNEL_HOST; TUNNEL_HOST=${TUNNEL_HOST:-}
LICENSE_SERVER="http://license.skyshield.space:8002"
LICENSE_KEY=""
read -rp "OpenVPN transport tcp/udp [udp]: " OPENVPN_PROTO; OPENVPN_PROTO=${OPENVPN_PROTO:-udp}; OPENVPN_PROTO=$(echo "$OPENVPN_PROTO"|tr A-Z a-z); [[ "$OPENVPN_PROTO" == "tcp" ]] || OPENVPN_PROTO=udp
read -rp "OpenVPN UDP port [1194]: " OPENVPN_UDP; OPENVPN_UDP=${OPENVPN_UDP:-1194}
read -rp "OpenVPN TCP port [1195]: " OPENVPN_TCP; OPENVPN_TCP=${OPENVPN_TCP:-1195}
read -rp "Cisco/Ocserv TCP/UDP port [8445]: " OCSERV_PORT; OCSERV_PORT=${OCSERV_PORT:-8445}
read -rp "WireGuard UDP port [51820]: " WIREGUARD_PORT; WIREGUARD_PORT=${WIREGUARD_PORT:-51820}
read -rp "Xray TCP port [443]: " XRAY_PORT; XRAY_PORT=${XRAY_PORT:-443}
read -rp "Xray local API port [10085]: " XRAY_API_PORT; XRAY_API_PORT=${XRAY_API_PORT:-10085}
read -rp "PPTP TCP port [1723]: " PPTP_PORT; PPTP_PORT=${PPTP_PORT:-1723}
read -rp "Hysteria2 UDP port [4433]: " HYSTERIA2_PORT; HYSTERIA2_PORT=${HYSTERIA2_PORT:-4433}

APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
mkdir -p "$APP_DIR" "$ETC_DIR" "$ETC_DIR/profiles"
rsync -a --delete ./ "$APP_DIR/"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nginx snapd openssl curl rsync sqlite3 qrencode iptables-persistent ca-certificates
install_certbot_safe

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
ExecStart=/bin/bash -lc 'CERT="\${IRONPANEL_SSL_CERT:-}"; KEY="\${IRONPANEL_SSL_KEY:-}"; SSL_ARGS=""; if [ -n "\$CERT" ] && [ -n "\$KEY" ] && [ -f "\$CERT" ] && [ -f "\$KEY" ]; then SSL_ARGS="--certfile \$CERT --keyfile \$KEY"; fi; exec $APP_DIR/.venv/bin/gunicorn -k gthread -w 2 -b 0.0.0.0:\${IRONPANEL_PORT} \$SSL_ARGS run:app'
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

cat > /etc/systemd/system/ironpanel-sales-bot.service <<SALESBOTSERVICE
[Unit]
Description=IronPanel Telegram Sales Bot
After=network.target ironpanel.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ETC_DIR/ironpanel.env
ExecStart=$APP_DIR/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SALESBOTSERVICE

cat > /etc/systemd/system/ironpanel-sales-reminders.service <<SALESREMINDERSERVICE
[Unit]
Description=IronPanel Sales Bot Expiry and Traffic Reminders
After=network.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ETC_DIR/ironpanel.env
ExecStart=$APP_DIR/.venv/bin/python -m bot.reminders
User=root
SALESREMINDERSERVICE

cat > /etc/systemd/system/ironpanel-sales-reminders.timer <<SALESREMINDERTIMER
[Unit]
Description=Run IronPanel Sales Bot reminders daily

[Timer]
OnBootSec=180s
OnCalendar=*-*-* 10:00:00
Persistent=true

[Install]
WantedBy=timers.target
SALESREMINDERTIMER

# Always install/repair the real VPN core daemons. OpenVPN is installed here.
env ETC_DIR="$ETC_DIR" PUBLIC_HOST="$PUBLIC_HOST" OPENVPN_PROTO="$OPENVPN_PROTO" OPENVPN_UDP="$OPENVPN_UDP" OPENVPN_TCP="$OPENVPN_TCP" OCSERV_PORT="$OCSERV_PORT" OCSERV_TCP="$OCSERV_PORT" OCSERV_UDP="$OCSERV_PORT" WIREGUARD_PORT="$WIREGUARD_PORT" XRAY_PORT="$XRAY_PORT" XRAY_API_PORT="$XRAY_API_PORT" bash "$APP_DIR/scripts/install_vpn_core.sh"

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
 "port_xray_tcp": "$XRAY_PORT",
 "port_xray_api": "$XRAY_API_PORT",
 "xray_port": "$XRAY_PORT",
 "xray_api_port": "$XRAY_API_PORT",
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
bash "$APP_DIR/scripts/repair_xray.sh" >/dev/null 2>&1 || true
chmod +x "$APP_DIR/scripts/update_from_github.sh" 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now ironpanel >/dev/null 2>&1 || true
systemctl enable --now ironpanel-usage-sync.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-reminders.timer >/dev/null 2>&1 || true
# v17 scheduled full backup timer
cat > /etc/systemd/system/ironpanel-backup-v17.service <<'V17BACKUPSERVICE'
[Unit]
Description=IronPanel v17 Full Backup
After=network.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=/opt/ironpanel
EnvironmentFile=/etc/ironpanel/ironpanel.env
ExecStart=/opt/ironpanel/.venv/bin/flask --app run.py backup-v17
User=root
V17BACKUPSERVICE
cat > /etc/systemd/system/ironpanel-backup-v17.timer <<'V17BACKUPTIMER'
[Unit]
Description=Run IronPanel v17 backup daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
V17BACKUPTIMER
systemctl daemon-reload
systemctl enable --now ironpanel-backup-v17.timer >/dev/null 2>&1 || true
systemctl restart ironpanel
systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true
cat <<INFO

Ironpanel installed.
VPN cores: OpenVPN, WireGuard, Ocserv/Cisco AnyConnect, StrongSwan/IPsec, xl2tpd/L2TP and Xray Core are installed/updated automatically.
OpenVPN: ${OPENVPN_PROTO}/$( [[ "$OPENVPN_PROTO" == "tcp" ]] && echo "$OPENVPN_TCP" || echo "$OPENVPN_UDP" )
URL: http://$PUBLIC_HOST:$PANEL_PORT
Admin username: $ADMIN_USER
Admin password: $ADMIN_PASS
Global API key: $API_KEY
License server: $LICENSE_SERVER
Xray: tcp/$XRAY_PORT
Edition: Beginner Free (no license key required)
Config: $ETC_DIR
INFO

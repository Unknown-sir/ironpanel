#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash upgrade.sh"; exit 1; fi
APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ "${1:-}" == "--restart-only" ]]; then
  chmod +x "$APP_DIR/scripts/"*.sh "$APP_DIR/scripts/"*.py 2>/dev/null || true
chmod +x "$APP_DIR/scripts/update_from_github.sh" 2>/dev/null || true

# v15.5: force OpenVPN server config refresh to remove old auth-user-pass/user drop remnants.
if [[ -f /etc/openvpn/server/server.conf ]]; then
  sed -i '/^auth-user-pass-verify/d;/^client-cert-not-required/d;/^verify-client-cert none/d;/^username-as-common-name/d;/^plugin .*openvpn-plugin-auth-pam/d;/^user nobody/d;/^group nogroup/d' /etc/openvpn/server/server.conf || true
fi
if [[ -f "$APP_DIR/scripts/repair_xray.sh" ]]; then bash "$APP_DIR/scripts/repair_xray.sh" >/dev/null 2>&1 || true; fi
# v16.1: repair Xray runtime permissions before restarting services
systemctl daemon-reload
  systemctl restart ironpanel
systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true
systemctl restart xray >/dev/null 2>&1 || true
  echo "Ironpanel restarted."
  exit 0
fi
mkdir -p "$APP_DIR" "$ETC_DIR"
apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y sqlite3 snapd ca-certificates python3-venv python3-pip >/dev/null 2>&1 || true
if [[ -f "$SRC_DIR/scripts/repair_certbot.sh" ]]; then bash "$SRC_DIR/scripts/repair_certbot.sh" >/dev/null 2>&1 || true; fi
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
vals={'OPENVPN_UDP':'1194','OPENVPN_TCP':'1195','OPENVPN_PROTO':'udp','OCSERV_PORT':'8445','OCSERV_TCP':'8445','OCSERV_UDP':'8445','WIREGUARD_PORT':'51820','XRAY_PORT':'443','XRAY_API_PORT':'10085','PPTP_PORT':'1723','HYSTERIA2_PORT':'4433','OCSERV_TRANSPORT':'tcp_udp','WIREGUARD_TRANSPORT':'udp','L2TP_TRANSPORT':'udp'}
mapk={'OPENVPN_UDP':'port_openvpn_udp','OPENVPN_TCP':'port_openvpn_tcp','OPENVPN_PROTO':'openvpn_transport','OCSERV_PORT':'port_ocserv_tcp','OCSERV_TCP':'port_ocserv_tcp','OCSERV_UDP':'port_ocserv_udp','WIREGUARD_PORT':'port_wireguard_udp','XRAY_PORT':'port_xray_tcp','XRAY_API_PORT':'port_xray_api','PPTP_PORT':'port_pptp_tcp','HYSTERIA2_PORT':'port_hysteria2_udp','OCSERV_TRANSPORT':'ocserv_transport','WIREGUARD_TRANSPORT':'wireguard_transport','L2TP_TRANSPORT':'l2tp_transport'}
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
if [[ -f "$APP_DIR/scripts/repair_xray.sh" ]]; then bash "$APP_DIR/scripts/repair_xray.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_wireguard.sh" ]]; then bash "$APP_DIR/scripts/repair_wireguard.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_ocserv.sh" ]]; then bash "$APP_DIR/scripts/repair_ocserv.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_pptp.sh" ]]; then bash "$APP_DIR/scripts/repair_pptp.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_hysteria2.sh" ]]; then bash "$APP_DIR/scripts/repair_hysteria2.sh" || true; fi
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

cat > /etc/systemd/system/ironpanel-admin-bot.service <<ADMINBOTSERVICE
[Unit]
Description=IronPanel Telegram Admin Bot
After=network.target ironpanel.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ETC_DIR/ironpanel.env
ExecStart=$APP_DIR/.venv/bin/python -m bot.admin
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
ADMINBOTSERVICE

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

chmod +x "$APP_DIR/scripts/"*.sh "$APP_DIR/scripts/"*.py 2>/dev/null || true
chmod +x "$APP_DIR/scripts/update_from_github.sh" 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now ironpanel
systemctl enable --now ironpanel-usage-sync.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl enable --now ironpanel-admin-bot >/dev/null 2>&1 || true
systemctl enable --now ironpanel-admin-report.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-reminders.timer >/dev/null 2>&1 || true
# v17 scheduled full backup timer
cat > /etc/systemd/system/ironpanel-admin-report.service <<ADMINREPORTSERVICE
[Unit]
Description=IronPanel Telegram Admin Daily Report
After=network.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ETC_DIR/ironpanel.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/scripts/admin_telegram_report.py
User=root
ADMINREPORTSERVICE
cat > /etc/systemd/system/ironpanel-admin-report.timer <<ADMINREPORTTIMER
[Unit]
Description=Run IronPanel Telegram admin report daily

[Timer]
OnBootSec=240s
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
ADMINREPORTTIMER

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
systemctl enable --now ironpanel-admin-report.timer >/dev/null 2>&1 || true
systemctl restart ironpanel
systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true
if [[ -f "$APP_DIR/scripts/repair_xray.sh" ]]; then bash "$APP_DIR/scripts/repair_xray.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_wireguard.sh" ]]; then bash "$APP_DIR/scripts/repair_wireguard.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_ocserv.sh" ]]; then bash "$APP_DIR/scripts/repair_ocserv.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_pptp.sh" ]]; then bash "$APP_DIR/scripts/repair_pptp.sh" || true; fi
if [[ -f "$APP_DIR/scripts/repair_hysteria2.sh" ]]; then bash "$APP_DIR/scripts/repair_hysteria2.sh" || true; fi
systemctl restart xray >/dev/null 2>&1 || true
cat <<INFO
Ironpanel upgraded.
VPN cores installed/updated: OpenVPN, WireGuard, Ocserv/Cisco AnyConnect, StrongSwan/IPsec, xl2tpd/L2TP, Xray Core.
Panel port: ${PANEL_PORT_DB:-$IRONPANEL_PORT}
Open: http://${IRONPANEL_PUBLIC_HOST}:${PANEL_PORT_DB:-$IRONPANEL_PORT}
INFO

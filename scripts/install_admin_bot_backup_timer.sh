#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
ENV_FILE="$ETC_DIR/ironpanel.env"
cat > /etc/systemd/system/ironpanel-admin-report.service <<SERVICE
[Unit]
Description=IronPanel Telegram Admin Report and 24h Backup
After=network-online.target ironpanel.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/scripts/admin_telegram_report.py
TimeoutStartSec=30min
User=root
SERVICE
cat > /etc/systemd/system/ironpanel-admin-report.timer <<TIMER
[Unit]
Description=Run IronPanel Telegram admin backup every 24 hours

[Timer]
OnBootSec=10min
OnUnitActiveSec=24h
AccuracySec=10min
Persistent=true

[Install]
WantedBy=timers.target
TIMER
systemctl daemon-reload
systemctl enable --now ironpanel-admin-report.timer >/dev/null 2>&1 || true
systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true
echo "Admin bot 24h backup timer installed."

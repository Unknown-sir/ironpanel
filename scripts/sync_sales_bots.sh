#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/ironpanel"
ENV_FILE="/etc/ironpanel/ironpanel.env"
DB="/opt/ironpanel/instance/ironpanel.db"
if [[ ! -f "$DB" ]]; then DB="$APP_DIR/instance/ironpanel.db"; fi
cat > /etc/systemd/system/ironpanel-sales-bot@.service <<'SERVICE'
[Unit]
Description=IronPanel Reseller Telegram Sales Bot %i
After=network-online.target ironpanel.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/ironpanel
EnvironmentFile=/etc/ironpanel/ironpanel.env
Environment=IRONPANEL_SALES_BOT_OWNER_ID=%i
ExecStart=/opt/ironpanel/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload >/dev/null 2>&1 || true
# Stop template instances that are no longer enabled or no longer have a token.
for unit in $(systemctl list-units 'ironpanel-sales-bot@*.service' --all --no-legend 2>/dev/null | awk '{print $1}'); do
  owner="${unit#ironpanel-sales-bot@}"; owner="${owner%.service}"
  if ! sqlite3 "$DB" "SELECT value FROM app_setting WHERE key='sales_bot_enabled_owner_${owner}'" 2>/dev/null | grep -qx '1'; then
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
  fi
done
# Enable/start every reseller bot with enabled=1 and a non-empty token.
if command -v sqlite3 >/dev/null 2>&1 && [[ -f "$DB" ]]; then
  sqlite3 -separator '|' "$DB" "SELECT REPLACE(key,'sales_bot_enabled_owner_','') FROM app_setting WHERE key LIKE 'sales_bot_enabled_owner_%' AND value='1'" 2>/dev/null | while read -r owner; do
    [[ -z "$owner" ]] && continue
    token=$(sqlite3 "$DB" "SELECT value FROM app_setting WHERE key='sales_bot_token_owner_${owner}'" 2>/dev/null || true)
    if [[ -n "$token" ]]; then
      systemctl enable --now "ironpanel-sales-bot@${owner}.service" >/dev/null 2>&1 || true
      systemctl restart "ironpanel-sales-bot@${owner}.service" >/dev/null 2>&1 || true
    fi
  done
fi

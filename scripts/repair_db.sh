#!/usr/bin/env bash
set -euo pipefail
APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash $0"; exit 1; fi
systemctl stop ironpanel 2>/dev/null || true
set -a; . "$ETC_DIR/ironpanel.env"; set +a
cd "$APP_DIR"
"$APP_DIR/.venv/bin/flask" --app run.py upgrade-db
systemctl restart ironpanel
echo "Database repaired and Ironpanel restarted."

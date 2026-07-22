#!/usr/bin/env bash
set -euo pipefail
APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
source "$ETC_DIR/ironpanel.env"
cd "$APP_DIR"
"$APP_DIR/.venv/bin/flask" --app run.py backup-v17

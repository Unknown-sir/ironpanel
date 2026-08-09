#!/usr/bin/env bash
set -euo pipefail
APP_DIR=/opt/ironpanel
ETC_DIR=/etc/ironpanel
set -a
# shellcheck disable=SC1091
source "$ETC_DIR/ironpanel.env"
set +a
export IRONPANEL_CONFIG_ROOT=${IRONPANEL_CONFIG_ROOT:-$ETC_DIR}
export DATABASE_URL=${DATABASE_URL:-sqlite:///$ETC_DIR/ironpanel.db}
cd "$APP_DIR"
"$APP_DIR/.venv/bin/flask" --app run.py backup-v17

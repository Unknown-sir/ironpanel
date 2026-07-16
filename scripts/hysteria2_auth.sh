#!/usr/bin/env bash
set -euo pipefail
# Hysteria2 command auth receives: addr auth tx
ADDR="${1:-}"
PASS="${2:-}"
TX="${3:-0}"
if [[ -z "$PASS" ]]; then read -r PASS || true; fi
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then set -a; . "$ETC_DIR/ironpanel.env"; set +a; fi
PY="$APP_DIR/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3
cd "$APP_DIR"
export PASS ADDR TX
$PY - <<'AUTHCODE'
from app import create_app
from app.core.models import VpnUser
from app.services.provisioning import user_access_status, hysteria2_password_for, protocol_enabled_for_user
import os, sys
pw=os.environ.get('PASS','').strip()
addr=os.environ.get('ADDR','')
app=create_app(); ok_user=None
with app.app_context():
    for u in VpnUser.query.all():
        if protocol_enabled_for_user(u,'hysteria2') and user_access_status(u)[0] and hysteria2_password_for(u)==pw:
            ok_user=u.username
            break
if ok_user:
    print(ok_user)
    sys.exit(0)
sys.exit(1)
AUTHCODE

#!/usr/bin/env bash
set -euo pipefail
PASS="${1:-}"
if [[ -z "$PASS" ]]; then read -r PASS || true; fi
PY=/opt/ironpanel/.venv/bin/python
[[ -x "$PY" ]] || PY=python3
export PASS
$PY - <<'AUTHCODE'
from app import create_app
from app.core.models import VpnUser
from app.services.provisioning import user_access_status, hysteria2_password_for, protocol_enabled_for_user
import os, sys
pw=os.environ.get('PASS','').strip()
app=create_app(); ok=False
with app.app_context():
    for u in VpnUser.query.all():
        if protocol_enabled_for_user(u,'hysteria2') and user_access_status(u)[0] and hysteria2_password_for(u)==pw:
            ok=True; break
sys.exit(0 if ok else 1)
AUTHCODE

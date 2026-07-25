#!/usr/bin/env bash
set -euo pipefail
cd /opt/ironpanel
/opt/ironpanel/.venv/bin/flask --app run.py sync-all-users >/dev/null 2>&1 || /opt/ironpanel/.venv/bin/python - <<'PY'
from app import create_app
from app.services.provisioning import apply_runtime_configs, sync_all_users
app=create_app()
with app.app_context():
    apply_runtime_configs()
    sync_all_users(restart=True)
PY
chmod +x /opt/ironpanel/scripts/*.sh /opt/ironpanel/scripts/*.py 2>/dev/null || true
systemctl restart openvpn-server@server
echo 'OpenVPN repaired and restarted.'

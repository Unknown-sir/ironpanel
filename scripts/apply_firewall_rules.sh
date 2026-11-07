#!/usr/bin/env bash
set -euo pipefail
cd /opt/ironpanel
if [ -d .venv ]; then . .venv/bin/activate; fi
python3 - <<'PY'
from app import create_app
from app.services.firewall_manager import apply_firewall_rules
app=create_app()
with app.app_context():
    apply_firewall_rules()
    print('IronPanel firewall rules applied')
PY

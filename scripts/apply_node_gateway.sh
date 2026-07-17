#!/usr/bin/env bash
set -euo pipefail
cd /opt/ironpanel
if [ -d .venv ]; then . .venv/bin/activate; fi
python3 - <<'NODEGWPY'
from app import create_app
from app.services.node_gateway import apply_node_gateway_runtime
app=create_app()
with app.app_context():
    print(apply_node_gateway_runtime())
NODEGWPY

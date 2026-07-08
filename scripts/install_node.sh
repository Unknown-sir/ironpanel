#!/usr/bin/env bash
set -euo pipefail
MASTER=""; TOKEN=""; HOST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --master) MASTER="$2"; shift 2;;
    --token) TOKEN="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    *) shift;;
  esac
done
if [[ -z "$MASTER" || -z "$TOKEN" ]]; then
  echo "Usage: sudo bash scripts/install_node.sh --master https://panel.example.com --token TOKEN --host node.example.com"; exit 1
fi
APP_DIR=/opt/ironpanel-node
mkdir -p "$APP_DIR"
cp -a scripts/node_agent.py "$APP_DIR/node_agent.py"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel psutil >/dev/null
cat > /etc/systemd/system/ironpanel-node.service <<SERVICE
[Unit]
Description=IronPanel v17 Node Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/node_agent.py --master "$MASTER" --token "$TOKEN"
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable --now ironpanel-node
systemctl status ironpanel-node --no-pager || true

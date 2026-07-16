#!/usr/bin/env bash
set -euo pipefail
MASTER=""; TOKEN=""; HOST=""; PROTOCOLS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --master) MASTER="$2"; shift 2;;
    --token) TOKEN="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --protocols) PROTOCOLS="$2"; shift 2;;
    *) shift;;
  esac
done
if [[ -z "$MASTER" ]]; then read -rp "Master Panel URL: " MASTER; fi
if [[ -z "$TOKEN" ]]; then read -rp "Node Token: " TOKEN; fi
if [[ -z "$HOST" ]]; then read -rp "Node Public IP/Domain [auto]: " HOST; HOST=${HOST:-$(hostname -I | awk '{print $1}')}; fi
if [[ -z "$PROTOCOLS" ]]; then read -rp "Protocols [openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2]: " PROTOCOLS; PROTOCOLS=${PROTOCOLS:-openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2}; fi
APP_DIR=/opt/ironpanel-node
mkdir -p "$APP_DIR" /etc/ironpanel-node
cp -a scripts/node_agent.py "$APP_DIR/node_agent.py"
cat > /etc/ironpanel-node/node.env <<ENV
IRONPANEL_NODE_MASTER=$MASTER
IRONPANEL_NODE_TOKEN=$TOKEN
IRONPANEL_NODE_HOST=$HOST
IRONPANEL_NODE_PROTOCOLS=$PROTOCOLS
ENV
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel psutil requests >/dev/null
cat > /etc/systemd/system/ironpanel-node.service <<SERVICE
[Unit]
Description=IronPanel v18 Node Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=/etc/ironpanel-node/node.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/node_agent.py --master "\${IRONPANEL_NODE_MASTER}" --token "\${IRONPANEL_NODE_TOKEN}"
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable --now ironpanel-node
systemctl status ironpanel-node --no-pager || true

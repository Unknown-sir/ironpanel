#!/usr/bin/env bash
set -euo pipefail
MASTER=""; TOKEN=""; HOST=""; PROTOCOLS=""; NODE_NAME=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --master|--panel) MASTER="$2"; shift 2;;
    --token) TOKEN="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --protocols) PROTOCOLS="$2"; shift 2;;
    --name) NODE_NAME="$2"; shift 2;;
    *) shift;;
  esac
done
if [[ -z "$MASTER" ]]; then read -rp "Master Panel URL: " MASTER; fi
if [[ -z "$TOKEN" ]]; then read -rp "Node Token: " TOKEN; fi
if [[ -z "$HOST" ]]; then HOST=$(curl -fsS4 --max-time 3 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}'); fi
if [[ -z "$PROTOCOLS" ]]; then PROTOCOLS="openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh"; fi
APP_DIR=/opt/ironpanel-node
mkdir -p "$APP_DIR" /etc/ironpanel-node /etc/ironpanel-node/users
if [[ -f scripts/node_agent.py ]]; then
  cp -a scripts/node_agent.py "$APP_DIR/node_agent.py"
fi
if [[ ! -s "$APP_DIR/node_agent.py" ]]; then
cat > "$APP_DIR/node_agent.py" <<'PY'
#!/usr/bin/env python3
print('node_agent.py missing; reinstall from IronPanel package')
PY
fi
cat > /etc/ironpanel-node/node.env <<ENV
IRONPANEL_NODE_MASTER=$MASTER
IRONPANEL_NODE_TOKEN=$TOKEN
IRONPANEL_NODE_HOST=$HOST
IRONPANEL_NODE_PROTOCOLS=$PROTOCOLS
IRONPANEL_NODE_NAME=$NODE_NAME
ENV
apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip curl iproute2 iptables openssh-server >/dev/null 2>&1 || true
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel psutil requests >/dev/null
chmod +x "$APP_DIR/node_agent.py"
cat > /etc/systemd/system/ironpanel-node.service <<SERVICE
[Unit]
Description=IronPanel Node Agent
After=network-online.target
Wants=network-online.target

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

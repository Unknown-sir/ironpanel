#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then set -a; . "$ETC_DIR/ironpanel.env"; set +a; fi
PORT=${HYSTERIA2_PORT:-4433}
PUBLIC_HOST=${IRONPANEL_PUBLIC_HOST:-${PUBLIC_HOST:-ironpanel}}
UP=${HYSTERIA2_UP:-100 mbps}
DOWN=${HYSTERIA2_DOWN:-300 mbps}
mkdir -p /etc/hysteria /var/log/hysteria
# Install hysteria binary when missing. If GitHub is blocked, place the binary at /usr/local/bin/hysteria and rerun this script.
if ! command -v hysteria >/dev/null 2>&1 && [[ ! -x /usr/local/bin/hysteria ]]; then
  ARCH=$(uname -m); case "$ARCH" in x86_64|amd64) HARCH=amd64;; aarch64|arm64) HARCH=arm64;; *) HARCH=amd64;; esac
  curl -fsSL "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-${HARCH}" -o /usr/local/bin/hysteria || true
  chmod +x /usr/local/bin/hysteria 2>/dev/null || true
fi
BIN=$(command -v hysteria || echo /usr/local/bin/hysteria)
if [[ ! -x "$BIN" ]]; then echo '[IronPanel] hysteria binary not found' >&2; exit 0; fi
# Use panel/AutoSSL certificate when available; otherwise generate a local self-signed cert.
CERT=${HYSTERIA2_CERT:-/etc/hysteria/server.crt}
KEY=${HYSTERIA2_KEY:-/etc/hysteria/server.key}
if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  CERT=/etc/hysteria/server.crt
  KEY=/etc/hysteria/server.key
fi
if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$KEY" -out "$CERT" -days 3650 \
    -subj "/CN=${PUBLIC_HOST}" >/dev/null 2>&1
fi
chmod 600 "$KEY" 2>/dev/null || true
chmod 644 "$CERT" 2>/dev/null || true
cat > /etc/hysteria/config.yaml <<YAML
# Managed by IronPanel v18.5.2
# Hysteria2 is QUIC over UDP. Open UDP/${PORT} in your cloud firewall.
listen: :${PORT}
tls:
  cert: ${CERT}
  key: ${KEY}
  sniGuard: disable
auth:
  type: command
  command: ${APP_DIR}/scripts/hysteria2_auth.sh
bandwidth:
  up: ${UP}
  down: ${DOWN}
ignoreClientBandwidth: false
congestion:
  type: bbr
masquerade:
  type: proxy
  proxy:
    url: https://www.cloudflare.com/
    rewriteHost: true
sniff:
  enable: true
  timeout: 2s
YAML
cat > /etc/systemd/system/hysteria-server.service <<SERVICE
[Unit]
Description=IronPanel Hysteria2 Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=-${ETC_DIR}/ironpanel.env
ExecStart=${BIN} server -c /etc/hysteria/config.yaml
Restart=always
RestartSec=3
LimitNOFILE=1048576
User=root

[Install]
WantedBy=multi-user.target
SERVICE
chmod +x "$APP_DIR/scripts/hysteria2_auth.sh" 2>/dev/null || true
if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi active; then ufw allow "${PORT}/udp" || true; fi
iptables -C INPUT -p udp --dport "${PORT}" -j ACCEPT 2>/dev/null || iptables -I INPUT -p udp --dport "${PORT}" -j ACCEPT 2>/dev/null || true
systemctl reset-failed hysteria-server >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable --now hysteria-server >/dev/null 2>&1 || true
systemctl restart hysteria-server || true

#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then set -a; . "$ETC_DIR/ironpanel.env"; set +a; fi
PORT=${HYSTERIA2_PORT:-4433}
mkdir -p /etc/hysteria /var/log/hysteria
# Install hysteria binary when missing. If GitHub is blocked, place the binary at /usr/local/bin/hysteria and rerun this script.
if ! command -v hysteria >/dev/null 2>&1 && [[ ! -x /usr/local/bin/hysteria ]]; then
  ARCH=$(uname -m); case "$ARCH" in x86_64|amd64) HARCH=amd64;; aarch64|arm64) HARCH=arm64;; *) HARCH=amd64;; esac
  curl -fsSL "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-${HARCH}" -o /usr/local/bin/hysteria || true
  chmod +x /usr/local/bin/hysteria 2>/dev/null || true
fi
BIN=$(command -v hysteria || echo /usr/local/bin/hysteria)
# Use an existing certificate when available. Otherwise generate a temporary self-signed certificate so service can start.
CERT=${HYSTERIA2_CERT:-/etc/hysteria/server.crt}
KEY=${HYSTERIA2_KEY:-/etc/hysteria/server.key}
if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout "$KEY" -out "$CERT" -subj "/CN=${IRONPANEL_PUBLIC_HOST:-ironpanel}" >/dev/null 2>&1
fi
cat > /etc/hysteria/config.yaml <<YAML
listen: :${PORT}
tls:
  cert: ${CERT}
  key: ${KEY}
auth:
  type: command
  command: ${APP_DIR}/scripts/hysteria2_auth.sh
masquerade:
  type: proxy
  proxy:
    url: https://www.cloudflare.com/
    rewriteHost: true
YAML
cat > /etc/systemd/system/hysteria-server.service <<SERVICE
[Unit]
Description=IronPanel Hysteria2 Server
After=network.target

[Service]
Type=simple
ExecStart=${BIN} server -c /etc/hysteria/config.yaml
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SERVICE
chmod +x "$APP_DIR/scripts/hysteria2_auth.sh" 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now hysteria-server || true
systemctl restart hysteria-server || true

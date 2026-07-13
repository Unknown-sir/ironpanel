#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then set -a; . "$ETC_DIR/ironpanel.env"; set +a; fi
PORT=${HYSTERIA2_PORT:-4433}
PUBLIC_HOST=${IRONPANEL_PUBLIC_HOST:-${PUBLIC_HOST:-ironpanel}}
PASS_FILE=${HYSTERIA2_PASS_FILE:-/etc/hysteria/ironpanel-auth-password}
mkdir -p /etc/hysteria /var/log/hysteria
# Install hysteria binary when missing. If GitHub is blocked, place the binary at /usr/local/bin/hysteria and rerun this script.
if ! command -v hysteria >/dev/null 2>&1 && [[ ! -x /usr/local/bin/hysteria ]]; then
  ARCH=$(uname -m); case "$ARCH" in x86_64|amd64) HARCH=amd64;; aarch64|arm64) HARCH=arm64;; *) HARCH=amd64;; esac
  curl -fsSL "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-${HARCH}" -o /usr/local/bin/hysteria || true
  chmod +x /usr/local/bin/hysteria 2>/dev/null || true
fi
BIN=$(command -v hysteria || echo /usr/local/bin/hysteria)
if [[ ! -x "$BIN" ]]; then echo '[IronPanel] hysteria binary not found' >&2; exit 0; fi
# Hysteria2 is QUIC/TLS based; IronPanel v18.2 uses self-signed certificate + client insecure mode by default.
# This avoids public SSL/Let\'s Encrypt and fixes the old YOUR_DOMAIN placeholder loop.
CERT=/etc/hysteria/server.crt
KEY=/etc/hysteria/server.key
if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$KEY" -out "$CERT" -days 3650 \
    -subj "/CN=${PUBLIC_HOST}" >/dev/null 2>&1
fi
chmod 600 "$KEY"
chmod 644 "$CERT"
if [[ ! -f "$PASS_FILE" ]]; then openssl rand -base64 32 > "$PASS_FILE"; chmod 600 "$PASS_FILE"; fi
cat > /etc/hysteria/config.yaml <<YAML
# Managed by IronPanel v18.2
# No public SSL/Let's Encrypt is required. Clients are generated with insecure=true.
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
ignoreClientBandwidth: false
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
User=root

[Install]
WantedBy=multi-user.target
SERVICE
chmod +x "$APP_DIR/scripts/hysteria2_auth.sh" 2>/dev/null || true
systemctl reset-failed hysteria-server >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable --now hysteria-server >/dev/null 2>&1 || true
systemctl restart hysteria-server || true

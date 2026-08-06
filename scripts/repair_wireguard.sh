#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
if [[ -x "$APP_DIR/scripts/install_protocol_prerequisites.sh" ]]; then APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$APP_DIR/scripts/install_protocol_prerequisites.sh" --packages || true; fi
command -v wg >/dev/null 2>&1 || { echo "[IronPanel] wg binary is missing" >&2; exit 20; }
mkdir -p /etc/wireguard
if [[ ! -f /etc/wireguard/server_private.key ]]; then wg genkey > /etc/wireguard/server_private.key; chmod 600 /etc/wireguard/server_private.key; fi
PRIV=$(cat /etc/wireguard/server_private.key)
PORT=${WIREGUARD_PORT:-51820}
MTU=${IRONPANEL_WIREGUARD_MTU:-1280}
if [[ -f /etc/ironpanel/ironpanel.env ]]; then set -a; . /etc/ironpanel/ironpanel.env; set +a; fi
MTU=${IRONPANEL_WIREGUARD_MTU:-${MTU:-1280}}
PUB=$(printf "%s" "$PRIV" | wg pubkey)
mkdir -p /etc/ironpanel
echo "$PUB" > /etc/ironpanel/wg_server_public.key
cat > /etc/wireguard/wg0.conf <<WG
[Interface]
Address = 10.66.66.1/24
ListenPort = $PORT
PrivateKey = $PRIV
MTU = $MTU
SaveConfig = false
PostUp = sysctl -w net.ipv4.ip_forward=1; iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || true
# BEGIN IRONPANEL PEERS
# END IRONPANEL PEERS
WG
chmod 600 /etc/wireguard/wg0.conf
sysctl -w net.ipv4.ip_forward=1
systemctl enable wg-quick@wg0 >/dev/null 2>&1 || true
systemctl reset-failed wg-quick@wg0 >/dev/null 2>&1 || true
systemctl restart wg-quick@wg0
sleep 1
systemctl is-active --quiet wg-quick@wg0 || { journalctl -u wg-quick@wg0 -n 80 --no-pager >&2 || true; exit 21; }

#!/usr/bin/env bash
set -euo pipefail
mkdir -p /etc/wireguard
if [[ ! -f /etc/wireguard/server_private.key ]]; then wg genkey > /etc/wireguard/server_private.key; chmod 600 /etc/wireguard/server_private.key; fi
PRIV=$(cat /etc/wireguard/server_private.key)
PORT=${WIREGUARD_PORT:-51820}
if [[ -f /etc/ironpanel/ironpanel.env ]]; then set -a; . /etc/ironpanel/ironpanel.env; set +a; fi
PUB=$(printf "%s" "$PRIV" | wg pubkey)
mkdir -p /etc/ironpanel
echo "$PUB" > /etc/ironpanel/wg_server_public.key
cat > /etc/wireguard/wg0.conf <<WG
[Interface]
Address = 10.66.66.1/24
ListenPort = $PORT
PrivateKey = $PRIV
SaveConfig = false
PostUp = sysctl -w net.ipv4.ip_forward=1; iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || true
# BEGIN IRONPANEL PEERS
# END IRONPANEL PEERS
WG
chmod 600 /etc/wireguard/wg0.conf
sysctl -w net.ipv4.ip_forward=1
systemctl enable --now wg-quick@wg0 || true
systemctl restart wg-quick@wg0 || true

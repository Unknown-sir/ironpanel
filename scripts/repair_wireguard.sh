#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
if [[ -x "$APP_DIR/scripts/install_protocol_prerequisites.sh" ]]; then APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$APP_DIR/scripts/install_protocol_prerequisites.sh" --wireguard-packages || true; fi
command -v wg >/dev/null 2>&1 || { echo "[IronPanel] wg binary is missing" >&2; exit 20; }
mkdir -p /etc/wireguard
if [[ ! -f /etc/wireguard/server_private.key ]]; then wg genkey > /etc/wireguard/server_private.key; chmod 600 /etc/wireguard/server_private.key; fi
PRIV=$(cat /etc/wireguard/server_private.key)
PORT=${WIREGUARD_PORT:-51820}
MTU=${IRONPANEL_WIREGUARD_MTU:-1280}
WAN_IF=${WAN_IF:-$(ip route show default | head -n1 | tr -s ' ' | cut -d' ' -f5)}
[[ -n "$WAN_IF" ]] || { echo '[IronPanel] default network interface not found' >&2; exit 22; }
if [[ -f /etc/ironpanel/ironpanel.env ]]; then set -a; . /etc/ironpanel/ironpanel.env; set +a; fi
MTU=${IRONPANEL_WIREGUARD_MTU:-${MTU:-1280}}
PUB=$(printf "%s" "$PRIV" | wg pubkey)
mkdir -p /etc/ironpanel
echo "$PUB" > /etc/ironpanel/wg_server_public.key
TMP_CONF=$(mktemp)
cat > "$TMP_CONF" <<WG
[Interface]
Address = 10.66.66.1/24
ListenPort = $PORT
PrivateKey = $PRIV
MTU = $MTU
SaveConfig = false
PostUp = sysctl -w net.ipv4.ip_forward=1; iptables -C INPUT -p udp --dport $PORT -j ACCEPT 2>/dev/null || iptables -I INPUT -p udp --dport $PORT -j ACCEPT; iptables -C FORWARD -i %i -j ACCEPT 2>/dev/null || iptables -A FORWARD -i %i -j ACCEPT; iptables -C FORWARD -o %i -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -o %i -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT 2>/dev/null || true; iptables -D FORWARD -o %i -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true; iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE 2>/dev/null || true
# BEGIN IRONPANEL PEERS
# END IRONPANEL PEERS
WG
if [[ -f /etc/wireguard/wg0.conf ]]; then
  awk 'f || /# BEGIN IRONPANEL PEERS/{print} /# BEGIN IRONPANEL PEERS/{f=1}' /etc/wireguard/wg0.conf > /tmp/ironpanel-wg-peers.$$ || true
  if [[ -s /tmp/ironpanel-wg-peers.$$ ]]; then
    awk 'BEGIN{stop=0} /# BEGIN IRONPANEL PEERS/{stop=1} !stop{print}' "$TMP_CONF" > /tmp/ironpanel-wg-base.$$
    cat /tmp/ironpanel-wg-base.$$ /tmp/ironpanel-wg-peers.$$ > /etc/wireguard/wg0.conf
  else
    mv "$TMP_CONF" /etc/wireguard/wg0.conf
  fi
else
  mv "$TMP_CONF" /etc/wireguard/wg0.conf
fi
rm -f "$TMP_CONF" /tmp/ironpanel-wg-peers.$$ /tmp/ironpanel-wg-base.$$ 2>/dev/null || true
chmod 600 /etc/wireguard/wg0.conf
sysctl -w net.ipv4.ip_forward=1
systemctl enable wg-quick@wg0 >/dev/null 2>&1 || true
systemctl reset-failed wg-quick@wg0 >/dev/null 2>&1 || true
systemctl restart wg-quick@wg0
sleep 1
systemctl is-active --quiet wg-quick@wg0 || { journalctl -u wg-quick@wg0 -n 80 --no-pager >&2 || true; exit 21; }

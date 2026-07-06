#!/usr/bin/env bash
set -euo pipefail
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
PUBLIC_HOST=${PUBLIC_HOST:-${IRONPANEL_PUBLIC_HOST:-$(hostname -I | awk '{print $1}')}}
OPENVPN_UDP=${OPENVPN_UDP:-1194}
OPENVPN_TCP=${OPENVPN_TCP:-1195}
OPENVPN_PROTO=${OPENVPN_PROTO:-${OPENVPN_TRANSPORT:-udp}}
OPENVPN_PROTO=$(echo "$OPENVPN_PROTO" | tr A-Z a-z)
if [[ "$OPENVPN_PROTO" != "tcp" ]]; then OPENVPN_PROTO=udp; fi
OPENVPN_PORT=$OPENVPN_UDP
if [[ "$OPENVPN_PROTO" == "tcp" ]]; then OPENVPN_PORT=$OPENVPN_TCP; fi
OCSERV_PORT=${OCSERV_PORT:-8443}
OCSERV_TCP=${OCSERV_TCP:-$OCSERV_PORT}
OCSERV_UDP=${OCSERV_UDP:-$OCSERV_PORT}
OCSERV_TRANSPORT=${OCSERV_TRANSPORT:-tcp_udp}
WIREGUARD_PORT=${WIREGUARD_PORT:-51820}
L2TP_PORT=${L2TP_PORT:-1701}
WAN_IF=${WAN_IF:-$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')}
mkdir -p "$ETC_DIR" /etc/openvpn/server /etc/wireguard /etc/ocserv /etc/ppp
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  openvpn easy-rsa \
  wireguard wireguard-tools \
  ocserv \
  strongswan strongswan-starter libcharon-extra-plugins \
  xl2tpd ppp \
  iptables iptables-persistent openssl ca-certificates qrencode curl net-tools
sysctl -w net.ipv4.ip_forward=1 >/dev/null || true
sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null || true
cat > /etc/sysctl.d/99-ironpanel.conf <<SYSCTL
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
SYSCTL
# NAT for every VPN subnet. Duplicate rules are avoided.
ensure_nat(){
  local subnet="$1"
  if [[ -n "${WAN_IF:-}" ]] && ! iptables -t nat -C POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE 2>/dev/null; then
    iptables -t nat -A POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE || true
  fi
}
ensure_forward(){
  local iface="$1"
  if ! iptables -C FORWARD -i "$iface" -j ACCEPT 2>/dev/null; then iptables -A FORWARD -i "$iface" -j ACCEPT || true; fi
  if ! iptables -C FORWARD -o "$iface" -j ACCEPT 2>/dev/null; then iptables -A FORWARD -o "$iface" -j ACCEPT || true; fi
}
ensure_nat 10.8.0.0/24
ensure_nat 10.10.10.0/24
ensure_nat 10.20.20.0/24
ensure_nat 10.66.66.0/24
ensure_forward tun0
ensure_forward vpns0
ensure_forward wg0
# Accept VPN listening ports on local firewall. Provider/cloud firewall must also allow them.
for rule in "${OPENVPN_UDP}/udp" "${OPENVPN_TCP}/tcp" "${OCSERV_TCP}/tcp" "${OCSERV_UDP}/udp" "${WIREGUARD_PORT}/udp" "500/udp" "4500/udp" "${L2TP_PORT}/udp"; do
  proto=${rule##*/}; port=${rule%%/*}
  if ! iptables -C INPUT -p "$proto" --dport "$port" -j ACCEPT 2>/dev/null; then iptables -A INPUT -p "$proto" --dport "$port" -j ACCEPT || true; fi
done
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
# OpenVPN core + CA
if [[ ! -f /etc/openvpn/server/ca.crt ]]; then
  rm -rf /etc/openvpn/easy-rsa
  make-cadir /etc/openvpn/easy-rsa >/dev/null 2>&1 || cp -r /usr/share/easy-rsa /etc/openvpn/easy-rsa
  cd /etc/openvpn/easy-rsa
  EASYRSA_BATCH=1 ./easyrsa init-pki
  EASYRSA_BATCH=1 EASYRSA_REQ_CN=Ironpanel-CA ./easyrsa build-ca nopass
  EASYRSA_BATCH=1 EASYRSA_REQ_CN=server ./easyrsa build-server-full server nopass
  EASYRSA_BATCH=1 ./easyrsa gen-dh
  cp pki/ca.crt /etc/openvpn/server/ca.crt
  cp pki/issued/server.crt /etc/openvpn/server/server.crt
  cp pki/private/server.key /etc/openvpn/server/server.key
  cp pki/dh.pem /etc/openvpn/server/dh.pem
  openvpn --genkey secret /etc/openvpn/server/tls-crypt.key
fi
if [[ ! -f /etc/openvpn/server/crl.pem ]]; then
  cd /etc/openvpn/easy-rsa && EASYRSA_BATCH=1 ./easyrsa gen-crl >/dev/null 2>&1 || true
  cp /etc/openvpn/easy-rsa/pki/crl.pem /etc/openvpn/server/crl.pem 2>/dev/null || touch /etc/openvpn/server/crl.pem
  chmod 644 /etc/openvpn/server/crl.pem
fi
cat > /etc/openvpn/server/server.conf <<OVPN
port $OPENVPN_PORT
proto $OPENVPN_PROTO
dev tun
server 10.8.0.0 255.255.255.0
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
push "dhcp-option DNS 8.8.8.8"
keepalive 10 120
persist-key
persist-tun
user nobody
group nogroup
ca /etc/openvpn/server/ca.crt
cert /etc/openvpn/server/server.crt
key /etc/openvpn/server/server.key
dh /etc/openvpn/server/dh.pem
tls-crypt /etc/openvpn/server/tls-crypt.key
auth SHA256
cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
verify-client-cert require
crl-verify /etc/openvpn/server/crl.pem
verb 3
OVPN
# Ocserv / Cisco AnyConnect compatible core
touch "$ETC_DIR/ocpasswd" "$ETC_DIR/users.passwd"; chmod 600 "$ETC_DIR/ocpasswd" "$ETC_DIR/users.passwd"
if [[ ! -f /etc/ocserv/server-cert.pem ]]; then
  openssl genrsa -out /etc/ocserv/server-key.pem 2048
  openssl req -x509 -new -nodes -key /etc/ocserv/server-key.pem -sha256 -days 3650 -subj "/CN=${PUBLIC_HOST}" -out /etc/ocserv/server-cert.pem
fi
cat > /etc/ocserv/ocserv.conf <<OC
tcp-port = $OCSERV_TCP
udp-port = $( [[ "$OCSERV_TRANSPORT" == "tcp" ]] && echo 0 || echo "$OCSERV_UDP" )
auth = "plain[passwd=$ETC_DIR/ocpasswd]"
server-cert = /etc/ocserv/server-cert.pem
server-key = /etc/ocserv/server-key.pem
run-as-user = nobody
run-as-group = nogroup
socket-file = /run/ocserv.socket
try-mtu-discovery = true
max-clients = 512
max-same-clients = 3
mobile-dpd = 1800
ipv4-network = 10.10.10.0
ipv4-netmask = 255.255.255.0
dns = 1.1.1.1
dns = 8.8.8.8
route = default
no-route = 192.168.0.0/16
cisco-client-compat = true
OC
# L2TP/IPsec core
if [[ ! -f "$ETC_DIR/ipsec.psk" ]]; then openssl rand -base64 24 > "$ETC_DIR/ipsec.psk"; chmod 600 "$ETC_DIR/ipsec.psk"; fi
cat > /etc/ipsec.conf <<'IPSEC'
config setup
  uniqueids=no
  charondebug="ike 1, knl 1, cfg 0"
conn L2TP-PSK
  keyexchange=ikev1
  authby=secret
  type=transport
  left=%any
  leftprotoport=17/1701
  right=%any
  rightprotoport=17/%any
  auto=add
  ike=aes256-sha1-modp1024,3des-sha1-modp1024!
  esp=aes256-sha1,3des-sha1!
  rekey=no
  forceencaps=yes
  dpddelay=30
  dpdtimeout=120
  dpdaction=clear
IPSEC
cat > /etc/ipsec.secrets <<IPSECSEC
%any %any : PSK "$(cat $ETC_DIR/ipsec.psk)"
IPSECSEC
chmod 600 /etc/ipsec.secrets
cat > /etc/xl2tpd/xl2tpd.conf <<XL2TP
[global]
port = $L2TP_PORT
[lns default]
ip range = 10.20.20.10-10.20.20.250
local ip = 10.20.20.1
require chap = yes
refuse pap = yes
require authentication = yes
name = l2tpd
pppoptfile = /etc/ppp/options.xl2tpd
length bit = yes
XL2TP
cat > /etc/ppp/options.xl2tpd <<'PPP'
require-mschap-v2
ms-dns 1.1.1.1
ms-dns 8.8.8.8
asyncmap 0
auth
crtscts
lock
hide-password
modem
name l2tpd
proxyarp
mtu 1280
mru 1280
noccp
lcp-echo-interval 30
lcp-echo-failure 4
PPP
touch /etc/ppp/chap-secrets; chmod 600 /etc/ppp/chap-secrets
# WireGuard core
if [[ ! -f /etc/wireguard/server_private.key ]]; then wg genkey > /etc/wireguard/server_private.key; chmod 600 /etc/wireguard/server_private.key; fi
SERVER_PRIV=$(cat /etc/wireguard/server_private.key)
SERVER_PUB=$(printf "%s" "$SERVER_PRIV" | wg pubkey)
cat > /etc/wireguard/wg0.conf.tmp <<WG
[Interface]
Address = 10.66.66.1/24
ListenPort = $WIREGUARD_PORT
PrivateKey = $SERVER_PRIV
# BEGIN IRONPANEL PEERS
# END IRONPANEL PEERS
WG
if [[ -f /etc/wireguard/wg0.conf ]]; then
  awk 'BEGIN{keep=1} /# BEGIN IRONPANEL PEERS/{keep=0} keep{print}' /etc/wireguard/wg0.conf.tmp > /tmp/wg0.base
  awk 'f{print} /# BEGIN IRONPANEL PEERS/{f=1}' /etc/wireguard/wg0.conf > /tmp/wg0.peers || true
  cat /tmp/wg0.base /tmp/wg0.peers > /etc/wireguard/wg0.conf
else
  mv /etc/wireguard/wg0.conf.tmp /etc/wireguard/wg0.conf
fi
chmod 600 /etc/wireguard/wg0.conf
rm -f /etc/wireguard/wg0.conf.tmp /tmp/wg0.base /tmp/wg0.peers 2>/dev/null || true
echo "$SERVER_PUB" > "$ETC_DIR/wg_server_public.key"
# Open firewall if ufw is active. Cloud firewall must still be opened by provider.
if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi active; then
  ufw allow "${OPENVPN_UDP}/udp" || true
  ufw allow "${OPENVPN_TCP}/tcp" || true
  ufw allow "${OCSERV_TCP}/tcp" || true
  ufw allow "${OCSERV_UDP}/udp" || true
  ufw allow "${WIREGUARD_PORT}/udp" || true
  ufw allow 500/udp || true
  ufw allow 4500/udp || true
  ufw allow "${L2TP_PORT}/udp" || true
fi
systemctl daemon-reload
systemctl enable openvpn-server@server ocserv strongswan-starter xl2tpd wg-quick@wg0 >/dev/null 2>&1 || true
systemctl restart openvpn-server@server || true
systemctl restart ocserv || true
systemctl restart strongswan-starter || systemctl restart strongswan || ipsec restart || true
systemctl restart xl2tpd || true
systemctl restart wg-quick@wg0 || true
cat <<INFO
Ironpanel VPN cores installed/updated:
- OpenVPN: $OPENVPN_PROTO/$OPENVPN_PORT
- Ocserv/Cisco AnyConnect: transport/$OCSERV_TRANSPORT tcp/$OCSERV_TCP udp/$OCSERV_UDP
- WireGuard: udp/$WIREGUARD_PORT
- L2TP/IPsec: udp/500 udp/4500 udp/$L2TP_PORT
INFO

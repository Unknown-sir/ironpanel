#!/usr/bin/env bash
set -euo pipefail
WIREGUARD_MTU=${IRONPANEL_WIREGUARD_MTU:-${WIREGUARD_MTU:-1280}}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
PUBLIC_HOST=${PUBLIC_HOST:-${IRONPANEL_PUBLIC_HOST:-$(hostname -I | awk '{print $1}')}}
OPENVPN_UDP=${OPENVPN_UDP:-1194}
OPENVPN_TCP=${OPENVPN_TCP:-1195}
OPENVPN_PROTO=${OPENVPN_PROTO:-${OPENVPN_TRANSPORT:-udp}}
OPENVPN_PROTO=$(echo "$OPENVPN_PROTO" | tr A-Z a-z)
if [[ "$OPENVPN_PROTO" != "tcp" ]]; then OPENVPN_PROTO=udp; fi
OPENVPN_PORT=$OPENVPN_UDP
if [[ "$OPENVPN_PROTO" == "tcp" ]]; then OPENVPN_PORT=$OPENVPN_TCP; fi
OCSERV_PORT=${OCSERV_PORT:-8445}
OCSERV_TCP=${OCSERV_TCP:-$OCSERV_PORT}
OCSERV_UDP=${OCSERV_UDP:-$OCSERV_PORT}
OCSERV_TRANSPORT=${OCSERV_TRANSPORT:-tcp_udp}
WIREGUARD_PORT=${WIREGUARD_PORT:-51820}
XRAY_PORT=${XRAY_PORT:-443}
XRAY_API_PORT=${XRAY_API_PORT:-10085}
L2TP_PORT=${L2TP_PORT:-1701}
PPTP_PORT=${PPTP_PORT:-1723}
HYSTERIA2_PORT=${HYSTERIA2_PORT:-4433}
SSH_PORT=${SSH_PORT:-422}
WAN_IF=${WAN_IF:-$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')}
mkdir -p "$ETC_DIR" /etc/openvpn/server /etc/wireguard /etc/ocserv /etc/ppp /var/log/openvpn /usr/local/etc/xray /var/log/xray
export DEBIAN_FRONTEND=noninteractive
apt-get update || true
CORE_PACKAGES=(
  openvpn easy-rsa
  openssh-server
  wireguard wireguard-tools
  ocserv
  strongswan strongswan-starter libcharon-extra-plugins
  xl2tpd ppp pptpd
  iptables iptables-persistent openssl ca-certificates qrencode curl net-tools
)
for pkg in "${CORE_PACKAGES[@]}"; do
  DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" || echo "WARN: package $pkg could not be installed on this OS; continuing"
done
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
ensure_nat 10.70.70.0/24
ensure_forward tun0
ensure_forward vpns0
ensure_forward wg0
# Accept VPN listening ports on local firewall. Provider/cloud firewall must also allow them.
for rule in "${OPENVPN_UDP}/udp" "${OPENVPN_TCP}/tcp" "${OCSERV_TCP}/tcp" "${OCSERV_UDP}/udp" "${WIREGUARD_PORT}/udp" "${XRAY_PORT}/tcp" "${PPTP_PORT}/tcp" "${HYSTERIA2_PORT}/udp" "${SSH_PORT}/tcp" "500/udp" "4500/udp" "${L2TP_PORT}/udp"; do
  proto=${rule##*/}; port=${rule%%/*}
  if ! iptables -C INPUT -p "$proto" --dport "$port" -j ACCEPT 2>/dev/null; then iptables -A INPUT -p "$proto" --dport "$port" -j ACCEPT || true; fi
done
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
# SSH core
if [[ -x /opt/ironpanel/scripts/repair_ssh.sh ]]; then
  SSH_PORT="$SSH_PORT" IRONPANEL_SSH_PORT="$SSH_PORT" bash /opt/ironpanel/scripts/repair_ssh.sh --install || true
fi

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
# IronPanel OpenVPN runs without privilege drop because client-connect/client-disconnect
# scripts must read/write the IronPanel SQLite database for quota enforcement.
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
status /var/log/openvpn/status.log 10
status-version 2
script-security 2
client-connect /opt/ironpanel/scripts/openvpn_client_connect.sh
client-disconnect /opt/ironpanel/scripts/openvpn_client_disconnect.sh
verb 3
OVPN
# Ocserv / Cisco AnyConnect compatible core
mkdir -p /etc/ocserv/certs
if [[ -x /opt/ironpanel/scripts/repair_ocserv.sh ]]; then
  OCSERV_PORT=${OCSERV_TCP:-8445} OCSERV_TCP=${OCSERV_TCP:-8445} OCSERV_UDP=${OCSERV_UDP:-8445} OCSERV_TRANSPORT=${OCSERV_TRANSPORT:-tcp_udp} bash /opt/ironpanel/scripts/repair_ocserv.sh || true
fi
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
# PPP hooks for L2TP online-session tracking. PEERNAME is provided by pppd on most xl2tpd builds.
mkdir -p /etc/ppp/ip-up.d /etc/ppp/ip-down.d
cat > /etc/ppp/ip-up.d/ironpanel-online <<'PPPHOOKUP'
#!/usr/bin/env bash
set +e
PY="/opt/ironpanel/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
USER_NAME="${PEERNAME:-${PPP_PEER:-${IFNAME:-l2tp}}}"
REMOTE_IP="${IPREMOTE:-${5:-}}"
DEVICE_ID="${IFNAME:-${1:-ppp}}"
"$PY" /opt/ironpanel/scripts/ironpanel_session_account.py connect l2tp "$USER_NAME" "$REMOTE_IP" "$DEVICE_ID" >/dev/null 2>&1 || true
exit 0
PPPHOOKUP
cat > /etc/ppp/ip-down.d/ironpanel-online <<'PPPHOOKDOWN'
#!/usr/bin/env bash
set +e
PY="/opt/ironpanel/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
USER_NAME="${PEERNAME:-${PPP_PEER:-${IFNAME:-l2tp}}}"
REMOTE_IP="${IPREMOTE:-${5:-}}"
DEVICE_ID="${IFNAME:-${1:-ppp}}"
"$PY" /opt/ironpanel/scripts/ironpanel_session_account.py disconnect l2tp "$USER_NAME" "$REMOTE_IP" "$DEVICE_ID" >/dev/null 2>&1 || true
exit 0
PPPHOOKDOWN
chmod +x /etc/ppp/ip-up.d/ironpanel-online /etc/ppp/ip-down.d/ironpanel-online
# WireGuard core
if [[ ! -f /etc/wireguard/server_private.key ]]; then wg genkey > /etc/wireguard/server_private.key; chmod 600 /etc/wireguard/server_private.key; fi
SERVER_PRIV=$(cat /etc/wireguard/server_private.key)
SERVER_PUB=$(printf "%s" "$SERVER_PRIV" | wg pubkey)
cat > /etc/wireguard/wg0.conf.tmp <<WG
[Interface]
Address = 10.66.66.1/24
ListenPort = $WIREGUARD_PORT
PrivateKey = $SERVER_PRIV
MTU = $WIREGUARD_MTU
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

# Xray core. The official installer is used when xray is not already installed.
# If the server has no GitHub access, install xray manually and rerun upgrade.sh.
if ! command -v xray >/dev/null 2>&1 && [[ ! -x /usr/local/bin/xray ]]; then
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray-install.sh || true
  if [[ -s /tmp/xray-install.sh ]]; then bash /tmp/xray-install.sh install || true; fi
fi

ensure_xray_runtime_permissions() {
  # v16.3: use a clean IronPanel-managed unit instead of the upstream unit/drop-ins.
  # The upstream installer may leave User=nobody and our old v16.1 drop-in had
  # DynamicUser= with an empty value, which systemd rejects as "Failed to parse
  # boolean value". When that drop-in is ignored, Xray keeps running as nobody
  # and cannot open /var/log/xray/access.log.
  install -d -m 755 -o root -g root /usr/local/etc/xray 2>/dev/null || mkdir -p /usr/local/etc/xray
  install -d -m 755 -o root -g root /var/log/xray 2>/dev/null || mkdir -p /var/log/xray
  touch /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  chown root:root /var/log/xray /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  chmod 755 /var/log/xray 2>/dev/null || true
  chmod 644 /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  if [[ -f /usr/local/etc/xray/config.json ]]; then
    chown root:root /usr/local/etc/xray/config.json 2>/dev/null || true
    chmod 644 /usr/local/etc/xray/config.json 2>/dev/null || true
  fi
  if [[ -x /usr/local/bin/xray || -x /usr/bin/xray || -n "$(command -v xray 2>/dev/null || true)" ]]; then
    XRAY_BIN="$(command -v xray 2>/dev/null || true)"
    [[ -n "$XRAY_BIN" ]] || XRAY_BIN=/usr/local/bin/xray
    # Remove broken/old drop-ins, including:
    # - 10-donot_touch_single_conf.conf from the official installer
    # - 20-ironpanel-runtime.conf from v16.1/v16.2 with DynamicUser=
    if [[ -d /etc/systemd/system/xray.service.d ]]; then
      BACKUP_DIR="/etc/systemd/system/xray.service.d.ironpanel-backup-$(date +%Y%m%d%H%M%S)"
      mkdir -p "$BACKUP_DIR" 2>/dev/null || true
      cp -a /etc/systemd/system/xray.service.d/. "$BACKUP_DIR"/ 2>/dev/null || true
      rm -rf /etc/systemd/system/xray.service.d
    fi
    cat > /etc/systemd/system/xray.service <<EOF_SERVICE
[Unit]
Description=Xray Service - IronPanel Managed
Documentation=https://github.com/XTLS/Xray-core
After=network.target nss-lookup.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
ExecStartPre=/bin/sh -c 'mkdir -p /var/log/xray /usr/local/etc/xray; touch /var/log/xray/access.log /var/log/xray/error.log; chmod 755 /var/log/xray; chmod 644 /var/log/xray/access.log /var/log/xray/error.log'
ExecStart=$XRAY_BIN run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF_SERVICE
  fi
}

ensure_xray_runtime_permissions
if [[ ! -f /usr/local/etc/xray/config.json ]]; then
  cat > /usr/local/etc/xray/config.json <<XRAYJSON
{
  "log": {"loglevel": "warning", "access": "/var/log/xray/access.log", "error": "/var/log/xray/error.log"},
  "inbounds": [{"tag":"ironpanel-xray","listen":"0.0.0.0","port": $XRAY_PORT,"protocol":"vless","settings":{"clients":[],"decryption":"none"},"streamSettings":{"network":"tcp","security":"none"}}],
  "outbounds": [{"tag":"direct","protocol":"freedom"}]
}
XRAYJSON
fi
# Open firewall if ufw is active. Cloud firewall must still be opened by provider.
if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi active; then
  ufw allow "${OPENVPN_UDP}/udp" || true
  ufw allow "${OPENVPN_TCP}/tcp" || true
  ufw allow "${OCSERV_TCP}/tcp" || true
  ufw allow "${OCSERV_UDP}/udp" || true
  ufw allow "${WIREGUARD_PORT}/udp" || true
  ufw allow "${XRAY_PORT}/tcp" || true
  ufw allow 500/udp || true
  ufw allow 4500/udp || true
  ufw allow "${L2TP_PORT}/udp" || true
fi
ensure_xray_runtime_permissions
systemctl daemon-reload
systemctl enable openvpn-server@server xray ocserv strongswan-starter xl2tpd wg-quick@wg0 >/dev/null 2>&1 || true
systemctl restart openvpn-server@server || true
ensure_xray_runtime_permissions
systemctl restart xray || true
systemctl restart ocserv || true
systemctl restart strongswan-starter || systemctl restart strongswan || ipsec restart || true
systemctl restart xl2tpd || true
systemctl restart wg-quick@wg0 || true
# v18 legacy/new cores
if [[ -x /opt/ironpanel/scripts/repair_pptp.sh ]]; then bash /opt/ironpanel/scripts/repair_pptp.sh || true; fi
if [[ -x /opt/ironpanel/scripts/repair_hysteria2.sh ]]; then HYSTERIA2_PORT=${HYSTERIA2_PORT:-4433}
SSH_PORT=${SSH_PORT:-422} HYSTERIA2_UP="${HYSTERIA2_UP:-100 mbps}" HYSTERIA2_DOWN="${HYSTERIA2_DOWN:-300 mbps}" bash /opt/ironpanel/scripts/repair_hysteria2.sh || true; fi
cat <<INFO
Ironpanel VPN cores installed/updated:
- OpenVPN: $OPENVPN_PROTO/$OPENVPN_PORT
- Ocserv/Cisco AnyConnect: transport/$OCSERV_TRANSPORT tcp/$OCSERV_TCP udp/$OCSERV_UDP
- WireGuard: udp/$WIREGUARD_PORT
- L2TP/IPsec: udp/500 udp/4500 udp/$L2TP_PORT
- PPTP: tcp/$PPTP_PORT
- Hysteria2: udp/$HYSTERIA2_PORT
INFO

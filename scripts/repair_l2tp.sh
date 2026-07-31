#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
PUBLIC_HOST=${IRONPANEL_PUBLIC_HOST:-${PUBLIC_HOST:-}}
L2TP_PORT=${L2TP_PORT:-1701}
IKEV2_POOL=${IKEV2_POOL:-10.21.21.10-10.21.21.250}
L2TP_POOL=${L2TP_POOL:-10.20.20.10-10.20.20.250}
L2TP_LOCAL=${L2TP_LOCAL:-10.20.20.1}
LOG_PREFIX='[IronPanel L2TP/IKEv2]'
log(){ echo "$LOG_PREFIX $*"; }

if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST=$(hostname -f 2>/dev/null || hostname 2>/dev/null || echo ironpanel.local)
fi
PUBLIC_HOST=${PUBLIC_HOST#http://}; PUBLIC_HOST=${PUBLIC_HOST#https://}; PUBLIC_HOST=${PUBLIC_HOST%%/*}; PUBLIC_HOST=${PUBLIC_HOST%%:*}; PUBLIC_HOST=${PUBLIC_HOST//[^A-Za-z0-9_.-]/}
[[ -n "$PUBLIC_HOST" ]] || PUBLIC_HOST=ironpanel.local

install_packages(){
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y || true
    apt-get install -y strongswan strongswan-starter libcharon-extra-plugins xl2tpd ppp iptables openssl || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y strongswan xl2tpd ppp iptables openssl || true
  fi
}

ensure_cert(){
  mkdir -p /etc/ipsec.d/certs /etc/ipsec.d/private "$ETC_DIR"
  local cert=/etc/ipsec.d/certs/ironpanel-ikev2-server.crt
  local key=/etc/ipsec.d/private/ironpanel-ikev2-server.key
  local le_cert="/etc/letsencrypt/live/$PUBLIC_HOST/fullchain.pem"
  local le_key="/etc/letsencrypt/live/$PUBLIC_HOST/privkey.pem"
  if openssl x509 -in "$le_cert" -noout >/dev/null 2>&1 && openssl pkey -in "$le_key" -noout >/dev/null 2>&1; then
    cp -f "$le_cert" "$cert"; cp -f "$le_key" "$key"; chmod 600 "$key"; chmod 644 "$cert"; echo letsencrypt > "$ETC_DIR/ikev2_cert_mode"; return 0
  fi
  if openssl x509 -in "$cert" -noout >/dev/null 2>&1 && openssl pkey -in "$key" -noout >/dev/null 2>&1; then
    return 0
  fi
  local san="DNS:$PUBLIC_HOST"
  if [[ "$PUBLIC_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then san="IP:$PUBLIC_HOST"; fi
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 \
    -keyout "$key" -out "$cert" -subj "/CN=$PUBLIC_HOST" \
    -addext "subjectAltName=$san" \
    -addext 'keyUsage=digitalSignature,keyEncipherment' \
    -addext 'extendedKeyUsage=serverAuth' >/dev/null 2>&1
  chmod 600 "$key"; chmod 644 "$cert"; echo self-signed > "$ETC_DIR/ikev2_cert_mode"
}

ensure_psk(){
  mkdir -p "$ETC_DIR"
  if [[ ! -s "$ETC_DIR/ipsec.psk" ]]; then openssl rand -base64 24 > "$ETC_DIR/ipsec.psk"; chmod 600 "$ETC_DIR/ipsec.psk"; fi
}

write_ipsec_config(){
  cat > /etc/ipsec.conf <<IPSEC
# Managed by IronPanel. Supports classic L2TP/IPsec-PSK and IKEv2-EAP.
config setup
  uniqueids=no
  charondebug="ike 1, knl 1, cfg 0, net 1, enc 0"

conn L2TP-PSK
  keyexchange=ikev1
  authby=secret
  type=transport
  left=%any
  leftprotoport=17/1701
  right=%any
  rightprotoport=17/%any
  auto=add
  ike=aes256-sha1-modp1024,aes128-sha1-modp1024,3des-sha1-modp1024!
  esp=aes256-sha1,aes128-sha1,3des-sha1!
  rekey=no
  forceencaps=yes
  dpddelay=30
  dpdtimeout=120
  dpdaction=clear

conn IKEv2-EAP
  keyexchange=ikev2
  type=tunnel
  left=%any
  leftid=@$PUBLIC_HOST
  leftcert=/etc/ipsec.d/certs/ironpanel-ikev2-server.crt
  leftauth=pubkey
  leftsendcert=always
  leftsubnet=0.0.0.0/0,::/0
  right=%any
  rightid=%any
  rightauth=eap-mschapv2
  rightsourceip=$IKEV2_POOL
  rightdns=1.1.1.1,8.8.8.8
  eap_identity=%identity
  fragmentation=yes
  rekey=no
  dpddelay=30s
  dpdtimeout=120s
  dpdaction=clear
  ike=aes256gcm16-prfsha384-ecp256,aes256-sha256-modp2048,aes128-sha256-modp2048,aes256-sha1-modp1024!
  esp=aes256gcm16-ecp256,aes256-sha256,aes128-sha256,aes256-sha1!
  auto=add
IPSEC
  cat > /etc/strongswan.conf <<'STRONGSWAN'
# Managed by IronPanel
charon {
  load_modular = yes
  plugins {
    include strongswan.d/charon/*.conf
  }
  install_virtual_ip = yes
  install_routes = yes
}
include strongswan.d/*.conf
STRONGSWAN
}

write_secrets(){
  local psk; psk=$(cat "$ETC_DIR/ipsec.psk")
  {
    printf '%%any %%any : PSK "%s"\n' "$psk"
    printf ': RSA /etc/ipsec.d/private/ironpanel-ikev2-server.key\n'
    if [[ -f /etc/ppp/chap-secrets ]]; then
      awk 'BEGIN{FS="[ \t]+"} $2=="l2tpd" {gsub(/^"|"$/,"",$1); gsub(/^"|"$/,"",$3); if($1!="" && $3!="") printf "\"%s\" : EAP \"%s\"\n", $1, $3}' /etc/ppp/chap-secrets
    fi
  } > /etc/ipsec.secrets
  chmod 600 /etc/ipsec.secrets
}

write_xl2tpd(){
  mkdir -p /etc/xl2tpd /etc/ppp /etc/ppp/ip-up.d /etc/ppp/ip-down.d
  cat > /etc/xl2tpd/xl2tpd.conf <<XL2TP
[global]
port = $L2TP_PORT
[lns default]
ip range = $L2TP_POOL
local ip = $L2TP_LOCAL
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
}

firewall_nat(){
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
  sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null 2>&1 || true
  cat > /etc/sysctl.d/99-ironpanel-l2tp.conf <<'SYSCTL'
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
SYSCTL
  iptables -t nat -C POSTROUTING -s 10.20.20.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.20.20.0/24 -j MASQUERADE || true
  iptables -t nat -C POSTROUTING -s 10.21.21.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.21.21.0/24 -j MASQUERADE || true
  ufw allow 500/udp >/dev/null 2>&1 || true
  ufw allow 4500/udp >/dev/null 2>&1 || true
  ufw allow "$L2TP_PORT/udp" >/dev/null 2>&1 || true
}

restart_services(){
  systemctl daemon-reload || true
  systemctl enable --now xl2tpd >/dev/null 2>&1 || true
  systemctl enable --now strongswan-starter >/dev/null 2>&1 || systemctl enable --now strongswan >/dev/null 2>&1 || true
  ipsec rereadall >/dev/null 2>&1 || true
  ipsec reload >/dev/null 2>&1 || true
  systemctl restart xl2tpd >/dev/null 2>&1 || true
  systemctl restart strongswan-starter >/dev/null 2>&1 || systemctl restart strongswan >/dev/null 2>&1 || true
}

case "${1:---repair}" in
  --status|--diagnose)
    echo "Public host / IKEv2 remote ID: $PUBLIC_HOST"
    echo "PSK file: $ETC_DIR/ipsec.psk"
    echo "Server cert: /etc/ipsec.d/certs/ironpanel-ikev2-server.crt"
    systemctl status strongswan-starter --no-pager 2>/dev/null || systemctl status strongswan --no-pager 2>/dev/null || true
    systemctl status xl2tpd --no-pager 2>/dev/null || true
    ss -lunp 2>/dev/null | grep -E ':(500|4500|1701)\b' || true
    exit 0
    ;;
esac

log "Repairing L2TP/IPsec + IKEv2-EAP runtime for $PUBLIC_HOST"
install_packages
ensure_psk
ensure_cert
write_ipsec_config
write_xl2tpd
write_secrets
firewall_nat
restart_services
log "Done. Use IKEv2 EAP (Username/Password) in strongSwan Android; use L2TP/IPsec PSK only in legacy/native L2TP clients."

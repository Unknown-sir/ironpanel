#!/usr/bin/env bash
set -euo pipefail
if [[ -f /etc/ironpanel/ironpanel.env ]]; then set -a; . /etc/ironpanel/ironpanel.env; set +a; fi
PORT=${OCSERV_PORT:-${OCSERV_TCP:-8445}}
UDP_PORT=${OCSERV_UDP:-$PORT}
TRANSPORT=${OCSERV_TRANSPORT:-tcp_udp}
PUBLIC_HOST=${IRONPANEL_PUBLIC_HOST:-${PUBLIC_HOST:-IronPanel-Ocserv}}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
OC_NET=${OCSERV_IPV4_NETWORK:-10.44.0.0}
OC_MASK=${OCSERV_IPV4_NETMASK:-255.255.255.0}
OC_CIDR=${OCSERV_IPV4_CIDR:-10.44.0.0/24}
mkdir -p /etc/ocserv/certs "$ETC_DIR" /var/run
chmod +x /opt/ironpanel/scripts/ocserv_session_hook.sh 2>/dev/null || true
: > "$ETC_DIR/ocpasswd"
chmod 600 "$ETC_DIR/ocpasswd" || true
# Cisco AnyConnect / Ocserv always needs TLS material. IronPanel uses a self-signed cert by default, not Let's Encrypt.
if [[ ! -f /etc/ocserv/certs/server-key.pem || ! -f /etc/ocserv/certs/server-cert.pem ]]; then
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout /etc/ocserv/certs/server-key.pem \
    -out /etc/ocserv/certs/server-cert.pem \
    -days 3650 -subj "/CN=${PUBLIC_HOST}" >/dev/null 2>&1
fi
chmod 600 /etc/ocserv/certs/server-key.pem
chmod 644 /etc/ocserv/certs/server-cert.pem
UDP_LINE="udp-port = ${UDP_PORT}"
if [[ "$TRANSPORT" == "tcp" ]]; then UDP_LINE="udp-port = 0"; fi
cat > /etc/ocserv/ocserv.conf <<OC
# Managed by IronPanel v18.2
# Cisco AnyConnect / OpenConnect uses TLS/DTLS internally. This config uses a self-signed certificate by default.
isolate-workers = false
socket-file = /var/run/ocserv-socket
occtl-socket-file = /var/run/occtl.socket
device = vpns
tcp-port = ${PORT}
${UDP_LINE}
auth = "plain[passwd=${ETC_DIR}/ocpasswd]"
server-cert = /etc/ocserv/certs/server-cert.pem
server-key = /etc/ocserv/certs/server-key.pem
try-mtu-discovery = true
ipv4-network = ${OC_NET}
ipv4-netmask = ${OC_MASK}
dns = 1.1.1.1
dns = 8.8.8.8
route = default
tunnel-all-dns = true
cisco-client-compat = true
# Keep IronPanel online sessions accurate for Cisco/AnyConnect clients.
connect-script = /opt/ironpanel/scripts/ocserv_session_hook.sh connect
disconnect-script = /opt/ironpanel/scripts/ocserv_session_hook.sh disconnect
max-clients = 512
max-same-clients = 3
mobile-dpd = 1800
OC
# Routing/NAT
sysctl -w net.ipv4.ip_forward=1 >/dev/null || true
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-ironpanel-ocserv.conf
EXT_IF=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')
if [[ -n "${EXT_IF:-}" ]]; then
  iptables -t nat -C POSTROUTING -s "$OC_CIDR" -o "$EXT_IF" -j MASQUERADE 2>/dev/null || \
  iptables -t nat -A POSTROUTING -s "$OC_CIDR" -o "$EXT_IF" -j MASQUERADE || true
fi
rm -f /var/run/ocserv-socket /var/run/occtl.socket /run/ocserv-socket /run/occtl.socket 2>/dev/null || true
if ocserv -t -c /etc/ocserv/ocserv.conf; then
  systemctl daemon-reload
  systemctl enable --now ocserv >/dev/null 2>&1 || true
  systemctl restart ocserv || true
else
  echo '[IronPanel] ocserv config test failed' >&2
  exit 1
fi

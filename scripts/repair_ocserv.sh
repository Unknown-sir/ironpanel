#!/usr/bin/env bash
set -euo pipefail
PORT=${OCSERV_PORT:-8445}
if [[ -f /etc/ironpanel/ironpanel.env ]]; then set -a; . /etc/ironpanel/ironpanel.env; set +a; fi
mkdir -p /etc/ocserv /etc/ironpanel
if [[ ! -f /etc/ocserv/server-key.pem ]]; then openssl req -newkey rsa:2048 -nodes -keyout /etc/ocserv/server-key.pem -x509 -days 3650 -out /etc/ocserv/server-cert.pem -subj "/CN=${IRONPANEL_PUBLIC_HOST:-ironpanel}"; fi
cat > /etc/ocserv/ocserv.conf <<OC
isolate-workers = false
tcp-port = ${OCSERV_PORT:-$PORT}
udp-port = ${OCSERV_UDP:-$PORT}
auth = "plain[passwd=/etc/ironpanel/ocpasswd]"
server-cert = /etc/ocserv/server-cert.pem
server-key = /etc/ocserv/server-key.pem
try-mtu-discovery = true
ipv4-network = 10.10.10.0
ipv4-netmask = 255.255.255.0
dns = 1.1.1.1
route = default
cisco-client-compat = true
max-clients = 512
max-same-clients = 3
mobile-dpd = 1800
OC
systemctl enable --now ocserv || true
systemctl restart ocserv || true

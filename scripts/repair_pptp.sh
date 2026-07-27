#!/usr/bin/env bash
set -euo pipefail
apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y pptpd ppp >/dev/null 2>&1 || true
cat > /etc/pptpd.conf <<'PPTP'
option /etc/ppp/pptpd-options
localip 10.70.70.1
remoteip 10.70.70.10-250
listen 0.0.0.0
PPTP
cat > /etc/ppp/pptpd-options <<'OPT'
name pptpd
refuse-pap
refuse-chap
refuse-mschap
require-mschap-v2
require-mppe-128
ms-dns 1.1.1.1
ms-dns 8.8.8.8
proxyarp
lock
nobsdcomp
novj
novjccomp
nologfd
OPT
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -C POSTROUTING -s 10.70.70.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.70.70.0/24 -j MASQUERADE
systemctl enable --now pptpd || true
systemctl restart pptpd || true

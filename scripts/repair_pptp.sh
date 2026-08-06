#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
LOG=${LOG:-/var/log/ironpanel-pptp-repair.log}
mkdir -p "$(dirname "$LOG")" /etc/ppp
exec > >(tee -a "$LOG") 2>&1

if [[ ! -x "$APP_DIR/scripts/install_protocol_prerequisites.sh" ]]; then
  echo '[IronPanel] protocol prerequisite installer is missing' >&2
  exit 20
fi
APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$APP_DIR/scripts/install_protocol_prerequisites.sh" --packages || true
command -v pptpd >/dev/null 2>&1 || { echo '[IronPanel] pptpd binary is unavailable after package/source installation' >&2; exit 21; }
command -v pppd >/dev/null 2>&1 || { echo '[IronPanel] pppd binary is missing' >&2; exit 22; }

# PPTP needs MPPE and GRE/PPTP connection tracking support. Some kernels build
# these in; modprobe then returns non-zero even though the feature is present.
modprobe ppp_generic >/dev/null 2>&1 || true
modprobe ppp_mppe >/dev/null 2>&1 || true
modprobe nf_conntrack_pptp >/dev/null 2>&1 || true
modprobe nf_nat_pptp >/dev/null 2>&1 || true
if [[ ! -r /proc/crypto ]] || ! grep -qiE '(^|[[:space:]])mppe([[:space:]]|$)' /proc/crypto; then
  if ! modinfo ppp_mppe >/dev/null 2>&1 && [[ ! -d /sys/module/ppp_mppe ]]; then
    echo '[IronPanel] WARNING: ppp_mppe kernel support could not be confirmed; PPTP clients may fail MPPE negotiation' >&2
  fi
fi

cat > /etc/pptpd.conf <<'PPTP'
option /etc/ppp/pptpd-options
localip 10.70.70.1
remoteip 10.70.70.10-250
listen 0.0.0.0
PPTP
cat > /etc/ppp/pptpd-options <<'OPT'
name pptpd
ipparam ironpanel-pptp
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
touch /etc/ppp/chap-secrets
chmod 600 /etc/ppp/chap-secrets
if [[ -x "$APP_DIR/scripts/install_ppp_usage_hooks.sh" ]]; then
  APP_DIR="$APP_DIR" bash "$APP_DIR/scripts/install_ppp_usage_hooks.sh"
fi
sysctl -w net.ipv4.ip_forward=1 >/dev/null
WAN_IF=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')
if [[ -n "$WAN_IF" ]]; then
  iptables -t nat -C POSTROUTING -s 10.70.70.0/24 -o "$WAN_IF" -j MASQUERADE 2>/dev/null \
    || iptables -t nat -A POSTROUTING -s 10.70.70.0/24 -o "$WAN_IF" -j MASQUERADE
fi
iptables -C INPUT -p tcp --dport 1723 -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport 1723 -j ACCEPT
iptables -C INPUT -p gre -j ACCEPT 2>/dev/null || iptables -I INPUT -p gre -j ACCEPT
systemctl daemon-reload
systemctl enable pptpd >/dev/null 2>&1 || true
systemctl reset-failed pptpd >/dev/null 2>&1 || true
systemctl restart pptpd
sleep 1
systemctl is-active --quiet pptpd || { journalctl -u pptpd -n 80 --no-pager >&2 || true; exit 23; }
echo '[IronPanel] PPTP repair completed successfully'

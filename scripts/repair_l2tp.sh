#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
log(){ echo "[IronPanel L2TP] $*"; }
log "Repairing L2TP/IPsec runtime"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y || true
  apt-get install -y strongswan strongswan-starter libcharon-extra-plugins xl2tpd ppp iptables || true
fi
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
cat > /etc/sysctl.d/99-ironpanel-l2tp.conf <<'SYSCTL'
net.ipv4.ip_forward=1
SYSCTL
systemctl daemon-reload || true
systemctl enable --now xl2tpd >/dev/null 2>&1 || true
systemctl enable --now strongswan-starter >/dev/null 2>&1 || systemctl enable --now strongswan >/dev/null 2>&1 || true
systemctl restart xl2tpd >/dev/null 2>&1 || true
systemctl restart strongswan-starter >/dev/null 2>&1 || systemctl restart strongswan >/dev/null 2>&1 || true
log "Done"

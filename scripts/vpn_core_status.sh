#!/usr/bin/env bash
set -euo pipefail
services=(openvpn-server@server ocserv strongswan-starter xl2tpd wg-quick@wg0)
echo "Ironpanel VPN core status"
for svc in "${services[@]}"; do
  printf '%-28s %s\n' "$svc" "$(systemctl is-active "$svc" 2>/dev/null || echo unknown)"
done
echo
ss -lntup 2>/dev/null | grep -E ':(1194|1195|8443|51820|500|4500|1701)\b' || true

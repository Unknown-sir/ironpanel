#!/usr/bin/env bash
set +e
echo '=== IronPanel usage accounting ==='
echo "Version: $(cat /opt/ironpanel/VERSION 2>/dev/null || echo unknown)"
systemctl status ironpanel-usage.timer --no-pager 2>/dev/null | sed -n '1,12p'
echo
echo '--- latest collector logs ---'
journalctl -u ironpanel-usage.service -n 40 --no-pager 2>/dev/null || true
echo
echo '--- runtime sources ---'
for p in /var/log/openvpn/status.log /run/openvpn-server/status-server.log /etc/hysteria/config.yaml /etc/ocserv/ocserv.conf; do
  [[ -e "$p" ]] && echo "OK  $p" || echo "MISS $p"
done
command -v wg >/dev/null && wg show wg0 transfer 2>/dev/null | head -5
command -v occtl >/dev/null && (occtl -j show users 2>/dev/null || occtl --json show users 2>/dev/null) | head -30
find /var/lib/ironpanel/usage-events /run/ironpanel-ppp -maxdepth 1 -type f 2>/dev/null | sed 's/^/EVENT /' | head -30
echo
echo 'Run a forced sync with:'
echo '  /opt/ironpanel/.venv/bin/flask --app run.py sync-usage'

#!/usr/bin/env bash
set +e
echo '=== IronPanel usage accounting ==='
echo "Version: $(cat /opt/ironpanel/VERSION 2>/dev/null || echo unknown)"
systemctl status ironpanel-usage-sync.timer --no-pager 2>/dev/null | sed -n '1,12p'
echo
echo '--- latest collector logs ---'
journalctl -u ironpanel-usage-sync.service -n 40 --no-pager 2>/dev/null || true
echo
echo '--- runtime sources ---'
for p in /var/log/openvpn/status.log /run/openvpn-server/status-server.log /etc/hysteria/config.yaml /etc/ocserv/ocserv.conf; do
  [[ -e "$p" ]] && echo "OK  $p" || echo "MISS $p"
done
command -v wg >/dev/null && wg show wg0 transfer 2>/dev/null | head -5
command -v occtl >/dev/null && (occtl -j show users 2>/dev/null || occtl --json show users 2>/dev/null) | head -30

echo
echo '--- Xray Stats API ---'
XRAY_BIN="$(command -v xray 2>/dev/null || true)"
[[ -z "$XRAY_BIN" && -x /usr/local/bin/xray ]] && XRAY_BIN=/usr/local/bin/xray
[[ -z "$XRAY_BIN" && -x /usr/bin/xray ]] && XRAY_BIN=/usr/bin/xray
XRAY_API_PORT="$(python3 - <<'PYX'
import json
from pathlib import Path
for raw in ('/usr/local/etc/xray/config.json','/etc/xray/config.json','/etc/ironpanel/xray/config.json'):
    try: data=json.loads(Path(raw).read_text(errors='ignore'))
    except Exception: continue
    for item in data.get('inbounds',[]) if isinstance(data,dict) else []:
        if not isinstance(item,dict): continue
        tag=str(item.get('tag') or '').lower(); proto=str(item.get('protocol') or '').lower()
        if tag == 'api' or ('api' in tag and proto == 'dokodemo-door'):
            try:
                port=int(item.get('port') or 0)
                if 0 < port <= 65535:
                    print(port); raise SystemExit
            except Exception: pass
print(10085)
PYX
)"
if [[ -n "$XRAY_BIN" ]]; then
  echo "Binary: $XRAY_BIN"
  echo "Server: 127.0.0.1:${XRAY_API_PORT}"
  "$XRAY_BIN" api statsquery --server="127.0.0.1:${XRAY_API_PORT}" 2>&1 | sed -n '1,80p'
else
  echo 'MISS xray binary'
fi

find /var/lib/ironpanel/usage-events /run/ironpanel-ppp -maxdepth 1 -type f 2>/dev/null | sed 's/^/EVENT /' | head -30
echo
echo 'Run a forced sync with:'
echo '  /opt/ironpanel/.venv/bin/flask --app run.py sync-usage'

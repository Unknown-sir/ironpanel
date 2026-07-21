#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${IRONPANEL_APP_DIR:-/opt/ironpanel}
ETC_DIR=${IRONPANEL_ETC_DIR:-/etc/ironpanel}
REPAIR=0
[[ "${1:-}" == "--repair" ]] && REPAIR=1

if [[ -x "$APP_DIR/.venv/bin/flask" && -f "$APP_DIR/run.py" ]]; then
  cd "$APP_DIR"
  if [[ "$REPAIR" == "1" ]]; then
    "$APP_DIR/.venv/bin/flask" --app run.py doctor --repair
  else
    "$APP_DIR/.venv/bin/flask" --app run.py doctor
  fi
  exit $?
fi

echo "IronPanel Doctor fallback"
echo "========================="
echo "App: $APP_DIR"
echo "Config: $ETC_DIR"
[[ -d "$APP_DIR" ]] && echo "OK app directory" || echo "FAIL missing app directory"
[[ -f "$ETC_DIR/ironpanel.env" ]] && echo "OK env file" || echo "FAIL missing env file"
[[ -f "$ETC_DIR/ironpanel.db" ]] && echo "OK database" || echo "WARN database missing"
for svc in ironpanel ironpanel-usage-sync.timer openvpn-server@server wg-quick@wg0 ocserv xray hysteria-server ironpanel-tgproxy ssh sshd; do
  state=$(systemctl is-active "$svc" 2>/dev/null || true)
  [[ -n "$state" ]] && echo "$svc: $state"
done
if [[ "$REPAIR" == "1" ]]; then
  systemctl daemon-reload || true
  systemctl restart ironpanel || true
  echo "Fallback repair finished"
fi

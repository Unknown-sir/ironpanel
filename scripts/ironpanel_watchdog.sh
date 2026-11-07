#!/usr/bin/env bash
set -euo pipefail
ENV_FILE=/etc/ironpanel/ironpanel.env
STATE=/run/ironpanel-watchdog.fail
LOG=/var/log/ironpanel-watchdog.log
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a || true
PORT="${IRONPANEL_PORT:-8080}"
now(){ date '+%Y-%m-%d %H:%M:%S'; }
log(){ echo "[$(now)] $*" | tee -a "$LOG" >/dev/null; }
if ! systemctl is-active --quiet ironpanel; then
  log "ironpanel is not active; restarting"
  systemctl restart ironpanel || true
  echo 0 > "$STATE"
  exit 0
fi
ok=0
curl -fsS --max-time 8 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1 && ok=1 || true
if [ "$ok" != "1" ]; then
  curl -kfsS --max-time 8 "https://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1 && ok=1 || true
fi
if [ "$ok" = "1" ]; then
  echo 0 > "$STATE"
  exit 0
fi
fails=0
[ -f "$STATE" ] && fails=$(cat "$STATE" 2>/dev/null || echo 0)
fails=$((fails+1))
echo "$fails" > "$STATE"
log "health endpoint failed count=$fails port=$PORT"
if [ "$fails" -ge 2 ]; then
  log "restarting ironpanel after repeated health failures"
  systemctl restart ironpanel || true
  echo 0 > "$STATE"
fi

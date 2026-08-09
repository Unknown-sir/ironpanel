#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
TIMEOUT=${IRONPANEL_PROTOCOL_REPAIR_TIMEOUT:-240}
HEALTH_TIMEOUT=${IRONPANEL_PROTOCOL_HEALTH_TIMEOUT:-30}
CHECK_ONLY=0
ALL=0
STRICT=0
while (($#)); do
  case "$1" in
    --check-only) CHECK_ONLY=1 ;;
    --all) ALL=1 ;;
    --strict) STRICT=1 ;;
  esac
  shift || true
done

HEALTH="$APP_DIR/scripts/protocol_health_check.sh"
[[ -x "$HEALTH" ]] || { echo "[IronPanel] health checker missing: $HEALTH" >&2; exit 2; }
PY="$APP_DIR/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

ACTIVE='openvpn,xray'
if [[ -d "$APP_DIR/app" ]]; then
  ACTIVE=$(
    cd "$APP_DIR" && "$PY" - <<'PY' 2>/dev/null || true
from app import create_app
from app.services.provisioning import active_protocols
app=create_app()
with app.app_context(): print(','.join(active_protocols()))
PY
  )
fi
[[ -n "$ACTIVE" ]] || ACTIVE='openvpn,xray'
contains(){ [[ ",$ACTIVE," == *",$1,"* ]]; }

all_protocols=(openvpn wireguard ocserv l2tp pptp xray hysteria2 telegram_proxy ssh)
failures=0
run_repair(){
  local p="$1"
  case "$p" in
    openvpn) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_openvpn.sh" ;;
    wireguard) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_wireguard.sh" ;;
    ocserv) timeout "$TIMEOUT" env ETC_DIR="$ETC_DIR" PUBLIC_HOST="${IRONPANEL_PUBLIC_HOST:-}" IRONPANEL_PUBLIC_HOST="${IRONPANEL_PUBLIC_HOST:-}" bash "$APP_DIR/scripts/repair_ocserv.sh" ;;
    l2tp) timeout "$TIMEOUT" env ETC_DIR="$ETC_DIR" PUBLIC_HOST="${IRONPANEL_PUBLIC_HOST:-}" IRONPANEL_PUBLIC_HOST="${IRONPANEL_PUBLIC_HOST:-}" bash "$APP_DIR/scripts/repair_l2tp.sh" ;;
    pptp) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_pptp.sh" ;;
    xray) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_xray.sh" ;;
    hysteria2) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_hysteria2.sh" ;;
    telegram_proxy) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_telegram_proxy.sh" --sync ;;
    ssh) timeout "$TIMEOUT" bash "$APP_DIR/scripts/repair_ssh.sh" --sync ;;
  esac
}

for p in "${all_protocols[@]}"; do
  if (( ! ALL )) && ! contains "$p"; then
    continue
  fi
  args=(--protocol "$p" --strict --quiet)
  # When --all is used, inactive paid-only protocols need only have a healthy
  # installation/config; the license reconciler owns start/stop decisions.
  if (( ALL )) && ! contains "$p"; then args+=(--installed-only); fi
  if timeout "$HEALTH_TIMEOUT" env APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$HEALTH" "${args[@]}"; then
    echo "[IronPanel] SKIP $p: files/config/service state is healthy"
    continue
  fi
  if (( CHECK_ONLY )); then
    echo "[IronPanel] FAIL $p: health check failed"
    failures=$((failures+1))
    continue
  fi
  echo "[IronPanel] REPAIR $p: health check found a problem (timeout=${TIMEOUT}s)"
  set +e
  run_repair "$p"
  rc=$?
  set -e
  if (( rc != 0 )); then
    echo "[IronPanel] WARN $p repair returned rc=$rc; update will continue" >&2
  fi
  if timeout "$HEALTH_TIMEOUT" env APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$HEALTH" "${args[@]}"; then
    echo "[IronPanel] OK $p after repair"
  else
    echo "[IronPanel] WARN $p is still unhealthy after repair" >&2
    failures=$((failures+1))
  fi
done

if (( STRICT && failures > 0 )); then exit 30; fi
exit 0

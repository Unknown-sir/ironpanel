#!/usr/bin/env bash
set -Eeuo pipefail
REPAIR=0
[[ "${1:-}" == "--repair" ]] && REPAIR=1
APP_DIR=${IRONPANEL_APP_DIR:-/opt/ironpanel}
ETC_DIR=${IRONPANEL_ETC_DIR:-/etc/ironpanel}
ENV_FILE="$ETC_DIR/ironpanel.env"
SERVICES=(ironpanel ironpanel-usage-sync.timer xray openvpn-server@server wg-quick@wg0 ocserv strongswan-starter xl2tpd pptpd hysteria-server)

echo "IronPanel Doctor"
echo "================"
echo "App: $APP_DIR"
echo "Config: $ETC_DIR"
echo ""

ok(){ echo "✅ $*"; }
warn(){ echo "⚠️  $*"; }
fail(){ echo "❌ $*"; }

[[ -d "$APP_DIR" ]] && ok "app directory exists" || fail "missing $APP_DIR"
[[ -f "$ENV_FILE" ]] && ok "env file exists" || fail "missing $ENV_FILE"
[[ -x "$APP_DIR/.venv/bin/python" ]] && ok "python venv exists" || fail "missing python venv"
[[ -f "$ETC_DIR/ironpanel.db" ]] && ok "database exists" || warn "database not found yet"

for svc in "${SERVICES[@]}"; do
  if systemctl list-unit-files "$svc" >/dev/null 2>&1 || systemctl status "$svc" >/dev/null 2>&1; then
    state=$(systemctl is-active "$svc" 2>/dev/null || true)
    [[ "$state" == "active" ]] && ok "$svc active" || warn "$svc $state"
    if [[ "$REPAIR" == "1" && "$state" != "active" ]]; then systemctl restart "$svc" >/dev/null 2>&1 || true; fi
  fi
done

if command -v certbot >/dev/null 2>&1; then
  certbot --version >/dev/null 2>&1 && ok "certbot works" || warn "certbot installed but broken"
else
  warn "certbot not found"
fi

if [[ "$REPAIR" == "1" ]]; then
  echo ""
  echo "Running best-effort repairs..."
  bash "$APP_DIR/scripts/repair_certbot.sh" >/dev/null 2>&1 || true
  bash "$APP_DIR/scripts/repair_xray.sh" >/dev/null 2>&1 || true
  bash "$APP_DIR/scripts/repair_ocserv.sh" >/dev/null 2>&1 || true
  bash "$APP_DIR/scripts/repair_hysteria2.sh" >/dev/null 2>&1 || true
  systemctl daemon-reload || true
  systemctl restart ironpanel || true
  ok "repair commands finished"
fi

echo ""
echo "For panel logs: journalctl -u ironpanel -n 120 --no-pager"

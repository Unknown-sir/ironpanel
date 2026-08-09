#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
LOG=${LOG:-/var/log/ironpanel-license-reconcile.log}
mkdir -p "$(dirname "$LOG")"
exec 9>/run/ironpanel-license-reconcile.lock
flock -w 5 9 || exit 0
exec >>"$LOG" 2>&1

echo "[$(date -Is)] license runtime reconcile started"
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ETC_DIR/ironpanel.env"
  set +a
fi

# Do not run the all-protocol installer on every license change. The base install
# prepares protocol dependencies, and the smart repair below installs only a newly
# licensed protocol that is actually missing/broken. This keeps activation quick.

cd "$APP_DIR"
PY="$APP_DIR/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3

# Expand the saved protocol set to every protocol granted by the current paid
# license, then rewrite all user/runtime configs before targeted daemon repair.
"$PY" - <<'PY'
from app import create_app
from app.services.license import allowed_protocols_for_license, paid_license_active
from app.services.provisioning import get_setting, set_setting, apply_runtime_configs, sync_all_users, PROTOCOLS

app = create_app()
with app.app_context():
    allowed = [p for p in allowed_protocols_for_license() if p in PROTOCOLS]
    raw = [p.strip() for p in (get_setting('active_protocols', '') or '').split(',') if p.strip() in PROTOCOLS]
    merged = [p for p in PROTOCOLS if p in set(raw) | set(allowed)] if paid_license_active() else raw
    if paid_license_active() and merged:
        set_setting('active_protocols', ','.join(merged))
    apply_runtime_configs()
    sync_all_users(restart=False)
    print('paid=', paid_license_active(), 'allowed=', ','.join(allowed), 'active_saved=', ','.join(merged))
PY

# Repair/start only protocols currently allowed by the effective license. Healthy
# services are skipped; each broken protocol has a bounded repair timeout.
if [[ -x "$APP_DIR/scripts/smart_protocol_repair.sh" ]]; then
  APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$APP_DIR/scripts/smart_protocol_repair.sh" || true
fi

# Regenerate peers/certificates/auth files once more after repair scripts.
"$PY" - <<'PY'
from app import create_app
from app.services.provisioning import apply_runtime_configs, sync_all_users
app=create_app()
with app.app_context():
    apply_runtime_configs()
    sync_all_users(restart=False)
PY

# A downgrade keeps admin SSH reachable but stops protocol daemons not allowed by
# the effective tier so old paid credentials cannot remain usable accidentally.
$PY - <<'PY' > /tmp/ironpanel-effective-protocols.$$
from app import create_app
from app.services.provisioning import active_protocols
app=create_app()
with app.app_context(): print(' '.join(active_protocols()))
PY
EFFECTIVE="$(cat /tmp/ironpanel-effective-protocols.$$ 2>/dev/null || true)"
rm -f /tmp/ironpanel-effective-protocols.$$
has(){ [[ " $EFFECTIVE " == *" $1 "* ]]; }
has ocserv || systemctl stop ocserv >/dev/null 2>&1 || true
if ! has l2tp; then systemctl stop xl2tpd strongswan-starter >/dev/null 2>&1 || true; fi
has wireguard || systemctl stop wg-quick@wg0 >/dev/null 2>&1 || true
has pptp || systemctl stop pptpd >/dev/null 2>&1 || true
has hysteria2 || systemctl stop hysteria-server >/dev/null 2>&1 || true
has telegram_proxy || systemctl stop ironpanel-tgproxy >/dev/null 2>&1 || true

if [[ -x "$APP_DIR/scripts/smart_protocol_repair.sh" ]]; then
  APP_DIR="$APP_DIR" ETC_DIR="$ETC_DIR" bash "$APP_DIR/scripts/smart_protocol_repair.sh" --check-only || true
fi
echo "[$(date -Is)] license runtime reconcile finished"

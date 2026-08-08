#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
mkdir -p /etc/ppp/ip-up.d /etc/ppp/ip-down.d /run/ironpanel-ppp /var/lib/ironpanel/usage-events
cat > /etc/ppp/ip-up.d/ironpanel-usage <<'HOOK'
#!/usr/bin/env bash
set +e
export IFNAME="${IFNAME:-${1:-ppp}}"
export IPPARAM="${IPPARAM:-${6:-}}"
PY=/opt/ironpanel/.venv/bin/python; [[ -x "$PY" ]] || PY=python3
"$PY" /opt/ironpanel/scripts/ironpanel_usage_event_hook.py ppp-up "$IFNAME" >/dev/null 2>&1 || true
exit 0
HOOK
cat > /etc/ppp/ip-down.d/ironpanel-usage <<'HOOK'
#!/usr/bin/env bash
set +e
export IFNAME="${IFNAME:-${1:-ppp}}"
export IPPARAM="${IPPARAM:-${6:-}}"
PY=/opt/ironpanel/.venv/bin/python; [[ -x "$PY" ]] || PY=python3
"$PY" /opt/ironpanel/scripts/ironpanel_usage_event_hook.py ppp-down "$IFNAME" >/dev/null 2>&1 || true
exit 0
HOOK
chmod 755 /etc/ppp/ip-up.d/ironpanel-usage /etc/ppp/ip-down.d/ironpanel-usage
chmod 700 /run/ironpanel-ppp /var/lib/ironpanel/usage-events 2>/dev/null || true

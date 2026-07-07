#!/usr/bin/env bash
# Account final OpenVPN counters on disconnect. Never block disconnect.
set +e
ENV_FILE="/etc/ironpanel/ironpanel.env"
[[ -f "$ENV_FILE" ]] && set -a && . "$ENV_FILE" && set +a
PY="/opt/ironpanel/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
CN="${common_name:-${username:-}}"
RX="${bytes_received:-0}"
TX="${bytes_sent:-0}"
REMOTE_IP="${trusted_ip:-${untrusted_ip:-}}"
DEVICE_ID="${ifconfig_pool_remote_ip:-${trusted_port:-}}"
[[ -n "$CN" ]] && "$PY" /opt/ironpanel/scripts/ironpanel_usage_account.py openvpn "$CN" "$RX" "$TX" >/dev/null 2>&1
[[ -n "$CN" ]] && "$PY" /opt/ironpanel/scripts/ironpanel_session_account.py disconnect openvpn "$CN" "$REMOTE_IP" "$DEVICE_ID" >/dev/null 2>&1
exit 0

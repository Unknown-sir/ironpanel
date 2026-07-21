#!/usr/bin/env bash
# IronPanel OpenVPN certificate/quota gate.
# Non-zero exit denies the OpenVPN connection.
# Keep this shell wrapper minimal and do NOT source /etc/ironpanel/ironpanel.env;
# admin-entered UTF-8 text in env files can break shell parsing and cause false AUTH_FAILED.
set +e
CN="${common_name:-${username:-}}"
REMOTE_IP="${trusted_ip:-${untrusted_ip:-}}"
DEVICE_ID="${ifconfig_pool_remote_ip:-${trusted_port:-}}"
PY="/opt/ironpanel/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
exec "$PY" /opt/ironpanel/scripts/ironpanel_openvpn_auth.py "$CN" "$REMOTE_IP" "$DEVICE_ID"

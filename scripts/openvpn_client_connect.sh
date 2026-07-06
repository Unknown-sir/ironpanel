#!/usr/bin/env bash
# IronPanel OpenVPN quota/expiry gate.
# OpenVPN calls this before completing a client connection. Non-zero exit denies access.
set -euo pipefail
CN="${common_name:-${username:-}}"
[[ -n "$CN" ]] || exit 1
ENV_FILE="/etc/ironpanel/ironpanel.env"
[[ -f "$ENV_FILE" ]] && set -a && . "$ENV_FILE" && set +a
DB="${DATABASE_URL#sqlite:///}"
[[ "$DB" != "$DATABASE_URL" && -f "$DB" ]] || DB="/etc/ironpanel/ironpanel.db"
[[ -f "$DB" ]] || exit 1
SQL_CN=${CN//\'/\'\'}
ROW=$(sqlite3 -separator '|' "$DB" "SELECT username, enabled, COALESCE(data_limit_mb,0), COALESCE(used_upload_bytes, COALESCE(used_upload_mb,0)*1048576, 0)+COALESCE(used_download_bytes, COALESCE(used_download_mb,0)*1048576, 0), COALESCE(expires_at,'') FROM vpn_user WHERE username='$SQL_CN' OR replace(replace(replace(username,' ','_'),'/','_'),'@','_')='$SQL_CN' LIMIT 1;" 2>/dev/null || true)
[[ -n "$ROW" ]] || exit 1
IFS='|' read -r USERNAME ENABLED LIMIT_MB USED_BYTES EXPIRES <<< "$ROW"
[[ "${ENABLED:-0}" == "1" ]] || exit 1
if [[ -n "${EXPIRES:-}" ]]; then
  NOW=$(date -u '+%Y-%m-%d %H:%M:%S')
  [[ "$EXPIRES" > "$NOW" ]] || exit 1
fi
if [[ "${LIMIT_MB:-0}" -gt 0 ]]; then
  LIMIT_BYTES=$(( LIMIT_MB * 1024 * 1024 ))
  [[ "${USED_BYTES:-0}" -lt "$LIMIT_BYTES" ]] || exit 1
fi
REMOTE_IP="${trusted_ip:-${untrusted_ip:-}}"
DEVICE_ID="${ifconfig_pool_remote_ip:-${trusted_port:-}}"
PY="/opt/ironpanel/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
"$PY" /opt/ironpanel/scripts/ironpanel_session_account.py connect openvpn "$CN" "$REMOTE_IP" "$DEVICE_ID" >/dev/null 2>&1 || true
exit 0

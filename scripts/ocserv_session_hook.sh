#!/usr/bin/env bash
# IronPanel Ocserv/Cisco AnyConnect online-session hook.
# Ocserv builds expose slightly different env names. This hook accepts both
# env-based values and optional positional values and never blocks the VPN login.
set +e
ACTION="${1:-seen}"
shift || true
USER_NAME="${1:-${USERNAME:-${USER:-${OCSERV_USERNAME:-${OCSERV_USER:-${X_CSTP_USERNAME:-}}}}}}"
REMOTE_IP="${2:-${IP_REAL:-${REMOTE_ADDR:-${OCSERV_REMOTE_IP:-${IP_REMOTE:-${X_CSTP_REMOTE_ADDR:-}}}}}}"
DEVICE_ID="${3:-${DEVICE_ID:-${X_CSTP_DEVICE_ID:-${CSTP_DEVICE_ID:-}}}}"
REMOTE_IP="${REMOTE_IP%%:*}"
REMOTE_IP="${REMOTE_IP#[}"
REMOTE_IP="${REMOTE_IP%]}"
if [[ -z "$USER_NAME" ]]; then
  # Last-resort: ocserv sometimes supplies USERNAME through username in lowercase
  USER_NAME="${username:-${user:-}}"
fi
if [[ -n "$USER_NAME" && -x /opt/ironpanel/scripts/ironpanel_session_account.py ]]; then
  /opt/ironpanel/scripts/ironpanel_session_account.py "$ACTION" ocserv "$USER_NAME" "$REMOTE_IP" "$DEVICE_ID" >/dev/null 2>&1 || true
fi
exit 0

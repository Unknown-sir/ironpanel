#!/usr/bin/env bash
set -euo pipefail
ACTION="${1:-apply}"
ETC_DIR="${ETC_DIR:-/etc/ironpanel}"
DB="${DATABASE_URL:-sqlite:////etc/ironpanel/ironpanel.db}"
DB_PATH="${DB#sqlite:///}"
TABLE="166"
MARK="0x66"
IFACE="ironout"
TPROXY_PORT="12345"
PROTOCOLS=""
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ETC_DIR/ironpanel.env" || true
  set +a
  DB="${DATABASE_URL:-$DB}"; DB_PATH="${DB#sqlite:///}"
fi
if command -v sqlite3 >/dev/null 2>&1 && [[ -f "$DB_PATH" ]]; then
  TABLE="$(sqlite3 "$DB_PATH" "select value from app_setting where key='outbound_policy_table'" 2>/dev/null || echo 166)"; TABLE="${TABLE:-166}"
  MARK="$(sqlite3 "$DB_PATH" "select value from app_setting where key='outbound_policy_mark'" 2>/dev/null || echo 0x66)"; MARK="${MARK:-0x66}"
  IFACE="$(sqlite3 "$DB_PATH" "select value from app_setting where key='outbound_openvpn_interface'" 2>/dev/null || echo ironout)"; IFACE="${IFACE:-ironout}"
  TPROXY_PORT="$(sqlite3 "$DB_PATH" "select value from app_setting where key='outbound_tproxy_port'" 2>/dev/null || echo 12345)"; TPROXY_PORT="${TPROXY_PORT:-12345}"
  PROTOCOLS="$(sqlite3 "$DB_PATH" "select value from app_setting where key='outbound_protocols'" 2>/dev/null || true)"
fi
have_proto(){ [[ ",$PROTOCOLS," == *",$1,"* ]]; }
subnets_for(){
  case "$1" in
    openvpn) echo "10.8.0.0/24" ;;
    wireguard) echo "10.66.66.0/24" ;;
    ocserv) echo "10.12.0.0/16 192.168.100.0/24" ;;
    l2tp) echo "10.10.10.0/24 192.168.42.0/24" ;;
  esac
}
cleanup(){
  iptables -t mangle -D PREROUTING -j IRONPANEL_OUTBOUND 2>/dev/null || true
  iptables -t mangle -F IRONPANEL_OUTBOUND 2>/dev/null || true
  iptables -t mangle -X IRONPANEL_OUTBOUND 2>/dev/null || true
  iptables -t nat -D POSTROUTING -j IRONPANEL_OUTBOUND_NAT 2>/dev/null || true
  iptables -t nat -F IRONPANEL_OUTBOUND_NAT 2>/dev/null || true
  iptables -t nat -X IRONPANEL_OUTBOUND_NAT 2>/dev/null || true
  iptables -t mangle -D PREROUTING -j IRONPANEL_OUTBOUND_TPROXY 2>/dev/null || true
  iptables -t mangle -F IRONPANEL_OUTBOUND_TPROXY 2>/dev/null || true
  iptables -t mangle -X IRONPANEL_OUTBOUND_TPROXY 2>/dev/null || true
  ip rule del fwmark "$MARK" table "$TABLE" 2>/dev/null || true
  ip route flush table "$TABLE" 2>/dev/null || true
}
if [[ "$ACTION" == "disable" ]]; then
  cleanup
  echo "IronPanel outbound policy routing disabled"
  exit 0
fi
cleanup
iptables -t mangle -N IRONPANEL_OUTBOUND 2>/dev/null || true
iptables -t mangle -A PREROUTING -j IRONPANEL_OUTBOUND
iptables -t nat -N IRONPANEL_OUTBOUND_NAT 2>/dev/null || true
iptables -t nat -A POSTROUTING -j IRONPANEL_OUTBOUND_NAT
for proto in openvpn wireguard ocserv l2tp; do
  if have_proto "$proto"; then
    for subnet in $(subnets_for "$proto"); do
      if [[ "$ACTION" == "apply-tproxy" ]]; then
        # Best-effort transparent proxy mark for future Xray TProxy modes.
        iptables -t mangle -A IRONPANEL_OUTBOUND -s "$subnet" -p tcp -j TPROXY --on-port "$TPROXY_PORT" --tproxy-mark "$MARK"/"$MARK" 2>/dev/null || true
        iptables -t mangle -A IRONPANEL_OUTBOUND -s "$subnet" -p udp -j TPROXY --on-port "$TPROXY_PORT" --tproxy-mark "$MARK"/"$MARK" 2>/dev/null || true
      else
        iptables -t mangle -A IRONPANEL_OUTBOUND -s "$subnet" -j MARK --set-mark "$MARK" 2>/dev/null || true
        iptables -t nat -A IRONPANEL_OUTBOUND_NAT -s "$subnet" -o "$IFACE" -j MASQUERADE 2>/dev/null || true
      fi
    done
  fi
done
ip rule add fwmark "$MARK" table "$TABLE" priority "$TABLE" 2>/dev/null || true
if [[ "$ACTION" == "apply-tproxy" ]]; then
  ip route replace local 0.0.0.0/0 dev lo table "$TABLE" 2>/dev/null || true
  echo "V2Ray outbound applied: Xray inbound routed to upstream and classic VPN TProxy rules prepared on port $TPROXY_PORT."
else
  ip link show "$IFACE" >/dev/null 2>&1 && ip route replace default dev "$IFACE" table "$TABLE" 2>/dev/null || true
  echo "OpenVPN outbound policy routing applied on interface $IFACE for protocols: ${PROTOCOLS:-none}"
fi

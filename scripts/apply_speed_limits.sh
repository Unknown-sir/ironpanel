#!/usr/bin/env bash
set -u
CONFIG="${IRONPANEL_SPEED_CONFIG:-/etc/ironpanel/speed_limits.conf}"
SERVICE=/etc/systemd/system/ironpanel-speed-limits.service
log(){ echo "[speed-limit] $*"; }
default_iface(){ ip route show default 2>/dev/null | awk 'NR==1{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'; }
install_service(){
  cat > "$SERVICE" <<'UNIT'
[Unit]
Description=IronPanel per-protocol speed limits
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/ironpanel/scripts/apply_speed_limits.sh --apply
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable ironpanel-speed-limits.service >/dev/null 2>&1 || true
  log "systemd service installed"
}
apply_limits(){
  command -v tc >/dev/null 2>&1 || { log "tc command not found; installing iproute2"; apt-get update >/dev/null 2>&1 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y iproute2 >/dev/null 2>&1 || true; }
  IFACE="${IRONPANEL_SPEED_IFACE:-$(default_iface)}"
  if [[ -z "${IFACE:-}" ]]; then log "no default interface found"; exit 1; fi
  tc qdisc del dev "$IFACE" root >/dev/null 2>&1 || true
  if [[ ! -s "$CONFIG" ]] || ! grep -Eq '^[a-z0-9_]+[[:space:]]+(tcp|udp)[[:space:]]+[0-9]+[[:space:]]+[1-9][0-9]*' "$CONFIG"; then
    log "no enabled limits; cleared tc root on $IFACE"
    exit 0
  fi
  tc qdisc add dev "$IFACE" root handle 1: htb default 999
  tc class add dev "$IFACE" parent 1: classid 1:999 htb rate 10000mbit ceil 10000mbit >/dev/null 2>&1 || true
  CLASS=10
  while read -r PROTOCOL PROTO PORT MBPS REST; do
    [[ -z "${PROTOCOL:-}" || "${PROTOCOL:0:1}" == "#" ]] && continue
    [[ "$PROTO" != "tcp" && "$PROTO" != "udp" ]] && continue
    [[ "$PORT" =~ ^[0-9]+$ ]] || continue
    [[ "$MBPS" =~ ^[0-9]+$ ]] || continue
    [[ "$MBPS" -gt 0 ]] || continue
    HEX=$(printf '%x' "$CLASS")
    tc class add dev "$IFACE" parent 1:1 classid "1:$HEX" htb rate "${MBPS}mbit" ceil "${MBPS}mbit" burst 32k cburst 32k
    IPPROTO=6; [[ "$PROTO" == "udp" ]] && IPPROTO=17
    # Egress from the VPN server to clients uses source port of the protocol service.
    tc filter add dev "$IFACE" protocol ip parent 1: prio "$CLASS" u32 match ip protocol "$IPPROTO" 0xff match ip sport "$PORT" 0xffff flowid "1:$HEX" >/dev/null 2>&1 || true
    log "$PROTOCOL $PROTO/$PORT limited to ${MBPS} Mbps on $IFACE"
    CLASS=$((CLASS+1))
  done < "$CONFIG"
}
case "${1:---apply}" in
  --install-service) install_service; apply_limits ;;
  --apply) apply_limits ;;
  --clear) IFACE="${IRONPANEL_SPEED_IFACE:-$(default_iface)}"; [[ -n "${IFACE:-}" ]] && tc qdisc del dev "$IFACE" root >/dev/null 2>&1 || true; log "cleared" ;;
  *) echo "Usage: $0 [--apply|--clear|--install-service]"; exit 2 ;;
esac

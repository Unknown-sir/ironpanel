#!/usr/bin/env bash
set -u
CONFIG="${IRONPANEL_SPEED_CONFIG:-/etc/ironpanel/speed_limits.conf}"
SERVICE=/etc/systemd/system/ironpanel-speed-limits.service
CHAIN=IRONPANEL_SPEED_MARK
log(){ echo "[speed-limit] $*"; }
default_iface(){ ip route show default 2>/dev/null | awk 'NR==1{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'; }
install_service(){
  cat > "$SERVICE" <<'UNIT'
[Unit]
Description=IronPanel per-user and per-protocol speed limits
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
clear_runtime(){
  IFACE="${IRONPANEL_SPEED_IFACE:-$(default_iface)}"
  [[ -n "${IFACE:-}" ]] && tc qdisc del dev "$IFACE" root >/dev/null 2>&1 || true
  iptables -t mangle -D OUTPUT -j "$CHAIN" >/dev/null 2>&1 || true
  iptables -t mangle -D FORWARD -j "$CHAIN" >/dev/null 2>&1 || true
  iptables -t mangle -F "$CHAIN" >/dev/null 2>&1 || true
  iptables -t mangle -X "$CHAIN" >/dev/null 2>&1 || true
}
apply_limits(){
  command -v tc >/dev/null 2>&1 || { log "tc command not found; installing iproute2"; apt-get update >/dev/null 2>&1 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y iproute2 iptables >/dev/null 2>&1 || true; }
  IFACE="${IRONPANEL_SPEED_IFACE:-$(default_iface)}"
  if [[ -z "${IFACE:-}" ]]; then log "no default interface found"; exit 1; fi
  clear_runtime
  if [[ ! -s "$CONFIG" ]] || ! grep -Eq '^[^#][^[:space:]]+[[:space:]]+[0-9]+[[:space:]]+[a-z0-9_]+[[:space:]]+(tcp|udp)[[:space:]]+[0-9]+[[:space:]]+[1-9][0-9]*' "$CONFIG"; then
    log "no enabled per-user limits; cleared runtime on $IFACE"
    exit 0
  fi
  iptables -t mangle -N "$CHAIN" >/dev/null 2>&1 || true
  iptables -t mangle -C OUTPUT -j "$CHAIN" >/dev/null 2>&1 || iptables -t mangle -A OUTPUT -j "$CHAIN" >/dev/null 2>&1 || true
  # v19.10.29: node-gateway/DNAT relayed client traffic traverses FORWARD, not
  # OUTPUT; hook the same chain there so relayed users are shaped too.
  iptables -t mangle -C FORWARD -j "$CHAIN" >/dev/null 2>&1 || iptables -t mangle -A FORWARD -j "$CHAIN" >/dev/null 2>&1 || true
  tc qdisc add dev "$IFACE" root handle 1: htb default 999
  # Root HTB class is required before attaching per-user child classes. Older
  # releases used parent 1:1 without creating it, so tc silently rejected the
  # user classes while the service still looked healthy.
  tc class add dev "$IFACE" parent 1: classid 1:1 htb rate 10000mbit ceil 10000mbit >/dev/null 2>&1 || true
  tc class add dev "$IFACE" parent 1:1 classid 1:999 htb rate 10000mbit ceil 10000mbit >/dev/null 2>&1 || true
  CLASS=10; APPLIED=0; RULES=0
  declare -A GROUP_MARK GROUP_HEX GROUP_RATE
  while read -r USERNAME USER_ID PROTOCOL PROTO PORT MBPS MATCH_TYPE MATCH_VALUE GROUP_KEY REST; do
    [[ -z "${USERNAME:-}" || "${USERNAME:0:1}" == "#" ]] && continue
    [[ "$PROTO" != "tcp" && "$PROTO" != "udp" ]] && continue
    [[ "$PORT" =~ ^[0-9]+$ ]] || continue
    [[ "$MBPS" =~ ^[0-9]+$ ]] || continue
    [[ "$MBPS" -gt 0 ]] || continue
    [[ "$MATCH_TYPE" == "pending" || -z "${MATCH_VALUE:-}" || "$MATCH_VALUE" == "-" ]] && { log "pending: $USERNAME/$PROTOCOL ${MBPS}Mbps waiting for active session/ip"; continue; }
    [[ -n "${GROUP_KEY:-}" ]] || GROUP_KEY="user-${USER_ID}-${PROTOCOL}"
    if [[ -z "${GROUP_MARK[$GROUP_KEY]+x}" ]]; then
      HEX=$(printf '%x' "$CLASS"); MARK=$CLASS
      GROUP_MARK[$GROUP_KEY]=$MARK; GROUP_HEX[$GROUP_KEY]=$HEX; GROUP_RATE[$GROUP_KEY]=$MBPS
      tc class add dev "$IFACE" parent 1:1 classid "1:$HEX" htb rate "${MBPS}mbit" ceil "${MBPS}mbit" burst 32k cburst 32k >/dev/null 2>&1 || true
      tc filter add dev "$IFACE" protocol ip parent 1: prio "$CLASS" handle "$MARK" fw flowid "1:$HEX" >/dev/null 2>&1 || true
      CLASS=$((CLASS+1)); APPLIED=$((APPLIED+1))
    else
      MARK=${GROUP_MARK[$GROUP_KEY]}; HEX=${GROUP_HEX[$GROUP_KEY]}
    fi
    if [[ "$MATCH_TYPE" == "remote_ip" ]]; then
      iptables -t mangle -A "$CHAIN" -p "$PROTO" --sport "$PORT" -d "$MATCH_VALUE" -j MARK --set-mark "$MARK" >/dev/null 2>&1 || true
    elif [[ "$MATCH_TYPE" == "port_only" ]]; then
      # v19.10.29: shared-port protocols with a single limited user — shape the
      # whole service port for that user (precise because only one user carries
      # a limit on this port).
      iptables -t mangle -A "$CHAIN" -p "$PROTO" --sport "$PORT" -j MARK --set-mark "$MARK" >/dev/null 2>&1 || true
    elif [[ "$MATCH_TYPE" == "remote_endpoint" ]]; then
      EP_IP=${MATCH_VALUE%:*}; EP_PORT=${MATCH_VALUE##*:}
      if [[ -n "$EP_IP" && "$EP_PORT" =~ ^[0-9]+$ ]]; then
        iptables -t mangle -A "$CHAIN" -p "$PROTO" --sport "$PORT" -d "$EP_IP" --dport "$EP_PORT" -j MARK --set-mark "$MARK" >/dev/null 2>&1 || true
      fi
    elif [[ "$MATCH_TYPE" == "dst_ip" ]]; then
      iptables -t mangle -A "$CHAIN" -d "$MATCH_VALUE" -j MARK --set-mark "$MARK" >/dev/null 2>&1 || true
    elif [[ "$MATCH_TYPE" == "uid" ]]; then
      iptables -t mangle -A "$CHAIN" -m owner --uid-owner "$MATCH_VALUE" -j MARK --set-mark "$MARK" >/dev/null 2>&1 || true
    fi
    RULES=$((RULES+1))
    log "$USERNAME/$PROTOCOL limited to ${MBPS} Mbps (group=$GROUP_KEY, $MATCH_TYPE=$MATCH_VALUE)"
  done < "$CONFIG"
  log "applied $APPLIED speed classes with $RULES match rules"
}
case "${1:---apply}" in
  --install-service) install_service; apply_limits ;;
  --apply) apply_limits ;;
  --clear) clear_runtime; log "cleared" ;;
  *) echo "Usage: $0 [--apply|--clear|--install-service]"; exit 2 ;;
esac

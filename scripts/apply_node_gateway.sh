#!/usr/bin/env bash
set -euo pipefail
PLAN="${IRONPANEL_NODE_GATEWAY_PLAN:-/etc/ironpanel/node-gateway-plan.json}"
LOG=/var/log/ironpanel-node-gateway.log
CHAIN=IRONPANEL_NODE_GW
FWDCHAIN=IRONPANEL_NODE_GW_FWD
SERVICE=/etc/systemd/system/ironpanel-node-gateway.service
log(){ mkdir -p "$(dirname "$LOG")"; echo "[node-gateway] $*" | tee -a "$LOG"; }
ipt(){ iptables "$@" >/dev/null 2>&1 || true; }
clean_rules(){
  iptables -t nat -D PREROUTING -j "$CHAIN" >/dev/null 2>&1 || true
  iptables -D FORWARD -j "$FWDCHAIN" >/dev/null 2>&1 || true
  iptables -t nat -F "$CHAIN" >/dev/null 2>&1 || true
  iptables -t nat -X "$CHAIN" >/dev/null 2>&1 || true
  iptables -F "$FWDCHAIN" >/dev/null 2>&1 || true
  iptables -X "$FWDCHAIN" >/dev/null 2>&1 || true
  iptables -t nat -S POSTROUTING 2>/dev/null | grep 'IRONPANEL_NODE_GW_MASQ' | sed 's/^-A /-D /' | while read -r rule; do iptables -t nat $rule >/dev/null 2>&1 || true; done
}
resolve_host(){ getent ahostsv4 "$1" 2>/dev/null | awk 'NR==1{print $1}' || true; }
prepare_kernel(){
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
  cat >/etc/sysctl.d/99-ironpanel-node-gateway.conf <<'SYSCTL' 2>/dev/null || true
net.ipv4.ip_forward=1
net.ipv4.conf.all.rp_filter=0
net.ipv4.conf.default.rp_filter=0
SYSCTL
  sysctl -w net.ipv4.conf.all.rp_filter=0 >/dev/null 2>&1 || true
  sysctl -w net.ipv4.conf.default.rp_filter=0 >/dev/null 2>&1 || true
}
install_service(){
  cat > "$SERVICE" <<SERVICE_EOF
[Unit]
Description=IronPanel Node Gateway forwarding rules
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash /opt/ironpanel/scripts/apply_node_gateway.sh --apply
ExecStop=/bin/bash /opt/ironpanel/scripts/apply_node_gateway.sh --clear
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE_EOF
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable ironpanel-node-gateway.service >/dev/null 2>&1 || true
  log "systemd service installed"
}
apply_rules(){
  : > "$LOG"
  if [[ ! -s "$PLAN" ]]; then log "plan not found: $PLAN"; exit 1; fi
  command -v python3 >/dev/null 2>&1 || { log "python3 missing"; exit 1; }
  prepare_kernel
  clean_rules
  iptables -t nat -N "$CHAIN" >/dev/null 2>&1 || true
  iptables -N "$FWDCHAIN" >/dev/null 2>&1 || true
  iptables -t nat -C PREROUTING -j "$CHAIN" >/dev/null 2>&1 || iptables -t nat -I PREROUTING 1 -j "$CHAIN" >/dev/null 2>&1 || true
  iptables -C FORWARD -j "$FWDCHAIN" >/dev/null 2>&1 || iptables -I FORWARD 1 -j "$FWDCHAIN" >/dev/null 2>&1 || true
  iptables -A "$FWDCHAIN" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || true
  python3 -c 'import json,sys,re
plan=json.load(open(sys.argv[1])).get("plan",[])
for r in plan:
    if not (r.get("enabled") and r.get("selected_node_host")): continue
    host=str(r.get("selected_node_host","")).replace("https://","").replace("http://","").split("/")[0].split(":")[0]
    protocol=str(r.get("protocol") or "proto")
    name=re.sub(r"[^A-Za-z0-9_.-]","_",protocol)
    entries=r.get("ports") or []
    if not entries and r.get("port"):
        entries=[{"proto":str(r.get("transport") or "tcp").split("+")[0],"port":int(r.get("port") or 0)}]
    for e in entries:
        proto=str(e.get("proto") or "tcp").lower(); port=int(e.get("port") or 0)
        if host and proto in ("tcp","udp","gre") and (port or proto=="gre"):
            print(f"{name} {proto} {port} {host}")' "$PLAN" > /tmp/ironpanel-nodegw.rules
  while read -r NAME PROTO PORT HOST; do
    [[ -z "${NAME:-}" ]] && continue
    IP=$(resolve_host "$HOST")
    [[ -z "$IP" ]] && { log "cannot resolve $HOST for $NAME"; continue; }
    if [[ "$PROTO" == "gre" ]]; then
      iptables -t nat -A "$CHAIN" -p gre -j DNAT --to-destination "$IP" -m comment --comment "IRONPANEL_NODE_GW_${NAME}_gre" >/dev/null 2>&1 || true
      iptables -A "$FWDCHAIN" -p gre -d "$IP" -j ACCEPT -m comment --comment "IRONPANEL_NODE_GW_FWD_${NAME}_gre" >/dev/null 2>&1 || true
      iptables -t nat -A POSTROUTING -p gre -d "$IP" -j MASQUERADE -m comment --comment "IRONPANEL_NODE_GW_MASQ_${NAME}_gre" >/dev/null 2>&1 || true
      log "$NAME GRE -> $IP"
      continue
    fi
    iptables -t nat -A "$CHAIN" -p "$PROTO" --dport "$PORT" -j DNAT --to-destination "$IP:$PORT" -m comment --comment "IRONPANEL_NODE_GW_${NAME}_${PROTO}_${PORT}" >/dev/null 2>&1 || true
    iptables -A "$FWDCHAIN" -p "$PROTO" -d "$IP" --dport "$PORT" -j ACCEPT -m comment --comment "IRONPANEL_NODE_GW_FWD_${NAME}_${PROTO}_${PORT}" >/dev/null 2>&1 || true
    iptables -t nat -A POSTROUTING -p "$PROTO" -d "$IP" --dport "$PORT" -j MASQUERADE -m comment --comment "IRONPANEL_NODE_GW_MASQ_${NAME}_${PROTO}_${PORT}" >/dev/null 2>&1 || true
    log "$NAME $PROTO/$PORT -> $IP:$PORT"
  done < /tmp/ironpanel-nodegw.rules
  log "gateway rules applied; users can keep main-panel configs while selected protocol ports are DNATed to node(s)"
}
case "${1:---apply}" in
  --apply) apply_rules ;;
  --clear) clean_rules; log "cleared; all protocols returned to local/main server" ;;
  --install-service) install_service ;;
  *) echo "Usage: $0 [--apply|--clear|--install-service]"; exit 2 ;;
esac

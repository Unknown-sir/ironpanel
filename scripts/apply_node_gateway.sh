#!/usr/bin/env bash
set -euo pipefail
PLAN="${IRONPANEL_NODE_GATEWAY_PLAN:-/etc/ironpanel/node-gateway-plan.json}"
LOG=/var/log/ironpanel-node-gateway.log
CHAIN=IRONPANEL_NODE_GW
log(){ echo "[node-gateway] $*" | tee -a "$LOG"; }
clean_rules(){
  iptables -t nat -D PREROUTING -j "$CHAIN" >/dev/null 2>&1 || true
  iptables -t nat -F "$CHAIN" >/dev/null 2>&1 || true
  iptables -t nat -X "$CHAIN" >/dev/null 2>&1 || true
  iptables -t nat -S POSTROUTING 2>/dev/null | grep 'IRONPANEL_NODE_GW_MASQ' | sed 's/^-A /-D /' | while read -r rule; do iptables -t nat $rule >/dev/null 2>&1 || true; done
}
resolve_host(){ getent ahostsv4 "$1" 2>/dev/null | awk 'NR==1{print $1}' || true; }
apply_rules(){
  : > "$LOG"
  if [[ ! -s "$PLAN" ]]; then log "plan not found: $PLAN"; exit 1; fi
  command -v python3 >/dev/null 2>&1 || { log "python3 missing"; exit 1; }
  clean_rules
  iptables -t nat -N "$CHAIN" >/dev/null 2>&1 || true
  iptables -t nat -C PREROUTING -j "$CHAIN" >/dev/null 2>&1 || iptables -t nat -A PREROUTING -j "$CHAIN" >/dev/null 2>&1 || true
  python3 -c 'import json,sys,re
plan=json.load(open(sys.argv[1])).get("plan",[])
for r in plan:
    if not (r.get("enabled") and r.get("selected_node_host") and r.get("port")): continue
    host=str(r.get("selected_node_host","")).replace("https://","").replace("http://","").split("/")[0].split(":")[0]
    proto=str(r.get("transport") or "tcp")
    port=int(r.get("port") or 0)
    name=re.sub(r"[^A-Za-z0-9_.-]","_",str(r.get("protocol") or "proto"))
    if host and port and proto in ("tcp","udp"):
        print(f"{name} {proto} {port} {host}")' "$PLAN" > /tmp/ironpanel-nodegw.rules
  while read -r NAME PROTO PORT HOST; do
    [[ -z "${NAME:-}" ]] && continue
    IP=$(resolve_host "$HOST")
    [[ -z "$IP" ]] && { log "cannot resolve $HOST for $NAME"; continue; }
    iptables -t nat -A "$CHAIN" -p "$PROTO" --dport "$PORT" -j DNAT --to-destination "$IP:$PORT" -m comment --comment "IRONPANEL_NODE_GW_${NAME}" >/dev/null 2>&1 || true
    iptables -t nat -A POSTROUTING -p "$PROTO" -d "$IP" --dport "$PORT" -j MASQUERADE -m comment --comment "IRONPANEL_NODE_GW_MASQ_${NAME}" >/dev/null 2>&1 || true
    log "$NAME $PROTO/$PORT -> $IP:$PORT"
  done < /tmp/ironpanel-nodegw.rules
  log "gateway rules applied"
}
case "${1:---apply}" in
  --apply) apply_rules ;;
  --clear) clean_rules; log "cleared" ;;
  *) echo "Usage: $0 [--apply|--clear]"; exit 2 ;;
esac

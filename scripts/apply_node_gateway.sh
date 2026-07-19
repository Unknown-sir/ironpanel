#!/usr/bin/env bash
set -Eeuo pipefail
PLAN="${IRONPANEL_NODE_GATEWAY_PLAN:-/etc/ironpanel/node-gateway-plan.json}"
LOG=/var/log/ironpanel-node-gateway.log
CHAIN=IRONPANEL_NODE_GW
FWDCHAIN=IRONPANEL_NODE_GW_FWD
SERVICE=/etc/systemd/system/ironpanel-node-gateway.service
PANEL_PORT="${IRONPANEL_PANEL_PORT:-}"
log(){ mkdir -p "$(dirname "$LOG")"; echo "[node-gateway] $*" | tee -a "$LOG"; }
run_ipt(){ iptables "$@" >/dev/null 2>&1; }

clean_rules(){
  run_ipt -t nat -D PREROUTING -j "$CHAIN" || true
  run_ipt -D FORWARD -j "$FWDCHAIN" || true
  run_ipt -t nat -F "$CHAIN" || true
  run_ipt -t nat -X "$CHAIN" || true
  run_ipt -F "$FWDCHAIN" || true
  run_ipt -X "$FWDCHAIN" || true
  # With pipefail enabled, a no-match grep used to abort the whole script before
  # any new forwarding rule was applied. Capture matches first and loop safely.
  local masq_rules=""
  masq_rules="$(iptables -t nat -S POSTROUTING 2>/dev/null | grep 'IRONPANEL_NODE_GW_MASQ' || true)"
  if [[ -n "$masq_rules" ]]; then
    while IFS= read -r rule; do
      [[ -z "$rule" ]] && continue
      rule="${rule/#-A /-D }"
      iptables -t nat $rule >/dev/null 2>&1 || true
    done <<< "$masq_rules"
  fi
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

render_rules(){
  python3 - "$PLAN" <<'PYRULES'
import json,sys,re
try:
    doc=json.load(open(sys.argv[1], encoding='utf-8'))
except Exception as e:
    print('ERROR plan-json '+str(e)); sys.exit(0)
plan=doc.get('plan') or []
panel_ports=set()
for x in (doc.get('panel_ports') or []):
    try: panel_ports.add(int(x))
    except Exception: pass
for r in plan:
    if not (r.get('enabled') and r.get('selected_node_host')):
        continue
    host=str(r.get('selected_node_host','')).replace('https://','').replace('http://','').split('/')[0].split(':')[0]
    protocol=str(r.get('protocol') or 'proto')
    name=re.sub(r'[^A-Za-z0-9_.-]','_',protocol)
    entries=r.get('ports') or []
    if not entries and r.get('port'):
        entries=[{'proto':str(r.get('transport') or 'tcp').split('+')[0], 'port':int(r.get('port') or 0)}]
    seen=set()
    for e in entries:
        proto=str(e.get('proto') or 'tcp').lower().strip()
        try: port=int(e.get('port') or 0)
        except Exception: port=0
        if proto not in ('tcp','udp','gre'):
            continue
        if proto != 'gre' and not (1 <= port <= 65535):
            continue
        if name == 'xray' and proto == 'tcp' and port in (10085,10086):
            print(f'SKIPINTERNAL {name} {proto} {port} {host}')
            continue
        key=(name,proto,port,host)
        if key in seen:
            continue
        seen.add(key)
        if proto == 'tcp' and port in panel_ports:
            print(f'SKIPPANEL {name} {proto} {port} {host}')
        elif host:
            print(f'RULE {name} {proto} {port} {host}')
PYRULES
}

apply_rules(){
  : > "$LOG"
  if [[ ! -s "$PLAN" ]]; then log "plan not found or empty: $PLAN"; exit 1; fi
  command -v python3 >/dev/null 2>&1 || { log "python3 missing"; exit 1; }
  command -v iptables >/dev/null 2>&1 || { log "iptables missing"; exit 1; }
  prepare_kernel
  clean_rules
  run_ipt -t nat -N "$CHAIN" || true
  run_ipt -N "$FWDCHAIN" || true
  iptables -t nat -C PREROUTING -j "$CHAIN" >/dev/null 2>&1 || iptables -t nat -I PREROUTING 1 -j "$CHAIN" >/dev/null 2>&1 || { log "failed to attach NAT PREROUTING chain"; exit 1; }
  iptables -C FORWARD -j "$FWDCHAIN" >/dev/null 2>&1 || iptables -I FORWARD 1 -j "$FWDCHAIN" >/dev/null 2>&1 || { log "failed to attach FORWARD chain"; exit 1; }
  iptables -A "$FWDCHAIN" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || true
  local rendered=/tmp/ironpanel-nodegw.rules
  render_rules > "$rendered"
  if grep -q '^ERROR ' "$rendered"; then cat "$rendered" >> "$LOG"; exit 1; fi
  if ! grep -q '^RULE ' "$rendered"; then
    log "no active fixed/fixed_only node forwarding rows in plan; chains were cleaned"
    cat "$PLAN" >> "$LOG" 2>/dev/null || true
    exit 0
  fi
  local applied=0 skipped=0 failed=0
  while read -r KIND NAME PROTO PORT HOST; do
    [[ -z "${KIND:-}" ]] && continue
    if [[ "$KIND" == "SKIPPANEL" ]]; then log "SKIP $NAME $PROTO/$PORT because it is panel port"; skipped=$((skipped+1)); continue; fi
    if [[ "$KIND" == "SKIPINTERNAL" ]]; then log "SKIP $NAME $PROTO/$PORT because it is an internal/API port"; skipped=$((skipped+1)); continue; fi
    [[ "$KIND" == "RULE" ]] || continue
    IP=$(resolve_host "$HOST")
    if [[ -z "$IP" ]]; then log "cannot resolve $HOST for $NAME"; failed=$((failed+1)); continue; fi
    if [[ "$PROTO" == "gre" ]]; then
      iptables -t nat -A "$CHAIN" -m addrtype --dst-type LOCAL -p gre -j DNAT --to-destination "$IP" -m comment --comment "IRONPANEL_NODE_GW_${NAME}_gre" >/dev/null 2>&1 || { log "failed NAT $NAME GRE -> $IP"; failed=$((failed+1)); continue; }
      iptables -A "$FWDCHAIN" -p gre -d "$IP" -j ACCEPT -m comment --comment "IRONPANEL_NODE_GW_FWD_${NAME}_gre" >/dev/null 2>&1 || true
      iptables -t nat -A POSTROUTING -p gre -d "$IP" -j MASQUERADE -m comment --comment "IRONPANEL_NODE_GW_MASQ_${NAME}_gre" >/dev/null 2>&1 || true
      log "$NAME GRE -> $IP"; applied=$((applied+1)); continue
    fi
    if [[ -n "${PANEL_PORT:-}" && "$PROTO" == "tcp" && "$PORT" == "$PANEL_PORT" ]]; then log "SKIP $NAME $PROTO/$PORT because it is panel port"; skipped=$((skipped+1)); continue; fi
    iptables -t nat -A "$CHAIN" -m addrtype --dst-type LOCAL -p "$PROTO" --dport "$PORT" -j DNAT --to-destination "$IP:$PORT" -m comment --comment "IRONPANEL_NODE_GW_${NAME}_${PROTO}_${PORT}" >/dev/null 2>&1 || { log "failed NAT $NAME $PROTO/$PORT -> $IP:$PORT"; failed=$((failed+1)); continue; }
    iptables -A "$FWDCHAIN" -p "$PROTO" -d "$IP" --dport "$PORT" -j ACCEPT -m comment --comment "IRONPANEL_NODE_GW_FWD_${NAME}_${PROTO}_${PORT}" >/dev/null 2>&1 || true
    iptables -t nat -A POSTROUTING -p "$PROTO" -d "$IP" --dport "$PORT" -j MASQUERADE -m comment --comment "IRONPANEL_NODE_GW_MASQ_${NAME}_${PROTO}_${PORT}" >/dev/null 2>&1 || true
    log "$NAME $PROTO/$PORT -> $IP:$PORT"; applied=$((applied+1))
  done < "$rendered"
  iptables -t nat -S "$CHAIN" 2>/dev/null | sed 's/^/[nat] /' >> "$LOG" || true
  iptables -S "$FWDCHAIN" 2>/dev/null | sed 's/^/[filter] /' >> "$LOG" || true
  iptables -t nat -L "$CHAIN" -n -v 2>/dev/null | sed 's/^/[nat-counters] /' >> "$LOG" || true
  iptables -L "$FWDCHAIN" -n -v 2>/dev/null | sed 's/^/[filter-counters] /' >> "$LOG" || true
  log "gateway rules applied: applied=$applied skipped=$skipped failed=$failed"
  if [[ "$failed" -gt 0 || "$applied" -eq 0 ]]; then exit 1; fi
}
case "${1:---apply}" in
  --apply) apply_rules ;;
  --clear) : > "$LOG"; clean_rules; log "cleared; all protocols returned to local/main server" ;;
  --install-service) install_service ;;
  *) echo "Usage: $0 [--apply|--clear|--install-service]"; exit 2 ;;
esac

#!/usr/bin/env bash
set -Eeuo pipefail
PLAN="${IRONPANEL_NODE_GATEWAY_PLAN:-/etc/ironpanel/node-gateway-plan.json}"
LOG=/var/log/ironpanel-node-gateway.log
CHAIN=IRONPANEL_NODE_GW
FWDCHAIN=IRONPANEL_NODE_GW_FWD
RELAY_SERVICE=/etc/systemd/system/ironpanel-node-gateway-relay.service
GATEWAY_SERVICE=/etc/systemd/system/ironpanel-node-gateway.service
RELAY_CONFIG=/etc/ironpanel/node-gateway-relay.json
RELAY_SCRIPT=/opt/ironpanel/scripts/node_gateway_relay.py
PANEL_PORT="${IRONPANEL_PANEL_PORT:-}"
log(){ mkdir -p "$(dirname "$LOG")"; echo "[node-gateway] $*" | tee -a "$LOG"; }
run_ipt(){ iptables "$@" >/dev/null 2>&1; }

clean_rules(){
  run_ipt -t nat -D PREROUTING -j "$CHAIN" || true
  run_ipt -t nat -D OUTPUT -m addrtype --dst-type LOCAL -j "$CHAIN" || true
  run_ipt -D FORWARD -j "$FWDCHAIN" || true
  run_ipt -t nat -F "$CHAIN" || true
  run_ipt -t nat -X "$CHAIN" || true
  run_ipt -F "$FWDCHAIN" || true
  run_ipt -X "$FWDCHAIN" || true
  local post_rules=""
  post_rules="$(iptables -t nat -S POSTROUTING 2>/dev/null | grep 'IRONPANEL_NODE_GW_\(MASQ\|SNAT\)' || true)"
  if [[ -n "$post_rules" ]]; then
    while IFS= read -r rule; do
      [[ -z "$rule" ]] && continue
      rule="${rule/#-A /-D }"
      iptables -t nat $rule >/dev/null 2>&1 || true
    done <<< "$post_rules"
  fi
}

resolve_host(){ getent ahostsv4 "$1" 2>/dev/null | awk 'NR==1{print $1}' || true; }
route_info(){
  local ip="$1"
  ip route get "$ip" 2>/dev/null | awk '{for(i=1;i<=NF;i++){if($i=="dev") dev=$(i+1); if($i=="src") src=$(i+1)} } END{print dev" "src}'
}
prepare_kernel(){
  modprobe nf_nat >/dev/null 2>&1 || true
  modprobe nf_conntrack >/dev/null 2>&1 || true
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
  cat >/etc/sysctl.d/99-ironpanel-node-gateway.conf <<'SYSCTL' 2>/dev/null || true
net.ipv4.ip_forward=1
net.ipv4.conf.all.rp_filter=0
net.ipv4.conf.default.rp_filter=0
SYSCTL
  sysctl -w net.ipv4.conf.all.rp_filter=0 >/dev/null 2>&1 || true
  sysctl -w net.ipv4.conf.default.rp_filter=0 >/dev/null 2>&1 || true
  for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > "$f" 2>/dev/null || true; done
}
install_service(){
  cat > "$GATEWAY_SERVICE" <<SERVICE_EOF
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
install_relay_service(){
  cat > "$RELAY_SERVICE" <<SERVICE_EOF
[Unit]
Description=IronPanel Node Gateway userspace relay
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/ironpanel/scripts/node_gateway_relay.py --config $RELAY_CONFIG
Restart=always
RestartSec=2
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SERVICE_EOF
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable ironpanel-node-gateway-relay.service >/dev/null 2>&1 || true
}

tcp_probe(){
  local ip="$1" port="$2"
  timeout 3 bash -lc "</dev/tcp/$ip/$port" >/dev/null 2>&1
}

relay_port(){
  local proto="$1" port="$2"
  # Keep relay ports deterministic and outside normal VPN ranges.
  # TCP and UDP can share a numeric relay port because protocol sockets differ.
  echo $(( 31000 + (port % 30000) ))
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
seen_public={}
for r in plan:
    if not (r.get('enabled') and r.get('selected_node_host')):
        continue
    mode=str(r.get('mode') or '').lower()
    if mode not in ('fixed','fixed_only','auto'):
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
        pubkey=(proto,port)
        old=seen_public.get(pubkey)
        if old and old != host:
            print(f'CONFLICT {name} {proto} {port} {host} {old}')
            continue
        seen_public[pubkey]=host
        if proto == 'tcp' and port in panel_ports:
            print(f'SKIPPANEL {name} {proto} {port} {host}')
        elif host:
            print(f'RULE {name} {proto} {port} {host}')
PYRULES
}

add_relay_config_item(){
  local name="$1" proto="$2" public_port="$3" target_ip="$4" target_port="$5" local_port="$6"
  python3 - "$RELAY_CONFIG" "$name" "$proto" "$public_port" "$target_ip" "$target_port" "$local_port" <<'PYCFG'
import json,sys,os
path,name,proto,public_port,target_ip,target_port,local_port=sys.argv[1:]
try:
    data=json.load(open(path, encoding='utf-8'))
except Exception:
    data={'version':1,'mappings':[]}
item={'name':name,'proto':proto,'public_port':int(public_port),'listen_host':'0.0.0.0','listen_port':int(local_port),'target_host':target_ip,'target_port':int(target_port)}
# replace same proto/listen_port/public_port
out=[]
for m in data.get('mappings') or []:
    if (m.get('proto'), int(m.get('public_port',0)), int(m.get('listen_port',0))) == (item['proto'], item['public_port'], item['listen_port']):
        continue
    out.append(m)
out.append(item)
data['mappings']=out
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path,'w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=2))
PYCFG
}

start_relay(){
  [[ -s "$RELAY_CONFIG" ]] || return 0
  install_relay_service
  systemctl restart ironpanel-node-gateway-relay.service >/dev/null 2>&1 || {
    log "WARN relay service failed to restart; check: journalctl -u ironpanel-node-gateway-relay -n 100 --no-pager"
    return 1
  }
  log "relay service restarted"
}

apply_relay_for_rule(){
  local name="$1" proto="$2" port="$3" host="$4"
  local ip dev src ri lport
  ip="$(resolve_host "$host")"
  if [[ -z "$ip" ]]; then log "cannot resolve $host for $name"; return 2; fi
  ri="$(route_info "$ip")"; dev="${ri%% *}"; src="${ri##* }"
  [[ "$dev" == "$src" ]] && src=""
  log "route to $ip for $name: dev=${dev:-unknown} src=${src:-auto}"
  if [[ "$proto" == "gre" ]]; then
    # GRE cannot be handled by the userspace relay. Keep deterministic DNAT/SNAT fallback for PPTP data channel.
    iptables -t nat -A "$CHAIN" ! -s "$ip" -p gre -j DNAT --to-destination "$ip" -m comment --comment "IRONPANEL_NODE_GW_${name}_gre" >/dev/null 2>&1 || { log "failed NAT $name GRE -> $ip"; return 2; }
    iptables -A "$FWDCHAIN" -p gre -d "$ip" -j ACCEPT -m comment --comment "IRONPANEL_NODE_GW_FWD_${name}_gre" >/dev/null 2>&1 || true
    iptables -A "$FWDCHAIN" -p gre -s "$ip" -j ACCEPT -m comment --comment "IRONPANEL_NODE_GW_REV_${name}_gre" >/dev/null 2>&1 || true
    if [[ -n "$src" ]]; then
      iptables -t nat -A POSTROUTING -p gre -d "$ip" -j SNAT --to-source "$src" -m comment --comment "IRONPANEL_NODE_GW_SNAT_${name}_gre" >/dev/null 2>&1 || true
    else
      iptables -t nat -A POSTROUTING -p gre -d "$ip" -j MASQUERADE -m comment --comment "IRONPANEL_NODE_GW_MASQ_${name}_gre" >/dev/null 2>&1 || true
    fi
    log "$name GRE -> $ip via kernel DNAT fallback"; return 0
  fi
  if [[ -n "${PANEL_PORT:-}" && "$proto" == "tcp" && "$port" == "$PANEL_PORT" ]]; then log "SKIP $name $proto/$port because it is panel port"; return 1; fi
  if [[ "$proto" == "tcp" ]]; then
    if tcp_probe "$ip" "$port"; then log "node port probe OK: $ip:$port/tcp"; else log "WARN node port probe failed: $ip:$port/tcp is not reachable from main server; relay will be created but client cannot connect until node firewall/service is fixed"; fi
  fi
  lport="$(relay_port "$proto" "$port")"
  add_relay_config_item "$name" "$proto" "$port" "$ip" "$port" "$lport"
  # Transparent relay mode: user still dials main-panel public port. The main server
  # REDIRECTs that local destination port to the relay listener. The relay opens a
  # separate connection to the node, so replies necessarily return to main first.
  if [[ "$proto" == "tcp" ]]; then
    iptables -t nat -A "$CHAIN" ! -s "$ip" -p tcp --dport "$port" -j REDIRECT --to-ports "$lport" -m comment --comment "IRONPANEL_NODE_GW_RELAY_${name}_tcp_${port}" >/dev/null 2>&1 || { log "failed REDIRECT $name tcp/$port -> relay:$lport"; return 2; }
    command -v conntrack >/dev/null 2>&1 && conntrack -D -p tcp --dport "$port" >/dev/null 2>&1 || true
  elif [[ "$proto" == "udp" ]]; then
    iptables -t nat -A "$CHAIN" ! -s "$ip" -p udp --dport "$port" -j REDIRECT --to-ports "$lport" -m comment --comment "IRONPANEL_NODE_GW_RELAY_${name}_udp_${port}" >/dev/null 2>&1 || { log "failed REDIRECT $name udp/$port -> relay:$lport"; return 2; }
    command -v conntrack >/dev/null 2>&1 && conntrack -D -p udp --dport "$port" >/dev/null 2>&1 || true
  fi
  log "$name $proto/$port -> relay:127.0.0.1:$lport -> $ip:$port"
  return 0
}

apply_rules(){
  : > "$LOG"
  rm -f "$RELAY_CONFIG"
  if [[ ! -s "$PLAN" ]]; then log "plan not found or empty: $PLAN"; exit 1; fi
  command -v python3 >/dev/null 2>&1 || { log "python3 missing"; exit 1; }
  command -v iptables >/dev/null 2>&1 || { log "iptables missing"; exit 1; }
  prepare_kernel
  clean_rules
  run_ipt -t nat -N "$CHAIN" || true
  run_ipt -N "$FWDCHAIN" || true
  iptables -t nat -C PREROUTING -j "$CHAIN" >/dev/null 2>&1 || iptables -t nat -I PREROUTING 1 -j "$CHAIN" >/dev/null 2>&1 || { log "failed to attach NAT PREROUTING chain"; exit 1; }
  # OUTPUT hook is only for local tests that dial the main-panel IP/port from the main server itself.
  iptables -t nat -C OUTPUT -m addrtype --dst-type LOCAL -j "$CHAIN" >/dev/null 2>&1 || iptables -t nat -I OUTPUT 1 -m addrtype --dst-type LOCAL -j "$CHAIN" >/dev/null 2>&1 || true
  iptables -C FORWARD -j "$FWDCHAIN" >/dev/null 2>&1 || iptables -I FORWARD 1 -j "$FWDCHAIN" >/dev/null 2>&1 || true
  iptables -A "$FWDCHAIN" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || true
  local rendered=/tmp/ironpanel-nodegw.rules
  render_rules > "$rendered"
  if grep -q '^ERROR ' "$rendered"; then cat "$rendered" >> "$LOG"; exit 1; fi
  if ! grep -q '^RULE ' "$rendered"; then
    systemctl stop ironpanel-node-gateway-relay.service >/dev/null 2>&1 || true
    log "no active fixed/fixed_only node forwarding rows in plan; chains were cleaned"
    cat "$PLAN" >> "$LOG" 2>/dev/null || true
    exit 0
  fi
  local applied=0 skipped=0 failed=0 rc=0
  while read -r KIND NAME PROTO PORT HOST EXTRA; do
    [[ -z "${KIND:-}" ]] && continue
    if [[ "$KIND" == "SKIPPANEL" ]]; then log "SKIP $NAME $PROTO/$PORT because it is panel port"; skipped=$((skipped+1)); continue; fi
    if [[ "$KIND" == "SKIPINTERNAL" ]]; then log "SKIP $NAME $PROTO/$PORT because it is an internal/API port"; skipped=$((skipped+1)); continue; fi
    if [[ "$KIND" == "CONFLICT" ]]; then log "SKIP $NAME $PROTO/$PORT because another node already owns this public port ($EXTRA)"; skipped=$((skipped+1)); continue; fi
    [[ "$KIND" == "RULE" ]] || continue
    set +e
    apply_relay_for_rule "$NAME" "$PROTO" "$PORT" "$HOST"; rc=$?
    set -e
    if [[ "$rc" -eq 0 ]]; then applied=$((applied+1)); elif [[ "$rc" -eq 1 ]]; then skipped=$((skipped+1)); else failed=$((failed+1)); fi
  done < "$rendered"
  if [[ "$applied" -gt 0 ]]; then start_relay || failed=$((failed+1)); fi
  iptables -t nat -S PREROUTING 2>/dev/null | grep "$CHAIN" | sed 's/^/[nat-hook] /' >> "$LOG" || true
  iptables -t nat -S OUTPUT 2>/dev/null | grep "$CHAIN" | sed 's/^/[nat-output-hook] /' >> "$LOG" || true
  iptables -S FORWARD 2>/dev/null | grep "$FWDCHAIN" | sed 's/^/[filter-hook] /' >> "$LOG" || true
  iptables -t nat -S "$CHAIN" 2>/dev/null | sed 's/^/[nat] /' >> "$LOG" || true
  iptables -S "$FWDCHAIN" 2>/dev/null | sed 's/^/[filter] /' >> "$LOG" || true
  iptables -t nat -S POSTROUTING 2>/dev/null | grep 'IRONPANEL_NODE_GW_\(MASQ\|SNAT\)' | sed 's/^/[postrouting] /' >> "$LOG" || true
  iptables -t nat -L "$CHAIN" -n -v 2>/dev/null | sed 's/^/[nat-counters] /' >> "$LOG" || true
  iptables -L "$FWDCHAIN" -n -v 2>/dev/null | sed 's/^/[filter-counters] /' >> "$LOG" || true
  systemctl status ironpanel-node-gateway-relay.service --no-pager 2>/dev/null | sed 's/^/[relay-service] /' >> "$LOG" || true
  log "gateway relay rules applied: applied=$applied skipped=$skipped failed=$failed"
  log "note: transparent relay mode is active. Client configs keep main-panel IP/domain. Path: client/Iran -> main public port -> local relay -> node -> relay -> main -> client/Iran. Verify with relay logs and public IP after connecting."
  if [[ "$failed" -gt 0 || "$applied" -eq 0 ]]; then exit 1; fi
}
case "${1:---apply}" in
  --apply) apply_rules ;;
  --clear) : > "$LOG"; clean_rules; rm -f "$RELAY_CONFIG"; systemctl stop ironpanel-node-gateway-relay.service >/dev/null 2>&1 || true; log "cleared; all protocols returned to local/main server" ;;
  --install-service) install_service; install_relay_service ;;
  *) echo "Usage: $0 [--apply|--clear|--install-service]"; exit 2 ;;
esac

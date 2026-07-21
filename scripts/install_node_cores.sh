#!/usr/bin/env bash
set -euo pipefail
PROTOCOLS="${1:-${IRONPANEL_NODE_PROTOCOLS:-openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh}}"
LOG=/var/log/ironpanel-node-core-install.log
mkdir -p /var/log /etc/ironpanel-node /opt/ironpanel-node/scripts
: > "$LOG"
log(){ echo "[IronPanel Node Cores] $*" | tee -a "$LOG"; }

# v19.8.15 dynamic protocol ports: open actual ports from configs copied from main panel.
configured_ports(){
  local proto="$1"
  python3 - "$proto" <<'INNERPY' 2>/dev/null || true
import json, os, re, sys, pathlib
proto=sys.argv[1]
ports=[]
def add(p, t):
    try:
        p=int(p)
        if 0 < p <= 65535:
            item=(t,p)
            if item not in ports: ports.append(item)
    except Exception: pass

def direct_port(proto):
    try:
        data=json.loads(os.environ.get('IRONPANEL_NODE_DIRECT_PORTS_JSON') or '{}')
        p=int(data.get(proto) or 0)
        return p if 0 < p <= 65535 else 0
    except Exception:
        return 0
def json_ports(path, t):
    try: data=json.loads(pathlib.Path(path).read_text())
    except Exception: return
    def walk(o):
        if isinstance(o, dict):
            if 'port' in o: add(o.get('port'), t)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
def text_ports(paths, patterns, t):
    for p in paths:
        try: txt=pathlib.Path(p).read_text(errors='ignore')
        except Exception: continue
        for pat in patterns:
            for m in re.finditer(pat, txt, re.I|re.M): add(m.group(1), t)
dp=direct_port(proto)
if dp:
    if proto in ('openvpn','wireguard','ocserv','hysteria2'):
        add(dp, 'udp')
    if proto in ('openvpn','ocserv','xray','telegram_proxy','pptp','ssh'):
        add(dp, 'tcp')
if proto=='openvpn':
    text_ports(['/etc/openvpn/server/server.conf','/etc/openvpn/server.conf'], [r'^port\s+([0-9]{2,5})'], 'udp')
    try:
        txt='\n'.join(pathlib.Path(x).read_text(errors='ignore') for x in ('/etc/openvpn/server/server.conf','/etc/openvpn/server.conf') if pathlib.Path(x).exists())
        transport='tcp' if re.search(r'^proto\s+tcp', txt, re.I|re.M) else 'udp'
        ports[:]=[(transport,p) for _t,p in ports]
    except Exception: pass
elif proto=='wireguard':
    text_ports(['/etc/wireguard/wg0.conf','/etc/wireguard/wg-ironpanel.conf'], [r'^ListenPort\s*=\s*([0-9]{2,5})'], 'udp')
elif proto=='ocserv':
    text_ports(['/etc/ocserv/ocserv.conf'], [r'^tcp-port\s*=\s*([0-9]{2,5})'], 'tcp')
    text_ports(['/etc/ocserv/ocserv.conf'], [r'^udp-port\s*=\s*([0-9]{2,5})'], 'udp')
elif proto=='l2tp':
    add(500,'udp'); add(4500,'udp')
    text_ports(['/etc/xl2tpd/xl2tpd.conf'], [r'^port\s*=\s*([0-9]{2,5})'], 'udp')
elif proto=='pptp':
    add(1723,'tcp')
elif proto=='ssh':
    text_ports(['/etc/ssh/sshd_config','/etc/ssh/sshd_config.d/ironpanel.conf'], [r'^Port\s+([0-9]{2,5})'], 'tcp')
elif proto=='xray':
    for p in ('/usr/local/etc/xray/config.json','/etc/xray/config.json','/etc/ironpanel/xray/config.json'): json_ports(p,'tcp')
elif proto=='hysteria2':
    text_ports(['/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'], [r'listen\s*:\s*(?:[0-9.\[\]:a-fA-F]*:)?([0-9]{2,5})', r':([0-9]{2,5})\s*(?:#.*)?$'], 'udp')
elif proto=='telegram_proxy':
    for p in ('/opt/ironpanel-telegram-proxy/ironpanel/config.json','/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json'): json_ports(p,'tcp')
    text_ports(['/etc/systemd/system/ironpanel-tgproxy.service','/etc/ironpanel/telegram_proxy.env','/etc/ironpanel/tgproxy.env'], [r'(?:--port|PORT|port)\D+([0-9]{2,5})'], 'tcp')
for t,p in ports:
    print(f'{p}/{t}')
INNERPY
}
open_dynamic_ports(){
  local proto="$1" entry port transport
  while IFS= read -r entry; do
    [[ -z "$entry" ]] && continue
    port="${entry%/*}"; transport="${entry#*/}"
    open_port "$port" "$transport"
  done < <(configured_ports "$proto")
}

has_proto(){ [[ ",${PROTOCOLS}," == *",$1,"* ]]; }
export DEBIAN_FRONTEND=noninteractive
log "Installing selected protocol cores: $PROTOCOLS"
log "Direct port overrides: ${IRONPANEL_NODE_DIRECT_PORTS_JSON:-{}}"
log "Refreshing apt package lists"
apt-get update -y >>"$LOG" 2>&1 || true
BASE_PKGS=(curl ca-certificates iproute2 iptables openssl net-tools cron iptables-persistent)
PKGS=("${BASE_PKGS[@]}")
has_proto ssh && PKGS+=(openssh-server)
has_proto openvpn && PKGS+=(openvpn easy-rsa)
has_proto wireguard && PKGS+=(wireguard wireguard-tools)
has_proto ocserv && PKGS+=(ocserv)
if has_proto l2tp; then PKGS+=(strongswan strongswan-starter libcharon-extra-plugins xl2tpd ppp); fi
has_proto pptp && PKGS+=(pptpd ppp)
has_proto telegram_proxy && PKGS+=(nodejs)
# hysteria2/xray may be installed by upstream release scripts below.
for pkg in "${PKGS[@]}"; do
  log "Installing package: $pkg"
  apt-get install -y "$pkg" >>"$LOG" 2>&1 || log "WARN: package $pkg could not be installed; continuing"
done
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
cat > /etc/sysctl.d/99-ironpanel-node.conf <<'SYSCTL'
net.ipv4.ip_forward=1
SYSCTL
WAN_IF=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')
open_port(){ local port="$1" proto="$2"; [[ -z "$port" || -z "$proto" || "$port" == "0" ]] && return 0; iptables -C INPUT -p "$proto" --dport "$port" -j ACCEPT >/dev/null 2>&1 || iptables -I INPUT -p "$proto" --dport "$port" -j ACCEPT >/dev/null 2>&1 || true; }
open_direct_env_ports(){
  python3 - <<'PYDIRECT' 2>/dev/null | while IFS=/ read -r port proto; do open_port "$port" "$proto"; done
import json, os
data=json.loads(os.environ.get('IRONPANEL_NODE_DIRECT_PORTS_JSON') or '{}')
for proto,p in data.items():
    try: p=int(p)
    except Exception: continue
    if not (0 < p <= 65535): continue
    if proto in ('openvpn','wireguard','ocserv','hysteria2','l2tp'):
        print(f'{p}/udp')
    if proto in ('openvpn','ocserv','xray','telegram_proxy','pptp','ssh'):
        print(f'{p}/tcp')
PYDIRECT
}
open_direct_env_ports

direct_port_for(){
  python3 - "$1" <<'PYPORT' 2>/dev/null || true
import json, os, sys
proto=sys.argv[1]
try:
    data=json.loads(os.environ.get('IRONPANEL_NODE_DIRECT_PORTS_JSON') or '{}')
    p=int(data.get(proto) or 0)
    if 0 < p <= 65535:
        print(p)
except Exception:
    pass
PYPORT
}

setup_telegram_proxy(){
  local port node_bin script_src runtime config usage logf
  port="$(direct_port_for telegram_proxy)"
  [[ -n "$port" ]] || port=6969
  runtime=/opt/ironpanel-telegram-proxy/ironpanel
  config="$runtime/config.json"
  usage="$runtime/usage.json"
  logf=/var/log/ironpanel-tgproxy.log
  mkdir -p "$runtime" /etc/ironpanel /var/log

  node_bin="$(command -v node || command -v nodejs || true)"
  if [[ -z "$node_bin" ]]; then
    log "NodeJS was not found after package pass; retrying nodejs/npm install"
    apt-get update -y >>"$LOG" 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm >>"$LOG" 2>&1 || true
    if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then ln -sf "$(command -v nodejs)" /usr/bin/node 2>>"$LOG" || true; fi
    node_bin="$(command -v node || command -v nodejs || true)"
  fi
  [[ -n "$node_bin" ]] || { log "ERROR: NodeJS binary is still missing"; return 1; }

  script_src="/opt/ironpanel-node/scripts/ironpanel_mtproxy.js"
  if [[ ! -s "$script_src" ]]; then script_src="$(dirname "$0")/ironpanel_mtproxy.js"; fi
  [[ -s "$script_src" ]] || { log "ERROR: ironpanel_mtproxy.js missing from node runtime package"; return 1; }
  "$node_bin" --check "$script_src" >>"$LOG" 2>&1 || { log "ERROR: ironpanel_mtproxy.js failed node --check"; return 1; }
  install -m 755 "$script_src" "$runtime/ironpanel_mtproxy.js"

  python3 - "$config" "$port" <<'PYCFG'
import json, sys
from pathlib import Path
path=Path(sys.argv[1]); port=int(sys.argv[2])
try:
    data=json.loads(path.read_text() or '{}') if path.exists() else {}
    if not isinstance(data, dict): data={}
except Exception:
    data={}
data['port']=port
data.setdefault('mode','single-port-multi-secret')
if not isinstance(data.get('users'), list): data['users']=[]
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
PYCFG
  cp -f "$config" /etc/ironpanel/telegram_proxy.json 2>/dev/null || true
  [[ -s "$usage" ]] || printf '{"updated_at":null,"users":{}}\n' > "$usage"
  touch "$logf" || true

  cat > /etc/systemd/system/ironpanel-tgproxy.service <<SERVICE
[Unit]
Description=IronPanel shared Telegram MTProto proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$runtime
Environment=IRONPANEL_TGPROXY_CONFIG=$config
Environment=IRONPANEL_TGPROXY_USAGE=$usage
Environment=IRONPANEL_TGPROXY_LOG=$logf
Environment=IRONPANEL_TGPROXY_PORT=$port
ExecStartPre=$node_bin --check $runtime/ironpanel_mtproxy.js
ExecStart=$node_bin $runtime/ironpanel_mtproxy.js
Restart=always
RestartSec=3
LimitNOFILE=81920
StandardOutput=append:$logf
StandardError=append:$logf

[Install]
WantedBy=multi-user.target
SERVICE
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable ironpanel-tgproxy.service >/dev/null 2>&1 || true
  systemctl restart ironpanel-tgproxy.service >>"$LOG" 2>&1 || true
  sleep 1
  open_port "$port" tcp
  if systemctl is-active --quiet ironpanel-tgproxy.service && ss -H -lnt "sport = :$port" 2>/dev/null | grep -q .; then
    log "Telegram Proxy runtime active on direct tcp/$port"
    return 0
  fi
  log "ERROR: Telegram Proxy service did not listen on tcp/$port"
  journalctl -u ironpanel-tgproxy.service -n 80 --no-pager >>"$LOG" 2>&1 || true
  tail -80 "$logf" >>"$LOG" 2>&1 || true
  return 1
}
ensure_nat(){ local subnet="$1"; iptables -C FORWARD -s "$subnet" -j ACCEPT >/dev/null 2>&1 || iptables -I FORWARD -s "$subnet" -j ACCEPT >/dev/null 2>&1 || true; iptables -C FORWARD -d "$subnet" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT >/dev/null 2>&1 || iptables -I FORWARD -d "$subnet" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT >/dev/null 2>&1 || true; [[ -z "${WAN_IF:-}" ]] && return 0; iptables -t nat -C POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || iptables -t nat -A POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || true; }
# Standard IronPanel protocol ports. The main panel may override configs later via node jobs.
has_proto openvpn && { open_port 1194 udp; open_port 1195 tcp; open_dynamic_ports openvpn; ensure_nat 10.8.0.0/24; }
has_proto wireguard && { open_port 51820 udp; open_dynamic_ports wireguard; ensure_nat 10.66.66.0/24; }
has_proto ocserv && { open_port 443 tcp; open_port 443 udp; open_port 8445 tcp; open_port 8445 udp; open_dynamic_ports ocserv; ensure_nat 10.44.0.0/24; }
if has_proto l2tp; then open_port 500 udp; open_port 4500 udp; open_port 1701 udp; open_dynamic_ports l2tp; ensure_nat 10.20.20.0/24; systemctl enable --now xl2tpd >/dev/null 2>&1 || true; systemctl enable --now strongswan-starter >/dev/null 2>&1 || systemctl enable --now strongswan >/dev/null 2>&1 || true; fi
has_proto pptp && { open_port 1723 tcp; open_dynamic_ports pptp; ensure_nat 10.70.70.0/24; systemctl enable --now pptpd >/dev/null 2>&1 || true; }
has_proto xray && { open_port 443 tcp; open_dynamic_ports xray; if ! command -v xray >/dev/null 2>&1 && [[ ! -x /usr/local/bin/xray ]]; then log "Installing Xray core"; curl -fsSL --connect-timeout 8 --max-time 80 https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray-install.sh >>"$LOG" 2>&1 || true; [[ -s /tmp/xray-install.sh ]] && timeout 180 bash /tmp/xray-install.sh install >>"$LOG" 2>&1 || true; fi; }
has_proto hysteria2 && { open_port 443 udp; open_port 4433 udp; open_dynamic_ports hysteria2; if ! command -v hysteria >/dev/null 2>&1 && ! command -v hysteria2 >/dev/null 2>&1; then log "Installing Hysteria2 core"; timeout 180 bash -c 'curl -fsSL --connect-timeout 8 --max-time 80 https://get.hy2.sh/ | bash' >>"$LOG" 2>&1 || true; fi; }
if has_proto telegram_proxy; then
  open_port 6969 tcp
  open_dynamic_ports telegram_proxy
  setup_telegram_proxy || { log "ERROR: Telegram Proxy core/runtime setup failed"; tail -n 160 "$LOG" 2>/dev/null || true; exit 20; }
fi
has_proto ssh && { open_port 22 tcp; open_port 422 tcp; open_dynamic_ports ssh; systemctl enable --now ssh >/dev/null 2>&1 || systemctl enable --now sshd >/dev/null 2>&1 || true; }
mkdir -p /etc/iptables
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
systemctl daemon-reload >/dev/null 2>&1 || true

# Do not report a successful ensure_protocols job when package/release installs
# were skipped or failed. Services may stay inactive until configs are synced,
# but every selected core binary must exist at this point.
missing=()
has_proto openvpn && command -v openvpn >/dev/null 2>&1 || { has_proto openvpn && missing+=(openvpn) || true; }
has_proto wireguard && command -v wg >/dev/null 2>&1 || { has_proto wireguard && missing+=(wireguard) || true; }
has_proto ocserv && command -v ocserv >/dev/null 2>&1 || { has_proto ocserv && missing+=(ocserv) || true; }
has_proto l2tp && command -v xl2tpd >/dev/null 2>&1 || { has_proto l2tp && missing+=(l2tp) || true; }
has_proto pptp && command -v pptpd >/dev/null 2>&1 || { has_proto pptp && missing+=(pptp) || true; }
has_proto xray && { command -v xray >/dev/null 2>&1 || [[ -x /usr/local/bin/xray ]]; } || { has_proto xray && missing+=(xray) || true; }
has_proto hysteria2 && { command -v hysteria >/dev/null 2>&1 || command -v hysteria2 >/dev/null 2>&1; } || { has_proto hysteria2 && missing+=(hysteria2) || true; }
has_proto telegram_proxy && { command -v node >/dev/null 2>&1 || command -v nodejs >/dev/null 2>&1; } || { has_proto telegram_proxy && missing+=(telegram_proxy) || true; }
has_proto ssh && command -v sshd >/dev/null 2>&1 || { has_proto ssh && missing+=(ssh) || true; }
if (( ${#missing[@]} > 0 )); then
  log "ERROR: selected protocol cores are still missing: ${missing[*]}"
  log "Last apt/core details:"
  tail -n 120 "$LOG" 2>/dev/null || true
  exit 20
fi
log "Protocol core installation verified successfully"

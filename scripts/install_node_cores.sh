#!/usr/bin/env bash
set -euo pipefail
PROTOCOLS="${1:-${IRONPANEL_NODE_PROTOCOLS:-openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh}}"
LOG=/var/log/ironpanel-node-core-install.log
mkdir -p /var/log /etc/ironpanel-node /opt/ironpanel-node/scripts
: > "$LOG"
log(){ echo "[IronPanel Node Cores] $*" | tee -a "$LOG"; }

normalize_direct_ports_env(){
  python3 - <<'PYDIRECTJSON'
import json, os, re
raw = (os.environ.get('IRONPANEL_NODE_DIRECT_PORTS_JSON') or '{}')
text = str(raw).strip().strip('\x00')

def clean_obj(data):
    out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                p = int(v)
                if 0 < p <= 65535:
                    out[str(k)] = p
            except Exception:
                pass
    return out

def try_load(s):
    try:
        return clean_obj(json.loads(s))
    except Exception:
        return None

# Strict JSON first.
out = try_load(text)

# If a shell/template left trailing braces or text, try every balanced object
# prefix. This fixes legacy values such as {"telegram_proxy":6974}} and }} }.
if out is None:
    candidates = []
    if '{' in text and '}' in text:
        first = text.find('{')
        depth = 0
        for i, ch in enumerate(text[first:], start=first):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidates.append(text[first:i+1])
                    # continue collecting shorter/longer candidates if present
        # Also try simple right-trim for badly unbalanced trailing braces.
        s = text[first:]
        while s:
            candidates.append(s)
            if s.count('}') <= s.count('{'):
                break
            s = s[:-1].rstrip()
    for c in candidates:
        out = try_load(c)
        if out is not None:
            break

# Last resort: regex extraction from any malformed payload.
if out is None:
    out = clean_obj({m.group(1): int(m.group(2)) for m in re.finditer(r"[\'\"]?([A-Za-z0-9_]+)[\'\"]?\s*:\s*([0-9]{1,5})", text)})

print(json.dumps(out or {}, separators=(',', ':')))
PYDIRECTJSON
}
IRONPANEL_NODE_DIRECT_PORTS_JSON="$(normalize_direct_ports_env)"
export IRONPANEL_NODE_DIRECT_PORTS_JSON

normalize_node_ssl_domain(){
  python3 - <<'PYSSLHOST'
import os, re
raw=(os.environ.get('IRONPANEL_NODE_SSL_DOMAIN') or os.environ.get('NODE_SSL_DOMAIN') or '').strip()
raw=re.sub(r'^https?://', '', raw, flags=re.I).split('/')[0].strip()
if ':' in raw and not raw.startswith('['):
    h, _, p = raw.rpartition(':')
    if p.isdigit(): raw=h
print(raw.strip('[]').lower())
PYSSLHOST
}
IRONPANEL_NODE_SSL_DOMAIN="$(normalize_node_ssl_domain)"
export IRONPANEL_NODE_SSL_DOMAIN

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
log "Direct port overrides: $(printf %s "${IRONPANEL_NODE_DIRECT_PORTS_JSON:-}" | tr -d '\r\n')"
[[ -n "${IRONPANEL_NODE_SSL_DOMAIN:-}" ]] && log "Node SSL domain: ${IRONPANEL_NODE_SSL_DOMAIN}"
log "Refreshing apt package lists"
apt-get update -y >>"$LOG" 2>&1 || true
BASE_PKGS=(curl ca-certificates iproute2 iptables openssl net-tools cron iptables-persistent unzip)
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

NODE_SSL_CERT=""
NODE_SSL_KEY=""
_node_public_ips(){
  { hostname -I 2>/dev/null | tr ' ' '\n'; ip -4 addr show scope global 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1; curl -fsS4 --max-time 4 https://api.ipify.org 2>/dev/null || true; } | awk 'NF && !seen[$1]++'
}
_domain_points_to_node(){
  local domain="$1" ip
  [[ -n "$domain" ]] || return 1
  local resolved="$(getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
  [[ -n "$resolved" ]] || return 1
  while IFS= read -r ip; do
    [[ -n "$ip" ]] || continue
    if printf ' %s ' "$resolved" | grep -q " $ip "; then return 0; fi
  done < <(_node_public_ips)
  return 1
}
_ensure_node_ssl_cert(){
  local domain="$IRONPANEL_NODE_SSL_DOMAIN" live cert key
  [[ -n "$domain" ]] || return 1
  live="/etc/letsencrypt/live/$domain"; cert="$live/fullchain.pem"; key="$live/privkey.pem"
  if [[ -s "$cert" && -s "$key" ]]; then
    NODE_SSL_CERT="$cert"; NODE_SSL_KEY="$key"; log "Using existing node SSL certificate for $domain"; return 0
  fi
  if ! _domain_points_to_node "$domain"; then
    log "WARN: node SSL domain $domain does not resolve to this node IP; skipping Let's Encrypt and using local fallback cert"
    return 1
  fi
  log "Issuing node SSL certificate for $domain"
  apt-get install -y certbot >>"$LOG" 2>&1 || true
  command -v certbot >/dev/null 2>&1 || { log "WARN: certbot unavailable; cannot issue node SSL for $domain"; return 1; }
  open_port 80 tcp
  systemctl stop nginx apache2 caddy 2>/dev/null || true
  certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email \
    --preferred-challenges http --http-01-port 80 -d "$domain" >>"$LOG" 2>&1 || true
  if [[ -s "$cert" && -s "$key" ]]; then
    NODE_SSL_CERT="$cert"; NODE_SSL_KEY="$key"; log "Node SSL certificate ready for $domain"; return 0
  fi
  log "WARN: certbot could not issue node SSL for $domain; services will use fallback cert"
  return 1
}
_apply_node_ssl_to_existing_configs(){
  _ensure_node_ssl_cert || return 0
  local cert="$NODE_SSL_CERT" key="$NODE_SSL_KEY"
  if [[ -s /etc/ocserv/ocserv.conf ]]; then
    if grep -q '^server-cert' /etc/ocserv/ocserv.conf; then sed -i "s#^server-cert[[:space:]]*=.*#server-cert = $cert#" /etc/ocserv/ocserv.conf; else echo "server-cert = $cert" >> /etc/ocserv/ocserv.conf; fi
    if grep -q '^server-key' /etc/ocserv/ocserv.conf; then sed -i "s#^server-key[[:space:]]*=.*#server-key = $key#" /etc/ocserv/ocserv.conf; else echo "server-key = $key" >> /etc/ocserv/ocserv.conf; fi
  fi
  python3 - "$cert" "$key" <<'PYSSLAPPLY' || true
import json, re, sys
from pathlib import Path
cert,key=sys.argv[1],sys.argv[2]
# Hysteria2 YAML-ish config
for raw in ('/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'):
    p=Path(raw)
    if not p.exists(): continue
    txt=p.read_text(errors='ignore')
    if re.search(r'^\s*cert\s*:', txt, re.M): txt=re.sub(r'^(\s*cert\s*:\s*).+$', r'\1'+cert, txt, flags=re.M)
    else: txt=re.sub(r'(^\s*tls\s*:\s*\n)', r'\1  cert: '+cert+'\n', txt, count=1, flags=re.M) if re.search(r'^\s*tls\s*:', txt, re.M) else 'tls:\n  cert: '+cert+'\n  key: '+key+'\n'+txt
    if re.search(r'^\s*key\s*:', txt, re.M): txt=re.sub(r'^(\s*key\s*:\s*).+$', r'\1'+key, txt, flags=re.M)
    else: txt=re.sub(r'(^\s*tls\s*:\s*\n(?:\s*cert:.*\n)?)', r'\1  key: '+key+'\n', txt, count=1, flags=re.M)
    p.write_text(txt if txt.endswith('\n') else txt+'\n')
# Xray TLS certificate paths if the copied config uses TLS certificates.
for raw in ('/usr/local/etc/xray/config.json','/etc/xray/config.json','/etc/ironpanel/xray/config.json'):
    p=Path(raw)
    if not p.exists(): continue
    try: data=json.loads(p.read_text())
    except Exception: continue
    changed=False
    for ib in data.get('inbounds') or []:
        if not isinstance(ib, dict): continue
        st=ib.get('streamSettings') or {}
        if not isinstance(st, dict): continue
        tls=st.get('tlsSettings') or {}
        if not isinstance(tls, dict): continue
        certs=tls.get('certificates')
        if isinstance(certs, list) and certs:
            if isinstance(certs[0], dict):
                certs[0]['certificateFile']=cert; certs[0]['keyFile']=key; changed=True
    if changed: p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
PYSSLAPPLY
}


_config_value_from_yaml(){
  local key="$1" path="$2"
  awk -v k="$key" '$0 ~ "^[[:space:]]*" k "[[:space:]]*:" {sub(/^[^:]*:[[:space:]]*/, ""); gsub(/[\"'"'"']/, ""); print; exit}' "$path" 2>/dev/null || true
}

_hysteria_config_port(){
  local p
  p="$(direct_port_for hysteria2)"
  if [[ -n "$p" ]]; then printf '%s\n' "$p"; return 0; fi
  python3 - <<'PYHYP' 2>/dev/null || true
import re
from pathlib import Path
for raw in ('/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'):
    try: txt=Path(raw).read_text(errors='ignore')
    except Exception: continue
    for pat in (r'^\s*listen\s*:\s*(?:[^\n:]+:)?(\d+)', r'^\s*addr\s*:\s*(?:[^\n:]+:)?(\d+)'):
        m=re.search(pat, txt, re.I|re.M)
        if m:
            print(m.group(1)); raise SystemExit(0)
print('4433')
PYHYP
}

_setup_hysteria2_runtime(){
  local port bin cert key auth_src cfg
  port="$(_hysteria_config_port | head -n1)"
  [[ -n "$port" ]] || port=4433
  mkdir -p /etc/hysteria /etc/hysteria2 /etc/ironpanel /opt/ironpanel/scripts /var/log/hysteria
  local stats_secret_file stats_secret
  stats_secret_file=/etc/ironpanel/hysteria2_stats_secret
  if [[ ! -s "$stats_secret_file" ]]; then
    umask 077
    (command -v openssl >/dev/null 2>&1 && openssl rand -hex 32 || head -c 48 /dev/urandom | base64 | tr -d '\n') > "$stats_secret_file"
  fi
  chmod 600 "$stats_secret_file" 2>/dev/null || true
  stats_secret=$(tr -d '\r\n' < "$stats_secret_file")

  if ! command -v hysteria >/dev/null 2>&1 && ! command -v hysteria2 >/dev/null 2>&1; then
    log "Installing Hysteria2 core"
    timeout 180 bash -c 'curl -fsSL --connect-timeout 8 --max-time 80 https://get.hy2.sh/ | bash' >>"$LOG" 2>&1 || true
  fi
  bin="$(command -v hysteria || command -v hysteria2 || true)"
  [[ -n "$bin" ]] || { log "ERROR: Hysteria2 binary is missing after install attempt"; return 1; }

  # Runtime package may place the auth script under /opt/ironpanel-node/scripts.
  if [[ ! -s /opt/ironpanel/scripts/hysteria2_auth.sh && -s /opt/ironpanel-node/scripts/hysteria2_auth.sh ]]; then
    install -m 755 /opt/ironpanel-node/scripts/hysteria2_auth.sh /opt/ironpanel/scripts/hysteria2_auth.sh || true
  fi
  chmod +x /opt/ironpanel/scripts/hysteria2_auth.sh /opt/ironpanel-node/scripts/hysteria2_auth.sh 2>/dev/null || true
  if [[ ! -x /opt/ironpanel/scripts/hysteria2_auth.sh ]]; then
    # A fail-open auth helper is safer than a service that never starts during node bootstrap.
    cat > /opt/ironpanel/scripts/hysteria2_auth.sh <<'SHAUTH'
#!/usr/bin/env bash
exit 1
SHAUTH
    chmod +x /opt/ironpanel/scripts/hysteria2_auth.sh
  fi

  cfg=/etc/hysteria/config.yaml
  if [[ ! -s "$cfg" ]]; then
    cat > "$cfg" <<YAML
listen: :${port}
trafficStats:
  listen: 127.0.0.1:9999
  secret: ${stats_secret}
tls:
  cert: /etc/hysteria/server.crt
  key: /etc/hysteria/server.key
  sniGuard: disable
auth:
  type: command
  command: /opt/ironpanel/scripts/hysteria2_auth.sh
bandwidth:
  up: 100 mbps
  down: 300 mbps
ignoreClientBandwidth: false
congestion:
  type: bbr
YAML
  fi

  # Force the direct UDP port after the bundle is written.
  python3 - "$cfg" "$port" <<'PYHYCFG'
import re, sys
from pathlib import Path
path=Path(sys.argv[1]); port=str(int(sys.argv[2]))
txt=path.read_text(errors='ignore') if path.exists() else ''
if re.search(r'^\s*listen\s*:', txt, re.M):
    txt=re.sub(r'^(\s*listen\s*:\s*)(?:[^\n:]+:)?\d+\s*$', r'\1:'+port, txt, flags=re.M)
else:
    txt='listen: :'+port+'\n'+txt
path.write_text(txt if txt.endswith('\n') else txt+'\n')
PYHYCFG
  python3 - "$cfg" "$stats_secret" <<'PYHYSTATS'
import re, sys
from pathlib import Path
p=Path(sys.argv[1]); secret=sys.argv[2]
txt=p.read_text(errors='ignore') if p.exists() else ''
block='trafficStats:\n  listen: 127.0.0.1:9999\n  secret: '+secret+'\n'
if re.search(r'^trafficStats:\s*$', txt, re.M):
    txt=re.sub(r'^trafficStats:\s*\n(?:[ \t]+.*\n)*', block, txt, count=1, flags=re.M)
else:
    txt=block+txt
p.write_text(txt if txt.endswith('\n') else txt+'\n')
PYHYSTATS

  if _ensure_node_ssl_cert; then
    cert="$NODE_SSL_CERT"; key="$NODE_SSL_KEY"
  else
    cert="$(_config_value_from_yaml cert "$cfg")"
    key="$(_config_value_from_yaml key "$cfg")"
    [[ -n "$cert" ]] || cert=/etc/hysteria/server.crt
    [[ -n "$key" ]] || key=/etc/hysteria/server.key
  fi
  mkdir -p "$(dirname "$cert")" "$(dirname "$key")"
  if [[ ! -s "$cert" || ! -s "$key" ]]; then
    cn="${IRONPANEL_NODE_SSL_DOMAIN:-IronPanel-Hysteria2-Node}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 -keyout "$key" -out "$cert" -subj "/CN=${cn}" >>"$LOG" 2>&1 || true
  fi
  python3 - "$cfg" "$cert" "$key" <<'PYHYSSL'
import re, sys
from pathlib import Path
p=Path(sys.argv[1]); cert=sys.argv[2]; key=sys.argv[3]
txt=p.read_text(errors='ignore') if p.exists() else ''
if re.search(r'^\s*tls\s*:', txt, re.M):
    if re.search(r'^\s*cert\s*:', txt, re.M):
        txt=re.sub(r'^(\s*cert\s*:\s*).+$', lambda m: m.group(1)+cert, txt, flags=re.M)
    else:
        txt=re.sub(r'(^\s*tls\s*:\s*\n)', lambda m: m.group(1)+'  cert: '+cert+'\n', txt, count=1, flags=re.M)
    if re.search(r'^\s*key\s*:', txt, re.M):
        txt=re.sub(r'^(\s*key\s*:\s*).+$', lambda m: m.group(1)+key, txt, flags=re.M)
    else:
        txt=re.sub(r'(^\s*tls\s*:\s*\n(?:\s*cert:.*\n)?)', lambda m: m.group(1)+'  key: '+key+'\n', txt, count=1, flags=re.M)
else:
    txt='tls:\n  cert: '+cert+'\n  key: '+key+'\n  sniGuard: disable\n'+txt
p.write_text(txt if txt.endswith('\n') else txt+'\n')
PYHYSSL
  chmod 600 "$key" 2>/dev/null || true
  chmod 644 "$cert" 2>/dev/null || true

  cat > /etc/systemd/system/hysteria-server.service <<SERVICE
[Unit]
Description=IronPanel Hysteria2 Server (Node)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$bin server -c /etc/hysteria/config.yaml
Restart=always
RestartSec=3
LimitNOFILE=1048576
User=root

[Install]
WantedBy=multi-user.target
SERVICE
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl reset-failed hysteria-server >/dev/null 2>&1 || true
  systemctl enable hysteria-server.service >/dev/null 2>&1 || true
  systemctl restart hysteria-server.service >>"$LOG" 2>&1 || true
  sleep 2
  open_port "$port" udp
  if systemctl is-active --quiet hysteria-server.service && ss -H -lnu "sport = :$port" 2>/dev/null | grep -q .; then
    log "Hysteria2 runtime active on direct udp/$port"
    return 0
  fi
  log "ERROR: Hysteria2 service did not listen on udp/$port"
  systemctl status hysteria-server.service --no-pager >>"$LOG" 2>&1 || true
  journalctl -u hysteria-server.service -n 120 --no-pager >>"$LOG" 2>&1 || true
  return 1
}


_xray_bin(){
  local b
  for b in "$(command -v xray 2>/dev/null || true)" /usr/local/bin/xray /usr/bin/xray /usr/local/xray/xray /opt/xray/xray; do
    [[ -n "$b" && -x "$b" ]] && { printf '%s\n' "$b"; return 0; }
  done
  return 1
}

_install_xray_from_release_zip(){
  local arch asset tag tmp zip bin
  arch="$(uname -m 2>/dev/null || echo x86_64)"
  case "$arch" in
    x86_64|amd64) asset='Xray-linux-64.zip' ;;
    aarch64|arm64) asset='Xray-linux-arm64-v8a.zip' ;;
    armv7l|armv7*) asset='Xray-linux-arm32-v7a.zip' ;;
    *) asset='Xray-linux-64.zip' ;;
  esac
  tag="$(curl -fsSL --connect-timeout 8 --max-time 30 https://api.github.com/repos/XTLS/Xray-core/releases/latest 2>>"$LOG" | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1 || true)"
  [[ -n "$tag" ]] || tag='v1.8.24'
  tmp="$(mktemp -d /tmp/ironpanel-xray.XXXXXX)"
  zip="$tmp/$asset"
  log "Installing Xray core fallback release $tag/$asset"
  if ! curl -fL --connect-timeout 10 --max-time 160 --retry 2 --retry-delay 2 \
      "https://github.com/XTLS/Xray-core/releases/download/${tag}/${asset}" -o "$zip" >>"$LOG" 2>&1; then
    rm -rf "$tmp"
    return 1
  fi
  unzip -oq "$zip" -d "$tmp/extract" >>"$LOG" 2>&1 || { rm -rf "$tmp"; return 1; }
  bin="$(find "$tmp/extract" -type f -name xray -perm /111 | head -n1 || true)"
  if [[ -z "$bin" ]]; then
    bin="$(find "$tmp/extract" -type f -name xray | head -n1 || true)"
    [[ -n "$bin" ]] && chmod +x "$bin" 2>>"$LOG" || true
  fi
  [[ -n "$bin" && -x "$bin" ]] || { rm -rf "$tmp"; return 1; }
  install -m 755 "$bin" /usr/local/bin/xray
  mkdir -p /usr/local/share/xray /usr/local/etc/xray /var/log/xray
  find "$tmp/extract" -type f \( -name geoip.dat -o -name geosite.dat \) -exec install -m 644 {} /usr/local/share/xray/ \; 2>>"$LOG" || true
  rm -rf "$tmp"
  return 0
}

_setup_xray_runtime(){
  local bin port
  mkdir -p /usr/local/etc/xray /usr/local/share/xray /var/log/xray
  if ! _xray_bin >/dev/null 2>&1; then
    log "Installing Xray core"
    curl -fsSL --connect-timeout 8 --max-time 80 https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray-install.sh >>"$LOG" 2>&1 || true
    if [[ -s /tmp/xray-install.sh ]]; then timeout 240 bash /tmp/xray-install.sh install >>"$LOG" 2>&1 || true; fi
  fi
  if ! _xray_bin >/dev/null 2>&1; then
    _install_xray_from_release_zip >>"$LOG" 2>&1 || true
  fi
  bin="$(_xray_bin || true)"
  [[ -n "$bin" ]] || { log "ERROR: Xray binary is missing after install attempts"; return 1; }
  if ! command -v xray >/dev/null 2>&1; then ln -sf "$bin" /usr/bin/xray 2>>"$LOG" || true; fi
  bin="$(_xray_bin || true)"
  port="$(direct_port_for xray)"; [[ -n "$port" ]] || port=443
  if [[ ! -s /usr/local/etc/xray/config.json ]]; then
    cat > /usr/local/etc/xray/config.json <<XRAYCFG
{
  "log": {"loglevel": "warning", "access": "/var/log/xray/access.log", "error": "/var/log/xray/error.log"},
  "inbounds": [{"tag":"ironpanel-bootstrap","listen":"0.0.0.0","port": ${port}, "protocol":"dokodemo-door", "settings":{"address":"127.0.0.1"}}],
  "outbounds": [{"protocol":"freedom","tag":"direct"}]
}
XRAYCFG
  fi
  touch /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  chmod 644 /usr/local/etc/xray/config.json /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  cat > /etc/systemd/system/xray.service <<XRAYSERVICE
[Unit]
Description=Xray Service - IronPanel Node Managed
After=network.target nss-lookup.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
ExecStartPre=/bin/sh -c 'mkdir -p /var/log/xray /usr/local/etc/xray; touch /var/log/xray/access.log /var/log/xray/error.log'
ExecStart=$bin run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
XRAYSERVICE
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable xray >/dev/null 2>&1 || true
  open_port "$port" tcp
  log "Xray core binary ready: $bin"
  return 0
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
  open_port "$port" tcp
  for _try in 1 2 3 4 5; do
    if systemctl is-active --quiet ironpanel-tgproxy.service && ss -H -lnt "sport = :$port" 2>/dev/null | grep -q .; then
      log "Telegram Proxy runtime active on direct tcp/$port"
      return 0
    fi
    sleep 1
  done
  log "ERROR: Telegram Proxy service did not listen on tcp/$port"
  journalctl -u ironpanel-tgproxy.service -n 80 --no-pager >>"$LOG" 2>&1 || true
  tail -80 "$logf" >>"$LOG" 2>&1 || true
  return 1
}
ensure_nat(){ local subnet="$1"; iptables -C FORWARD -s "$subnet" -j ACCEPT >/dev/null 2>&1 || iptables -I FORWARD -s "$subnet" -j ACCEPT >/dev/null 2>&1 || true; iptables -C FORWARD -d "$subnet" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT >/dev/null 2>&1 || iptables -I FORWARD -d "$subnet" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT >/dev/null 2>&1 || true; [[ -z "${WAN_IF:-}" ]] && return 0; iptables -t nat -C POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || iptables -t nat -A POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || true; }
# Install the same non-blocking accounting hooks used by the main server.
mkdir -p /opt/ironpanel/scripts /var/lib/ironpanel/usage-events
for _usage_script in ironpanel_usage_event_hook.py ocserv_usage_disconnect.sh install_ppp_usage_hooks.sh; do
  if [[ -s "/opt/ironpanel-node/scripts/${_usage_script}" ]]; then
    install -m 755 "/opt/ironpanel-node/scripts/${_usage_script}" "/opt/ironpanel/scripts/${_usage_script}" || true
  fi
done
chmod 700 /var/lib/ironpanel/usage-events 2>/dev/null || true
if [[ -x /opt/ironpanel/scripts/install_ppp_usage_hooks.sh ]]; then
  APP_DIR=/opt/ironpanel bash /opt/ironpanel/scripts/install_ppp_usage_hooks.sh || true
fi
if [[ -s /etc/ocserv/ocserv.conf && -x /opt/ironpanel/scripts/ocserv_usage_disconnect.sh ]]; then
  sed -i -e '/^connect-script[[:space:]]*=.*ocserv_session_hook\.sh/d' -e '/^disconnect-script[[:space:]]*=.*ocserv_session_hook\.sh/d' /etc/ocserv/ocserv.conf || true
  grep -q '^disconnect-script[[:space:]]*=[[:space:]]*/opt/ironpanel/scripts/ocserv_usage_disconnect.sh' /etc/ocserv/ocserv.conf || echo 'disconnect-script = /opt/ironpanel/scripts/ocserv_usage_disconnect.sh' >> /etc/ocserv/ocserv.conf
fi
# Standard IronPanel protocol ports. The main panel may override configs later via node jobs.
has_proto openvpn && { open_port 1194 udp; open_port 1195 tcp; open_dynamic_ports openvpn; ensure_nat 10.8.0.0/24; }
has_proto wireguard && { open_port 51820 udp; open_dynamic_ports wireguard; ensure_nat 10.66.66.0/24; }
has_proto ocserv && { open_port 443 tcp; open_port 443 udp; open_port 8445 tcp; open_port 8445 udp; open_dynamic_ports ocserv; ensure_nat 10.44.0.0/24; }
if has_proto l2tp; then
  open_port 500 udp; open_port 4500 udp; open_port 1701 udp; open_dynamic_ports l2tp; ensure_nat 10.20.20.0/24; ensure_nat 10.21.21.0/24
  if [[ -x /opt/ironpanel-node/scripts/repair_l2tp.sh ]]; then
    IRONPANEL_PUBLIC_HOST="${IRONPANEL_NODE_SSL_DOMAIN:-${IRONPANEL_CONFIG_DOMAIN:-}}" ETC_DIR=/etc/ironpanel bash /opt/ironpanel-node/scripts/repair_l2tp.sh --node-install >>"$LOG" 2>&1 || true
  fi
  if [[ -x /opt/ironpanel/scripts/install_ppp_usage_hooks.sh ]]; then APP_DIR=/opt/ironpanel bash /opt/ironpanel/scripts/install_ppp_usage_hooks.sh || true; fi
  grep -q '^ipparam ' /etc/ppp/options.xl2tpd 2>/dev/null || echo 'ipparam ironpanel-l2tp' >> /etc/ppp/options.xl2tpd
  systemctl enable --now xl2tpd >/dev/null 2>&1 || true; systemctl enable --now strongswan-starter >/dev/null 2>&1 || systemctl enable --now strongswan >/dev/null 2>&1 || true
fi
if has_proto pptp; then
  open_port 1723 tcp; open_dynamic_ports pptp; ensure_nat 10.70.70.0/24
  if [[ -x /opt/ironpanel-node/scripts/repair_pptp.sh ]]; then bash /opt/ironpanel-node/scripts/repair_pptp.sh >>"$LOG" 2>&1 || true; fi
  grep -q '^ipparam ' /etc/ppp/pptpd-options 2>/dev/null || echo 'ipparam ironpanel-pptp' >> /etc/ppp/pptpd-options
  if [[ -x /opt/ironpanel/scripts/install_ppp_usage_hooks.sh ]]; then APP_DIR=/opt/ironpanel bash /opt/ironpanel/scripts/install_ppp_usage_hooks.sh || true; fi
  systemctl enable --now pptpd >/dev/null 2>&1 || true
fi
has_proto xray && { open_port 443 tcp; open_dynamic_ports xray; _setup_xray_runtime || { log "ERROR: Xray core/runtime setup failed"; tail -n 160 "$LOG" 2>/dev/null || true; exit 20; }; }
has_proto hysteria2 && { open_port 443 udp; open_port 4433 udp; open_dynamic_ports hysteria2; _setup_hysteria2_runtime || { log "ERROR: Hysteria2 core/runtime setup failed"; tail -n 160 "$LOG" 2>/dev/null || true; exit 20; }; }
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
if has_proto xray; then [[ -n "$(_xray_bin || true)" ]] || missing+=(xray); fi
_apply_node_ssl_to_existing_configs || true
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

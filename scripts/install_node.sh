#!/usr/bin/env bash
set -euo pipefail
MASTER=""; TOKEN=""; HOST=""; PROTOCOLS=""; NODE_NAME=""; INSECURE_TLS="0"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --master|--panel) MASTER="${2:-}"; shift 2;;
    --token) TOKEN="${2:-}"; shift 2;;
    --host) HOST="${2:-}"; shift 2;;
    --protocols) PROTOCOLS="${2:-}"; shift 2;;
    --name) NODE_NAME="${2:-}"; shift 2;;
    --insecure-tls|--allow-self-signed) INSECURE_TLS="1"; shift;;
    *) shift;;
  esac
done
log(){ echo "[IronPanel Node] $*"; }
if [[ -z "$MASTER" ]]; then read -rp "Master Panel URL: " MASTER; fi
if [[ -z "$TOKEN" ]]; then read -rp "Node Token: " TOKEN; fi
if [[ -z "$HOST" ]]; then HOST=$(curl -fsS4 --max-time 3 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}'); fi
if [[ -z "$PROTOCOLS" ]]; then PROTOCOLS="openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh"; fi
APP_DIR=/opt/ironpanel-node
STATE_DIR=/etc/ironpanel-node
mkdir -p "$APP_DIR" "$STATE_DIR" "$STATE_DIR/users"
log "Installing prerequisites"
apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip curl ca-certificates git iproute2 iptables openssh-server >/dev/null 2>&1 || true

# Generate candidate master URLs. This protects node installs created by older
# panels as https://IP without the real panel port. The installer probes common
# panel ports and stores the first reachable URL before systemd starts.
mapfile -t MASTER_CANDIDATES < <(python3 - "$MASTER" <<'PYCANDIDATES'
import sys, re
from urllib.parse import urlparse
raw=(sys.argv[1] or '').strip().rstrip('/')
if not raw:
    sys.exit(0)
def add(out, url):
    url=url.rstrip('/')
    if url and url not in out:
        out.append(url)
parsed=urlparse(raw if re.match(r'^https?://', raw, re.I) else '//' + raw)
scheme=(parsed.scheme or '').lower()
host=parsed.hostname or raw.split('/')[0].split(':')[0].strip('[]')
port=parsed.port
path='' if not parsed.path or parsed.path=='/' else parsed.path.rstrip('/')
out=[]
if scheme:
    add(out, raw)
else:
    add(out, 'http://' + raw.lstrip('/'))
if host:
    hostpart=f'[{host}]' if ':' in host and not host.startswith('[') else host
    if scheme == 'https':
        # Most IP based IronPanel installs are plain HTTP on a custom port.
        if port:
            add(out, f'http://{hostpart}:{port}{path}')
        else:
            for p in (8001,8080,5000,80,443):
                add(out, f'http://{hostpart}:{p}{path}')
            for p in (443,8001,8080):
                add(out, f'https://{hostpart}:{p}{path}')
    elif scheme == 'http':
        if not port:
            for p in (8001,8080,5000,80):
                add(out, f'http://{hostpart}:{p}{path}')
    else:
        for p in (8001,8080,5000,80):
            add(out, f'http://{hostpart}:{p}{path}')
for x in out:
    print(x)
PYCANDIDATES
)

probe_master(){
  local base="$1" code="000"
  code=$(curl -k -sS -o /tmp/ironpanel-node-probe.out -w "%{http_code}" --connect-timeout 5 --max-time 10 "$base/api/v2/node/ping" 2>/dev/null || true)
  case "$code" in 200|204|301|302|401|403|404|405) return 0;; esac
  code=$(curl -k -sS -o /tmp/ironpanel-node-probe.out -w "%{http_code}" --connect-timeout 5 --max-time 10 "$base/" 2>/dev/null || true)
  case "$code" in 200|204|301|302|401|403|404|405) return 0;; esac
  return 1
}
RESOLVED_MASTER="$MASTER"
log "Checking master panel reachability"
for candidate in "${MASTER_CANDIDATES[@]}"; do
  [[ -z "$candidate" ]] && continue
  if probe_master "$candidate"; then
    RESOLVED_MASTER="$candidate"
    log "Master reachable: $RESOLVED_MASTER"
    break
  else
    log "No response from: $candidate"
  fi
done
if [[ "$RESOLVED_MASTER" == "$MASTER" ]]; then
  log "Using provided master URL. If the node stays offline, verify scheme/port/firewall: $RESOLVED_MASTER"
fi
# Automatically allow self-signed HTTPS only when explicitly requested or when
# the admin still chooses HTTPS on a raw IP. Plain HTTP is preferred for non-SSL IP panels.
if [[ "$RESOLVED_MASTER" =~ ^https://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(:[0-9]+)?(/|$) ]]; then
  INSECURE_TLS="1"
fi

if [[ -f scripts/node_agent.py ]]; then
  cp -a scripts/node_agent.py "$APP_DIR/node_agent.py"
fi
if [[ ! -s "$APP_DIR/node_agent.py" ]]; then
cat > "$APP_DIR/node_agent.py" <<'PYNODEMISSING'
#!/usr/bin/env python3
print('node_agent.py missing; reinstall from IronPanel package')
PYNODEMISSING
fi
python3 - "$STATE_DIR/node.env" "$RESOLVED_MASTER" "$TOKEN" "$HOST" "$PROTOCOLS" "$NODE_NAME" "$INSECURE_TLS" <<'PYENV'
import sys
path, master, token, host, protocols, name, insecure=sys.argv[1:]
def q(v):
    v=str(v or '').replace('\\','\\\\').replace('"','\\"').replace('\n',' ').replace('\r',' ')
    return '"'+v+'"'
items={
 'IRONPANEL_NODE_MASTER': master,
 'IRONPANEL_NODE_TOKEN': token,
 'IRONPANEL_NODE_HOST': host,
 'IRONPANEL_NODE_PROTOCOLS': protocols,
 'IRONPANEL_NODE_NAME': name,
 'IRONPANEL_NODE_INSECURE_TLS': insecure,
}
with open(path,'w',encoding='utf-8') as f:
    for k,v in items.items():
        f.write(f'{k}={q(v)}\n')
PYENV
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel psutil >/dev/null
chmod +x "$APP_DIR/node_agent.py"
cat > /etc/systemd/system/ironpanel-node.service <<SERVICE
[Unit]
Description=IronPanel Node Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$STATE_DIR/node.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/node_agent.py --master "\${IRONPANEL_NODE_MASTER}" --token "\${IRONPANEL_NODE_TOKEN}"
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
Alias=ironpanel-node-agent.service
SERVICE
systemctl daemon-reload
ln -sf /etc/systemd/system/ironpanel-node.service /etc/systemd/system/ironpanel-node-agent.service || true
systemctl enable --now ironpanel-node.service
log "Running one-shot heartbeat test"
set +e
"$APP_DIR/.venv/bin/python" "$APP_DIR/node_agent.py" --master "$RESOLVED_MASTER" --token "$TOKEN" --once
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  log "One-shot heartbeat failed. Check: journalctl -u ironpanel-node -n 100 --no-pager"
else
  log "One-shot heartbeat completed. The node should become Online in the main panel."
fi
systemctl status ironpanel-node --no-pager || true

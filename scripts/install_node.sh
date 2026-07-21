#!/usr/bin/env bash
set -euo pipefail
MASTER=""; TOKEN=""; HOST=""; PROTOCOLS=""; NODE_NAME=""; DIRECT_PORTS_JSON="{}"; INSECURE_TLS="0"; INSTALL_CORES="1"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --master|--panel) MASTER="${2:-}"; shift 2;;
    --token) TOKEN="${2:-}"; shift 2;;
    --host) HOST="${2:-}"; shift 2;;
    --protocols) PROTOCOLS="${2:-}"; shift 2;;
    --name) NODE_NAME="${2:-}"; shift 2;;
    --direct-ports|--direct-ports-json|--ports-json) DIRECT_PORTS_JSON="${2:-{}}"; shift 2;;
    --install-cores|--with-cores) INSTALL_CORES="1"; shift;;
    --skip-cores|--no-cores) INSTALL_CORES="0"; shift;;
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
mkdir -p "$APP_DIR" "$APP_DIR/scripts" "$STATE_DIR" "$STATE_DIR/users"
log "Installing prerequisites"
apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip curl ca-certificates git iproute2 iptables openssh-server >/dev/null 2>&1 || true

mapfile -t MASTER_CANDIDATES < <(python3 - "$MASTER" <<'PYCANDIDATES'
import sys, re
from urllib.parse import urlparse
raw=(sys.argv[1] or '').strip().rstrip('/')
if not raw:
    sys.exit(0)
out=[]
def add(url):
    url=(url or '').rstrip('/')
    if url and url not in out:
        out.append(url)
def is_ip_or_local(host):
    host=(host or '').strip('[]').lower()
    return host in ('localhost','127.0.0.1','::1') or bool(re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', host))
parsed=urlparse(raw if re.match(r'^https?://', raw, re.I) else '//' + raw)
scheme=(parsed.scheme or '').lower()
host=parsed.hostname or raw.split('/')[0].split(':')[0].strip('[]')
port=parsed.port
path='' if not parsed.path or parsed.path=='/' else parsed.path.rstrip('/')
hostpart=f'[{host}]' if ':' in host and not host.startswith('[') else host
if host:
    ipish=is_ip_or_local(host)
    if scheme in ('http','https'):
        if port:
            # v19.9.15: explicit custom panel ports may be either HTTP or HTTPS.
            # Probe both instead of assuming the scheme is correct.
            add(f'{scheme}://{hostpart}:{port}{path}')
            add(f'{"https" if scheme == "http" else "http"}://{hostpart}:{port}{path}')
        else:
            add(f'{scheme}://{hostpart}{path}')
            add(f'{"https" if scheme == "http" else "http"}://{hostpart}{path}')
    if ipish:
        for p in (443,8001,8080): add(f'https://{hostpart}:{p}{path}')
        for p in (8001,8080,5000,80): add(f'http://{hostpart}:{p}{path}')
    else:
        for p in (443,8001,8080): add(f'https://{hostpart}:{p}{path}')
        for p in (8001,8080,5000,80): add(f'http://{hostpart}:{p}{path}')
else:
    add(raw if scheme else 'http://' + raw.lstrip('/'))
for x in out:
    print(x)
PYCANDIDATES
)
printf '[IronPanel Node] candidate endpoint: %s\n' "${MASTER_CANDIDATES[@]}"

probe_master(){
  local base="$1" insecure="${2:-0}" rc=1
  rm -f /tmp/ironpanel-node-probe.out /tmp/ironpanel-node-probe.err /tmp/ironpanel-node-probe.auth
  IRONPANEL_PROBE_BASE="$base" IRONPANEL_PROBE_TOKEN="$TOKEN" IRONPANEL_PROBE_HOST="$HOST" IRONPANEL_PROBE_PROTOCOLS="$PROTOCOLS" IRONPANEL_PROBE_INSECURE="$insecure" python3 - <<'PYPROBE' >/tmp/ironpanel-node-probe.out 2>/tmp/ironpanel-node-probe.err
import json, os, ssl, sys, urllib.request, urllib.error, re
base=(os.environ.get('IRONPANEL_PROBE_BASE') or '').rstrip('/')
token=os.environ.get('IRONPANEL_PROBE_TOKEN') or ''
payload={
  'version':'19.9.15','agent_version':'19.9.15','public_ip':os.environ.get('IRONPANEL_PROBE_HOST') or '',
  'protocols':os.environ.get('IRONPANEL_PROBE_PROTOCOLS') or '', 'probe': True,
  'protocol_health':{}, 'cpu_percent':0, 'ram_percent':0, 'disk_percent':0, 'ping_ms':0,
  'traffic_rx_bytes':0, 'traffic_tx_bytes':0, 'online_users':0
}
def ctx_for(url):
    if not url.lower().startswith('https://'):
        return None
    insecure=(os.environ.get('IRONPANEL_PROBE_INSECURE','0') == '1')
    if insecure:
        return ssl._create_unverified_context()
    return None
try:
    req=urllib.request.Request(base + '/api/v2/node/heartbeat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','X-NODE-TOKEN':token,'User-Agent':'IronPanel-Node-Installer/19.9.15'})
    ctx=ctx_for(base)
    r=urllib.request.urlopen(req, timeout=8, context=ctx) if ctx else urllib.request.urlopen(req, timeout=8)
    body=r.read().decode(errors='ignore')[:500]
    print('heartbeat-ok', r.status, body)
    sys.exit(0)
except urllib.error.HTTPError as e:
    body=e.read().decode(errors='ignore')[:500]
    print(f'heartbeat-http-{e.code}', body)
    if e.code in (401,403):
        # The endpoint exists, but this node token is invalid. Do not accept the
        # URL as healthy because the installed agent would remain permanently offline.
        sys.exit(2)
except Exception as e:
    print(type(e).__name__ + ': ' + str(e))
# Heartbeat must authenticate successfully; a public ping is not enough.
sys.exit(1)
PYPROBE
  rc=$?
  if [[ $rc -eq 0 ]]; then
    if grep -q 'heartbeat-http-401\|heartbeat-http-403' /tmp/ironpanel-node-probe.out 2>/dev/null; then
      cat /tmp/ironpanel-node-probe.out > /tmp/ironpanel-node-probe.auth
    fi
    return 0
  fi
  return 1
}
RESOLVED_MASTER=""
log "Checking real master heartbeat endpoint"
# First pass: only strict TLS-valid HTTPS or normal HTTP. This prevents a
# certificate-mismatched https://IP endpoint from winning before the correct
# HTTP endpoint or SSL domain is tested.
for candidate in "${MASTER_CANDIDATES[@]}"; do
  [[ -z "$candidate" ]] && continue
  if probe_master "$candidate" 0; then
    RESOLVED_MASTER="$candidate"
    INSECURE_TLS="0"
    log "Master heartbeat endpoint selected: $RESOLVED_MASTER"
    break
  else
    err=$(cat /tmp/ironpanel-node-probe.err /tmp/ironpanel-node-probe.out 2>/dev/null | tail -n 1 || true)
    log "No strict node heartbeat endpoint at: $candidate ${err:+($err)}"
  fi
done
# Second pass: only if strict probing failed everywhere, allow self-signed or
# IP-mismatch HTTPS. The selected fallback is recorded into node.env.
if [[ -z "$RESOLVED_MASTER" ]]; then
  for candidate in "${MASTER_CANDIDATES[@]}"; do
    [[ -z "$candidate" ]] && continue
    [[ "$candidate" =~ ^https:// ]] || continue
    if probe_master "$candidate" 1; then
      RESOLVED_MASTER="$candidate"
      INSECURE_TLS="1"
      log "Master heartbeat verified with TLS fallback: $RESOLVED_MASTER"
      break
    else
      err=$(cat /tmp/ironpanel-node-probe.err /tmp/ironpanel-node-probe.out 2>/dev/null | tail -n 1 || true)
      log "No fallback node heartbeat endpoint at: $candidate ${err:+($err)}"
    fi
  done
fi
if [[ -z "$RESOLVED_MASTER" ]]; then
  RESOLVED_MASTER="${MASTER%/}"
  log "ERROR: authenticated master heartbeat could not be verified: $RESOLVED_MASTER"
  log "Check panel URL/port, firewall, SSL and regenerate the node token, then run installation again."
  exit 12
fi

if [[ -f scripts/node_agent.py ]]; then cp -a scripts/node_agent.py "$APP_DIR/node_agent.py"; fi
if [[ -f scripts/install_node_cores.sh ]]; then cp -a scripts/install_node_cores.sh "$APP_DIR/scripts/install_node_cores.sh"; chmod +x "$APP_DIR/scripts/install_node_cores.sh"; fi
if [[ -d scripts ]]; then cp -a scripts/*.sh "$APP_DIR/scripts/" 2>/dev/null || true; cp -a scripts/*.py "$APP_DIR/scripts/" 2>/dev/null || true; cp -a scripts/*.js "$APP_DIR/scripts/" 2>/dev/null || true; chmod +x "$APP_DIR/scripts"/* 2>/dev/null || true; fi
if [[ ! -s "$APP_DIR/node_agent.py" ]]; then
cat > "$APP_DIR/node_agent.py" <<'PYNODEMISSING'
#!/usr/bin/env python3
print('node_agent.py missing; reinstall from IronPanel package')
PYNODEMISSING
fi
python3 - "$STATE_DIR/node.env" "$RESOLVED_MASTER" "$TOKEN" "$HOST" "$PROTOCOLS" "$NODE_NAME" "$INSECURE_TLS" "$DIRECT_PORTS_JSON" <<'PYENV'
import sys
path, master, token, host, protocols, name, insecure, direct_ports_json=sys.argv[1:]
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
 'IRONPANEL_NODE_HEARTBEAT_INTERVAL': '60',
 'IRONPANEL_NODE_DIRECT_PORTS_JSON': direct_ports_json or '{}',
}

with open(path,'w',encoding='utf-8') as f:
    for k,v in items.items():
        f.write(f'{k}={q(v)}\n')
PYENV
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel psutil >/dev/null
chmod +x "$APP_DIR/node_agent.py"
if [[ "$INSTALL_CORES" == "1" ]]; then
  log "Installing selected VPN/proxy cores on this node"
  if [[ -x "$APP_DIR/scripts/install_node_cores.sh" ]]; then
    if ! IRONPANEL_NODE_DIRECT_PORTS_JSON="$DIRECT_PORTS_JSON" bash "$APP_DIR/scripts/install_node_cores.sh" "$PROTOCOLS"; then
      log "ERROR: selected core installation/verification failed. Recent /var/log/ironpanel-node-core-install.log:"
      tail -n 180 /var/log/ironpanel-node-core-install.log 2>/dev/null || true
      exit 21
    fi
  else
    log "ERROR: install_node_cores.sh not found"
    exit 20
  fi
fi
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
systemctl enable ironpanel-node.service >/dev/null 2>&1 || true
systemctl stop ironpanel-node.service >/dev/null 2>&1 || true
log "Running one-shot heartbeat and initial sync test"
rm -f "$STATE_DIR/last_job_failure.json"
# Load the same EnvironmentFile values used by systemd so the one-shot agent
# reports the selected protocols/host and uses the configured TLS mode.
set -a
. "$STATE_DIR/node.env"
set +a
set +e
"$APP_DIR/.venv/bin/python" "$APP_DIR/node_agent.py" --master "$RESOLVED_MASTER" --token "$TOKEN" --once
rc=$?
# Run a second pass so jobs auto-queued by the first heartbeat, such as core install,
# config sync and users bulk sync, are drained immediately during installation.
"$APP_DIR/.venv/bin/python" "$APP_DIR/node_agent.py" --master "$RESOLVED_MASTER" --token "$TOKEN" --once
rc2=$?
set -e
if [[ $rc -ne 0 && $rc2 -ne 0 ]]; then
  log "ERROR: authenticated heartbeat/sync failed twice. Check: journalctl -u ironpanel-node -n 100 --no-pager"
  systemctl status ironpanel-node --no-pager || true
  exit 22
fi
if [[ -s "$STATE_DIR/last_job_failure.json" ]]; then
  log "ERROR: one or more initial node jobs failed:"
  cat "$STATE_DIR/last_job_failure.json" || true
  exit 24
fi
log "Authenticated heartbeat and initial core/config/user sync completed successfully."
systemctl start ironpanel-node.service
systemctl is-active --quiet ironpanel-node || { systemctl status ironpanel-node --no-pager || true; exit 23; }
systemctl status ironpanel-node --no-pager || true

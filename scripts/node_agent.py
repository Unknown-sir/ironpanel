#!/usr/bin/env python3
import argparse, json, os, subprocess, time, urllib.request, urllib.error, ssl, re, sys
from pathlib import Path
from urllib.parse import urlparse
VERSION='19.8.10'
STATE=Path('/etc/ironpanel-node')
USERS=STATE/'users'
PROTOCOL_SERVICES={
 'openvpn':['openvpn-server@server','openvpn'], 'wireguard':['wg-quick@wg0','wg-quick@wg-ironpanel'],
 'ocserv':['ocserv'], 'l2tp':['xl2tpd','strongswan'], 'xray':['xray'], 'pptp':['pptpd'],
 'hysteria2':['hysteria-server','hysteria2-server'], 'telegram_proxy':['ironpanel-tgproxy'], 'ssh':['ssh','sshd']
}
LAST_ERROR=''

def sh(cmd, timeout=8):
    try: return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except Exception: return ''

def is_active(service): return sh(f'systemctl is-active {service} 2>/dev/null || true') == 'active'

def protocol_health():
    out={}
    for proto, services in PROTOCOL_SERVICES.items():
        active=[s for s in services if is_active(s)]
        out[proto]={'ok':bool(active),'detail':','.join(active) or 'inactive'}
    return out

def metrics():
    cpu=float(sh("python3 - <<'PY'\nimport psutil; print(psutil.cpu_percent(interval=0.2))\nPY") or 0)
    ram=float(sh("python3 - <<'PY'\nimport psutil; print(psutil.virtual_memory().percent)\nPY") or 0)
    disk=float(sh("python3 - <<'PY'\nimport psutil; print(psutil.disk_usage('/').percent)\nPY") or 0)
    iface=sh("ip route | awk '/default/ {print $5; exit}'")
    rx=int(sh(f"cat /sys/class/net/{iface}/statistics/rx_bytes 2>/dev/null") or 0) if iface else 0
    tx=int(sh(f"cat /sys/class/net/{iface}/statistics/tx_bytes 2>/dev/null") or 0) if iface else 0
    online=int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0)
    return {'version':VERSION,'agent_version':VERSION,'cpu_percent':cpu,'ram_percent':ram,'disk_percent':disk,'traffic_rx_bytes':rx,'traffic_tx_bytes':tx,'public_ip':sh('curl -fsS4 --max-time 3 https://api.ipify.org || true'), 'protocols': os.environ.get('IRONPANEL_NODE_PROTOCOLS','openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh'), 'protocol_health': protocol_health(), 'online_users': online, 'last_error': LAST_ERROR[:5000]}

def _add(out, url):
    url=(url or '').rstrip('/')
    if url and url not in out:
        out.append(url)

def _master_candidates(raw):
    raw=(raw or '').strip().rstrip('/')
    parsed=urlparse(raw if re.match(r'^https?://', raw, re.I) else '//' + raw)
    scheme=(parsed.scheme or '').lower(); host=parsed.hostname; port=parsed.port
    path='' if not parsed.path or parsed.path=='/' else parsed.path.rstrip('/')
    out=[]; _add(out, raw if scheme else 'http://' + raw.lstrip('/'))
    if host:
        hp=f'[{host}]' if ':' in host and not host.startswith('[') else host
        if scheme == 'https':
            if port:
                _add(out, f'http://{hp}:{port}{path}')
            else:
                for p in (8001,8080,5000,80,443): _add(out, f'http://{hp}:{p}{path}')
                for p in (443,8001,8080): _add(out, f'https://{hp}:{p}{path}')
        elif scheme == 'http' and not port:
            for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
        elif not scheme:
            for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
    return out

def _ssl_context(url):
    if not url.lower().startswith('https://'):
        return None
    insecure=(os.environ.get('IRONPANEL_NODE_INSECURE_TLS','0') == '1')
    if insecure:
        return ssl._create_unverified_context()
    return None

def post_json(url, token, path, data):
    global LAST_ERROR
    errors=[]
    for base in _master_candidates(url):
        try:
            req=urllib.request.Request(base.rstrip('/')+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json','X-NODE-TOKEN':token,'User-Agent':'IronPanel-Node-Agent/'+VERSION})
            ctx=_ssl_context(base)
            if ctx:
                r=urllib.request.urlopen(req, timeout=15, context=ctx)
            else:
                r=urllib.request.urlopen(req, timeout=15)
            body=r.read().decode() or '{}'
            LAST_ERROR=''
            if base.rstrip('/') != url.rstrip('/'):
                try: (STATE/'master.resolved').write_text(base.rstrip('/')+'\n', encoding='utf-8')
                except Exception: pass
            return json.loads(body)
        except urllib.error.HTTPError as e:
            body=''
            try: body=e.read().decode(errors='ignore')[:500]
            except Exception: pass
            if e.code in (400,401,403):
                LAST_ERROR=f'{base}: HTTP {e.code} {body}'
                raise RuntimeError(LAST_ERROR)
            errors.append(f'{base}: HTTP {e.code} {body}')
        except Exception as e:
            errors.append(f'{base}: {type(e).__name__}: {e}')
    LAST_ERROR=' | '.join(errors)[-5000:]
    raise RuntimeError(LAST_ERROR or 'all master candidates failed')

def handle_job(job):
    action=job.get('action'); payload=job.get('payload') or {}; USERS.mkdir(parents=True, exist_ok=True)
    if action == 'health_check':
        return True, json.dumps(protocol_health(), ensure_ascii=False), {'protocol_health': protocol_health(), 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0)}
    if action == 'sync_user':
        username=''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in str(payload.get('username') or 'user'))
        proto=str(payload.get('protocol') or 'all')
        (USERS/f'{username}.{proto}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return True, f'user {username}/{proto} synced to node metadata store', {}
    if action == 'delete_user':
        username=''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in str(payload.get('username') or 'user'))
        for p in USERS.glob(f'{username}.*.json'): p.unlink(missing_ok=True)
        return True, f'user {username} deleted from node metadata store', {}
    if action == 'ensure_protocols':
        protos=str(payload.get('protocols') or os.environ.get('IRONPANEL_NODE_PROTOCOLS','')).split(',')
        out=[]
        if 'ssh' in protos: out.append(sh('apt-get update >/dev/null 2>&1; DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server >/dev/null 2>&1; systemctl enable --now ssh || systemctl enable --now sshd || true', timeout=120))
        return True, 'protocol core check completed\n'+'\n'.join(out), {'protocol_health': protocol_health()}
    return False, 'unknown job: '+str(action), {}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--master', required=True); ap.add_argument('--token', required=True); ap.add_argument('--once', action='store_true')
    a=ap.parse_args()
    resolved_file=STATE/'master.resolved'
    if resolved_file.exists():
        try:
            saved=resolved_file.read_text(encoding='utf-8').strip()
            if saved: a.master=saved
        except Exception: pass
    exit_code=0
    while True:
        try:
            res=post_json(a.master, a.token, '/api/v2/node/heartbeat', metrics())
            print(json.dumps(res, ensure_ascii=False), flush=True)
            for job in res.get('jobs',[]) or []:
                ok,out,m=handle_job(job)
                try: print(json.dumps(post_json(a.master, a.token, '/api/v2/node/job-result', {'job_id':job.get('id'),'ok':ok,'output':out[-18000:],'metrics':m}), ensure_ascii=False), flush=True)
                except Exception as e: print('job report failed:', e, flush=True)
        except Exception as e:
            exit_code=2
            print('heartbeat failed:', e, flush=True)
        if a.once: break
        time.sleep(60)
    sys.exit(exit_code)
if __name__=='__main__': main()

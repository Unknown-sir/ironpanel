#!/usr/bin/env python3
import argparse, json, os, subprocess, time, urllib.request
from pathlib import Path
VERSION='19.5.0'
STATE=Path('/etc/ironpanel-node')
USERS=STATE/'users'
PROTOCOL_SERVICES={
 'openvpn':['openvpn-server@server','openvpn'], 'wireguard':['wg-quick@wg0','wg-quick@wg-ironpanel'],
 'ocserv':['ocserv'], 'l2tp':['xl2tpd','strongswan'], 'xray':['xray'], 'pptp':['pptpd'],
 'hysteria2':['hysteria-server','hysteria2-server'], 'telegram_proxy':['ironpanel-tgproxy'], 'ssh':['ssh','sshd']
}
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
    return {'version':VERSION,'agent_version':VERSION,'cpu_percent':cpu,'ram_percent':ram,'disk_percent':disk,'traffic_rx_bytes':rx,'traffic_tx_bytes':tx,'public_ip':sh('curl -fsS4 --max-time 3 https://api.ipify.org || true'), 'protocols': os.environ.get('IRONPANEL_NODE_PROTOCOLS','openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh'), 'protocol_health': protocol_health(), 'online_users': online}
def post_json(url, token, path, data):
    req=urllib.request.Request(url.rstrip('/')+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json','X-NODE-TOKEN':token})
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read().decode())
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
    while True:
        try:
            res=post_json(a.master, a.token, '/api/v2/node/heartbeat', metrics())
            print(json.dumps(res, ensure_ascii=False))
            for job in res.get('jobs',[]) or []:
                ok,out,m=handle_job(job)
                try: print(json.dumps(post_json(a.master, a.token, '/api/v2/node/job-result', {'job_id':job.get('id'),'ok':ok,'output':out[-18000:],'metrics':m}), ensure_ascii=False))
                except Exception as e: print('job report failed:', e)
        except Exception as e: print('heartbeat failed:', e)
        if a.once: break
        time.sleep(60)
if __name__=='__main__': main()

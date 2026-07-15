#!/usr/bin/env python3
import argparse, json, os, subprocess, time, urllib.request
from pathlib import Path

VERSION='18.0'

def sh(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=8).strip()
    except Exception as e: return ''

def metrics():
    def pct(path):
        return 0
    cpu=float(sh("python3 - <<'PY'\nimport psutil; print(psutil.cpu_percent(interval=0.2))\nPY") or 0)
    ram=float(sh("python3 - <<'PY'\nimport psutil; print(psutil.virtual_memory().percent)\nPY") or 0)
    disk=float(sh("python3 - <<'PY'\nimport psutil; print(psutil.disk_usage('/').percent)\nPY") or 0)
    rx=int(sh("cat /sys/class/net/$(ip route | awk '/default/ {print $5; exit}')/statistics/rx_bytes 2>/dev/null") or 0)
    tx=int(sh("cat /sys/class/net/$(ip route | awk '/default/ {print $5; exit}')/statistics/tx_bytes 2>/dev/null") or 0)
    return {'version':VERSION,'agent_version':VERSION,'cpu_percent':cpu,'ram_percent':ram,'disk_percent':disk,'traffic_rx_bytes':rx,'traffic_tx_bytes':tx,'public_ip':sh('curl -fsS4 --max-time 3 https://api.ipify.org || true'), 'protocols': os.environ.get('IRONPANEL_NODE_PROTOCOLS','openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2')}

def post(url, token, data):
    req=urllib.request.Request(url.rstrip('/')+'/api/v2/node/heartbeat', data=json.dumps(data).encode(), headers={'Content-Type':'application/json','X-NODE-TOKEN':token})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--master', required=True); ap.add_argument('--token', required=True); ap.add_argument('--once', action='store_true')
    a=ap.parse_args()
    while True:
        try: print(json.dumps(post(a.master, a.token, metrics()), ensure_ascii=False))
        except Exception as e: print('heartbeat failed:', e)
        if a.once: break
        time.sleep(60)
if __name__=='__main__': main()

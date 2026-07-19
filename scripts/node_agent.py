#!/usr/bin/env python3
import argparse, json, os, subprocess, time, urllib.request, urllib.error, ssl, re, sys, shutil, socket, base64, stat
from pathlib import Path
from urllib.parse import urlparse
VERSION='19.8.18'
STATE=Path('/etc/ironpanel-node')
USERS=STATE/'users'
PROTOCOL_SERVICES={
 'openvpn':['openvpn-server@server','openvpn'], 'wireguard':['wg-quick@wg0','wg-quick@wg-ironpanel'],
 'ocserv':['ocserv'], 'l2tp':['xl2tpd','strongswan','strongswan-starter'], 'xray':['xray'], 'pptp':['pptpd'],
 'hysteria2':['hysteria-server','hysteria2-server','hysteria-server@server'], 'telegram_proxy':['ironpanel-tgproxy','mtproxy'], 'ssh':['ssh','sshd']
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
        installed=False
        if proto=='openvpn': installed=bool(sh('command -v openvpn || true'))
        elif proto=='wireguard': installed=bool(sh('command -v wg || true'))
        elif proto=='ocserv': installed=bool(sh('command -v ocserv || true'))
        elif proto=='l2tp': installed=bool(sh('command -v xl2tpd || true'))
        elif proto=='pptp': installed=bool(sh('command -v pptpd || true'))
        elif proto=='xray': installed=bool(sh('command -v xray || test -x /usr/local/bin/xray && echo xray || true'))
        elif proto=='hysteria2': installed=bool(sh('command -v hysteria || command -v hysteria2 || true'))
        elif proto=='telegram_proxy': installed=bool(sh('command -v node || command -v nodejs || true'))
        elif proto=='ssh': installed=bool(sh('command -v sshd || true'))
        out[proto]={'ok':bool(active) or installed,'active':bool(active),'installed':bool(installed),'detail':','.join(active) if active else ('installed' if installed else 'inactive')}
    return out

def _cpu_percent():
    try:
        import psutil
        return float(psutil.cpu_percent(interval=0.2))
    except Exception:
        def read_cpu():
            vals=[int(x) for x in open('/proc/stat').readline().split()[1:]]
            idle=vals[3]+(vals[4] if len(vals)>4 else 0); total=sum(vals); return idle,total
        try:
            i1,t1=read_cpu(); time.sleep(0.2); i2,t2=read_cpu()
            return round(max(0.0, min(100.0, 100.0*(1.0-(i2-i1)/max(1,t2-t1)))), 1)
        except Exception: return 0.0

def _ram_percent():
    try:
        import psutil
        return float(psutil.virtual_memory().percent)
    except Exception:
        try:
            data={}
            for line in open('/proc/meminfo'):
                k,v=line.split(':',1); data[k]=int(v.split()[0])
            total=data.get('MemTotal',0); avail=data.get('MemAvailable',0)
            return round(100.0*(total-avail)/max(1,total),1)
        except Exception: return 0.0

def _disk_percent():
    try:
        import psutil
        return float(psutil.disk_usage('/').percent)
    except Exception:
        try:
            du=shutil.disk_usage('/')
            return round(100.0*du.used/max(1,du.total),1)
        except Exception: return 0.0

def _tcp_ping_ms(master):
    candidates=_master_candidates(master)
    for base in candidates[:4]:
        try:
            p=urlparse(base)
            host=p.hostname; port=p.port or (443 if p.scheme=='https' else 80)
            if not host: continue
            start=time.perf_counter()
            with socket.create_connection((host, port), timeout=2): pass
            return round((time.perf_counter()-start)*1000, 1)
        except Exception:
            continue
    return 0.0

def metrics(master=''):
    iface=sh("ip route | awk '/default/ {print $5; exit}'")
    rx=int(sh(f"cat /sys/class/net/{iface}/statistics/rx_bytes 2>/dev/null") or 0) if iface else 0
    tx=int(sh(f"cat /sys/class/net/{iface}/statistics/tx_bytes 2>/dev/null") or 0) if iface else 0
    online=int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0)
    return {'version':VERSION,'agent_version':VERSION,'cpu_percent':_cpu_percent(),'ram_percent':_ram_percent(),'disk_percent':_disk_percent(),'ping_ms':_tcp_ping_ms(master),'traffic_rx_bytes':rx,'traffic_tx_bytes':tx,'public_ip':sh('curl -fsS4 --max-time 3 https://api.ipify.org || true'), 'protocols': os.environ.get('IRONPANEL_NODE_PROTOCOLS','openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh'), 'protocol_health': protocol_health(), 'online_users': online, 'last_error': LAST_ERROR[:5000]}

def _add(out, url):
    url=(url or '').rstrip('/')
    if url and url not in out:
        out.append(url)

def _is_ip_or_local(host):
    host=(host or '').strip('[]').lower()
    return host in ('localhost','127.0.0.1','::1') or bool(re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', host))

def _master_candidates(raw):
    raw=(raw or '').strip().rstrip('/')
    parsed=urlparse(raw if re.match(r'^https?://', raw, re.I) else '//' + raw)
    scheme=(parsed.scheme or '').lower(); host=parsed.hostname; port=parsed.port
    path='' if not parsed.path or parsed.path=='/' else parsed.path.rstrip('/')
    out=[]
    if host:
        hp=f'[{host}]' if ':' in host and not host.startswith('[') else host
        ipish=_is_ip_or_local(host)
        if scheme == 'https':
            if port:
                # v19.8.16: try the explicitly configured HTTPS URL first.
                # Some panels really listen with TLS on custom ports such as 8001.
                _add(out, raw)
                _add(out, f'http://{hp}:{port}{path}')
            else:
                if ipish:
                    _add(out, raw)
                    for p in (443,8001,8080): _add(out, f'https://{hp}:{p}{path}')
                    for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
                else:
                    _add(out, raw)
                    for p in (443,8001,8080): _add(out, f'https://{hp}:{p}{path}')
                    for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
        elif scheme == 'http':
            _add(out, raw)
            if not port:
                for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
        else:
            for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
            _add(out, 'http://' + raw.lstrip('/'))
    else:
        _add(out, raw if scheme else 'http://' + raw.lstrip('/'))
    return out

def _ssl_context(url):
    if not url.lower().startswith('https://'):
        return None
    insecure=(os.environ.get('IRONPANEL_NODE_INSECURE_TLS','0') == '1') or bool(re.match(r'^https://\d+\.\d+\.\d+\.\d+(:\d+)?(/|$)', url, re.I))
    if insecure:
        return ssl._create_unverified_context()
    return None

def _open(req, base, timeout=8):
    ctx=_ssl_context(base)
    if ctx:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout)

def post_json(url, token, path, data):
    global LAST_ERROR
    errors=[]
    for base in _master_candidates(url):
        try:
            req=urllib.request.Request(base.rstrip('/')+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json','X-NODE-TOKEN':token,'User-Agent':'IronPanel-Node-Agent/'+VERSION})
            r=_open(req, base, timeout=8)
            body=r.read().decode() or '{}'
            LAST_ERROR=''
            if base.rstrip('/') != url.rstrip('/'):
                try: (STATE/'master.resolved').write_text(base.rstrip()+'\n', encoding='utf-8')
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

def _run_node_core_install(protos):
    script=Path('/opt/ironpanel-node/scripts/install_node_cores.sh')
    if not script.exists():
        script=Path(__file__).resolve().parent/'scripts'/'install_node_cores.sh'
    if script.exists():
        return sh(f'bash {script} "{protos}" 2>&1', timeout=900)
    return 'install_node_cores.sh not found'

SAFE_WRITE_PREFIXES = ('/etc/openvpn','/etc/wireguard','/etc/ocserv','/etc/xl2tpd','/etc/ppp','/etc/xray','/usr/local/etc/xray','/etc/hysteria','/etc/hysteria2','/etc/ironpanel','/etc/ssh/sshd_config.d','/etc/systemd/system/ironpanel-tgproxy.service','/opt/ironpanel/scripts')
SAFE_WRITE_FILES = ('/etc/ipsec.conf','/etc/ipsec.secrets','/etc/strongswan.conf','/etc/pptpd.conf','/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json')

def _safe_write_path(path):
    try:
        real=os.path.normpath(str(path))
        return real.startswith(SAFE_WRITE_PREFIXES) or real in SAFE_WRITE_FILES
    except Exception: return False


def _is_local_listen(value):
    v=str(value or '').strip().lower().strip('[]')
    return v in ('127.0.0.1','localhost','::1') or v.startswith('127.')

def _normalize_xray_node_config_file(path):
    p=Path(path)
    if not p.exists() or not p.is_file(): return []
    changed=[]
    try: data=json.loads(p.read_text(encoding='utf-8'))
    except Exception: return []
    for ib in data.get('inbounds') or []:
        if not isinstance(ib, dict): continue
        tag=str(ib.get('tag') or '').lower(); proto=str(ib.get('protocol') or '').lower()
        if 'api' in tag or 'stat' in tag or proto in ('api','dokodemo-door'): continue
        listen=str(ib.get('listen') or '').strip()
        if (not listen) or (not _is_local_listen(listen) and listen not in ('0.0.0.0','::')):
            ib['listen']='0.0.0.0'; changed.append(str(ib.get('port') or ''))
    if changed:
        try: p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception: return []
    return changed

def _normalize_hysteria_node_config_file(path):
    p=Path(path)
    if not p.exists() or not p.is_file(): return []
    try: text=p.read_text(encoding='utf-8', errors='ignore')
    except Exception: return []
    old=text
    def repl(m):
        prefix, host, port=m.group(1), m.group(2), m.group(3)
        if _is_local_listen(host): return m.group(0)
        return f'{prefix}:{port}'
    text=re.sub(r'(?m)^(\s*listen\s*:\s*)(\d{1,3}(?:\.\d{1,3}){3}|\[[0-9a-fA-F:]+\]|[A-Za-z0-9_.-]+):([0-9]{2,5})\s*$', repl, text)
    if text != old:
        try: p.write_text(text, encoding='utf-8'); return [str(p)]
        except Exception: return []
    return []


def _main_host_set_from_bundle(bundle):
    vals=set()
    try:
        for v in (bundle or {}).get('main_server_hosts') or []:
            v=str(v or '').strip().replace('https://','').replace('http://','').split('/')[0].split(':')[0].strip()
            if v: vals.add(v)
    except Exception:
        pass
    return vals

def _normalize_xray_outbounds_for_node(path, main_hosts=None):
    p=Path(path)
    if not p.exists() or not p.is_file(): return []
    changed=[]
    try: data=json.loads(p.read_text(encoding='utf-8'))
    except Exception: return []
    # A main-server config may contain outbound sendThrough bound to the main
    # server IP. That IP does not exist on the node and can make Xray fall back or
    # fail. Remove sendThrough on nodes so egress leaves from the node's own IP.
    for ob in data.get('outbounds') or []:
        if not isinstance(ob, dict): continue
        st=str(ob.get('sendThrough') or '').strip()
        if st:
            ob.pop('sendThrough', None); changed.append('outbound:sendThrough-removed')
        s=ob.get('settings')
        if isinstance(s, dict):
            # Prevent copied main-server reverse/proxy settings from pinning the node back to main.
            for key in ('domainStrategy',):
                pass
    if changed:
        try: p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception: return []
    return changed

def _normalize_node_protocol_configs(protocols, bundle=None):
    protos=set(protocols or []); changed=[]; main_hosts=_main_host_set_from_bundle(bundle)
    if 'xray' in protos:
        for path in ('/usr/local/etc/xray/config.json','/etc/xray/config.json','/etc/ironpanel/xray/config.json'):
            ports=_normalize_xray_node_config_file(path)
            if ports: changed.append(f'xray:{path}:listen=0.0.0.0 ports={",".join(ports)}')
            changed.extend([f'xray:{path}:{x}' for x in _normalize_xray_outbounds_for_node(path, main_hosts)])
    if 'hysteria2' in protos:
        for path in ('/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'):
            changed.extend([f'hysteria2:{x}:listen-wildcard' for x in _normalize_hysteria_node_config_file(path)])
    return changed

def _restart_protocols(protocols):
    sh('systemctl daemon-reload 2>/dev/null || true', timeout=20)
    mapping={
      'openvpn':['openvpn-server@server','openvpn'], 'wireguard':['wg-quick@wg0','wg-quick@wg-ironpanel'],
      'ocserv':['ocserv'], 'l2tp':['strongswan-starter','strongswan','xl2tpd'], 'xray':['xray'], 'pptp':['pptpd'],
      'hysteria2':['hysteria-server','hysteria2-server','hysteria-server@server'], 'telegram_proxy':['ironpanel-tgproxy'], 'ssh':['ssh','sshd']}
    touched=[]
    for proto in protocols or []:
        for svc in mapping.get(proto,[]):
            sh(f'systemctl restart {svc} 2>/dev/null || true', timeout=20); touched.append(svc)
    return touched

def _apply_config_bundle(bundle):
    if not isinstance(bundle, dict): return 'empty bundle'
    files=bundle.get('files') or []
    backup=STATE/'config-backups'/time.strftime('%Y%m%d-%H%M%S')
    written=[]; skipped=[]
    for item in files:
        path=os.path.normpath(str(item.get('path') or ''))
        if not _safe_write_path(path): skipped.append(path); continue
        try:
            data=base64.b64decode(item.get('content_b64') or '')
            target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.is_file():
                bp=backup / path.lstrip('/')
                bp.parent.mkdir(parents=True, exist_ok=True)
                try: shutil.copy2(target, bp)
                except Exception: pass
            target.write_bytes(data)
            try: os.chmod(target, int(item.get('mode') or 0o600))
            except Exception: pass
            written.append(path)
        except Exception as e:
            skipped.append(path+': '+str(e))
    return f'config files written={len(written)} skipped={len(skipped)} backup={backup}\n' + ('\n'.join(skipped[-30:]) if skipped else '')

def handle_job(job):
    action=job.get('action'); payload=job.get('payload') or {}; USERS.mkdir(parents=True, exist_ok=True)
    if action == 'health_check':
        ph=protocol_health()
        return True, json.dumps(ph, ensure_ascii=False), {'protocol_health': ph, 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
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
        protos=str(payload.get('protocols') or os.environ.get('IRONPANEL_NODE_PROTOCOLS',''))
        out=_run_node_core_install(protos)
        return True, 'protocol core install/repair completed\n'+out[-16000:], {'protocol_health': protocol_health(), 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
    if action == 'sync_protocol_configs':
        protos=payload.get('protocols') or []
        if isinstance(protos, str): protos=[x.strip() for x in protos.split(',') if x.strip()]
        before=_run_node_core_install(','.join(protos))
        out=_apply_config_bundle(payload.get('bundle') or {})
        normalized=_normalize_node_protocol_configs(protos, payload.get('bundle') or {})
        # Run the core/firewall installer again after config files are written so
        # dynamic ports from Xray/Hysteria2/Telegram configs are opened on the node.
        after=_run_node_core_install(','.join(protos))
        restarted=_restart_protocols(protos)
        norm_text='\nnormalized:\n' + ('\n'.join(normalized) if normalized else 'no bind changes needed')
        return True, 'pre-install:\n'+before[-4000:]+'\nconfig-sync:\n'+out+norm_text+'\npost-config ports/core:\n'+after[-4000:]+'\nrestarted: ' + ','.join(restarted), {'protocol_health': protocol_health(), 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
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
            res=post_json(a.master, a.token, '/api/v2/node/heartbeat', metrics(a.master))
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

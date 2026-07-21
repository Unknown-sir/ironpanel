#!/usr/bin/env python3
import argparse, json, os, subprocess, time, urllib.request, urllib.error, ssl, re, sys, shutil, socket, base64, stat
from pathlib import Path
from urllib.parse import urlparse
VERSION='19.9.15'
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

def _config_text(paths):
    for raw in paths:
        try:
            p=Path(raw)
            if p.is_file():
                return p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            pass
    return ''


def _text_port(text, pattern, default=0):
    try:
        m=re.search(pattern, text or '', re.I|re.M)
        p=int(m.group(1)) if m else int(default or 0)
        return p if 0 < p <= 65535 else 0
    except Exception:
        return int(default or 0)




def _direct_port_for(proto):
    try:
        data=json.loads(os.environ.get('IRONPANEL_NODE_DIRECT_PORTS_JSON') or '{}')
        port=int(data.get(str(proto)) or 0)
        return port if 0 < port <= 65535 else 0
    except Exception:
        return 0

def _port_listening(port, transport='tcp'):
    try:
        port=int(port or 0)
        if not (0 < port <= 65535): return False
        flag='t' if str(transport).lower() == 'tcp' else 'u'
        return bool(sh(f"ss -H -ln{flag} 'sport = :{port}' 2>/dev/null || true"))
    except Exception:
        return False


def _xray_public_ports():
    for raw in ('/usr/local/etc/xray/config.json','/etc/xray/config.json','/etc/ironpanel/xray/config.json'):
        try:
            data=json.loads(Path(raw).read_text(encoding='utf-8'))
        except Exception:
            continue
        ports=[]
        for ib in data.get('inbounds') or []:
            if not isinstance(ib, dict): continue
            tag=str(ib.get('tag') or '').lower(); proto=str(ib.get('protocol') or '').lower()
            if 'api' in tag or 'stat' in tag or proto in ('api','dokodemo-door'): continue
            try:
                p=int(ib.get('port') or 0)
                if 0 < p <= 65535 and p not in ports: ports.append(p)
            except Exception: pass
        if ports: return ports
    return []


def _json_config_port(paths, default=0):
    for raw in paths:
        try:
            data=json.loads(Path(raw).read_text(encoding='utf-8'))
        except Exception:
            continue
        candidates=[]
        if isinstance(data, dict):
            candidates.append(data.get('port'))
            for key in ('server','listen','mtproxy','telegram_proxy'):
                sub=data.get(key)
                if isinstance(sub, dict):
                    candidates.append(sub.get('port'))
        for value in candidates:
            try:
                p=int(value or 0)
                if 0 < p <= 65535: return p
            except Exception:
                pass
    return int(default or 0)


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
        if proto == 'l2tp':
            active_ok = is_active('xl2tpd') and any(is_active(x) for x in ('strongswan-starter','strongswan','ipsec'))
        else:
            active_ok = bool(active)

        runtime_ok=bool(active_ok)
        detail_parts=[','.join(active) if active else ('installed-not-running' if installed else 'missing')]
        if installed and active_ok and proto == 'ocserv':
            cfg='/etc/ocserv/ocserv.conf'; text=_config_text([cfg])
            direct=_direct_port_for('ocserv')
            tcp=direct or _text_port(text, r'^\s*tcp-port\s*=\s*(\d+)', 8445)
            udp=direct or _text_port(text, r'^\s*udp-port\s*=\s*(\d+)', 0)
            try:
                cfg_ok=Path(cfg).is_file() and not bool(subprocess.run(['ocserv','-t','-c',cfg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15).returncode)
            except Exception:
                cfg_ok=False
            tcp_ok=_port_listening(tcp,'tcp')
            udp_ok=True if udp == 0 else _port_listening(udp,'udp')
            auth_count=0
            try: auth_count=sum(1 for x in Path('/etc/ocserv/ocpasswd').read_text(errors='ignore').splitlines() if x.strip() and not x.lstrip().startswith('#') and ':' in x)
            except Exception: pass
            runtime_ok=bool(cfg_ok and tcp_ok and udp_ok)
            detail_parts.append(f'config={"ok" if cfg_ok else "invalid"};tcp={tcp}:{"listen" if tcp_ok else "closed"};udp={udp}:{"listen" if udp_ok else "closed"};auth-users={auth_count}')
        elif installed and active_ok and proto == 'openvpn':
            text=_config_text(['/etc/openvpn/server/server.conf','/etc/openvpn/server.conf'])
            port=_direct_port_for('openvpn') or _text_port(text, r'^\s*port\s+(\d+)',1194)
            transport='tcp' if re.search(r'^\s*proto\s+tcp', text, re.I|re.M) else 'udp'
            listen_ok=_port_listening(port,transport)
            runtime_ok=bool(listen_ok)
            detail_parts.append(f'{transport}/{port}:{"listen" if listen_ok else "closed"}')
        elif installed and active_ok and proto == 'wireguard':
            iface_ok=bool(sh('wg show wg0 2>/dev/null || wg show wg-ironpanel 2>/dev/null || true'))
            runtime_ok=bool(iface_ok); detail_parts.append('interface=up' if iface_ok else 'interface=missing')
        elif installed and active_ok and proto == 'xray':
            expected=_direct_port_for('xray')
            ports=_xray_public_ports(); listening=[p for p in ports if _port_listening(p,'tcp')]
            runtime_ok=bool((expected and expected in ports and expected in listening) or ((not expected) and ports and listening))
            detail_parts.append(f'expected={expected or "auto"};public-ports={ports};listening={listening}')
        elif installed and active_ok and proto == 'hysteria2':
            text=_config_text(['/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'])
            port=_direct_port_for('hysteria2') or _text_port(text, r'^\s*listen\s*:\s*(?:[^\n:]+:)?(\d+)',4433)
            listen_ok=_port_listening(port,'udp')
            runtime_ok=bool(listen_ok); detail_parts.append(f'udp/{port}:{"listen" if listen_ok else "closed"}')
        elif installed and active_ok and proto == 'telegram_proxy':
            direct=_direct_port_for('telegram_proxy')
            port=direct or _json_config_port(['/opt/ironpanel-telegram-proxy/ironpanel/config.json','/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json'], 6969)
            text=_config_text(['/etc/systemd/system/ironpanel-tgproxy.service','/etc/ironpanel/telegram_proxy.env','/etc/ironpanel/tgproxy.env'])
            port=direct or _text_port(text, r'(?:--port|PORT|IRONPANEL_TGPROXY_PORT|port)\D+(\d+)', port or 6969)
            listen_ok=_port_listening(port,'tcp')
            runtime_ok=bool(listen_ok); detail_parts.append(f'tcp/{port}:{"listen" if listen_ok else "closed"}')
        elif installed and active_ok and proto == 'ssh':
            text=_config_text(['/etc/ssh/sshd_config.d/ironpanel.conf','/etc/ssh/sshd_config'])
            port=_direct_port_for('ssh') or _text_port(text, r'^\s*Port\s+(\d+)',22)
            listen_ok=_port_listening(port,'tcp')
            runtime_ok=bool(listen_ok); detail_parts.append(f'tcp/{port}:{"listen" if listen_ok else "closed"}')
        out[proto]={'ok':bool(runtime_ok),'active':bool(active_ok),'installed':bool(installed),'detail':' | '.join(detail_parts)}
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


def _load_user_metadata():
    out=[]
    try:
        for p in USERS.glob('*.json'):
            try:
                data=json.loads(p.read_text(encoding='utf-8'))
                if isinstance(data, dict): out.append(data)
            except Exception:
                pass
    except Exception:
        pass
    return out


def collect_usage_reports():
    reports=[]
    # Xray Stats API. The master config enables StatsService and deterministic emails.
    out=sh('(xray api statsquery --server=127.0.0.1:10085 -pattern "user>>>" 2>/dev/null || /usr/local/bin/xray api statsquery --server=127.0.0.1:10085 -pattern "user>>>" 2>/dev/null || true)', timeout=6)
    xmap={}
    current=None
    for line in out.splitlines():
        m=re.search(r'name:\s*"([^"]+)"', line) or re.search(r'"name"\s*:\s*"([^"]+)"', line)
        if m:
            current=m.group(1); continue
        m=re.search(r'value:\s*(\d+)', line) or re.search(r'"value"\s*:\s*(\d+)', line)
        if m and current:
            parts=current.split('>>>')
            if len(parts) >= 4 and parts[0]=='user':
                email=parts[1]; direction=parts[-1]
                mm=re.match(r'ip-(\d+)-(.+)', email)
                key=mm.group(1) if mm else email
                row=xmap.setdefault(key, {'user_id': int(mm.group(1)) if mm else 0, 'username': (mm.group(2) if mm else email), 'protocol':'xray', 'rx':0, 'tx':0})
                if direction == 'uplink': row['rx']=int(m.group(1))
                if direction == 'downlink': row['tx']=int(m.group(1))
            current=None
    reports.extend(xmap.values())
    # WireGuard transfer counters, mapped using synced user metadata.
    metas=_load_user_metadata()
    wg_keys={str(m.get('wg_public_key') or ''):m for m in metas if m.get('protocol')=='wireguard' and m.get('wg_public_key')}
    wgout=sh('wg show wg0 transfer 2>/dev/null || true', timeout=4)
    for line in wgout.splitlines():
        parts=line.split()
        if len(parts) >= 3 and parts[0] in wg_keys:
            m=wg_keys[parts[0]]
            try: reports.append({'user_id':int(m.get('user_id') or 0),'username':m.get('username') or '', 'protocol':'wireguard','rx':int(parts[1]),'tx':int(parts[2])})
            except Exception: pass
    # OpenVPN status counters by username/CN.
    for path in ['/var/log/openvpn/status.log','/run/openvpn-server/status-server.log','/etc/openvpn/server/status.log','/var/log/openvpn/openvpn-status.log']:
        try: lines=Path(path).read_text(errors='ignore').splitlines()
        except Exception: continue
        name_to_meta={str(m.get('username') or ''):m for m in metas if m.get('protocol')=='openvpn'}
        in_v1=False
        for line in lines:
            if line.startswith('CLIENT_LIST,'):
                parts=line.split(',')
                if len(parts) >= 7:
                    cn=parts[1].strip(); rx_s,tx_s=parts[5],parts[6]
                elif len(parts) >= 5:
                    cn=parts[1].strip(); rx_s,tx_s=parts[3],parts[4]
                else: continue
                m=name_to_meta.get(cn)
                if m:
                    try: reports.append({'user_id':int(m.get('user_id') or 0),'username':m.get('username') or cn, 'protocol':'openvpn','rx':int(rx_s or 0),'tx':int(tx_s or 0)})
                    except Exception: pass
                continue
            if line.startswith('Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since'):
                in_v1=True; continue
            if line.startswith('ROUTING TABLE'):
                in_v1=False
            if in_v1 and ',' in line and not line.startswith('Updated,'):
                parts=line.split(',')
                if len(parts) >= 4:
                    cn=parts[0].strip(); m=name_to_meta.get(cn)
                    if m:
                        try: reports.append({'user_id':int(m.get('user_id') or 0),'username':m.get('username') or cn, 'protocol':'openvpn','rx':int(parts[2] or 0),'tx':int(parts[3] or 0)})
                        except Exception: pass
        break
    return reports[:2000]

def metrics(master=''):
    iface=sh("ip route | awk '/default/ {print $5; exit}'")
    rx=int(sh(f"cat /sys/class/net/{iface}/statistics/rx_bytes 2>/dev/null") or 0) if iface else 0
    tx=int(sh(f"cat /sys/class/net/{iface}/statistics/tx_bytes 2>/dev/null") or 0) if iface else 0
    online=int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0)
    return {'version':VERSION,'agent_version':VERSION,'cpu_percent':_cpu_percent(),'ram_percent':_ram_percent(),'disk_percent':_disk_percent(),'ping_ms':_tcp_ping_ms(master),'traffic_rx_bytes':rx,'traffic_tx_bytes':tx,'public_ip':sh('curl -fsS4 --max-time 3 https://api.ipify.org || true'), 'protocols': os.environ.get('IRONPANEL_NODE_PROTOCOLS','openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh'), 'protocol_health': protocol_health(), 'online_users': online, 'last_error': LAST_ERROR[:5000], 'usage_reports': collect_usage_reports()}

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
        if scheme in ('http','https'):
            if port:
                # v19.9.15: custom panel ports may terminate HTTP or HTTPS.
                _add(out, f'{scheme}://{hp}:{port}{path}')
                _add(out, f'{"https" if scheme == "http" else "http"}://{hp}:{port}{path}')
            else:
                _add(out, f'{scheme}://{hp}{path}')
                _add(out, f'{"https" if scheme == "http" else "http"}://{hp}{path}')
        if ipish:
            for p in (443,8001,8080): _add(out, f'https://{hp}:{p}{path}')
            for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
        else:
            for p in (443,8001,8080): _add(out, f'https://{hp}:{p}{path}')
            for p in (8001,8080,5000,80): _add(out, f'http://{hp}:{p}{path}')
    else:
        _add(out, raw if scheme else 'http://' + raw.lstrip('/'))
    return out


def _ssl_context(url):
    if not url.lower().startswith('https://'):
        return None
    insecure=(os.environ.get('IRONPANEL_NODE_INSECURE_TLS','0') == '1')
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

def _coerce_direct_ports(direct_ports=None):
    data=direct_ports
    if not data:
        try:
            data=json.loads(os.environ.get('IRONPANEL_NODE_DIRECT_PORTS_JSON') or '{}')
        except Exception:
            data={}
    try:
        out={}
        for k,v in (data or {}).items():
            try:
                iv=int(v)
            except Exception:
                continue
            if 0 < iv <= 65535:
                out[str(k)]=iv
        return out
    except Exception:
        return {}


def _direct_port_env(direct_ports=None):
    env={}
    dp=_coerce_direct_ports(direct_ports)
    if dp:
        env['IRONPANEL_NODE_DIRECT_PORTS_JSON']=json.dumps(dp, separators=(',',':'))
    mapping={
        'openvpn':'OPENVPN_PORT', 'wireguard':'WIREGUARD_PORT', 'ocserv':'OCSERV_PORT',
        'xray':'XRAY_PORT', 'hysteria2':'HYSTERIA2_PORT', 'telegram_proxy':'IRONPANEL_TGPROXY_PORT',
        'ssh':'SSH_PORT', 'pptp':'PPTP_PORT', 'l2tp':'L2TP_PORT',
    }
    for proto,key in mapping.items():
        if dp.get(proto): env[key]=str(dp[proto])
    if dp.get('ocserv'): env['OCSERV_TCP']=str(dp['ocserv']); env['OCSERV_UDP']=str(dp['ocserv'])
    return env


def _run_node_core_install(protos, direct_ports=None):
    script=Path('/opt/ironpanel-node/scripts/install_node_cores.sh')
    if not script.exists():
        script=Path(__file__).resolve().parent/'scripts'/'install_node_cores.sh'
    if not script.exists():
        return 127, 'install_node_cores.sh not found'
    try:
        env=os.environ.copy(); env.update(_direct_port_env(direct_ports))
        proc=subprocess.run(['bash', str(script), str(protos or '')], capture_output=True, text=True, timeout=1200, env=env)
        return int(proc.returncode), ((proc.stdout or '') + (proc.stderr or ''))[-20000:]
    except subprocess.TimeoutExpired as exc:
        out=((exc.stdout or '') if isinstance(exc.stdout, str) else '') + ((exc.stderr or '') if isinstance(exc.stderr, str) else '')
        return 124, ('core install timeout\n' + out)[-20000:]
    except Exception as exc:
        return 125, 'core install exception: ' + str(exc)


def _selected_protocols(value):
    if isinstance(value, str):
        value=value.split(',')
    out=[]
    for proto in value or []:
        proto=str(proto or '').strip()
        if proto in PROTOCOL_SERVICES and proto not in out:
            out.append(proto)
    return out


def _missing_installed_cores(protocols, health=None):
    health=health or protocol_health()
    return [p for p in _selected_protocols(protocols) if not bool((health.get(p) or {}).get('installed'))]

SAFE_WRITE_PREFIXES = ('/etc/openvpn','/etc/wireguard','/etc/ocserv','/etc/xl2tpd','/etc/ppp','/etc/xray','/usr/local/etc/xray','/etc/hysteria','/etc/hysteria2','/etc/ironpanel','/etc/ssh/sshd_config.d','/etc/systemd/system/ironpanel-tgproxy.service','/opt/ironpanel/scripts','/opt/ironpanel-telegram-proxy/ironpanel')
SAFE_WRITE_FILES = ('/etc/ipsec.conf','/etc/ipsec.secrets','/etc/strongswan.conf','/etc/pptpd.conf','/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json')

def _safe_write_path(path):
    try:
        real=os.path.normpath(str(path))
        return real.startswith(SAFE_WRITE_PREFIXES) or real in SAFE_WRITE_FILES
    except Exception: return False


def _is_local_listen(value):
    v=str(value or '').strip().lower().strip('[]')
    return v in ('127.0.0.1','localhost','::1') or v.startswith('127.')

def _normalize_xray_node_config_file(path, public_port=0):
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
        # Public protocol inbounds copied from the main server must listen on
        # the node's interfaces. The previous condition accidentally preserved
        # 127.0.0.1/localhost, so Xray was installed and active but unreachable.
        if listen not in ('0.0.0.0','::'):
            ib['listen']='0.0.0.0'; changed.append(str(ib.get('port') or ''))
        # Direct-location subscriptions can assign a node-specific Xray port.
        # The old code accepted public_port but never applied it, so generated
        # links targeted one port while Xray kept listening on the main port.
        if int(public_port or 0) > 0 and int(ib.get('port') or 0) != int(public_port):
            ib['port']=int(public_port); changed.append(f'port={int(public_port)}')
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
        prefix, _host, port=m.group(1), m.group(2), m.group(3)
        # Bind on every interface. Keeping localhost here made Hysteria healthy
        # in systemd while every external client timed out.
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


def _normalize_text_port_file(path, patterns):
    p=Path(path)
    if not p.exists() or not p.is_file(): return []
    try: text=p.read_text(encoding='utf-8', errors='ignore')
    except Exception: return []
    old=text; changed=[]
    for pattern, repl in patterns:
        text2=re.sub(pattern, repl, text, flags=re.M)
        if text2 != text:
            changed.append(str(path)); text=text2
    if text != old:
        try: p.write_text(text, encoding='utf-8')
        except Exception: return []
    return changed



def _normalize_json_port_file(path, port):
    p=Path(path)
    if not p.exists() or not p.is_file(): return []
    try:
        data=json.loads(p.read_text(encoding='utf-8') or '{}')
    except Exception:
        return []
    try:
        port=int(port or 0)
    except Exception:
        port=0
    if not (1 <= port <= 65535): return []
    changed=False
    if isinstance(data, dict):
        if data.get('port') != port:
            data['port']=port; changed=True
        # A few Telegram proxy forks nest listener settings; keep them aligned.
        for key in ('server','listen','mtproxy','telegram_proxy'):
            sub=data.get(key)
            if isinstance(sub, dict) and sub.get('port') != port:
                sub['port']=port; changed=True
    if changed:
        try:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            return [str(p)]
        except Exception:
            return []
    return []

def _normalize_node_direct_ports(protocols, direct_ports):
    changed=[]
    dp=_coerce_direct_ports(direct_ports)
    if 'openvpn' in protocols and dp.get('openvpn'):
        port=str(dp['openvpn']);
        for path in ('/etc/openvpn/server/server.conf','/etc/openvpn/server.conf'):
            for x in _normalize_text_port_file(path, [(r'^port\s+\d+\s*$', f'port {port}')]): changed.append(f'openvpn:{x}:port={port}')
    if 'wireguard' in protocols and dp.get('wireguard'):
        port=str(dp['wireguard']);
        for path in ('/etc/wireguard/wg0.conf','/etc/wireguard/wg-ironpanel.conf'):
            for x in _normalize_text_port_file(path, [(r'^ListenPort\s*=\s*\d+\s*$', f'ListenPort = {port}')]): changed.append(f'wireguard:{x}:ListenPort={port}')
    if 'ocserv' in protocols:
        port=str(dp.get('ocserv') or '')
        pats=[
            (r'^connect-script\s*=.*ocserv_session_hook\.sh.*$', ''),
            (r'^disconnect-script\s*=.*ocserv_session_hook\.sh.*$', ''),
        ]
        if port:
            pats.extend([(r'^tcp-port\s*=\s*\d+\s*$', f'tcp-port = {port}'),(r'^udp-port\s*=\s*\d+\s*$', f'udp-port = {port}')])
        for path in ('/etc/ocserv/ocserv.conf',):
            for x in _normalize_text_port_file(path, pats): changed.append(f'ocserv:{x}:safe-config{(":port="+port) if port else ""}')
    if 'hysteria2' in protocols and dp.get('hysteria2'):
        port=str(dp['hysteria2']);
        pats=[(r'^(\s*listen\s*:\s*)(?:[^\n:]+:)?\d+\s*$', r'\g<1>:%s'%port),(r'^(\s*addr\s*:\s*)(?:[^\n:]+:)?\d+\s*$', r'\g<1>:%s'%port)]
        for path in ('/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'):
            for x in _normalize_text_port_file(path, pats): changed.append(f'hysteria2:{x}:port={port}')
    if 'telegram_proxy' in protocols and dp.get('telegram_proxy'):
        port=str(dp['telegram_proxy'])
        for path in ('/opt/ironpanel-telegram-proxy/ironpanel/config.json','/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json'):
            for x in _normalize_json_port_file(path, port): changed.append(f'telegram_proxy:{x}:json-port={port}')
        pats=[(r'^(\s*PORT\s*=\s*)\d+\s*$', r'\g<1>'+port),(r'^(\s*IRONPANEL_TGPROXY_PORT\s*=\s*)\d+\s*$', r'\g<1>'+port),(r'(--port\s+)\d+', r'\g<1>'+port)]
        for path in ('/etc/ironpanel/telegram_proxy.env','/etc/ironpanel/tgproxy.env','/etc/systemd/system/ironpanel-tgproxy.service'):
            for x in _normalize_text_port_file(path, pats): changed.append(f'telegram_proxy:{x}:port={port}')
    if 'ssh' in protocols and dp.get('ssh'):
        port=str(dp['ssh'])
        for path in ('/etc/ssh/sshd_config.d/ironpanel.conf','/etc/ssh/sshd_config'):
            for x in _normalize_text_port_file(path, [(r'^Port\s+\d+\s*$', f'Port {port}')]): changed.append(f'ssh:{x}:port={port}')
    return changed

def _normalize_node_protocol_configs(protocols, bundle=None, direct_ports=None):
    protos=set(protocols or []); changed=[]; main_hosts=_main_host_set_from_bundle(bundle)
    if 'xray' in protos:
        for path in ('/usr/local/etc/xray/config.json','/etc/xray/config.json','/etc/ironpanel/xray/config.json'):
            ports=_normalize_xray_node_config_file(path, int((direct_ports or {}).get('xray') or 0))
            if ports: changed.append(f'xray:{path}:listen=0.0.0.0 ports={",".join(ports)}')
            changed.extend([f'xray:{path}:{x}' for x in _normalize_xray_outbounds_for_node(path, main_hosts)])
    if 'hysteria2' in protos:
        for path in ('/etc/hysteria/config.yaml','/etc/hysteria2/config.yaml','/etc/hysteria/server.yaml','/etc/hysteria2/server.yaml'):
            changed.extend([f'hysteria2:{x}:listen-wildcard' for x in _normalize_hysteria_node_config_file(path)])
    changed.extend(_normalize_node_direct_ports(protos, direct_ports or {}))
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



def _safe_user_name(value):
    return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in str(value or 'user')) or 'user'


def _write_user_metadata(payload):
    username=_safe_user_name(payload.get('username') or 'user')
    proto=str(payload.get('protocol') or 'all')
    target=USERS/f'{username}.{proto}.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    try: os.chmod(target, 0o600)
    except Exception: pass
    return str(target)


def _metadata_rows(protocols=None):
    selected=set(_selected_protocols(protocols or [])) if protocols else None
    rows=[]
    for path in USERS.glob('*.json'):
        try:
            item=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(item, dict): continue
            proto=str(item.get('protocol') or '')
            if selected is None or proto in selected:
                rows.append(item)
        except Exception:
            continue
    return rows


def _prune_stale_user_metadata(users, protocols):
    selected=set(_selected_protocols(protocols or []))
    wanted=set()
    for item in users or []:
        if not isinstance(item, dict): continue
        proto=str(item.get('protocol') or '')
        if proto not in selected: continue
        wanted.add(f"{_safe_user_name(item.get('username') or 'user')}.{proto}.json")
    removed=[]
    for path in USERS.glob('*.json'):
        try:
            name=path.name
            proto=name.rsplit('.', 2)[-2] if name.endswith('.json') and name.count('.') >= 2 else ''
            if proto in selected and name not in wanted:
                path.unlink(missing_ok=True); removed.append(name)
        except Exception:
            pass
    return removed


def _clean_auth(value, fallback='managed-by-panel'):
    return str(value or fallback).replace('\r','').replace('\n','')


def _ocserv_password_hash(password):
    password=str(password or 'managed-by-panel')
    try:
        import crypt
        salt=crypt.mksalt(crypt.METHOD_SHA512)
        hashed=crypt.crypt(password, salt)
        if hashed and hashed != password and hashed.startswith('$6$'):
            return hashed
    except Exception:
        pass
    proc=subprocess.run(['openssl','passwd','-6','-stdin'], input=password+'\n', capture_output=True, text=True, timeout=10)
    hashed=(proc.stdout or '').strip()
    if proc.returncode == 0 and hashed.startswith('$6$'):
        return hashed
    raise RuntimeError((proc.stderr or proc.stdout or 'unable to generate SHA-512 crypt hash')[-300:])



def _write_ocserv_password_file(target, credentials):
    target=Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp=target.with_name('.ocpasswd.node.tmp')
    tmp.unlink(missing_ok=True)
    credentials=[(_clean_auth(u,'user').replace(':','_'), _clean_auth(p)) for u,p in (credentials or [])]
    ocpasswd=shutil.which('ocpasswd')
    if ocpasswd:
        first=True
        for username,password in credentials:
            # ocpasswd requires -c <file> on every invocation.
            cmd=[ocpasswd, '-c', str(tmp), username]
            proc=subprocess.run(cmd, input=password+'\n'+password+'\n', capture_output=True, text=True, timeout=25)
            if proc.returncode != 0:
                tmp.unlink(missing_ok=True)
                raise RuntimeError((proc.stderr or proc.stdout or f'ocpasswd failed for {username}')[-500:])
            first=False
        if first:
            tmp.write_text('', encoding='utf-8')
    else:
        tmp.write_text(''.join(f'{username}:ironpanel:{_ocserv_password_hash(password)}\n' for username,password in credentials), encoding='utf-8')
    os.chmod(tmp,0o600); tmp.replace(target); os.chmod(target,0o600)
    return len(credentials)

def _mirror_ocserv_legacy_path(canonical):
    legacy=Path('/etc/ironpanel/ocpasswd')
    try:
        if legacy.exists() or legacy.is_symlink(): legacy.unlink()
        legacy.symlink_to(canonical)
    except Exception:
        try:
            legacy.write_text(Path(canonical).read_text(encoding='utf-8'), encoding='utf-8')
            os.chmod(legacy,0o600)
        except Exception:
            pass


def _rebuild_plain_auth_from_metadata(protocols):
    selected=set(_selected_protocols(protocols or []))
    # Load all metadata. A partial L2TP sync must not erase PPTP credentials (or
    # vice versa) because both protocols share /etc/ppp/chap-secrets.
    rows=_metadata_rows()
    details=[]; errors=[]
    Path('/etc/ironpanel').mkdir(parents=True, exist_ok=True)

    if 'ocserv' in selected:
        oc_rows=[r for r in rows if str(r.get('protocol') or '') == 'ocserv' and bool(r.get('enabled', True))]
        target=Path('/etc/ocserv/ocpasswd')
        credentials=[]
        for item in oc_rows:
            username=_clean_auth(item.get('username'), 'user').replace(':','_')
            password=_clean_auth(item.get('cisco_password') or item.get('l2tp_password'))
            credentials.append((username,password))
        try:
            _write_ocserv_password_file(target, credentials)
            _mirror_ocserv_legacy_path(target)
            details.append(f'ocserv-users={len(oc_rows)}')
        except Exception as exc:
            errors.append(f'ocpasswd rebuild: {exc}')
            if not target.exists(): target.touch(mode=0o600)
            _mirror_ocserv_legacy_path(target)

    if selected.intersection({'l2tp','pptp'}):
        lines=[]
        for item in rows:
            proto=str(item.get('protocol') or '')
            if proto not in ('l2tp','pptp') or not bool(item.get('enabled', True)): continue
            username=_clean_auth(item.get('username'),'user').replace('"','')
            password=_clean_auth(item.get('l2tp_password') or item.get('cisco_password')).replace('"','')
            service='l2tpd' if proto == 'l2tp' else 'pptpd'
            lines.append(f'"{username}" {service} "{password}" *\n')
        chap=Path('/etc/ppp/chap-secrets'); chap.parent.mkdir(parents=True, exist_ok=True)
        tmp=chap.with_name('.chap-secrets.ironpanel-node.tmp')
        tmp.write_text(''.join(lines), encoding='utf-8'); os.chmod(tmp,0o600); tmp.replace(chap)
        details.append(f'ppp-users={len(lines)}')

    return not errors, ', '.join(details) if details else 'no plain-auth protocols', errors


def _sync_ssh_account(payload):
    account=_safe_user_name(payload.get('ssh_account') or '')[:31]
    password=str(payload.get('ssh_password') or '')
    enabled=bool(payload.get('enabled', True))
    if not account or not password:
        return False, 'missing ssh_account/ssh_password'
    try:
        subprocess.run(['groupadd','-r','ironpanel-ssh'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=15)
        exists=subprocess.run(['id','-u',account], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=10).returncode == 0
        comment=f"IronPanel SSH user {int(payload.get('user_id') or 0)}:{str(payload.get('username') or '')}"
        cmd=['usermod','-g','ironpanel-ssh','-s','/bin/bash','-c',comment,account] if exists else ['useradd','-m','-s','/bin/bash','-g','ironpanel-ssh','-c',comment,account]
        proc=subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or 'useradd/usermod failed')[-1000:]
        proc=subprocess.run(['chpasswd'], input=f'{account}:{password}\n', capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or 'chpasswd failed')[-1000:]
        subprocess.run(['passwd','-u' if enabled else '-l',account], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=10)
        return True, f'ssh account {account} {"enabled" if enabled else "locked"}'
    except Exception as exc:
        return False, 'ssh account sync exception: ' + str(exc)


def _lock_stale_ssh_accounts(wanted):
    locked=[]
    try:
        for line in Path('/etc/passwd').read_text(errors='ignore').splitlines():
            parts=line.split(':')
            if len(parts) < 5 or not str(parts[4]).startswith('IronPanel SSH user '):
                continue
            account=parts[0]
            if account not in wanted:
                subprocess.run(['passwd','-l',account], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=10)
                locked.append(account)
    except Exception:
        pass
    return locked


def _node_sync_state(extra=None):
    data={'synced_at':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'version':VERSION}
    if isinstance(extra, dict): data.update(extra)
    try:
        (STATE/'last_full_sync.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass

def handle_job(job):
    action=job.get('action'); payload=job.get('payload') or {}; USERS.mkdir(parents=True, exist_ok=True)
    if action == 'health_check':
        ph=protocol_health()
        return True, json.dumps(ph, ensure_ascii=False), {'protocol_health': ph, 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
    if action == 'sync_user':
        path=_write_user_metadata(payload)
        proto=str(payload.get('protocol') or '')
        details=[f'user metadata synced: {path}']; ok=True
        if proto == 'ssh':
            ssh_ok, ssh_detail=_sync_ssh_account(payload); ok=ok and ssh_ok; details.append(ssh_detail)
        if proto in ('ocserv','l2tp','pptp'):
            auth_ok, auth_detail, auth_errors=_rebuild_plain_auth_from_metadata([proto])
            ok=ok and auth_ok; details.append(auth_detail)
            details.extend(auth_errors)
        return ok, '\n'.join(details), {}
    if action == 'sync_users_bulk':
        users=payload.get('users') or []
        written=[]; errors=[]; wanted_ssh=set()
        if not isinstance(users, list): users=[]
        for item in users:
            if not isinstance(item, dict):
                continue
            try:
                written.append(_write_user_metadata(item))
                if str(item.get('protocol') or '') == 'ssh':
                    account=_safe_user_name(item.get('ssh_account') or '')[:31]
                    if account and bool(item.get('enabled', True)): wanted_ssh.add(account)
                    ssh_ok, ssh_detail=_sync_ssh_account(item)
                    if not ssh_ok: errors.append(ssh_detail)
            except Exception as exc:
                errors.append(str(exc)[:500])
        selected=_selected_protocols(payload.get('protocols') or [])
        pruned=_prune_stale_user_metadata(users, selected)
        auth_ok, auth_detail, auth_errors=_rebuild_plain_auth_from_metadata(selected)
        errors.extend(auth_errors)
        stale_locked=_lock_stale_ssh_accounts(wanted_ssh) if 'ssh' in selected else []
        manifest={'count':len(written), 'protocols':selected, 'reason':payload.get('reason') or '', 'written':written[-500:], 'pruned':pruned[-500:], 'auth':auth_detail, 'ssh_accounts':sorted(wanted_ssh), 'stale_ssh_locked':stale_locked, 'errors':errors[-50:]}
        ok=not errors
        _node_sync_state({'users_count':len(written), 'protocols':payload.get('protocols') or [], 'user_sync_ok':ok, 'user_sync_errors':errors[-20:]})
        return ok, 'bulk users synced to node runtime: '+json.dumps(manifest, ensure_ascii=False)[:12000], {'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
    if action == 'delete_user':
        username=_safe_user_name(payload.get('username') or 'user')
        removed=[]
        for p in USERS.glob(f'{username}.*.json'):
            removed.append(p.name); p.unlink(missing_ok=True)
        auth_ok, auth_detail, auth_errors=_rebuild_plain_auth_from_metadata(['ocserv','l2tp','pptp'])
        return auth_ok, f'user {username} deleted; files={removed}; {auth_detail}; errors={auth_errors}', {}
    if action == 'ensure_protocols':
        protos=_selected_protocols(payload.get('protocols') or os.environ.get('IRONPANEL_NODE_PROTOCOLS',''))
        rc,out=_run_node_core_install(','.join(protos), payload.get('direct_ports') or {})
        ph=protocol_health(); missing=_missing_installed_cores(protos, ph)
        ok=(rc == 0 and not missing)
        detail=('protocol core install/repair ' + ('verified' if ok else 'failed') +
                f' (exit={rc}, missing={",".join(missing) or "none"})\n' + out[-16000:])
        return ok, detail, {'protocol_health': ph, 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
    if action == 'sync_protocol_configs':
        protos=_selected_protocols(payload.get('protocols') or [])
        direct_ports=payload.get('direct_ports') or {}
        pre_rc,before=_run_node_core_install(','.join(protos), direct_ports)
        out=_apply_config_bundle(payload.get('bundle') or {})
        normalized=_normalize_node_protocol_configs(protos, payload.get('bundle') or {}, direct_ports)
        auth_ok, auth_detail, auth_errors=_rebuild_plain_auth_from_metadata(protos)
        post_rc,after=_run_node_core_install(','.join(protos), direct_ports)
        restarted=_restart_protocols(protos)
        ph=protocol_health(); missing=_missing_installed_cores(protos, ph)
        inactive=[p for p in protos if (ph.get(p) or {}).get('installed') and not (ph.get(p) or {}).get('active')]
        unhealthy=[p for p in protos if (ph.get(p) or {}).get('installed') and not (ph.get(p) or {}).get('ok')]
        ok=(pre_rc == 0 and post_rc == 0 and auth_ok and not missing and not inactive and not unhealthy)
        _node_sync_state({'protocols':protos, 'protocol_health':ph, 'sync_ok':ok, 'missing':missing, 'inactive':inactive, 'unhealthy':unhealthy})
        norm_text='\nnormalized:\n' + ('\n'.join(normalized) if normalized else 'no bind changes needed')
        auth_text='\nauth-sync: '+auth_detail + ((' errors='+json.dumps(auth_errors, ensure_ascii=False)) if auth_errors else '')
        summary=f'\nverification: ok={ok} pre_exit={pre_rc} post_exit={post_rc} missing={",".join(missing) or "none"} inactive={",".join(inactive) or "none"} unhealthy={",".join(unhealthy) or "none"}'
        detail=('pre-install:\n'+before[-4000:]+'\nconfig-sync:\n'+out+norm_text+auth_text+
                '\npost-config ports/core:\n'+after[-4000:]+'\nrestarted: ' + ','.join(restarted) + summary)
        return ok, detail, {'protocol_health': ph, 'online_users': int(sh("ss -ntu state established 2>/dev/null | tail -n +2 | wc -l") or 0), 'cpu_percent': _cpu_percent(), 'ram_percent': _ram_percent(), 'disk_percent': _disk_percent()}
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
            jobs=res.get('jobs',[]) or []
            job_failures=[]
            for job in jobs:
                ok,out,m=handle_job(job)
                if not ok:
                    exit_code=3
                    job_failures.append({'id':job.get('id'),'action':job.get('action'),'output':str(out or '')[-4000:]})
                try:
                    print(json.dumps(post_json(a.master, a.token, '/api/v2/node/job-result', {'job_id':job.get('id'),'ok':ok,'output':out[-18000:],'metrics':m}), ensure_ascii=False), flush=True)
                except Exception as e:
                    exit_code=4
                    job_failures.append({'id':job.get('id'),'action':job.get('action'),'output':'job report failed: '+str(e)})
                    print('job report failed:', e, flush=True)
            failure_file=STATE/'last_job_failure.json'
            if jobs:
                if job_failures:
                    failure_file.write_text(json.dumps({'failed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'failures':job_failures}, ensure_ascii=False, indent=2), encoding='utf-8')
                else:
                    failure_file.unlink(missing_ok=True)
        except Exception as e:
            exit_code=2
            print('heartbeat failed:', e, flush=True)
        if a.once: break
        time.sleep(int(os.environ.get('IRONPANEL_NODE_HEARTBEAT_INTERVAL','60') or 60))
    sys.exit(exit_code)
if __name__=='__main__': main()

import json, subprocess, re, base64, os, stat
from datetime import datetime
from pathlib import Path
from ..core.extensions import db
from ..core.models import Node, AppSetting, OnlineSession, VpnUser, RemoteJob
from .provisioning import set_setting, get_port, run_cmd

PROTOCOLS = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
LABELS = {'openvpn':'OpenVPN','wireguard':'WireGuard','ocserv':'Cisco/Ocserv','l2tp':'L2TP/IPsec','xray':'Xray','pptp':'PPTP','hysteria2':'Hysteria2','telegram_proxy':'Telegram Proxy','ssh':'SSH'}
ICONS = {'openvpn':'🔐','wireguard':'🧬','ocserv':'🛡️','l2tp':'🌉','xray':'⚡','pptp':'🧩','hysteria2':'🚀','telegram_proxy':'✈️','ssh':'⌨️'}
PORT_DEFAULTS = {'openvpn_udp':1194,'openvpn_tcp':1195,'wireguard_udp':51820,'ocserv_tcp':443,'ocserv_udp':443,'l2tp_udp':1701,'ipsec_ike':500,'ipsec_nat':4500,'xray_tcp':443,'pptp_tcp':1723,'hysteria2_udp':443,'telegram_proxy_base':6969,'ssh_tcp':422}
STATE_DIR=Path('/etc/ironpanel')
PLAN_FILE=STATE_DIR/'node-gateway-plan.json'

def _setting(key, default=''):
    row=AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None,'') else default

def _json_setting(key, default):
    try: return json.loads(_setting(key, json.dumps(default)))
    except Exception: return default

def _port_value(key):
    try: return int(get_port(key, PORT_DEFAULTS.get(key, 0)) or PORT_DEFAULTS.get(key, 0))
    except Exception: return int(PORT_DEFAULTS.get(key, 0) or 0)

def protocol_port_entries(protocol):
    """Return every real port that must be forwarded for a protocol.

    v19.8.14: fixed-only node routing must be a real gateway. Older builds
    stored only one legacy port/transport, so OpenVPN UDP, Ocserv UDP, L2TP
    IPsec ports, PPTP GRE, etc. were not fully forwarded.
    """
    if protocol == 'openvpn':
        entries=[]
        udp=_port_value('openvpn_udp'); tcp=_port_value('openvpn_tcp')
        if udp: entries.append({'proto':'udp','port':udp})
        if tcp and tcp != udp: entries.append({'proto':'tcp','port':tcp})
        return entries
    if protocol == 'wireguard': return [{'proto':'udp','port':_port_value('wireguard_udp')}]
    if protocol == 'ocserv':
        tcp=_port_value('ocserv_tcp'); udp=_port_value('ocserv_udp')
        return [{'proto':'tcp','port':tcp},{'proto':'udp','port':udp}] if tcp==udp else [{'proto':'tcp','port':tcp},{'proto':'udp','port':udp}]
    if protocol == 'l2tp': return [{'proto':'udp','port':_port_value('ipsec_ike')},{'proto':'udp','port':_port_value('ipsec_nat')},{'proto':'udp','port':_port_value('l2tp_udp')}]
    if protocol == 'xray': return [{'proto':'tcp','port':_port_value('xray_tcp')}]
    if protocol == 'pptp': return [{'proto':'tcp','port':_port_value('pptp_tcp')},{'proto':'gre','port':0}]
    if protocol == 'hysteria2': return [{'proto':'udp','port':_port_value('hysteria2_udp')}]
    if protocol == 'telegram_proxy': return [{'proto':'tcp','port':_port_value('telegram_proxy_base')}]
    if protocol == 'ssh': return [{'proto':'tcp','port':_port_value('ssh_tcp')}]
    return []

def _port(protocol):
    entries=protocol_port_entries(protocol)
    return int(entries[0]['port']) if entries else 0

def _transport_label(protocol):
    entries=protocol_port_entries(protocol)
    protos=[]
    for e in entries:
        pr=e.get('proto')
        if pr not in protos: protos.append(pr)
    return '+'.join(protos) if protos else '-'

def _ports_label(protocol):
    parts=[]
    for e in protocol_port_entries(protocol):
        pr=e.get('proto'); po=int(e.get('port') or 0)
        parts.append(pr.upper() if pr=='gre' else f"{po}/{pr}")
    return ', '.join(parts)

def clean_host(host):
    host=str(host or '').replace('https://','').replace('http://','').split('/')[0]
    if '@' in host: host=host.split('@')[-1]
    return host.split(':')[0].strip()

def _node_online(n):
    h=(n.health or '').lower()
    if h in ('local','healthy','ok'): return True
    if h == 'online':
        if not n.last_seen: return True
        try: return (datetime.utcnow()-n.last_seen).total_seconds() < 240
        except Exception: return True
    return False

def _node_supports(n, protocol):
    parts=[x.strip() for x in (n.protocols or '').split(',') if x.strip()]
    return (not parts) or protocol in parts

def _protocol_ok(n, protocol):
    try:
        data=json.loads(getattr(n, 'protocol_health_json', '') or '{}')
        v=data.get(protocol)
        if isinstance(v, dict): return bool(v.get('ok', False))
        if isinstance(v, bool): return v
    except Exception: pass
    return _node_supports(n, protocol)

def _online_count(node_id, protocol=None):
    try:
        q=OnlineSession.query.filter_by(active=True, node_id=node_id)
        if protocol: q=q.filter_by(protocol=protocol)
        return q.count()
    except Exception: return 0

def _ping_ms(host):
    host=clean_host(host)
    if not host: return 9999.0
    try:
        p=subprocess.run(['ping','-c','1','-W','1',host], capture_output=True, text=True, timeout=2)
        m=re.search(r'time[=<]([0-9.]+)\s*ms', p.stdout+p.stderr)
        return float(m.group(1)) if m else 9999.0
    except Exception: return 9999.0

def _node_ping(n):
    cached=float(getattr(n,'ping_ms',0) or 0)
    if cached > 0 and _setting('node_gateway_live_ping','0')!='1': return cached
    ping=_ping_ms(n.host)
    try:
        n.ping_ms=ping; db.session.commit()
    except Exception: db.session.rollback()
    return ping

def _node_load_score(n, protocol):
    users=max(_online_count(n.id, protocol), int(getattr(n,'online_users',0) or 0))
    ping=_node_ping(n); cpu=float(getattr(n,'cpu_percent',0) or 0); ram=float(getattr(n,'ram_percent',0) or 0)
    weight=max(1, int(getattr(n,'weight',100) or 100))
    return (users*20 + ping/5 + cpu/10 + ram/20) / (weight/100)

def node_gateway_settings():
    rules=_json_setting('node_gateway_rules', {})
    nodes=Node.query.order_by(Node.name).all()
    rows=[]
    for p in PROTOCOLS:
        r=rules.get(p,{}) if isinstance(rules,dict) else {}
        candidates=[]
        for n in nodes:
            if _node_supports(n,p):
                candidates.append({'id':n.id,'name':n.name,'host':n.host,'health':n.health,'online':_node_online(n),'protocol_ok':_protocol_ok(n,p),'users':_online_count(n.id,p),'ping_ms':_node_ping(n) if _setting('node_gateway_live_ping','0')=='1' else getattr(n,'ping_ms',None),'score':round(_node_load_score(n,p),1)})
        rows.append({'protocol':p,'label':LABELS.get(p,p),'icon':ICONS.get(p,'•'),'port':_port(p),'ports':protocol_port_entries(p),'ports_label':_ports_label(p),'transport':_transport_label(p),'enabled':bool(r.get('enabled')),'mode':r.get('mode','local'),'node_id':int(r.get('node_id') or 0),'strategy':r.get('strategy', _setting('node_gateway_strategy','balanced')),'candidates':candidates})
    return {'enabled':_setting('node_gateway_enabled','0')=='1','strategy':_setting('node_gateway_strategy','balanced'),'live_ping':_setting('node_gateway_live_ping','0')=='1','failover':_setting('node_failover_enabled','1')=='1','auto_sync':_setting('node_auto_sync_enabled','1')=='1','notes':_setting('node_gateway_notes',''),'rules':rules if isinstance(rules,dict) else {},'rows':rows}

def save_node_gateway_settings(form):
    set_setting('node_gateway_enabled','1' if form.get('node_gateway_enabled')=='1' else '0')
    set_setting('node_gateway_strategy', form.get('node_gateway_strategy') or 'balanced')
    set_setting('node_gateway_live_ping','1' if form.get('node_gateway_live_ping')=='1' else '0')
    set_setting('node_failover_enabled','1' if form.get('node_failover_enabled')=='1' else '0')
    set_setting('node_auto_sync_enabled','1' if form.get('node_auto_sync_enabled')=='1' else '0')
    set_setting('node_gateway_notes',(form.get('node_gateway_notes') or '')[:2000])
    rules={}
    for p in PROTOCOLS:
        mode=form.get(f'mode_{p}','local')
        try: node_id=int(form.get(f'node_{p}') or 0)
        except Exception: node_id=0
        
        if mode not in ('local','fixed','auto','fixed_only'):
            mode='local'
        rules[p]={'enabled':form.get(f'enabled_{p}')=='1' and mode!='local','mode':mode,'node_id':node_id,'strategy':form.get(f'strategy_{p}') or form.get('node_gateway_strategy') or 'balanced','strict': mode=='fixed_only'}
    set_setting('node_gateway_rules', json.dumps(rules, ensure_ascii=False)); db.session.commit(); return rules

def _eligible(protocol):
    out=[]
    for n in Node.query.order_by(Node.id).all():
        if not (_node_online(n) and _node_supports(n,protocol) and _protocol_ok(n,protocol)): continue
        max_users=int(getattr(n,'max_users',0) or 0)
        if max_users and _online_count(n.id) >= max_users: continue
        out.append(n)
    return out

def select_node_for_protocol(protocol, rules=None):
    rules=rules or _json_setting('node_gateway_rules', {})
    rule=(rules or {}).get(protocol,{}) if isinstance(rules,dict) else {}
    if not rule.get('enabled') or rule.get('mode')=='local': return None, 'local'
    if rule.get('mode')=='fixed_only' and int(rule.get('node_id') or 0):
        node=Node.query.get(int(rule.get('node_id')))
        # Strict mode means this protocol must go only to the selected node.
        # It intentionally does not fail over to Local/other nodes, and it can
        # route even when protocol health is still being refreshed.
        if node and _node_supports(node, protocol): return node, 'fixed_only'
        return None, 'fixed-only-node-not-usable'
    nodes=_eligible(protocol)
    if not nodes: return None, 'no-online-node'
    if rule.get('mode')=='fixed' and int(rule.get('node_id') or 0):
        node=Node.query.get(int(rule.get('node_id')))
        if node and node in nodes: return node, 'fixed'
        if _setting('node_failover_enabled','1')!='1': return None, 'fixed-node-offline'
    strategy=rule.get('strategy') or _setting('node_gateway_strategy','balanced')
    if strategy=='best_ping': return sorted(nodes, key=lambda n: (_node_ping(n), _online_count(n.id,protocol), n.id))[0], 'best_ping'
    if strategy=='least_users': return sorted(nodes, key=lambda n: (_online_count(n.id,protocol), _node_ping(n), n.id))[0], 'least_users'
    return sorted(nodes, key=lambda n: (_node_load_score(n,protocol), n.id))[0], 'balanced'

def select_node_for_user(user, protocol):
    mode=getattr(user,'node_mode',None) or 'auto'
    preferred=int(getattr(user,'preferred_node_id',0) or 0)
    if mode == 'local': return None, 'user-local'
    if mode == 'fixed' and preferred:
        n=Node.query.get(preferred)
        if n and _node_online(n) and _node_supports(n,protocol) and _protocol_ok(n,protocol): return n, 'user-fixed'
        if _setting('node_failover_enabled','1')!='1': return None, 'user-fixed-offline'
    return select_node_for_protocol(protocol)

def node_gateway_plan():
    s=node_gateway_settings(); plan=[]
    for row in s['rows']:
        node,reason=select_node_for_protocol(row['protocol'], s['rules'])
        plan.append({'protocol':row['protocol'],'label':row['label'],'port':row['port'],'ports':row.get('ports') or protocol_port_entries(row['protocol']),'ports_label':row.get('ports_label') or _ports_label(row['protocol']),'transport':row['transport'],'enabled':row['enabled'],'mode':row['mode'],'selected_node_id':node.id if node else None,'selected_node_name':node.name if node else 'Local / Direct','selected_node_host':node.host if node else '', 'reason':reason})
    return plan

def _panel_ports_for_gateway():
    ports=set()
    try:
        pp=int(get_port('panel') or 0)
        if pp: ports.add(pp)
    except Exception:
        pass
    for k in ('panel_port','web_port'):
        try:
            v=int(_setting(k, '0') or 0)
            if v: ports.add(v)
        except Exception:
            pass
    return sorted(ports)

def write_node_gateway_runtime():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    plan=node_gateway_plan()
    PLAN_FILE.write_text(json.dumps({'generated_at':datetime.utcnow().isoformat(),'panel_ports':_panel_ports_for_gateway(),'plan':plan}, ensure_ascii=False, indent=2), encoding='utf-8')
    return True, 'Node Gateway runtime plan generated', plan

def apply_node_gateway_runtime():
    ok,msg,plan=write_node_gateway_runtime()
    script=Path('/opt/ironpanel/scripts/apply_node_gateway.sh')
    if not script.exists(): script=Path(__file__).resolve().parents[2] / 'scripts' / 'apply_node_gateway.sh'
    if _setting('node_gateway_enabled','0')=='1':
        p=run_cmd(['bash', str(script), '--apply'], timeout=120)
        out=(p.stdout or '')+(p.stderr or '')
        
        queued=queue_gateway_config_sync_from_plan(plan) if p.returncode==0 else 0
        msg='Node Gateway plan applied; real port forwarding is active' + (f' and {queued} config/core sync job(s) queued' if queued else '') if p.returncode==0 else 'Node Gateway apply error: '+out[-200:]
        return {'ok':p.returncode==0,'message':msg,'plan':plan,'log':out[-4000:]}
    if script.exists(): run_cmd(['bash', str(script), '--clear'], timeout=60)
    return {'ok':ok,'message':'Node Gateway plan saved; global gateway is disabled','plan':plan}

def node_gateway_status():
    try: plan=json.loads(PLAN_FILE.read_text(encoding='utf-8'))
    except Exception: plan={'generated_at':None,'plan':[]}
    try: log=run_cmd(['bash','-lc','tail -n 120 /var/log/ironpanel-node-gateway.log 2>/dev/null || true'], timeout=5).stdout
    except Exception: log=''
    return {'plan':plan,'log':log}

def queue_node_job(node_id, action, payload=None):
    job=RemoteJob(node_id=node_id, action=action, status='queued', output='')
    if hasattr(job,'payload_json'): job.payload_json=json.dumps(payload or {}, ensure_ascii=False)
    db.session.add(job); db.session.commit(); return job

def queue_node_health_check(node_id): return queue_node_job(node_id, 'health_check', {'protocols':PROTOCOLS})

def queue_user_sync(user):
    queued=[]
    for protocol in [p for p in (user.protocols or '').split(',') if p]:
        node,reason=select_node_for_user(user, protocol)
        if node:
            payload={'user_id':user.id,'username':user.username,'protocol':protocol,'enabled':bool(user.enabled),'data_limit_mb':int(user.data_limit_mb or 0),'expires_at':user.expires_at.isoformat() if user.expires_at else None,'reason':reason}
            queued.append(queue_node_job(node.id, 'sync_user', payload))
    try:
        user.node_sync_status='queued' if queued else 'local'; user.node_sync_error=''; db.session.commit()
    except Exception: db.session.rollback()
    return queued

def queue_all_user_sync():
    count=0
    for u in VpnUser.query.filter_by(enabled=True).all(): count += len(queue_user_sync(u))
    return count

def rebalance_users():
    moved=0
    for u in VpnUser.query.filter_by(enabled=True).all():
        if getattr(u,'node_mode','auto') in (None,'auto'):
            before=int(getattr(u,'preferred_node_id',0) or 0)
            best=None
            for p in [x for x in (u.protocols or '').split(',') if x]:
                n,reason=select_node_for_protocol(p)
                if n: best=n; break
            if best and before != best.id:
                u.preferred_node_id=best.id; u.node_mode='auto'; moved+=1
    db.session.commit()
    queued=queue_all_user_sync(); apply_node_gateway_runtime()
    return {'moved':moved,'queued_jobs':queued}

def assign_user_node(user_id, mode='auto', node_id=0):
    u=VpnUser.query.get(user_id)
    if not u: return False, 'user not found'
    u.node_mode=mode or 'auto'; u.preferred_node_id=int(node_id or 0) or None; db.session.commit()
    jobs=queue_user_sync(u)
    return True, f'{len(jobs)} sync job(s) queued'

def heartbeat_jobs_for_node(node, limit=10):
    jobs=RemoteJob.query.filter(RemoteJob.node_id==node.id, RemoteJob.status.in_(['queued','running'])).order_by(RemoteJob.id.asc()).limit(limit).all()
    out=[]
    for j in jobs:
        j.status='running'
        if hasattr(j,'updated_at'): j.updated_at=datetime.utcnow()
        try: payload=json.loads(getattr(j,'payload_json','') or '{}')
        except Exception: payload={}
        out.append({'id':j.id,'action':j.action,'payload':payload})
    db.session.commit(); return out

def complete_node_job(token, job_id, ok=True, output='', metrics=None):
    node=Node.query.filter_by(api_key=token).first()
    if not node: return None, 'invalid node token'
    job=RemoteJob.query.filter_by(id=job_id, node_id=node.id).first()
    if not job: return None, 'job not found'
    job.status='done' if ok else 'failed'; job.output=str(output or '')[:20000]
    if hasattr(job,'updated_at'): job.updated_at=datetime.utcnow()
    if metrics and isinstance(metrics,dict):
        if 'protocol_health' in metrics and hasattr(node,'protocol_health_json'):
            node.protocol_health_json=json.dumps(metrics.get('protocol_health') or {}, ensure_ascii=False)[:10000]
        if 'online_users' in metrics and hasattr(node,'online_users'): node.online_users=int(metrics.get('online_users') or 0)
        if 'cpu_percent' in metrics and hasattr(node,'cpu_percent'): node.cpu_percent=float(metrics.get('cpu_percent') or 0)
        if 'ram_percent' in metrics and hasattr(node,'ram_percent'): node.ram_percent=float(metrics.get('ram_percent') or 0)
        if 'disk_percent' in metrics and hasattr(node,'disk_percent'): node.disk_percent=float(metrics.get('disk_percent') or 0)
        if 'ping_ms' in metrics and hasattr(node,'ping_ms'): node.ping_ms=float(metrics.get('ping_ms') or 0)
    db.session.commit(); return job, None

def node_sync_status_summary():
    return {'nodes':Node.query.count(),'online_nodes':sum(1 for n in Node.query.all() if _node_online(n)),'queued_jobs':RemoteJob.query.filter_by(status='queued').count(),'running_jobs':RemoteJob.query.filter_by(status='running').count(),'failed_jobs':RemoteJob.query.filter_by(status='failed').count()}


CONFIG_PATHS = {
    'openvpn':['/etc/openvpn','/etc/ironpanel/ssl'],
    'wireguard':['/etc/wireguard'],
    'ocserv':['/etc/ocserv','/etc/ironpanel/ssl'],
    'l2tp':['/etc/xl2tpd','/etc/ipsec.conf','/etc/ipsec.secrets','/etc/ppp','/etc/strongswan.conf','/etc/strongswan.d'],
    'xray':['/usr/local/etc/xray','/etc/xray','/etc/ironpanel/ssl'],
    'pptp':['/etc/pptpd.conf','/etc/ppp'],
    'hysteria2':['/etc/hysteria','/etc/hysteria2','/etc/ironpanel/ssl'],
    'telegram_proxy':['/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json','/etc/systemd/system/ironpanel-tgproxy.service'],
    'ssh':['/etc/ssh/sshd_config.d/ironpanel.conf'],
    '_common':['/etc/ironpanel','/opt/ironpanel/scripts'],
}
SAFE_PREFIXES = ('/etc/openvpn','/etc/wireguard','/etc/ocserv','/etc/xl2tpd','/etc/ppp','/etc/xray','/usr/local/etc/xray','/etc/hysteria','/etc/hysteria2','/etc/ironpanel','/etc/ssh/sshd_config.d','/etc/systemd/system/ironpanel-tgproxy.service','/opt/ironpanel/scripts')
SAFE_FILES = ('/etc/ipsec.conf','/etc/ipsec.secrets','/etc/strongswan.conf','/etc/pptpd.conf','/etc/ironpanel/telegram_proxy.json','/etc/ironpanel/tgproxy.json')

def _collect_file(path, files, total_ref, max_total=12*1024*1024):
    try:
        p=Path(path)
        if not p.is_file() or p.is_symlink(): return
        real=str(p.resolve())
        if not (real.startswith(SAFE_PREFIXES) or real in SAFE_FILES): return
        size=p.stat().st_size
        if size > 2*1024*1024 or total_ref[0] + size > max_total: return
        data=p.read_bytes()
        files.append({'path':real,'mode':stat.S_IMODE(p.stat().st_mode),'content_b64':base64.b64encode(data).decode('ascii')})
        total_ref[0]+=size
    except Exception:
        return

def protocol_config_bundle(protocols):
    selected=[p for p in protocols if p in PROTOCOLS]
    files=[]; total=[0]
    seen=set()
    for proto in selected:
        raw_list = list(CONFIG_PATHS.get(proto, [])) + list(CONFIG_PATHS.get('_common', []))
        for raw in raw_list:
            base=Path(raw)
            if str(base) in seen: continue
            seen.add(str(base))
            if base.is_file():
                _collect_file(base, files, total)
            elif base.is_dir():
                try:
                    for child in base.rglob('*'):
                        _collect_file(child, files, total)
                except Exception:
                    pass
    return {'version':'19.8.14','protocols':selected,'files':files,'total_bytes':total[0]}

def queue_protocol_config_sync(node_id, protocols):
    selected=[p for p in protocols if p in PROTOCOLS]
    if not selected: return 0
    bundle=protocol_config_bundle(selected)
    queue_node_job(node_id, 'ensure_protocols', {'protocols': ','.join(selected)})
    queue_node_job(node_id, 'sync_protocol_configs', {'protocols': selected, 'bundle': bundle})
    return 2

def queue_gateway_config_sync_from_plan(plan=None):
    plan = plan or node_gateway_plan()
    grouped={}
    for item in plan:
        if item.get('enabled') and item.get('selected_node_id') and item.get('mode') not in ('local', None):
            grouped.setdefault(int(item['selected_node_id']), []).append(item.get('protocol'))
    jobs=0
    for node_id, protos in grouped.items():
        jobs += queue_protocol_config_sync(node_id, protos)
    return jobs

def reset_node_gateway_to_local():
    rules={p:{'enabled':False,'mode':'local','node_id':0,'strategy':_setting('node_gateway_strategy','balanced'),'strict':False} for p in PROTOCOLS}
    set_setting('node_gateway_enabled','0')
    set_setting('node_gateway_rules', json.dumps(rules, ensure_ascii=False))
    db.session.commit()
    ok,msg,plan=write_node_gateway_runtime()
    script=Path('/opt/ironpanel/scripts/apply_node_gateway.sh')
    if not script.exists(): script=Path(__file__).resolve().parents[2] / 'scripts' / 'apply_node_gateway.sh'
    out=''
    if script.exists():
        p=run_cmd(['bash', str(script), '--clear'], timeout=90)
        out=(p.stdout or '')+(p.stderr or '')
    return {'ok':True,'message':'تمام فورواردهای Node Gateway پاک شد و همه پروتکل‌ها به سرور اصلی برگشتند.','plan':plan,'log':out[-4000:]}

def _safe_port_conflicts_for_plan(plan):
    """Return warnings for ports that may break panel access or are already locally bound.

    Local services can remain bound because DNAT runs in PREROUTING for external
    traffic, but the panel port itself must not be forwarded or the admin may
    lock themselves out.
    """
    warnings=[]
    panel_ports=set(_panel_ports_for_gateway())
    for row in plan or []:
        if not (row.get('enabled') and row.get('selected_node_host')): continue
        proto=row.get('protocol')
        for e in row.get('ports') or []:
            pr=str(e.get('proto') or '').lower(); po=int(e.get('port') or 0)
            if pr in ('tcp','udp') and po in panel_ports:
                warnings.append(f'{proto}: port {po}/{pr} is the panel port and was skipped by gateway script')
    return warnings

def force_protocols_to_node(node_id, protocols):
    """Force selected protocols to a single node only (no Local or failover).

    v19.8.14: fixed Internal Server Error from the web route, queues full
    protocol config sync before/after gateway apply, and never crashes the panel
    if iptables or port validation fails.
    """
    node=Node.query.get(int(node_id or 0))
    if not node: return {'ok':False,'message':'node not found','count':0}
    allowed={p.strip() for p in (node.protocols or '').split(',') if p.strip()}
    selected=[p for p in protocols if p in PROTOCOLS and (not allowed or p in allowed)]
    if not selected:
        return {'ok':False,'message':'هیچ پروتکل معتبری برای این نود انتخاب نشده است.','count':0}
    old_rules=_json_setting('node_gateway_rules', {})
    old_enabled=_setting('node_gateway_enabled','0')
    if not isinstance(old_rules, dict): old_rules={}
    rules=dict(old_rules)
    for p in selected:
        rules[p]={'enabled':True,'mode':'fixed_only','node_id':node.id,'strategy':'fixed_only','strict':True}
    try:
        set_setting('node_gateway_enabled','1')
        set_setting('node_gateway_rules', json.dumps(rules, ensure_ascii=False))
        db.session.commit()
        # First queue config/core sync so the node receives main-server configs
        # on its next heartbeat even if gateway apply is slow.
        sync_jobs=queue_protocol_config_sync(node.id, selected)
        result=apply_node_gateway_runtime()
        plan=result.get('plan') or node_gateway_plan()
        warnings=_safe_port_conflicts_for_plan(plan)
        queued=0
        for u in VpnUser.query.filter_by(enabled=True).all():
            ups=[x for x in (u.protocols or '').split(',') if x in selected]
            for p in ups:
                queue_node_job(node.id, 'sync_user', {'user_id':u.id,'username':u.username,'protocol':p,'enabled':bool(u.enabled),'data_limit_mb':int(u.data_limit_mb or 0),'expires_at':u.expires_at.isoformat() if u.expires_at else None,'reason':'forced-protocol-route'})
                queued += 1
        ok=bool(result.get('ok', True))
        msg=f'{len(selected)} protocol(s) forced to {node.name}; DNAT/FORWARD rules applied; {sync_jobs} config/core job(s) and {queued} user sync job(s) queued.'
        if warnings:
            msg += ' هشدار: ' + ' | '.join(warnings[:4])
        if not ok:
            msg='Gateway apply warning/error: '+str(result.get('message',''))+'; config jobs are still queued.'
        return {'ok':ok, 'message':msg, 'count':len(selected), 'queued':queued, 'config_jobs':sync_jobs, 'log':result.get('log','')}
    except Exception as exc:
        db.session.rollback()
        try:
            set_setting('node_gateway_enabled', old_enabled)
            set_setting('node_gateway_rules', json.dumps(old_rules, ensure_ascii=False))
            db.session.commit()
        except Exception:
            db.session.rollback()
        return {'ok':False,'message':'Force protocol failed safely: '+str(exc),'count':0}

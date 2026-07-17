import json, subprocess
from datetime import datetime
from pathlib import Path
from ..core.extensions import db
from ..core.models import Node, AppSetting, OnlineSession
from .provisioning import set_setting, get_port, run_cmd

PROTOCOLS = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
LABELS = {'openvpn':'OpenVPN','wireguard':'WireGuard','ocserv':'Cisco/Ocserv','l2tp':'L2TP/IPsec','xray':'Xray','pptp':'PPTP','hysteria2':'Hysteria2','telegram_proxy':'Telegram Proxy','ssh':'SSH'}
ICONS = {'openvpn':'🔐','wireguard':'🧬','ocserv':'🛡️','l2tp':'🌉','xray':'⚡','pptp':'🧩','hysteria2':'🚀','telegram_proxy':'✈️','ssh':'⌨️'}
TCP_PROTOCOLS = {'openvpn','ocserv','xray','pptp','telegram_proxy','ssh'}
PORT_KEYS = {'openvpn':'openvpn','wireguard':'wireguard','ocserv':'ocserv','l2tp':'l2tp','xray':'xray_tls','pptp':'pptp','hysteria2':'hysteria2','telegram_proxy':'telegram_proxy_base','ssh':'ssh'}
PORT_DEFAULTS = {'openvpn':1194,'wireguard':51820,'ocserv':443,'l2tp':1701,'xray':443,'pptp':1723,'hysteria2':443,'telegram_proxy':6969,'ssh':422}
STATE_DIR=Path('/etc/ironpanel')
PLAN_FILE=STATE_DIR/'node-gateway-plan.json'
HAPROXY_CFG=Path('/etc/haproxy/ironpanel-nodes.cfg')

def _setting(key, default=''):
    row=AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None,'') else default

def _json_setting(key, default):
    try: return json.loads(_setting(key, json.dumps(default)))
    except Exception: return default

def _port(protocol):
    try: return int(get_port(PORT_KEYS.get(protocol, protocol), PORT_DEFAULTS.get(protocol, 0)) or PORT_DEFAULTS.get(protocol, 0))
    except Exception: return PORT_DEFAULTS.get(protocol, 0)

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

def _online_count(node_id, protocol=None):
    try:
        q=OnlineSession.query.filter_by(active=True, node_id=node_id)
        if protocol: q=q.filter_by(protocol=protocol)
        return q.count()
    except Exception: return 0

def _ping_ms(host):
    host=str(host or '').replace('https://','').replace('http://','').split('/')[0].split(':')[0]
    if not host: return 9999.0
    try:
        p=subprocess.run(['ping','-c','1','-W','1',host], capture_output=True, text=True, timeout=2)
        import re
        m=re.search(r'time[=<]([0-9.]+)\s*ms', p.stdout+p.stderr)
        return float(m.group(1)) if m else 9999.0
    except Exception: return 9999.0

def node_gateway_settings():
    rules=_json_setting('node_gateway_rules', {})
    nodes=Node.query.order_by(Node.name).all()
    rows=[]
    for p in PROTOCOLS:
        r=rules.get(p,{}) if isinstance(rules, dict) else {}
        candidates=[]
        for n in nodes:
            if _node_supports(n,p):
                candidates.append({'id':n.id,'name':n.name,'host':n.host,'health':n.health,'online':_node_online(n),'users':_online_count(n.id,p),'ping_ms': _ping_ms(n.host) if _setting('node_gateway_live_ping','0')=='1' else None})
        rows.append({'protocol':p,'label':LABELS.get(p,p),'icon':ICONS.get(p,'•'),'port':_port(p),'transport':'tcp' if p in TCP_PROTOCOLS else 'udp','enabled':bool(r.get('enabled')),'mode':r.get('mode','local'),'node_id':int(r.get('node_id') or 0),'strategy':r.get('strategy', _setting('node_gateway_strategy','least_users')),'candidates':candidates})
    return {'enabled':_setting('node_gateway_enabled','0')=='1','strategy':_setting('node_gateway_strategy','least_users'),'live_ping':_setting('node_gateway_live_ping','0')=='1','notes':_setting('node_gateway_notes',''),'rules':rules if isinstance(rules,dict) else {},'rows':rows}

def save_node_gateway_settings(form):
    set_setting('node_gateway_enabled','1' if form.get('node_gateway_enabled')=='1' else '0')
    set_setting('node_gateway_strategy', form.get('node_gateway_strategy') or 'least_users')
    set_setting('node_gateway_live_ping','1' if form.get('node_gateway_live_ping')=='1' else '0')
    set_setting('node_gateway_notes',(form.get('node_gateway_notes') or '')[:2000])
    rules={}
    for p in PROTOCOLS:
        mode=form.get(f'mode_{p}','local')
        try: node_id=int(form.get(f'node_{p}') or 0)
        except Exception: node_id=0
        rules[p]={'enabled': form.get(f'enabled_{p}')=='1' and mode!='local','mode':mode,'node_id':node_id,'strategy':form.get(f'strategy_{p}') or form.get('node_gateway_strategy') or 'least_users'}
    set_setting('node_gateway_rules', json.dumps(rules, ensure_ascii=False))
    db.session.commit(); return rules

def _eligible(protocol):
    return [n for n in Node.query.order_by(Node.id).all() if _node_online(n) and _node_supports(n,protocol)]

def select_node_for_protocol(protocol, rules=None):
    rules=rules or _json_setting('node_gateway_rules', {})
    rule=(rules or {}).get(protocol,{}) if isinstance(rules,dict) else {}
    if not rule.get('enabled') or rule.get('mode')=='local': return None, 'local'
    nodes=_eligible(protocol)
    if not nodes: return None, 'no-online-node'
    if rule.get('mode')=='fixed' and int(rule.get('node_id') or 0):
        node=Node.query.get(int(rule.get('node_id')))
        if node and node in nodes: return node, 'fixed'
    strategy=rule.get('strategy') or _setting('node_gateway_strategy','least_users')
    if strategy=='best_ping': return sorted(nodes, key=lambda n: (_ping_ms(n.host), _online_count(n.id,protocol), n.id))[0], 'best_ping'
    if strategy=='balanced': return sorted(nodes, key=lambda n: (_online_count(n.id,protocol)*10 + _ping_ms(n.host)/50, n.id))[0], 'balanced'
    return sorted(nodes, key=lambda n: (_online_count(n.id,protocol), _ping_ms(n.host), n.id))[0], 'least_users'

def node_gateway_plan():
    s=node_gateway_settings(); plan=[]
    for row in s['rows']:
        node,reason=select_node_for_protocol(row['protocol'], s['rules'])
        plan.append({'protocol':row['protocol'],'label':row['label'],'port':row['port'],'transport':row['transport'],'enabled':row['enabled'],'mode':row['mode'],'selected_node_id':node.id if node else None,'selected_node_name':node.name if node else 'Local / Direct','selected_node_host':node.host if node else '', 'reason':reason})
    return plan

def write_node_gateway_runtime():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    plan=node_gateway_plan(); PLAN_FILE.write_text(json.dumps({'generated_at':datetime.utcnow().isoformat(),'plan':plan}, ensure_ascii=False, indent=2), encoding='utf-8')
    cfg=['# Generated by IronPanel Node Gateway','global','  daemon','  maxconn 4096','defaults','  mode tcp','  timeout connect 8s','  timeout client 2m','  timeout server 2m']
    for row in plan:
        if not (row.get('enabled') and row.get('transport')=='tcp' and row.get('selected_node_host')): continue
        host=str(row['selected_node_host']).replace('https://','').replace('http://','').split('/')[0].split(':')[0]
        port=int(row['port'] or 0); proto=row['protocol']; name=str(row['selected_node_name']).replace(' ','_')
        if host and port: cfg += [f'frontend ironpanel_{proto}_in', f'  bind *:{port}', f'  default_backend ironpanel_{proto}_nodes', f'backend ironpanel_{proto}_nodes', f'  server {name} {host}:{port} check']
    HAPROXY_CFG.parent.mkdir(parents=True, exist_ok=True); HAPROXY_CFG.write_text('\n'.join(cfg)+'\n', encoding='utf-8')
    return True, 'Node Gateway runtime plan generated', plan

def apply_node_gateway_runtime():
    ok,msg,plan=write_node_gateway_runtime()
    if _setting('node_gateway_enabled','0')=='1':
        run_cmd(['bash','-lc','apt-get update >/dev/null 2>&1 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y haproxy >/dev/null 2>&1 || true'], timeout=600)
        run_cmd(['bash','-lc','haproxy -c -f /etc/haproxy/ironpanel-nodes.cfg >/var/log/ironpanel-node-gateway.log 2>&1 || true'], timeout=30)
        run_cmd(['bash','-lc','systemctl reload haproxy >/dev/null 2>&1 || systemctl restart haproxy >/dev/null 2>&1 || true'], timeout=30)
        return {'ok':ok,'message':'Node Gateway plan applied','plan':plan}
    return {'ok':ok,'message':'Node Gateway plan saved; global gateway is disabled','plan':plan}

def node_gateway_status():
    try: plan=json.loads(PLAN_FILE.read_text(encoding='utf-8'))
    except Exception: plan={'generated_at':None,'plan':[]}
    try: log=run_cmd(['bash','-lc','tail -n 80 /var/log/ironpanel-node-gateway.log 2>/dev/null || true'], timeout=5).stdout
    except Exception: log=''
    return {'plan':plan,'log':log}

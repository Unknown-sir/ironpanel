import base64, json, os, subprocess, time
from datetime import datetime
from pathlib import Path
from flask import current_app
from ..core.extensions import db
from ..core.models import Node, AppSetting, VpnUser, BackupRecord, OutboundProfile, ProtocolOutboundMap, SubscriptionAudit
from .provisioning import user_config_payload, user_access_status, backup_now, service_status_detailed, run_cmd, get_public_host
from .xray import xray_link, write_xray_config

V17_VERSION = '17.0'

CLIENT_FORMATS = ['raw', 'clash', 'singbox', 'hiddify']


def setting(key, default=''):
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, '') else default


def set_setting(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        db.session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
    db.session.commit()


def node_install_command(node):
    repo = setting('v17_node_install_repo', 'https://github.com/Unknown-sir/ironpanel.git')
    master = setting('public_host', '') or get_public_host()
    if not str(master).startswith(('http://', 'https://')):
        master = 'https://' + master
    return "\n".join([
        'apt update && apt install -y git curl python3 python3-venv iproute2',
        f'git clone {repo} ironpanel-node || true',
        'cd ironpanel-node',
        f'sudo bash scripts/install_node.sh --master "{master}" --token "{node.api_key}" --host "{node.host}"',
    ])


def update_node_from_heartbeat(token, payload):
    node = Node.query.filter_by(api_key=token).first()
    if not node:
        return None, 'invalid node token'
    node.health = 'online'
    node.version = str(payload.get('version') or node.version or '')
    node.agent_version = str(payload.get('agent_version') or payload.get('version') or node.agent_version or '')
    node.public_ip = str(payload.get('public_ip') or node.public_ip or '')
    if payload.get('protocols'):
        node.protocols = str(payload.get('protocols'))[:160]
    node.cpu_percent = float(payload.get('cpu_percent') or 0)
    node.ram_percent = float(payload.get('ram_percent') or 0)
    node.disk_percent = float(payload.get('disk_percent') or 0)
    node.traffic_rx_bytes = int(payload.get('traffic_rx_bytes') or 0)
    node.traffic_tx_bytes = int(payload.get('traffic_tx_bytes') or 0)
    node.last_error = str(payload.get('last_error') or '')[:5000]
    node.last_seen = datetime.utcnow()
    db.session.commit()
    return node, None


def node_health_summary():
    rows=[]
    now=time.time()
    for n in Node.query.order_by(Node.id.desc()).all():
        offline=True
        if n.last_seen:
            offline=(datetime.utcnow()-n.last_seen).total_seconds()>180
        if offline and n.health == 'online':
            n.health='offline'
        rows.append({
            'id': n.id, 'name': n.name, 'host': n.host, 'location': n.location,
            'health': n.health, 'protocols': n.protocols, 'cpu': n.cpu_percent,
            'ram': n.ram_percent, 'disk': n.disk_percent,
            'traffic_rx_bytes': n.traffic_rx_bytes, 'traffic_tx_bytes': n.traffic_tx_bytes,
            'last_seen': n.last_seen.isoformat() if n.last_seen else None,
            'install_command': node_install_command(n),
        })
    db.session.commit()
    return rows


def _audit_subscription(user, client_type, request=None):
    try:
        db.session.add(SubscriptionAudit(user_id=user.id, token=user.subscription_token, client_type=client_type, remote_ip=(request.remote_addr if request else ''), user_agent=((request.headers.get('User-Agent','') if request else '')[:255])))
        db.session.commit()
    except Exception:
        db.session.rollback()


def raw_subscription(user):
    payload=user_config_payload(user)
    links=[]
    if 'xray.txt' in payload or 'xray' in payload:
        links.append(xray_link(user))
    # keep raw output pure for clients
    return '\n'.join([x for x in links if x]) + '\n'


def clash_meta_subscription(user):
    link=xray_link(user)
    # Minimal Clash Meta compatible profile. Advanced fields are intentionally conservative.
    data={
        'mixed-port': 7890,
        'allow-lan': False,
        'mode': 'rule',
        'log-level': 'warning',
        'proxies': [{'name': user.username, 'type': 'vless', 'server': get_public_host(), 'port': 443, 'uuid': getattr(user, 'subscription_token', '')[:36], 'network': 'tcp', 'tls': False, 'udp': True, 'xray-uri': link}],
        'proxy-groups': [{'name':'IronPanel','type':'select','proxies':[user.username]}],
        'rules': ['MATCH,IronPanel'],
    }
    import yaml
    try: return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    except Exception: return json.dumps(data, ensure_ascii=False, indent=2)


def singbox_subscription(user):
    link=xray_link(user)
    return json.dumps({
        'log': {'level': 'warn'},
        'outbounds': [
            {'type': 'selector', 'tag': 'select', 'outbounds': [user.username]},
            {'type': 'urltest', 'tag': user.username, 'outbounds': ['ironpanel-xray'], 'url': 'https://www.gstatic.com/generate_204', 'interval': '5m'},
            {'type': 'direct', 'tag': 'direct'},
            {'type': 'block', 'tag': 'block'},
            {'type': 'vless', 'tag': 'ironpanel-xray', 'server': get_public_host(), 'server_port': 443, 'uuid': getattr(user, 'subscription_token', '')[:36], 'tls': {'enabled': False}, 'xray-uri': link},
        ],
        'route': {'final': 'select'}
    }, ensure_ascii=False, indent=2)


def hiddify_subscription(user):
    return raw_subscription(user)


def subscription_for_client(user, client_type='raw', request=None):
    ok, reason = user_access_status(user)
    if not ok:
        return reason + '\n', 'text/plain; charset=utf-8', 403
    client_type=(client_type or 'raw').lower()
    _audit_subscription(user, client_type, request=request)
    if client_type == 'clash': return clash_meta_subscription(user), 'text/yaml; charset=utf-8', 200
    if client_type == 'singbox': return singbox_subscription(user), 'application/json; charset=utf-8', 200
    if client_type == 'hiddify': return hiddify_subscription(user), 'text/plain; charset=utf-8', 200
    return raw_subscription(user), 'text/plain; charset=utf-8', 200


def validate_xray_before_delivery():
    try:
        write_xray_config(restart=False)
        p = subprocess.run(['/usr/local/bin/xray','test','-config','/usr/local/etc/xray/config.json'], capture_output=True, text=True, timeout=12)
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except Exception as e:
        return False, str(e)


def ensure_default_outbound_profiles():
    if OutboundProfile.query.count() == 0:
        db.session.add(OutboundProfile(name='Default Outbound', profile_type='openvpn', enabled=False, priority=100, kill_switch=False))
        db.session.commit()


def outbound_matrix():
    ensure_default_outbound_profiles()
    profiles=OutboundProfile.query.order_by(OutboundProfile.priority, OutboundProfile.id).all()
    maps=ProtocolOutboundMap.query.all()
    return profiles, maps


def test_outbound_profile(profile):
    # Safe placeholder test: validates syntax shape and records an actionable status.
    body=(profile.config_body or '').strip()
    if not body:
        profile.last_test_status='failed'; profile.last_test_detail='config is empty'; db.session.commit(); return False, profile.last_test_detail
    if profile.profile_type == 'openvpn' and 'remote ' not in body:
        profile.last_test_status='failed'; profile.last_test_detail='OpenVPN config must contain remote host'; db.session.commit(); return False, profile.last_test_detail
    if profile.profile_type == 'xray' and not any(body.startswith(x) for x in ['vless://','vmess://','trojan://','ss://']) and 'outbounds' not in body:
        profile.last_test_status='failed'; profile.last_test_detail='Xray outbound must be URI or JSON outbound config'; db.session.commit(); return False, profile.last_test_detail
    profile.last_test_status='passed'; profile.last_test_detail='syntax accepted; runtime apply will run service-level test'; profile.updated_at=datetime.utcnow(); db.session.commit(); return True, profile.last_test_detail


def run_full_backup_v17():
    p=backup_now()
    try:
        db.session.add(BackupRecord(filename=p.name, size_bytes=p.stat().st_size)); db.session.commit()
    except Exception: db.session.rollback()
    return p


def live_log_tail(service='ironpanel', lines=120):
    allowed={'ironpanel','ironpanel-sales-bot','ironpanel-usage-sync','xray','openvpn-server@server','ocserv','strongswan','xl2tpd','ironpanel-outbound-openvpn','ironpanel-node'}
    if service not in allowed:
        return 'service not allowed'
    try:
        p=subprocess.run(['journalctl','-u',service,'-n',str(int(lines)),'--no-pager'], capture_output=True, text=True, timeout=10)
        return (p.stdout or p.stderr or '').strip()
    except Exception as e:
        return str(e)


def v17_health_checks():
    data={'services': service_status_detailed(), 'xray_validation': None, 'outbound_profiles': []}
    try:
        data['xray_validation']=validate_xray_before_delivery()
    except Exception as e:
        data['xray_validation']=(False, str(e))
    for p in OutboundProfile.query.order_by(OutboundProfile.id).all():
        data['outbound_profiles'].append({'id':p.id,'name':p.name,'status':p.last_test_status,'detail':p.last_test_detail})
    return data

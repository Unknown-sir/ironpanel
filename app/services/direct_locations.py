"""Direct Location subscription delivery and node-side usage accounting.

v19.9.5: nodes can be delivered as real locations in a user's subscription.
The master still owns identity, limits and traffic quota; location configs only
change the public endpoint host/port.
"""
from __future__ import annotations
import json, re
from urllib.parse import quote
from datetime import datetime
from typing import Dict, List, Tuple
from ..core.extensions import db
from ..core.models import Node, VpnUser, AppSetting

DIRECT_PROTOCOLS = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
DEFAULT_PORT_KEYS = {
    'openvpn': 'port_openvpn_udp',
    'wireguard': 'port_wireguard_udp',
    'ocserv': 'port_ocserv_tcp',
    'l2tp': 'port_l2tp_udp',
    'xray': 'port_xray_tcp',
    'pptp': 'port_pptp_tcp',
    'hysteria2': 'port_hysteria2_udp',
    'telegram_proxy': 'port_telegram_proxy_base',
    'ssh': 'port_ssh_tcp',
}
DEFAULT_PORTS = {'openvpn':1194,'wireguard':51820,'ocserv':8445,'l2tp':1701,'xray':443,'pptp':1723,'hysteria2':4433,'telegram_proxy':6969,'ssh':422}


def _setting(key: str, default: str = '') -> str:
    row = AppSetting.query.filter_by(key=key).first()
    return str(row.value if row and row.value is not None else default)


def _get_port(protocol: str) -> int:
    key = DEFAULT_PORT_KEYS.get(protocol)
    try:
        value = _setting(key or '', str(DEFAULT_PORTS.get(protocol, 0)))
        return int(value or DEFAULT_PORTS.get(protocol, 0) or 0)
    except Exception:
        return int(DEFAULT_PORTS.get(protocol, 0) or 0)


def _clean_host(value: str) -> str:
    value = str(value or '').strip()
    value = re.sub(r'^https?://', '', value, flags=re.I).split('/')[0].strip()
    if ':' in value and not value.startswith('['):
        # Keep IPv6 bracket form; strip ordinary host:port because port is separate.
        parts = value.rsplit(':', 1)
        if len(parts) == 2 and parts[1].isdigit():
            value = parts[0]
    return value.strip('[]')


def _ports_json(node: Node) -> Dict[str, int]:
    raw = getattr(node, 'subscription_ports_json', '') or '{}'
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        data = {}
    out = {}
    for p in DIRECT_PROTOCOLS:
        try:
            v = int(data.get(p) or 0)
            if 0 < v <= 65535:
                out[p] = v
        except Exception:
            pass
    return out


def node_direct_enabled(node: Node, protocol: str | None = None) -> bool:
    if not node or not bool(getattr(node, 'subscription_enabled', False)):
        return False
    mode = (getattr(node, 'delivery_mode', '') or 'relay').lower()
    if mode not in ('direct','both'):
        return False
    if protocol:
        protos = [x.strip() for x in (node.protocols or '').split(',') if x.strip()]
        if protos and protocol not in protos:
            return False
    return True


def node_direct_host(node: Node) -> str:
    return _clean_host(getattr(node, 'subscription_host', '') or getattr(node, 'host', '') or getattr(node, 'public_ip', ''))


def node_direct_port(node: Node, protocol: str) -> int:
    return int(_ports_json(node).get(protocol) or _get_port(protocol) or 0)


def node_direct_label(node: Node, protocol: str = '') -> str:
    flag = (getattr(node, 'subscription_flag', '') or '').strip()
    label = (getattr(node, 'subscription_label', '') or getattr(node, 'location', '') or getattr(node, 'name', '') or 'Node').strip()
    proto = protocol.upper() if protocol else ''
    return ' '.join(x for x in [flag, label, proto] if x).strip()


def direct_location_nodes(protocol: str) -> List[Node]:
    out = []
    for n in Node.query.order_by(Node.name).all():
        if not node_direct_enabled(n, protocol):
            continue
        host = node_direct_host(n)
        port = node_direct_port(n, protocol)
        if host and port:
            out.append(n)
    return out


def direct_locations_summary() -> Dict[str, List[Dict[str, str]]]:
    rows = {}
    for p in DIRECT_PROTOCOLS:
        items = []
        for n in direct_location_nodes(p):
            items.append({'id': n.id, 'name': n.name, 'label': node_direct_label(n, p), 'host': node_direct_host(n), 'port': node_direct_port(n, p), 'mode': getattr(n, 'delivery_mode', 'relay')})
        if items:
            rows[p] = items
    return rows


def _xray_direct_links(user: VpnUser) -> str:
    try:
        from .xray import xray_settings, xray_link
    except Exception:
        return ''
    lines = []
    base = xray_settings()
    for n in direct_location_nodes('xray'):
        settings = dict(base)
        settings['xray_domain'] = node_direct_host(n)
        settings['xray_port'] = str(node_direct_port(n, 'xray'))
        settings['xray_remark'] = node_direct_label(n, 'xray') or 'IronPanel-Node'
        try:
            link = xray_link(user, settings).strip()
            if link:
                lines.append(link)
        except Exception:
            continue
    return ('\n'.join(lines) + '\n') if lines else ''


def _hash32(seed: str) -> str:
    import hashlib
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def _hysteria2_direct_links(user: VpnUser) -> str:
    lines = []
    obfs = _setting('hysteria2_obfs_password', '')
    password = _hash32(f'{user.subscription_token}:{user.username}:{obfs}')
    for n in direct_location_nodes('hysteria2'):
        host = node_direct_host(n); port = node_direct_port(n, 'hysteria2')
        if not host or not port: continue
        label = quote(node_direct_label(n, 'hysteria2') or f'{user.username}-Hysteria2')
        lines.append(f'hy2://{quote(password, safe="")}@{host}:{port}/?sni={quote(host, safe="")}&insecure=1#{label}')
    return ('\n'.join(lines) + '\n') if lines else ''


def _telegram_direct_links(user: VpnUser) -> str:
    lines = []
    secret = _hash32(f'{user.subscription_token}:{user.username}:telegram-proxy:{_setting("telegram_proxy_secret_salt", "")}')
    for n in direct_location_nodes('telegram_proxy'):
        host = node_direct_host(n); port = node_direct_port(n, 'telegram_proxy')
        if host and port:
            lines.append(f'tg://proxy?server={quote(host, safe="")}&port={port}&secret={secret}')
    return ('\n'.join(lines) + '\n') if lines else ''


def _append_block(existing: str, title: str, extra: str) -> str:
    extra = (extra or '').strip()
    if not extra:
        return existing
    existing = existing or ''
    sep = '\n' if existing.endswith('\n') or not existing else '\n\n'
    return existing + sep + f'# {title}\n' + extra + '\n'


def enrich_payload_with_direct_locations(user: VpnUser, files: Dict[str, str], allowed_protocols: List[str] | None = None) -> Dict[str, str]:
    """Add node-location configs to the standard user payload.

    Identity is never cloned. The same UUID/password/user is used on main and
    node configs, so traffic can be accounted against one VpnUser record.
    """
    allowed = set(allowed_protocols or [])
    if not allowed:
        allowed = set(DIRECT_PROTOCOLS)
    files = dict(files or {})

    if 'xray' in allowed:
        extra = _xray_direct_links(user)
        if extra:
            files['xray.txt'] = _append_block(files.get('xray.txt',''), 'Direct Location Nodes', extra)
    if 'hysteria2' in allowed:
        extra = _hysteria2_direct_links(user)
        if extra:
            files['hysteria2.txt'] = _append_block(files.get('hysteria2.txt',''), 'Direct Location Nodes', extra)
    if 'telegram_proxy' in allowed:
        extra = _telegram_direct_links(user)
        if extra:
            files['telegram_proxy.txt'] = _append_block(files.get('telegram_proxy.txt',''), 'Direct Location Nodes', extra)

    # Text protocols get one extra file per direct location. OpenVPN/WireGuard
    # reuse the main generated profile and only replace the public endpoint.
    safe_user = re.sub(r'[^A-Za-z0-9_.-]+', '_', user.username or 'user').strip('._-') or 'user'
    for protocol in ['openvpn','wireguard','ocserv','l2tp','pptp','ssh']:
        if protocol not in allowed:
            continue
        for n in direct_location_nodes(protocol):
            host = node_direct_host(n); port = node_direct_port(n, protocol); label = re.sub(r'[^A-Za-z0-9_.-]+','_', node_direct_label(n, protocol) or n.name).strip('_') or f'node{n.id}'
            if not host or not port: continue
            if protocol == 'openvpn':
                src_name = next((k for k in files if k.endswith('.ovpn')), '')
                src = files.get(src_name, '')
                if src:
                    files[f'{safe_user}-{label}.ovpn'] = re.sub(r'^remote\s+\S+\s+\d+', f'remote {host} {port}', src, count=1, flags=re.M)
            elif protocol == 'wireguard':
                src = files.get('wireguard.conf','')
                if src:
                    files[f'wireguard-{label}.conf'] = re.sub(r'^Endpoint\s*=\s*[^\n]+', f'Endpoint = {host}:{port} # Direct Location', src, count=1, flags=re.M)
            elif protocol == 'ocserv':
                files[f'ocserv-{label}.txt'] = f'Server: {host}:{port}\nUsername: {user.username}\nPassword: {user.cisco_password or "same-as-panel"}\nLocation: {node_direct_label(n, protocol)}\nClient: Cisco AnyConnect / OpenConnect\n'
            elif protocol == 'l2tp':
                files[f'l2tp-{label}.txt'] = f'Server: {host}\nType: L2TP/IPsec PSK\nUsername: {user.username}\nPassword: {user.l2tp_password or "same-as-panel"}\nPorts: UDP 500, 4500, 1701\nLocation: {node_direct_label(n, protocol)}\n'
            elif protocol == 'pptp':
                files[f'pptp-{label}.txt'] = f'Server: {host}\nPort: {port} TCP\nUsername: {user.username}\nPassword: {user.l2tp_password or "same-as-panel"}\nLocation: {node_direct_label(n, protocol)}\nType: PPTP\n'
            elif protocol == 'ssh':
                account = re.sub(r'[^A-Za-z0-9_-]+','_', f'ip{user.id}_{user.username}')[:31]
                files[f'ssh-{label}.txt'] = f'Server: {host}\nPort: {port}\nUsername: {account}\nPassword: same-as-node-synced-user\nLocation: {node_direct_label(n, protocol)}\nProtocol: SSH\n'
    return files


def apply_node_usage_reports(node: Node, reports: list) -> int:
    """Apply per-user counters reported by a node agent.

    Each report is a runtime counter. Deltas are calculated per node/protocol/user
    to keep all locations sharing one master traffic quota.
    """
    if not isinstance(reports, list):
        return 0
    try:
        from .provisioning import _account_runtime_counter, enforce_usage_limits
    except Exception:
        return 0
    changed = 0
    for r in reports:
        if not isinstance(r, dict):
            continue
        try:
            uid = int(r.get('user_id') or 0)
            username = str(r.get('username') or '').strip()
            proto = re.sub(r'[^a-z0-9_]+','_', str(r.get('protocol') or 'node').lower())[:40]
            rx = int(r.get('rx') or 0); tx = int(r.get('tx') or 0)
        except Exception:
            continue
        user = VpnUser.query.get(uid) if uid else None
        if not user and username:
            user = VpnUser.query.filter_by(username=username).first()
        if not user:
            continue
        if _account_runtime_counter(user, f'node{node.id}_{proto}', rx, tx):
            changed += 1
    if changed:
        try:
            node.last_usage_sync_at = datetime.utcnow()
        except Exception:
            pass
        try:
            enforce_usage_limits(commit=False)
        except Exception:
            pass
        db.session.commit()
    return changed

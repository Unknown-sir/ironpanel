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
    if not node:
        return False
    # v19.9.8: direct mode nodes are subscription locations by default.
    if not bool(getattr(node, 'subscription_enabled', False)) and (getattr(node, 'delivery_mode', '') or '').lower() not in ('direct','both'):
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
    return _clean_host(getattr(node, 'config_domain', '') or getattr(node, 'subscription_host', '') or getattr(node, 'host', '') or getattr(node, 'public_ip', ''))


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


PROTOCOL_META = {
    'openvpn': {'title': 'OpenVPN', 'icon': '🛡️'},
    'wireguard': {'title': 'WireGuard', 'icon': '⚡'},
    'ocserv': {'title': 'Cisco / Ocserv', 'icon': '🛰️'},
    'l2tp': {'title': 'L2TP', 'icon': '🌉'},
    'xray': {'title': 'Xray / V2Ray', 'icon': '🌐'},
    'pptp': {'title': 'PPTP', 'icon': '🔗'},
    'hysteria2': {'title': 'Hysteria2', 'icon': '🚀'},
    'telegram_proxy': {'title': 'Telegram Proxy', 'icon': '💬'},
    'ssh': {'title': 'SSH', 'icon': '🔐'},
    'account_status': {'title': 'Account Status', 'icon': 'ℹ️'},
    'config': {'title': 'Config', 'icon': '📄'},
}
NODE_CONFIG_RE = re.compile(r'^node-(\d+)-([a-z0-9_]+)\.(ovpn|conf|txt|yaml)$')


def _node_xray_link(user: VpnUser, node: Node) -> str:
    try:
        from .xray import xray_settings, xray_link
        settings = dict(xray_settings())
        settings['xray_domain'] = node_direct_host(node)
        settings['xray_port'] = str(node_direct_port(node, 'xray'))
        settings['xray_remark'] = node_direct_label(node, 'xray') or 'IronPanel-Node'
        return (xray_link(user, settings) or '').strip()
    except Exception:
        return ''


def _retarget_xray_body(body: str, node: Node) -> str:
    """Retarget already-generated Xray URIs without regenerating Reality keys."""
    import base64
    host = node_direct_host(node)
    port = node_direct_port(node, 'xray')
    remark = quote(node_direct_label(node, 'xray') or node.name or 'IronPanel-Node')
    output = []
    for raw in str(body or '').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('vmess://'):
            try:
                encoded = line[len('vmess://'):]
                data = json.loads(base64.b64decode(encoded + '=' * (-len(encoded) % 4)).decode())
                data['add'] = host
                data['port'] = str(port)
                data['ps'] = node_direct_label(node, 'xray') or node.name or 'IronPanel-Node'
                line = 'vmess://' + base64.b64encode(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()).decode()
            except Exception:
                pass
        else:
            line = re.sub(
                r'^([a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/\s]+@)?)(\[[^\]]+\]|[^:/?#\s]+)(:\d+)',
                lambda m: f'{m.group(1)}{host}:{port}', line, count=1,
            )
            if '#' in line:
                line = line.rsplit('#', 1)[0] + '#' + remark
            else:
                line += '#' + remark
        output.append(line)
    return '\n'.join(output).strip()


def _hash32(seed: str) -> str:
    import hashlib
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def _node_hysteria2_link(user: VpnUser, node: Node) -> str:
    host = node_direct_host(node)
    port = node_direct_port(node, 'hysteria2')
    if not host or not port:
        return ''
    obfs = _setting('hysteria2_obfs_password', '')
    password = _hash32(f'{user.subscription_token}:{user.username}:{obfs}')
    label = quote(node_direct_label(node, 'hysteria2') or f'{user.username}-Hysteria2')
    return f'hy2://{quote(password, safe="")}@{host}:{port}/?sni={quote(host, safe="")}&insecure=1#{label}'


def _node_telegram_link(user: VpnUser, node: Node) -> str:
    host = node_direct_host(node)
    port = node_direct_port(node, 'telegram_proxy')
    if not host or not port:
        return ''
    secret = _hash32(f'{user.subscription_token}:{user.username}:telegram-proxy:{_setting("telegram_proxy_secret_salt", "")}')
    return f'tg://proxy?server={quote(host, safe="")}&port={port}&secret={secret}'


def _replace_text_endpoint(body: str, host: str, port: int | None = None) -> str:
    body = str(body or '')
    endpoint = f'{host}:{port}' if port else host
    if re.search(r'^Server:\s*', body, flags=re.M | re.I):
        return re.sub(r'^Server:\s*[^\n]+', f'Server: {endpoint}', body, count=1, flags=re.M | re.I)
    return f'Server: {endpoint}\n' + body


def _node_config_name(node: Node, protocol: str, extension: str) -> str:
    return f'node-{int(node.id)}-{protocol}.{extension}'


def enrich_payload_with_direct_locations(user: VpnUser, files: Dict[str, str], allowed_protocols: List[str] | None = None) -> Dict[str, str]:
    """Create a separate, deterministic config file for every direct node.

    Main-server files stay untouched. Node files use the ``node-ID-protocol``
    naming scheme so the subscription page can reliably group them by server
    and the download route can persist/serve them from disk.
    """
    allowed = set(allowed_protocols or DIRECT_PROTOCOLS)
    files = dict(files or {})
    main_ovpn_name = next((k for k in files if k.endswith('.ovpn') and not k.startswith('node-')), '')

    for protocol in DIRECT_PROTOCOLS:
        if protocol not in allowed:
            continue
        for node in direct_location_nodes(protocol):
            host = node_direct_host(node)
            port = node_direct_port(node, protocol)
            if not host or not port:
                continue

            name = ''
            body = ''
            if protocol == 'openvpn':
                body = files.get(main_ovpn_name, '')
                if body:
                    body = re.sub(r'^remote\s+\S+\s+\d+', f'remote {host} {port}', body, count=1, flags=re.M)
                    name = _node_config_name(node, protocol, 'ovpn')
            elif protocol == 'wireguard':
                body = files.get('wireguard.conf', '')
                if body:
                    body = re.sub(r'^Endpoint\s*=\s*[^\n]+', f'Endpoint = {host}:{port} # Direct Location', body, count=1, flags=re.M)
                    name = _node_config_name(node, protocol, 'conf')
            elif protocol == 'xray':
                body = _retarget_xray_body(files.get('xray.txt', ''), node) or _node_xray_link(user, node)
                name = _node_config_name(node, protocol, 'txt')
            elif protocol == 'hysteria2':
                body = _node_hysteria2_link(user, node)
                name = _node_config_name(node, protocol, 'txt')
            elif protocol == 'telegram_proxy':
                body = _node_telegram_link(user, node)
                name = _node_config_name(node, protocol, 'txt')
            elif protocol == 'ocserv':
                body = _replace_text_endpoint(files.get('ocserv.txt', ''), host, port)
                name = _node_config_name(node, protocol, 'txt')
            elif protocol == 'l2tp':
                body = _replace_text_endpoint(files.get('l2tp.txt', ''), host)
                name = _node_config_name(node, protocol, 'txt')
            elif protocol == 'pptp':
                body = _replace_text_endpoint(files.get('pptp.txt', ''), host)
                body = re.sub(r'^Port:\s*[^\n]+', f'Port: {port} TCP', body, count=1, flags=re.M | re.I)
                name = _node_config_name(node, protocol, 'txt')
            elif protocol == 'ssh':
                body = _replace_text_endpoint(files.get('ssh.txt', ''), host)
                body = re.sub(r'^Port:\s*[^\n]+', f'Port: {port}', body, count=1, flags=re.M | re.I)
                name = _node_config_name(node, protocol, 'txt')

            body = str(body or '').strip()
            if name and body:
                files[name] = body + '\n'
    return files


def protocol_from_config_name(name: str) -> str:
    match = NODE_CONFIG_RE.match(str(name or ''))
    if match:
        return match.group(2)
    name = str(name or '')
    if name.endswith('.ovpn'):
        return 'openvpn'
    canonical = {
        'wireguard.conf': 'wireguard', 'ocserv.txt': 'ocserv',
        'l2tp.txt': 'l2tp', 'xray.txt': 'xray', 'pptp.txt': 'pptp',
        'hysteria2.txt': 'hysteria2', 'hysteria2.yaml': 'hysteria2',
        'telegram_proxy.txt': 'telegram_proxy', 'ssh.txt': 'ssh',
        'ACCOUNT_STATUS.txt': 'account_status',
    }
    return canonical.get(name, 'config')


def subscription_sections(files: Dict[str, str], main_host: str = '') -> List[Dict]:
    """Return main-server-first subscription groups for the public UI."""
    main = {
        'kind': 'main', 'node_id': None, 'flag': '🏠', 'title': 'سرور اصلی',
        'server_name': 'Main Server', 'location': '', 'host': main_host or '', 'configs': [],
    }
    node_groups: Dict[int, Dict] = {}

    for name, body in (files or {}).items():
        match = NODE_CONFIG_RE.match(str(name))
        protocol = protocol_from_config_name(name)
        meta = PROTOCOL_META.get(protocol, PROTOCOL_META['config'])
        item = {
            'name': name, 'body': body, 'protocol': protocol,
            'title': meta['title'], 'icon': meta['icon'],
            'download_only': protocol in ('openvpn', 'wireguard'),
            'copy_only': protocol == 'telegram_proxy',
        }
        if not match:
            main['configs'].append(item)
            continue
        node_id = int(match.group(1))
        node = Node.query.get(node_id)
        if not node:
            continue
        if node_id not in node_groups:
            title = (getattr(node, 'server_name', '') or getattr(node, 'subscription_label', '') or node.name or f'Node {node.id}').strip()
            location = (getattr(node, 'location', '') or getattr(node, 'subscription_label', '') or '').strip()
            node_groups[node_id] = {
                'kind': 'node', 'node_id': node_id,
                'flag': (getattr(node, 'subscription_flag', '') or '🌍').strip(),
                'title': title, 'server_name': node.name or title,
                'location': location, 'host': node_direct_host(node), 'configs': [],
            }
        node_groups[node_id]['configs'].append(item)

    order = {p: i for i, p in enumerate(DIRECT_PROTOCOLS)}
    key = lambda item: (order.get(item['protocol'], 999), item['name'])
    main['configs'].sort(key=key)
    sections = [main] if main['configs'] else []
    nodes = sorted(node_groups.values(), key=lambda x: ((x.get('title') or '').lower(), x['node_id']))
    for group in nodes:
        group['configs'].sort(key=key)
        if group['configs']:
            sections.append(group)
    return sections


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

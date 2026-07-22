import base64, io, json, os, subprocess, tarfile, time, re, shlex
from datetime import datetime
from pathlib import Path
from flask import current_app
from ..core.extensions import db
from ..core.models import Node, AppSetting, VpnUser, BackupRecord, OutboundProfile, ProtocolOutboundMap, SubscriptionAudit
from .provisioning import user_config_payload, user_access_status, backup_now, service_status_detailed, run_cmd, get_public_host, get_port
from .xray import xray_link, write_xray_config

V17_VERSION = '19.9.19'

CLIENT_FORMATS = ['raw', 'clash', 'singbox', 'hiddify']


def _node_master_host_is_ip_or_local(hostname: str) -> bool:
    host = (hostname or '').strip().strip('[]').lower()
    if host in ('localhost', '127.0.0.1', '::1'):
        return True
    return bool(re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', host))


def _format_node_master_url(raw: str = '', preserve_explicit_scheme: bool = False) -> str:
    """Normalize one candidate master URL without discarding its scheme.

    Nodes may be installed while the admin is browsing by IP, while the panel is
    actually served by a TLS domain, or vice versa. Keep the normalized value
    conservative; the node-side bootstrap/agent will actively probe both HTTP and
    HTTPS variants on the same host/port before selecting the final endpoint.
    """
    from urllib.parse import urlparse
    raw = (raw or '').strip().rstrip('/')
    panel_port = int(get_port('panel') or 0)
    if not raw:
        raw = f'127.0.0.1:{panel_port}' if panel_port else '127.0.0.1'

    explicit_url = raw.startswith(('http://', 'https://'))
    parsed = urlparse(raw if explicit_url else '//' + raw, scheme='')
    hostname = (parsed.hostname or raw.split('/')[0].split(':')[0].strip('[]')).strip()
    explicit_port = parsed.port
    host_is_ip = _node_master_host_is_ip_or_local(hostname)

    if explicit_url:
        scheme = parsed.scheme or 'http'
        effective_port = explicit_port or panel_port
        if (not preserve_explicit_scheme) and host_is_ip and scheme == 'https' and effective_port and effective_port != 443:
            scheme = 'http'
    else:
        if panel_port == 443 and not host_is_ip:
            scheme = 'https'
        else:
            scheme = 'http'

    port = explicit_port
    if not port and panel_port and not (scheme == 'http' and panel_port == 80) and not (scheme == 'https' and panel_port == 443):
        port = panel_port

    if ':' in hostname and not hostname.startswith('[') and not re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', hostname):
        host_part = f'[{hostname}]'
    else:
        host_part = hostname
    netloc = f'{host_part}:{port}' if port else host_part
    return f'{scheme}://{netloc}'


def _node_master_url_candidates(request_base_url: str = '') -> list[str]:
    """Return every plausible master panel URL in priority order.

    v19.9.15: auto-install previously handed the node a single URL. If the panel
    was opened through http://IP:8001 while SSL was on a domain, or the reverse,
    installation could only time out. We now pass all known hosts and let the node
    probe HTTP and HTTPS for each host/port with the current token.
    """
    # Prefer explicitly configured public/domain endpoints before the admin's
    # current request URL. The browser may be opened on https://IP:PORT while the
    # certificate belongs to a domain; using the domain first avoids forcing the
    # node into insecure TLS fallback.
    raw_values = [
        setting('node_master_url', '').strip(),
        setting('panel_public_url', '').strip(),
        setting('subscription_domain', '').strip(),
        setting('public_host', '').strip(),
        setting('tunnel_host', '').strip(),
        get_public_host() or '',
        (request_base_url or '').strip(),
    ]
    out=[]
    for raw in raw_values:
        if not raw:
            continue
        preserve = bool(str(raw).startswith(('http://','https://')))
        try:
            url = _format_node_master_url(raw, preserve_explicit_scheme=preserve)
        except Exception:
            continue
        if url and url not in out:
            out.append(url.rstrip('/'))
    if not out:
        out.append(_format_node_master_url('', preserve_explicit_scheme=False).rstrip('/'))
    return out


def _node_master_url(request_base_url: str = '') -> str:
    return _node_master_url_candidates(request_base_url)[0]


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


def node_package_bytes() -> bytes:
    """Build a small node-runtime package from the exact installed panel version.

    Node installation previously cloned a fixed GitHub repository, which could
    install stale Agent/core scripts that did not match the running panel. The
    package is generated from this installation and is delivered only to a
    valid node token.
    """
    project_root = Path(__file__).resolve().parents[2]
    scripts_dir = project_root / 'scripts'
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for path in sorted(scripts_dir.iterdir() if scripts_dir.exists() else []):
            if not path.is_file() or path.suffix not in ('.sh', '.py', '.js'):
                continue
            tar.add(path, arcname=f'scripts/{path.name}', recursive=False)
        version_file = project_root / 'VERSION'
        if version_file.is_file():
            tar.add(version_file, arcname='VERSION', recursive=False)
    return out.getvalue()


def node_install_command(node, request_base_url=''):
    master_candidates = _node_master_url_candidates(request_base_url)
    protocols = node.protocols or 'openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh'
    direct_ports = {}
    try:
        from .direct_locations import node_direct_port
        selected = [x.strip() for x in str(protocols or '').split(',') if x.strip()]
        direct_ports = {p: node_direct_port(node, p) for p in selected if node_direct_port(node, p)}
    except Exception:
        direct_ports = {}
    masters_json_q = shlex.quote(json.dumps(master_candidates, ensure_ascii=False))
    # v19.9.19: keep node direct-port payload compact and transport it via base64
    # so shell quoting or accidental brace concatenation can never corrupt JSON.
    direct_ports_json = json.dumps({str(k): int(v) for k, v in (direct_ports or {}).items() if int(v or 0) > 0}, ensure_ascii=False, separators=(',', ':'))
    direct_ports_json_q = shlex.quote(direct_ports_json)
    direct_ports_b64_q = shlex.quote(base64.b64encode(direct_ports_json.encode()).decode())
    token_q = shlex.quote(node.api_key or '')
    host_q = shlex.quote(node.host or '')
    protocols_q = shlex.quote(protocols)
    name_q = shlex.quote(node.name or '')
    header_q = shlex.quote('X-NODE-TOKEN: ' + (node.api_key or ''))
    candidate_py = r'''
import json, re, sys
from urllib.parse import urlparse
raws=json.loads(sys.argv[1] or '[]')
out=[]
def add(url):
    url=(url or '').strip().rstrip('/')
    if url and url not in out:
        out.append(url)
def ipish(host):
    host=(host or '').strip('[]').lower()
    return host in ('localhost','127.0.0.1','::1') or bool(re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', host))
for raw in raws:
    raw=(raw or '').strip().rstrip('/')
    if not raw:
        continue
    parsed=urlparse(raw if re.match(r'^https?://', raw, re.I) else '//' + raw)
    scheme=(parsed.scheme or '').lower(); host=parsed.hostname; port=parsed.port
    path='' if not parsed.path or parsed.path=='/' else parsed.path.rstrip('/')
    if not host:
        continue
    hp=f'[{host}]' if ':' in host and not host.startswith('[') else host
    if scheme in ('http','https'):
        if port:
            # Try both transports on the explicit custom panel port. For IP-based
            # HTTPS URLs, try the HTTP companion before any insecure TLS fallback.
            if ipish(host) and scheme == 'https':
                add(f'http://{hp}:{port}{path}')
                add(f'https://{hp}:{port}{path}')
            else:
                add(f'{scheme}://{hp}:{port}{path}')
                other='https' if scheme == 'http' else 'http'
                add(f'{other}://{hp}:{port}{path}')
        else:
            add(f'{scheme}://{hp}{path}')
            other='https' if scheme == 'http' else 'http'
            add(f'{other}://{hp}{path}')
    if ipish(host):
        for p in (8001,8080,5000,80): add(f'http://{hp}:{p}{path}')
        for p in (443,8001,8080): add(f'https://{hp}:{p}{path}')
    else:
        for p in (443,8001,8080): add(f'https://{hp}:{p}{path}')
        for p in (8001,8080,5000,80): add(f'http://{hp}:{p}{path}')
for item in out:
    print(item)
'''.strip()
    direct_ports_decode_sh = 'DIRECT_PORTS_JSON=$(python3 - <<\'PYPORTS\'\nimport base64, json, os, re\nraw = base64.b64decode(os.environ.get(\'IRONPANEL_BOOTSTRAP_DIRECT_PORTS_B64\',\'\') or \'e30=\').decode(\'utf-8\',\'ignore\')\ntext = str(raw or \'{}\').strip().strip(\'\\x00\')\ndef clean(d):\n    out={}\n    if isinstance(d, dict):\n        for k,v in d.items():\n            try:\n                p=int(v)\n                if 0 < p <= 65535: out[str(k)] = p\n            except Exception: pass\n    return out\ndef load(s):\n    try: return clean(json.loads(s or \'{}\'))\n    except Exception: return None\nout = load(text)\nif out is None:\n    candidates=[]\n    if \'{\' in text and \'}\' in text:\n        first=text.find(\'{\'); depth=0\n        for i,ch in enumerate(text[first:], start=first):\n            if ch == \'{\': depth += 1\n            elif ch == \'}\':\n                depth -= 1\n                if depth == 0: candidates.append(text[first:i+1])\n        s=text[first:]\n        while s:\n            candidates.append(s)\n            if s.count(\'}\') <= s.count(\'{\'): break\n            s=s[:-1].rstrip()\n    for c in candidates:\n        out=load(c)\n        if out is not None: break\nif out is None:\n    out = clean({m.group(1): int(m.group(2)) for m in re.finditer(r"[\\\'\\\"]?([A-Za-z0-9_]+)[\\\'\\\"]?\\s*:\\s*([0-9]{1,5})", text)})\nprint(json.dumps(out or {}, separators=(\',\',\':\')))\nPYPORTS\n)'.strip()
    return "\n".join([
        'set -e',
        'export DEBIAN_FRONTEND=noninteractive',
        'echo "[node-bootstrap] starting authenticated runtime bootstrap"',
        'if [ "$(id -u)" -eq 0 ]; then SUDO=""; elif command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else echo "Run this installer as root or install sudo" >&2; exit 2; fi',
        'echo "[node-bootstrap] installing bootstrap prerequisites"',
        '$SUDO apt-get update || true',
        '$SUDO apt-get install -y curl ca-certificates python3 python3-venv iproute2 iptables tar || { echo "[node-bootstrap] ERROR: prerequisite package install failed" >&2; exit 11; }',
        'NODE_TMP=$(mktemp -d /tmp/ironpanel-node-install.XXXXXX)',
        "trap 'rm -rf \"$NODE_TMP\"' EXIT",
        f'IRONPANEL_BOOTSTRAP_MASTERS={masters_json_q}',
        f'IRONPANEL_BOOTSTRAP_DIRECT_PORTS_B64={direct_ports_b64_q}',
        direct_ports_decode_sh,
        "cat > \"$NODE_TMP/master_candidates.py\" <<'PYMASTERS'\n" + candidate_py + "\nPYMASTERS",
        'python3 "$NODE_TMP/master_candidates.py" "$IRONPANEL_BOOTSTRAP_MASTERS" > "$NODE_TMP/master-candidates.txt"',
        "sed -n 's/^/[node-bootstrap] candidate: /p' \"$NODE_TMP/master-candidates.txt\"",
        'echo "[node-bootstrap] downloading runtime package from panel"',
        'RESOLVED_MASTER=""',
        'DOWNLOAD_ERRORS=""',
        '# First pass: accept only normal HTTP or TLS-valid HTTPS. Do not accept https://IP with -k before domain/http candidates have been tried.',
        'while IFS= read -r BASE; do [ -n "$BASE" ] || continue; URL="${BASE%/}/api/v2/node/package"; echo "[node-bootstrap] trying runtime package: $URL"; if curl -fsSL --connect-timeout 8 --max-time 45 -H ' + header_q + ' "$URL" -o "$NODE_TMP/node-runtime.tar.gz"; then RESOLVED_MASTER="${BASE%/}"; IRONPANEL_NODE_INSECURE_TLS=0; break; fi; RC=$?; DOWNLOAD_ERRORS="$DOWNLOAD_ERRORS | $URL curl=$RC"; done < "$NODE_TMP/master-candidates.txt"',
        '# Second pass: only if every strict candidate failed, allow self-signed/IP-mismatch HTTPS with explicit insecure marker.',
        'if [ -z "$RESOLVED_MASTER" ]; then while IFS= read -r BASE; do [ -n "$BASE" ] || continue; URL="${BASE%/}/api/v2/node/package"; printf %s "$URL" | grep -qi "^https://" || continue; echo "[node-bootstrap] trying runtime package with TLS fallback: $URL"; if curl -fksSL --connect-timeout 8 --max-time 45 -H ' + header_q + ' "$URL" -o "$NODE_TMP/node-runtime.tar.gz"; then RESOLVED_MASTER="${BASE%/}"; IRONPANEL_NODE_INSECURE_TLS=1; break; fi; RC=$?; DOWNLOAD_ERRORS="$DOWNLOAD_ERRORS | $URL insecure-curl=$RC"; done < "$NODE_TMP/master-candidates.txt"; fi',
        'test -n "$RESOLVED_MASTER" || { echo "[node-bootstrap] ERROR: runtime package download failed for all HTTP/HTTPS panel candidates:$DOWNLOAD_ERRORS" >&2; exit 12; }',
        'test -s "$NODE_TMP/node-runtime.tar.gz" || { echo "[node-bootstrap] ERROR: downloaded runtime package is empty" >&2; exit 13; }',
        'echo "[node-bootstrap] selected panel endpoint: $RESOLVED_MASTER"',
        'echo "[node-bootstrap] extracting runtime package"',
        'tar -xzf "$NODE_TMP/node-runtime.tar.gz" -C "$NODE_TMP" || { echo "[node-bootstrap] ERROR: runtime package extraction failed" >&2; exit 14; }',
        'test -s "$NODE_TMP/scripts/install_node.sh" && test -s "$NODE_TMP/scripts/node_agent.py" && test -s "$NODE_TMP/scripts/install_node_cores.sh" || { echo "[node-bootstrap] ERROR: runtime package is incomplete" >&2; find "$NODE_TMP" -maxdepth 3 -type f >&2 || true; exit 15; }',
        'cd "$NODE_TMP"',
        'echo "[node-bootstrap] launching node installer"',
        f'$SUDO bash scripts/install_node.sh --master "$RESOLVED_MASTER" --token {token_q} --host {host_q} --protocols {protocols_q} --name {name_q} --direct-ports "$DIRECT_PORTS_JSON" --install-cores $([ "${{IRONPANEL_NODE_INSECURE_TLS:-0}}" = "1" ] && printf %s --insecure-tls)',
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
    try:
        if payload.get('ping_ms') is not None and hasattr(node, 'ping_ms'):
            node.ping_ms = float(payload.get('ping_ms') or 0)
    except Exception:
        pass
    node.traffic_rx_bytes = int(payload.get('traffic_rx_bytes') or 0)
    node.traffic_tx_bytes = int(payload.get('traffic_tx_bytes') or 0)
    node.last_error = str(payload.get('last_error') or '')[:5000]
    try:
        if hasattr(node, 'protocol_health_json') and payload.get('protocol_health') is not None:
            node.protocol_health_json = json.dumps(payload.get('protocol_health') or {}, ensure_ascii=False)[:10000]
        if hasattr(node, 'online_users'):
            node.online_users = int(payload.get('online_users') or 0)
    except Exception:
        pass
    try:
        from .direct_locations import apply_node_usage_reports
        apply_node_usage_reports(node, payload.get('usage_reports') or [])
    except Exception:
        pass
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
            'last_seen': n.last_seen.isoformat() if n.last_seen else None, 'ping_ms': getattr(n,'ping_ms',0), 'online_users': getattr(n,'online_users',0), 'protocol_health_json': getattr(n,'protocol_health_json',''),
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
    payload = user_config_payload(user)
    # Keep the main server first, followed by one Xray link per direct node.
    names = ['xray.txt'] + sorted(
        name for name in payload if re.match(r'^node-\d+-xray\.txt$', str(name))
    )
    links = []
    for name in names:
        body = (payload.get(name) or '').strip()
        if body:
            links.append(body)
    if links:
        return '\n'.join(links).strip() + '\n'
    link = xray_link(user)
    return (link.strip() + '\n') if link else '\n'


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

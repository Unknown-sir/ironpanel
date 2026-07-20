import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import math
import os
import shlex
import json
from flask import current_app
from ..core.models import Admin, VpnUser, ActivityLog, AppSetting, DailyUsage, OnlineSession
from ..core.extensions import db

DEFAULT_PORTS = {
    'panel': 8080,
    'openvpn_udp': 1194,
    'openvpn_tcp': 1195,
    'ocserv_tcp': 8445,
    'ocserv_udp': 8445,
    'l2tp_udp': 1701,
    'ipsec_ike': 500,
    'ipsec_nat': 4500,
    'wireguard_udp': 51820,
    'xray_tcp': 443,
    'xray_api': 10085,
    'pptp_tcp': 1723,
    'hysteria2_udp': 4433,
    'telegram_proxy_base': 6969,
    'ssh_tcp': 422,
}


PROTOCOLS = ['openvpn', 'ocserv', 'l2tp', 'wireguard', 'xray', 'pptp', 'hysteria2', 'telegram_proxy', 'ssh']

def run_cmd(args, input_text=None, timeout=None):
    return subprocess.run(args, input=input_text, text=True, capture_output=True, check=False, timeout=timeout)

def shlex_quote(value):
    return shlex.quote(str(value or ''))

def log(actor, action, target=None, details=None):
    db.session.add(ActivityLog(actor=actor, action=action, target=target, details=details))
    db.session.commit()

def get_setting(key, default=None):
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, '') else default

def set_setting(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        row = AppSetting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)
    db.session.commit()
    return row

def get_public_host():
    return get_setting('tunnel_host') or get_setting('public_host') or current_app.config['PUBLIC_HOST']


def _normalize_public_base_url(raw: str | None, default_scheme: str = 'https') -> str:
    """Return a clean public base URL without trailing slash.

    Admins may enter a domain/subdomain, IP, host:port or a full URL.
    Full URLs are respected exactly. Plain domains default to HTTPS, while
    plain IP/localhost values default to HTTP to avoid broken certificate
    expectations when the admin intentionally uses an IP-based subscription host.
    """
    value = str(raw or '').strip().rstrip('/')
    if not value:
        return ''
    if value.startswith(('http://', 'https://')):
        return value
    host = value.split('/')[0].split(':')[0].strip('[]')
    is_ipv4 = bool(re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', host))
    is_local = host in ('localhost', '127.0.0.1')
    scheme = 'http' if (is_ipv4 or is_local) else default_scheme
    return f'{scheme}://{value}'

def get_subscription_base_url() -> str:
    """Dedicated subscription base URL, falling back to the panel URL."""
    sub_domain = get_setting('subscription_domain', '')
    if sub_domain:
        return _normalize_public_base_url(sub_domain, 'https')
    panel_host = get_public_host()
    if str(panel_host).startswith(('http://', 'https://')):
        return str(panel_host).rstrip('/')
    # Keep the panel port in fallback URLs; dedicated subscription domains should
    # normally be entered as a full hostname or URL and can be reverse-proxied.
    return f'http://{panel_host}:{get_port("panel")}'

def subscription_url_for_user(user: VpnUser) -> str:
    return f'{get_subscription_base_url()}/s/{user.subscription_token}'

def get_port(name):
    return int(get_setting(f'port_{name}', DEFAULT_PORTS.get(name, 0)))

def active_protocols():
    raw = get_setting('active_protocols', 'openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy,ssh')
    selected = [p for p in raw.split(',') if p in PROTOCOLS]
    try:
        from .license import filter_protocols_for_license
        return [p for p in filter_protocols_for_license(selected) if p in PROTOCOLS]
    except Exception:
        return selected

def openvpn_transport():
    proto = (get_setting('openvpn_transport', 'udp') or 'udp').lower().strip()
    return 'tcp' if proto == 'tcp' else 'udp'

def openvpn_port():
    return get_port('openvpn_tcp') if openvpn_transport() == 'tcp' else get_port('openvpn_udp')

def ocserv_transport():
    val=(get_setting('ocserv_transport','tcp_udp') or 'tcp_udp').lower().strip()
    return val if val in ('tcp','udp','tcp_udp') else 'tcp_udp'

def wireguard_transport():
    # WireGuard kernel protocol is UDP; the UI stores the requested mode but runtime remains UDP.
    return 'udp'

def wireguard_mtu():
    try:
        mtu = int(get_setting('wireguard_mtu', '1280') or 1280)
    except Exception:
        mtu = 1280
    return max(576, min(mtu, 1500))

def wireguard_keepalive():
    try:
        keepalive = int(get_setting('wireguard_persistent_keepalive', '25') or 25)
    except Exception:
        keepalive = 25
    return max(0, min(keepalive, 120))


def wireguard_dns():
    """Comma-separated DNS servers for generated WireGuard client configs."""
    raw = (get_setting('wireguard_dns', '1.1.1.1') or '1.1.1.1').strip()
    parts = []
    for item in raw.replace('؛', ',').replace(';', ',').split(','):
        val = item.strip()
        if not val:
            continue
        # Keep this permissive so admins can use IPv4, IPv6 or local DNS names.
        if len(val) <= 80 and all(c.isalnum() or c in '.:-_' for c in val):
            parts.append(val)
    return ', '.join(parts[:4]) or '1.1.1.1'

def l2tp_transport():
    # L2TP/IPsec standard ports are UDP-only.
    return 'udp'


def pptp_transport():
    return 'tcp'

def hysteria2_transport():
    # Hysteria2 is QUIC-based and uses UDP.
    return 'udp'

def ssh_port() -> int:
    try:
        port = int(get_setting('port_ssh_tcp', '422') or 422)
    except Exception:
        port = 422
    return max(1, min(port, 65535))


def hysteria2_password_for(user: VpnUser) -> str:
    import hashlib
    seed = f'{user.subscription_token}:{user.username}:{get_setting("hysteria2_obfs_password","")}'
    return hashlib.sha256(seed.encode()).hexdigest()[:32]

def telegram_proxy_base_port() -> int:
    try:
        base = int(get_setting('port_telegram_proxy_base', '6969') or 6969)
    except Exception:
        base = 6969
    return max(1024, min(base, 60000))


def telegram_proxy_port_for(user: VpnUser | None = None) -> int:
    """Telegram Proxy now uses one shared TCP port for all users.

    User separation is done by MTProto secret, not by port. This keeps the
    service practical for firewalls/CDNs and lets one systemd service serve all
    users while the IronPanel wrapper accounts traffic per secret/user_id.
    """
    return telegram_proxy_base_port()


def telegram_proxy_secret_for(user: VpnUser) -> str:
    import hashlib
    seed = f'{user.subscription_token}:{user.username}:telegram-proxy:{get_setting("telegram_proxy_secret_salt","")}'
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def _telegram_proxy_server_host() -> str:
    # Telegram proxy links must contain only a host/IP in the server field,
    # never a scheme, path, or panel port. Admins often paste https://domain:port
    # in Public Host, so normalize it before generating tg://proxy links.
    from urllib.parse import urlparse
    raw = str(get_public_host() or '').strip()
    if not raw:
        return '127.0.0.1'
    candidate = raw
    if '://' not in candidate:
        candidate = 'http://' + candidate
    try:
        parsed = urlparse(candidate)
        host = parsed.hostname or raw.split('/')[0].split(':')[0]
    except Exception:
        host = raw.split('/')[0].split(':')[0]
    return str(host or raw).strip('[]')




def _gateway_endpoint_for(protocol: str, default_host: str, default_port: int | None = None):
    """Return host/port for generated client configs.

    v19.8.22: Gateway mode is transparent relay mode. Client configs must keep
    the main-panel IP/domain; the main server forwards/relays the traffic to the
    selected node and relays the response back.
    """
    return default_host, int(default_port or 0)

def telegram_proxy_link_for(user: VpnUser) -> str:
    from urllib.parse import quote
    host = _telegram_proxy_server_host()
    port = telegram_proxy_base_port()
    host, port = _gateway_endpoint_for('telegram_proxy', host, port)
    secret = telegram_proxy_secret_for(user)
    return f'tg://proxy?server={quote(str(host), safe="")}&port={port}&secret={secret}'


def _telegram_proxy_service_name(user: VpnUser | None = None) -> str:
    return 'ironpanel-tgproxy'


def _telegram_proxy_root() -> Path:
    return Path('/opt/ironpanel-telegram-proxy')


def telegram_proxy_core_status():
    base = _telegram_proxy_root()
    wrapper = base / 'ironpanel' / 'ironpanel_mtproxy.js'
    config = base / 'ironpanel' / 'config.json'
    usage = base / 'ironpanel' / 'usage.json'
    node = shutil.which('node') or shutil.which('nodejs') or ''
    p = run_cmd(['bash', '-lc', "systemctl list-units 'ironpanel-tgproxy.service' 'ironpanel-tgproxy-*.service' --all --no-legend --no-pager 2>/dev/null | awk '{print $1, $3, $4}'"])
    units = []
    for line in (p.stdout or '').splitlines():
        parts = line.split()
        if parts:
            units.append({'unit': parts[0], 'active': parts[1] if len(parts)>1 else '', 'sub': parts[2] if len(parts)>2 else ''})
    log_tail = ''
    try:
        lp = Path('/var/log/ironpanel-tgproxy.log')
        if lp.exists():
            log_tail = '\n'.join(lp.read_text(errors='ignore').splitlines()[-25:])
    except Exception:
        log_tail = ''
    return {
        'base': str(base),
        'repo': get_setting('telegram_proxy_repo', 'https://github.com/Unknown-sir/JSMTProxy.git'),
        'installed': wrapper.exists(),
        'config_exists': config.exists(),
        'usage_exists': usage.exists(),
        'node': node,
        'base_port': telegram_proxy_base_port(),
        'shared_port': telegram_proxy_base_port(),
        'enabled': 'telegram_proxy' in active_protocols(),
        'units': units,
        'unit_count': len([u for u in units if u.get('unit') == 'ironpanel-tgproxy.service']),
        'last_error': _get_setting_raw('telegram_proxy_last_error',''),
        'last_usage_error': _get_setting_raw('usage_last_error_telegram_proxy',''),
        'log_tail': log_tail,
    }


def _telegram_proxy_usage_snapshot() -> dict:
    path = _telegram_proxy_root() / 'ironpanel' / 'usage.json'
    try:
        data = json.loads(path.read_text(errors='ignore'))
        return data.get('users', {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def telegram_proxy_user_rows(users=None):
    rows = []
    usage_snapshot = _telegram_proxy_usage_snapshot()
    svc = 'ironpanel-tgproxy.service'
    sp = run_cmd(['bash','-lc', f"systemctl is-active {shlex.quote(svc)} 2>/dev/null || true"])
    svc_active = (sp.stdout or '').strip()
    for u in list(users if users is not None else VpnUser.query.order_by(VpnUser.id.desc()).all()):
        enabled_for_user = ('telegram_proxy' in active_protocols()) and protocol_enabled_for_user(u, 'telegram_proxy') and bool(u.enabled)
        used = user_usage_summary(u) if u.id else {}
        usage_row = usage_snapshot.get(str(u.id), {})
        rows.append({
            'id': u.id,
            'username': u.username,
            'enabled': bool(u.enabled),
            'protocol_enabled': enabled_for_user,
            'port': telegram_proxy_base_port(),
            'secret': telegram_proxy_secret_for(u),
            'link': telegram_proxy_link_for(u) if enabled_for_user else '',
            'service': svc,
            'service_active': svc_active,
            'proxy_rx': int(usage_row.get('rx') or 0),
            'proxy_tx': int(usage_row.get('tx') or 0),
            'proxy_connections': int(usage_row.get('connections') or 0),
            'proxy_last_seen': usage_row.get('last_seen') or '',
            'used_human': used.get('used_human',''),
            'limit_human': used.get('total_human',''),
            'remaining_human': used.get('remaining_human',''),
        })
    return rows


def _write_telegram_proxy_instances(users=None, restart=True):
    """Provision one shared Telegram MTProto proxy service with per-user secrets.

    Previous builds created one port and one systemd service per user. Telegram
    MTProto is much better served from one shared TCP port; this wrapper matches
    the initial client handshake against every enabled user's secret and writes
    per-user byte counters to usage.json for quota enforcement.
    """
    base = _telegram_proxy_root()
    runtime = base / 'ironpanel'
    runtime.mkdir(parents=True, exist_ok=True)
    # Always stop legacy per-user services from older versions.
    run_cmd(['bash','-lc', 'systemctl disable --now ironpanel-tgproxy-*.service >/dev/null 2>&1 || true; rm -f /etc/systemd/system/ironpanel-tgproxy-*.service >/dev/null 2>&1 || true'])
    if 'telegram_proxy' not in active_protocols():
        run_cmd(['bash','-lc', 'systemctl disable --now ironpanel-tgproxy.service >/dev/null 2>&1 || true'])
        return True
    # Install dependencies/source as a compatibility check. The actual runtime is
    # IronPanel's wrapper because upstream JSMTProxy config supports only one
    # secret in config.json.
    try:
        repo = shlex_quote(get_setting('telegram_proxy_repo', 'https://github.com/Unknown-sir/JSMTProxy.git'))
        run_cmd(['bash', '-lc', f'IRONPANEL_TGPROXY_REPO={repo} /opt/ironpanel/scripts/repair_telegram_proxy.sh --install-only >/dev/null 2>&1 || true'], timeout=120)
    except Exception:
        pass
    source_wrapper = Path('/opt/ironpanel/scripts/ironpanel_mtproxy.js')
    if not source_wrapper.exists():
        _put_setting_raw('telegram_proxy_last_error', 'ironpanel_mtproxy.js missing. Re-run upgrade or repair.')
        return False
    shutil.copy2(source_wrapper, runtime / 'ironpanel_mtproxy.js')
    os.chmod(runtime / 'ironpanel_mtproxy.js', 0o755)
    users = list(users if users is not None else _valid_users())
    user_rows = []
    for u in users:
        enabled = bool(u.enabled) and (('telegram_proxy' in active_protocols()) and protocol_enabled_for_user(u, 'telegram_proxy'))
        if enabled:
            user_rows.append({'id': str(u.id), 'username': u.username, 'secret': telegram_proxy_secret_for(u), 'enabled': True})
    cfg = {
        'port': telegram_proxy_base_port(),
        'mode': 'single-port-multi-secret',
        'users': user_rows,
    }
    (runtime / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n')
    port = telegram_proxy_base_port()
    run_cmd(['bash','-lc', f'ufw allow {port}/tcp >/dev/null 2>&1 || true; iptables -C INPUT -p tcp --dport {port} -m comment --comment ironpanel-tgproxy-shared -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport {port} -m comment --comment ironpanel-tgproxy-shared -j ACCEPT || true'])
    service_path = Path('/etc/systemd/system/ironpanel-tgproxy.service')
    node_bin = shutil.which('node') or shutil.which('nodejs') or '/usr/bin/node'
    log_file = '/var/log/ironpanel-tgproxy.log'
    service_text = f"""[Unit]
Description=IronPanel shared Telegram MTProto proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={runtime}
Environment=IRONPANEL_TGPROXY_CONFIG={runtime}/config.json
Environment=IRONPANEL_TGPROXY_USAGE={runtime}/usage.json
Environment=IRONPANEL_TGPROXY_LOG={log_file}
ExecStartPre={node_bin} --check {runtime}/ironpanel_mtproxy.js
ExecStart={node_bin} {runtime}/ironpanel_mtproxy.js
Restart=always
RestartSec=3
LimitNOFILE=81920
StandardOutput=append:{log_file}
StandardError=append:{log_file}

[Install]
WantedBy=multi-user.target
"""
    service_path.write_text(service_text)
    run_cmd(['systemctl','daemon-reload'])
    if restart:
        run_cmd(['bash','-lc', f'systemctl stop ironpanel-tgproxy.service >/dev/null 2>&1 || true; pkill -f {shlex_quote(str(runtime / "ironpanel_mtproxy.js"))} >/dev/null 2>&1 || true'])
        run_cmd(['systemctl','enable','ironpanel-tgproxy.service'])
        run_cmd(['systemctl','restart','ironpanel-tgproxy.service'])
    else:
        # Do not interrupt existing Telegram proxy sessions during normal user edits.
        # The caller will explicitly restart only when telegram_proxy is part of the affected set.
        run_cmd(['systemctl','enable','ironpanel-tgproxy.service'])
    _put_setting_raw('telegram_proxy_last_error', '')
    return True

def ensure_hysteria2_tls_files(host: str | None = None) -> tuple[str, str]:
    """Return usable Hysteria2 cert/key paths and create a local fallback when needed.

    Auto SSL can replace these paths with Let's Encrypt files. Until then Hysteria2
    still works with a local self-signed cert and generated clients use insecure=1.
    """
    import subprocess
    host = host or get_public_host()
    cert = get_setting('hysteria2_tls_cert_file', '/etc/hysteria/server.crt') or '/etc/hysteria/server.crt'
    key = get_setting('hysteria2_tls_key_file', '/etc/hysteria/server.key') or '/etc/hysteria/server.key'
    if 'YOUR_DOMAIN' in cert or not Path(cert).exists() or not Path(key).exists():
        cert = '/etc/hysteria/server.crt'
        key = '/etc/hysteria/server.key'
    cpath, kpath = Path(cert), Path(key)
    if not cpath.exists() or not kpath.exists():
        cpath.parent.mkdir(parents=True, exist_ok=True)
        kpath.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(['openssl','req','-x509','-nodes','-newkey','rsa:2048','-keyout',str(kpath),'-out',str(cpath),'-days','3650','-subj',f'/CN={host}'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    return str(cpath), str(kpath)


def _user_used_bytes(user: VpnUser) -> int:
    """Return exact raw accounted bytes. Falls back to old MB columns on upgraded installs."""
    try:
        exact = int((getattr(user, 'used_upload_bytes', 0) or 0) + (getattr(user, 'used_download_bytes', 0) or 0))
    except Exception:
        exact = 0
    if exact > 0:
        return exact
    return int(((user.used_upload_mb or 0) + (user.used_download_mb or 0)) * 1024 * 1024)

def _traffic_limit_bytes(user: VpnUser) -> int:
    return int(user.data_limit_mb or 0) * 1024 * 1024

def normalize_traffic_multiplier(value, default=1.0):
    """Parse and clamp the global traffic accounting multiplier.

    The multiplier is a billing/accounting factor, not a daemon-level byte counter.
    Raw bytes stay intact; effective/charged usage is derived from raw bytes.
    """
    try:
        factor = float(str(value if value is not None else default).strip().replace(',', '.'))
    except Exception:
        factor = float(default)
    if not math.isfinite(factor) or factor <= 0:
        factor = float(default)
    return max(0.01, min(100.0, factor))

def traffic_multiplier_settings():
    enabled = str(get_setting('traffic_multiplier_enabled', '0') or '0').lower() in ('1', 'true', 'yes', 'on')
    factor = normalize_traffic_multiplier(get_setting('traffic_multiplier_value', '1'), 1.0)
    effective_factor = factor if enabled else 1.0
    return {
        'enabled': enabled,
        'value': factor,
        'factor': effective_factor,
        'label': f"x{effective_factor:g}",
    }

def set_traffic_multiplier(enabled, value):
    factor = normalize_traffic_multiplier(value, 1.0)
    set_setting('traffic_multiplier_enabled', '1' if enabled else '0')
    set_setting('traffic_multiplier_value', f'{factor:g}')
    return traffic_multiplier_settings()


def ip_limit_settings():
    enabled = str(get_setting('ip_limit_enabled', '0') or '0').lower() in ('1', 'true', 'yes', 'on')
    try:
        default_limit = int(get_setting('ip_limit_default', '0') or 0)
    except Exception:
        default_limit = 0
    action = (get_setting('ip_limit_action', 'disable') or 'disable').strip()
    if action not in ('disable', 'log'):
        action = 'disable'
    return {'enabled': enabled, 'default_limit': max(0, default_limit), 'action': action}


def set_ip_limit_settings(enabled, default_limit, action='disable'):
    try:
        default_limit = max(0, int(default_limit or 0))
    except Exception:
        default_limit = 0
    action = action if action in ('disable', 'log') else 'disable'
    set_setting('ip_limit_enabled', '1' if enabled else '0')
    set_setting('ip_limit_default', str(default_limit))
    set_setting('ip_limit_action', action)
    return ip_limit_settings()


def get_user_ip_limit(user: VpnUser) -> int:
    row = get_setting(f'ip_limit_user_{user.id}', '')
    if row not in (None, ''):
        try:
            return max(0, int(row))
        except Exception:
            return 0
    settings = ip_limit_settings()
    return int(settings.get('default_limit') or 0) if settings.get('enabled') else 0


def set_user_ip_limit(user: VpnUser, limit):
    try:
        limit = max(0, int(limit or 0))
    except Exception:
        limit = 0
    set_setting(f'ip_limit_user_{user.id}', str(limit))
    return limit


def active_ip_count_for_user(user: VpnUser, minutes: int = 15) -> int:
    try:
        cutoff = datetime.utcnow().timestamp() - minutes * 60
        ips = set()
        for s in OnlineSession.query.filter_by(user_id=user.id, active=True).all():
            if not s.remote_ip:
                continue
            # last_seen is authoritative when present, otherwise count the active row.
            if getattr(s, 'last_seen', None):
                try:
                    if s.last_seen.timestamp() < cutoff:
                        continue
                except Exception:
                    pass
            ips.add(s.remote_ip)
        return len(ips)
    except Exception:
        return 0


def enforce_ip_limits(commit=True):
    settings = ip_limit_settings()
    if not settings.get('enabled'):
        return 0
    stopped = []
    for user in VpnUser.query.all():
        if not user.enabled:
            continue
        limit = get_user_ip_limit(user)
        if limit <= 0:
            continue
        count = active_ip_count_for_user(user)
        if count > limit:
            detail = f'ip_limit:{count}>{limit}'
            db.session.add(ActivityLog(actor='system', action='ip_limit_exceeded', target=user.username, details=detail))
            if settings.get('action') == 'disable':
                user.enabled = False
                stopped.append(user.username)
    if stopped:
        db.session.commit()
        try:
            sync_all_users(restart=True)
        except Exception as exc:
            _put_setting_raw('ip_limit_sync_error', str(exc)[-500:])
    if commit:
        db.session.commit()
    return len(stopped)


def subscription_theme_settings():
    return {
        'brand_name': get_setting('sub_brand_name', 'IronPanel'),
        'notice': get_setting('sub_notice', 'تمام کانفیگ‌های فعال این کاربر از همین صفحه دریافت می‌شوند.'),
        'support_url': get_setting('sub_support_url', ''),
        'theme_color': get_setting('sub_theme_color', '#2f66ff'),
        'show_raw_configs': str(get_setting('sub_show_raw_configs', '1')) == '1',
    }


def set_subscription_theme(form):
    set_setting('sub_brand_name', form.get('sub_brand_name', 'IronPanel'))
    set_setting('sub_notice', form.get('sub_notice', ''))
    set_setting('sub_support_url', form.get('sub_support_url', ''))
    color = form.get('sub_theme_color', '#2f66ff') or '#2f66ff'
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color.strip()):
        color = '#2f66ff'
    set_setting('sub_theme_color', color)
    set_setting('sub_show_raw_configs', '1' if form.get('sub_show_raw_configs') else '0')
    return subscription_theme_settings()

def _effective_usage_bytes(raw_bytes: int) -> int:
    settings = traffic_multiplier_settings()
    return int(math.ceil(max(0, int(raw_bytes or 0)) * float(settings.get('factor') or 1.0)))

def _user_effective_used_bytes(user: VpnUser) -> int:
    return _effective_usage_bytes(_user_used_bytes(user))

def _format_bytes(num: int) -> str:
    num = max(0, int(num or 0))
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{int(value)} {unit}'
            return f'{value:.2f} {unit}'
        value /= 1024

def user_access_status(user: VpnUser):
    if not user.enabled:
        return False, 'کاربر غیرفعال است'
    # expires_at=None means unlimited. data_limit_mb=0 means unlimited traffic.
    if user.expired:
        return False, 'اعتبار کاربر منقضی شده است'
    limit = _traffic_limit_bytes(user)
    if limit > 0 and _user_effective_used_bytes(user) >= limit:
        return False, 'حجم کاربر تمام شده است'
    return True, 'فعال'

def _valid_users():
    return [u for u in VpnUser.query.all() if user_access_status(u)[0]]

def _safe_cn(username: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', username or 'user')
    return safe[:64] or 'user'

def _openvpn_cn(user: VpnUser) -> str:
    # Keep certificate CN ASCII-only and unique even when the panel username is Persian/Unicode.
    base = _safe_cn(user.username)
    uid = getattr(user, 'id', None) or 0
    return f'ip{uid}-{base}'[:64] if uid else base

def _find_user_by_identity(identity: str):
    user = VpnUser.query.filter_by(username=identity).first()
    if user:
        return user
    for u in VpnUser.query.all():
        if _safe_cn(u.username) == identity or _openvpn_cn(u) == identity:
            return u
    return None

def _easyrsa_dir() -> Path:
    return Path('/etc/openvpn/easy-rsa')

def _ensure_openvpn_cert(user: VpnUser):
    """Create a nopass per-user OpenVPN certificate so the profile connects without username/password."""
    cn = _openvpn_cn(user)
    easy = _easyrsa_dir()
    issued = easy / 'pki' / 'issued' / f'{cn}.crt'
    key = easy / 'pki' / 'private' / f'{cn}.key'
    if issued.exists() and key.exists():
        return cn
    if easy.exists() and (easy / 'easyrsa').exists():
        run_cmd(['bash', '-lc', f'cd {easy} && EASYRSA_BATCH=1 ./easyrsa build-client-full {cn} nopass'])
    return cn

def _revoke_openvpn_cert(username: str, user_id=None):
    cn = f'ip{user_id}-{_safe_cn(username)}'[:64] if user_id else _safe_cn(username)
    easy = _easyrsa_dir()
    if not easy.exists() or not (easy / 'easyrsa').exists():
        return
    run_cmd(['bash', '-lc', f'cd {easy} && EASYRSA_BATCH=1 ./easyrsa revoke {cn} >/dev/null 2>&1 || true && EASYRSA_BATCH=1 ./easyrsa gen-crl >/dev/null 2>&1 || true'])
    crl = easy / 'pki' / 'crl.pem'
    if crl.exists():
        shutil.copy2(crl, '/etc/openvpn/server/crl.pem')
        Path('/etc/openvpn/server/crl.pem').chmod(0o644)

def _ensure_wg_identity(user: VpnUser, index_hint: int = 10):
    if not user.wg_private_key or not user.wg_public_key:
        priv = run_cmd(['wg', 'genkey']).stdout.strip()
        if not priv:
            priv = 'CLIENT_PRIVATE_KEY_' + user.username
        pub = run_cmd(['wg', 'pubkey'], input_text=priv + '\n').stdout.strip()
        if not pub:
            pub = 'CLIENT_PUBLIC_KEY_' + user.username
        user.wg_private_key = priv
        user.wg_public_key = pub
    if not user.wg_ip:
        used = {u.wg_ip for u in VpnUser.query.all() if u.wg_ip}
        for i in range(index_hint, 250):
            ip = f'10.66.66.{i}'
            if ip not in used:
                user.wg_ip = ip
                break
    db.session.commit()


def _ssh_account_name(user: VpnUser) -> str:
    # Linux usernames must be ASCII-safe. Prefix by id to avoid collisions.
    base = _safe_cn(user.username).lower().strip('._-') or 'user'
    uid = getattr(user, 'id', None) or 0
    return f'ipssh{uid}-{base}'[:31] if uid else base[:31]


def _ssh_password_for(user: VpnUser) -> str:
    return user.l2tp_password or user.cisco_password or 'managed-by-panel'


def _write_ssh_users(users=None):
    """Synchronize restricted OpenSSH accounts for the IronPanel SSH protocol."""
    script = Path('/opt/ironpanel/scripts/repair_ssh.sh')
    if script.exists():
        run_cmd(['bash', str(script), '--install'], timeout=120)
    run_cmd(['bash','-lc','groupadd -r ironpanel-ssh 2>/dev/null || true'])
    wanted = set()
    for u in list(users if users is not None else _valid_users()):
        enabled = bool(u.enabled) and ('ssh' in active_protocols()) and protocol_enabled_for_user(u, 'ssh')
        if not enabled:
            continue
        account = _ssh_account_name(u)
        wanted.add(account)
        comment = f'IronPanel SSH user {u.id}:{u.username}'
        if run_cmd(['id','-u',account]).returncode != 0:
            run_cmd(['useradd','-m','-s','/bin/bash','-g','ironpanel-ssh','-c',comment,account])
        else:
            run_cmd(['usermod','-g','ironpanel-ssh','-s','/bin/bash','-c',comment,account])
        password = _ssh_password_for(u)
        run_cmd(['chpasswd'], input_text=f'{account}:{password}\n')
        run_cmd(['passwd','-u',account])
    passwd = Path('/etc/passwd')
    if passwd.exists():
        for line in passwd.read_text(errors='ignore').splitlines():
            parts=line.split(':')
            if len(parts) < 5:
                continue
            name, comment = parts[0], parts[4]
            if name.startswith('ipssh') and 'IronPanel SSH user' in comment and name not in wanted:
                run_cmd(['passwd','-l',name])
                run_cmd(['usermod','-s','/usr/sbin/nologin',name])
    try:
        mp = Path('/etc/ironpanel/ssh-users.map')
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text('\n'.join(f'{_ssh_account_name(u)}:{u.id}:{u.username}' for u in list(users if users is not None else _valid_users()) if protocol_enabled_for_user(u, 'ssh'))+'\n')
    except Exception:
        pass
    run_cmd(['bash','-lc', f'ufw allow {ssh_port()}/tcp >/dev/null 2>&1 || true; iptables -C INPUT -p tcp --dport {ssh_port()} -m comment --comment ironpanel-ssh -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport {ssh_port()} -m comment --comment ironpanel-ssh -j ACCEPT || true'])
    return True

def _write_plain_passwords(root: Path):
    users = _valid_users()
    passwd = root / 'users.passwd'
    passwd.write_text(''.join(f'{u.username}:{u.l2tp_password or "managed-by-panel"}\n' for u in users))
    chap = Path('/etc/ppp/chap-secrets')
    if chap.parent.exists():
        chap.write_text(''.join(f'"{u.username}" l2tpd "{u.l2tp_password or "managed-by-panel"}" *\n' for u in users) + ''.join(f'"{u.username}" pptpd "{u.l2tp_password or "managed-by-panel"}" *\n' for u in users))
        chap.chmod(0o600)
    ocpasswd = root / 'ocpasswd'
    ocpasswd.unlink(missing_ok=True)
    for u in users:
        password = u.cisco_password or u.l2tp_password or 'managed-by-panel'
        run_cmd(['ocpasswd', '-c', str(ocpasswd), u.username], input_text=f'{password}\n{password}\n')
    if ocpasswd.exists():
        ocpasswd.chmod(0o600)


def _ensure_wireguard_interface_value(config_text: str, key: str, value: str) -> str:
    """Set or insert a WireGuard [Interface] key while preserving peers."""
    lines = config_text.splitlines()
    in_interface = False
    found = False
    insert_at = None
    out = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '[Interface]':
            in_interface = True
            insert_at = len(out) + 1
            out.append(line)
            continue
        if stripped.startswith('[') and stripped != '[Interface]':
            if in_interface and not found:
                out.append(f'{key} = {value}')
                found = True
            in_interface = False
        if in_interface and stripped.lower().startswith(key.lower() + ' '):
            out.append(f'{key} = {value}')
            found = True
            continue
        out.append(line)
    if not found:
        if insert_at is None:
            out.insert(0, '[Interface]')
            out.insert(1, f'{key} = {value}')
        else:
            out.insert(insert_at, f'{key} = {value}')
    return '\n'.join(out).rstrip() + '\n'

def _rewrite_wireguard_server(root: Path, restart=True):
    wg_conf = Path('/etc/wireguard/wg0.conf')
    wg_conf.parent.mkdir(parents=True, exist_ok=True)
    if not wg_conf.exists():
        priv_file = Path('/etc/wireguard/server_private.key')
        pub_file = root / 'wg_server_public.key'
        priv_file.parent.mkdir(parents=True, exist_ok=True)
        if not priv_file.exists():
            generated = run_cmd(['bash','-lc','wg genkey 2>/dev/null || openssl rand -base64 32']).stdout.strip()
            priv_file.write_text(generated+'\n'); priv_file.chmod(0o600)
        pub = run_cmd(['wg','pubkey'], input_text=priv_file.read_text()).stdout.strip() or 'SERVER_PUBLIC_KEY'
        pub_file.write_text(pub+'\n')
        wg_conf.write_text(f'''[Interface]
Address = 10.66.66.1/24
ListenPort = {get_port('wireguard_udp')}
MTU = {wireguard_mtu()}
PrivateKey = {priv_file.read_text().strip()}
SaveConfig = false
PostUp = sysctl -w net.ipv4.ip_forward=1; iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || true
# BEGIN IRONPANEL PEERS
# END IRONPANEL PEERS
''')
        wg_conf.chmod(0o600)
    users = _valid_users()
    for idx, u in enumerate(users, start=10):
        _ensure_wg_identity(u, idx)
    txt = wg_conf.read_text()
    base = txt.split('# BEGIN IRONPANEL PEERS')[0].rstrip()
    base = _ensure_wireguard_interface_value(base, 'ListenPort', str(get_port('wireguard_udp'))).rstrip()
    base = _ensure_wireguard_interface_value(base, 'MTU', str(wireguard_mtu())).rstrip()
    peers = ['# BEGIN IRONPANEL PEERS']
    for u in users:
        if protocol_enabled_for_user(u, 'wireguard'):
            peers.append(f'\n[Peer]\n# {u.username}\nPublicKey = {u.wg_public_key}\nAllowedIPs = {u.wg_ip}/32')
    peers.append('# END IRONPANEL PEERS\n')
    wg_conf.write_text(base + '\n\n' + '\n'.join(peers))
    if restart:
        _apply_wireguard_runtime()

def _apply_wireguard_runtime():
    """Apply WireGuard peer changes with the least disruption possible.

    `wg syncconf` updates peers in-place and avoids dropping all WireGuard users.
    If the interface is down or the tools are unavailable, we fall back to the
    old service restart so repair/install workflows still recover correctly.
    """
    try:
        active = run_cmd(['systemctl', 'is-active', '--quiet', 'wg-quick@wg0']).returncode == 0
        if active and shutil.which('wg') and shutil.which('wg-quick'):
            p = run_cmd(['bash', '-lc', 'wg syncconf wg0 <(wg-quick strip wg0) >/dev/null 2>&1'])
            if p.returncode == 0:
                return True
    except Exception:
        pass
    return run_cmd(['systemctl', 'restart', 'wg-quick@wg0']).returncode == 0

def _restart_runtime_services():
    service_groups = [
        ['openvpn-server@server'],
        ['xray'],
        ['ocserv'],
        ['strongswan-starter', 'strongswan', 'ipsec'],
        ['xl2tpd'],
        ['pptpd'],
        ['hysteria-server', 'hysteria2', 'hysteria'],
        ['wg-quick@wg0'],
        ['ironpanel-tgproxy.service'],
        ['ssh', 'sshd'],
    ]
    for group in service_groups:
        for svc in group:
            if '*' in svc:
                p = run_cmd(['bash','-lc', f'systemctl restart {svc} >/dev/null 2>&1 || true'])
            else:
                p = run_cmd(['systemctl', 'restart', svc])
            if p.returncode == 0:
                break

def _user_protocol_set(user: VpnUser) -> set[str]:
    """Protocols that can be affected by a change to this user."""
    try:
        values = user.allowed_protocol_list() or user.protocol_list() or active_protocols()
    except Exception:
        values = active_protocols()
    return {p for p in values if p in PROTOCOLS}


def _service_restart_first_available(names: list[str]) -> bool:
    for svc in names:
        p = run_cmd(['bash', '-lc', f'systemctl reload-or-restart {shlex.quote(svc)} >/dev/null 2>&1 || systemctl restart {shlex.quote(svc)} >/dev/null 2>&1'])
        if p.returncode == 0:
            return True
    return False


def _reload_protocols(protocols) -> dict:
    """Reload only the runtime cores that are actually affected by a user change.

    This is the Smart Core Reload path. It replaces the previous behavior where
    creating/editing/deleting a single user could restart every VPN core and
    briefly disconnect unrelated users.
    """
    affected = {p for p in (protocols or []) if p in PROTOCOLS}
    result = {}
    if not affected:
        return result
    try:
        if 'wireguard' in affected:
            result['wireguard'] = bool(_apply_wireguard_runtime())
        if 'xray' in affected:
            try:
                from .xray import write_xray_config
                ok, out = write_xray_config(_valid_users(), restart=True)
                result['xray'] = bool(ok)
                if not ok:
                    _put_setting_raw('xray_sync_last_error', str(out)[-500:])
            except Exception as exc:
                result['xray'] = False
                _put_setting_raw('xray_sync_last_error', str(exc)[-500:])
        if 'telegram_proxy' in affected:
            result['telegram_proxy'] = bool(_write_telegram_proxy_instances(_valid_users(), restart=True))
        if 'ssh' in affected:
            # OpenSSH accounts are applied through useradd/usermod/chpasswd; avoid restarting sshd.
            result['ssh'] = bool(_write_ssh_users(_valid_users()))
        if 'openvpn' in affected:
            result['openvpn'] = _service_restart_first_available(['openvpn-server@server', 'openvpn@server'])
        if 'ocserv' in affected:
            result['ocserv'] = _service_restart_first_available(['ocserv'])
        if 'l2tp' in affected:
            result['l2tp'] = _service_restart_first_available(['strongswan-starter', 'strongswan', 'ipsec', 'xl2tpd'])
        if 'pptp' in affected:
            result['pptp'] = _service_restart_first_available(['pptpd'])
        if 'hysteria2' in affected:
            result['hysteria2'] = _service_restart_first_available(['hysteria-server', 'hysteria2', 'hysteria'])
        _put_setting_raw('smart_core_reload_last', json.dumps({'protocols': sorted(affected), 'result': result, 'at': datetime.utcnow().isoformat(timespec='seconds')}, ensure_ascii=False))
    except Exception as exc:
        _put_setting_raw('smart_core_reload_last_error', str(exc)[-800:])
    return result


def _sync_protocol_state(protocols=None, restart=True):
    """Rewrite config files for all users, then reload only selected protocols."""
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    affected = {p for p in (protocols or PROTOCOLS) if p in PROTOCOLS}
    users = _valid_users()
    for idx, u in enumerate(users, start=10):
        if 'wireguard' in affected:
            _ensure_wg_identity(u, idx)
        if 'openvpn' in affected and protocol_enabled_for_user(u, 'openvpn'):
            _ensure_openvpn_cert(u)
    if affected.intersection({'openvpn', 'ocserv', 'l2tp', 'pptp'}):
        _write_plain_passwords(root)
    if 'ssh' in affected:
        _write_ssh_users(users)
    if 'wireguard' in affected:
        _rewrite_wireguard_server(root, restart=False)
    if 'telegram_proxy' in affected:
        _write_telegram_proxy_instances(users, restart=False)
    if 'xray' in affected:
        try:
            from .xray import write_xray_config
            write_xray_config(users, restart=False)
        except Exception as exc:
            _put_setting_raw('xray_sync_last_error', str(exc)[-500:])
    for u in VpnUser.query.all():
        generate_profiles(u)
    if restart:
        _reload_protocols(affected)
    return True


def sync_user(user: VpnUser, restart=True, changed_protocols=None, previous_protocols=None):
    affected = set(changed_protocols or _user_protocol_set(user))
    if previous_protocols:
        affected |= set(previous_protocols)
    _sync_protocol_state(affected, restart=restart)
    generate_profiles(user)
    return True


def sync_all_users(restart=False):
    # Full manual/repair sync still rebuilds every protocol, but restart behavior is explicit.
    return _sync_protocol_state(PROTOCOLS, restart=restart)


def disable_user(user: VpnUser):
    affected = _user_protocol_set(user)
    user.enabled = False
    db.session.commit()
    sync_user(user, restart=True, changed_protocols=affected)


def delete_user(user: VpnUser):
    username = user.username
    affected = _user_protocol_set(user)
    _revoke_openvpn_cert(username, user.id)
    _revoke_openvpn_cert(username)  # revoke legacy CN too
    shutil.rmtree(current_app.config['CONFIG_ROOT'] / 'profiles' / username, ignore_errors=True)
    db.session.delete(user)
    db.session.commit()
    _sync_protocol_state(affected, restart=True)

def _read_file(path):
    p = Path(path)
    return p.read_text() if p.exists() else ''

def generate_profiles(user: VpnUser):
    root = current_app.config['CONFIG_ROOT'] / 'profiles' / user.username
    root.mkdir(parents=True, exist_ok=True)
    host = get_public_host()
    ovpn_proto = openvpn_transport()
    ovpn_selected_port = openvpn_port()
    ovpn_host, ovpn_selected_port = _gateway_endpoint_for('openvpn', host, ovpn_selected_port)
    oc_tcp = get_port('ocserv_tcp')
    oc_host, oc_tcp = _gateway_endpoint_for('ocserv', host, oc_tcp)
    wg_port = get_port('wireguard_udp')
    wg_host, wg_port = _gateway_endpoint_for('wireguard', host, wg_port)
    l2tp_host, _l2tp_unused_port = _gateway_endpoint_for('l2tp', host, get_port('l2tp_udp'))
    pptp_host, pptp_port_value = _gateway_endpoint_for('pptp', host, get_port('pptp_tcp'))
    hy_host, hy_port_value = _gateway_endpoint_for('hysteria2', host, get_port('hysteria2_udp'))
    ssh_host, ssh_port_value = _gateway_endpoint_for('ssh', host, ssh_port())
    ca = _read_file('/etc/openvpn/server/ca.crt')
    tls = _read_file('/etc/openvpn/server/tls-crypt.key')
    cn = _ensure_openvpn_cert(user) if user.enabled and not user.expired else _safe_cn(user.username)
    cert = _read_file(f'/etc/openvpn/easy-rsa/pki/issued/{cn}.crt')
    key = _read_file(f'/etc/openvpn/easy-rsa/pki/private/{cn}.key')
    ovpn = f'''client
dev tun
proto {ovpn_proto}
remote {ovpn_host} {ovpn_selected_port}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
auth SHA256
cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
verb 3
<ca>
{ca.strip()}
</ca>
<cert>
{cert.strip()}
</cert>
<key>
{key.strip()}
</key>
'''
    if tls:
        ovpn += f'<tls-crypt>\n{tls.strip()}\n</tls-crypt>\n'
    ovpn_filename = f'{_safe_cn(user.username)}.ovpn'
    root.joinpath(ovpn_filename).write_text(ovpn)
    for legacy in ['openvpn.ovpn', 'openvpn-udp.ovpn', 'openvpn-tcp.ovpn']:
        (root / legacy).unlink(missing_ok=True)
    psk_file = current_app.config['CONFIG_ROOT'] / 'ipsec.psk'
    psk = psk_file.read_text().strip() if psk_file.exists() else 'set-during-install'
    root.joinpath('l2tp.txt').write_text(f'''Server: {l2tp_host}
Type: L2TP/IPsec PSK
Username: {user.username}
Password: {user.l2tp_password or "same-as-panel"}
PSK: {psk}
Ports: UDP 500, 4500, 1701
''')
    root.joinpath('ocserv.txt').write_text(f'''Server: {oc_host}:{oc_tcp}
Username: {user.username}
Password: {user.cisco_password or "same-as-panel"}
Transport mode: {ocserv_transport()}
Client: Cisco AnyConnect / OpenConnect
''')
    server_pub_file = current_app.config['CONFIG_ROOT'] / 'wg_server_public.key'
    server_pub = server_pub_file.read_text().strip() if server_pub_file.exists() else 'SERVER_PUBLIC_KEY'
    if user.enabled and not user.expired:
        _ensure_wg_identity(user)
    root.joinpath('wireguard.conf').write_text(f'''[Interface]
PrivateKey = {user.wg_private_key or "generated-on-server"}
Address = {user.wg_ip or "10.66.66.x"}/32
DNS = {wireguard_dns()}
MTU = {wireguard_mtu()}

[Peer]
PublicKey = {server_pub}
Endpoint = {wg_host}:{wg_port} # UDP
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = {wireguard_keepalive()}
''')
    try:
        if protocol_enabled_for_user(user, 'xray'):
            from .xray import write_user_xray_profile
            write_user_xray_profile(user)
        else:
            root.joinpath('xray.txt').unlink(missing_ok=True)
    except Exception as exc:
        root.joinpath('xray_error.txt').write_text('Xray profile generation error: '+str(exc))
    if protocol_enabled_for_user(user, 'pptp'):
        root.joinpath('pptp.txt').write_text(f'''Server: {pptp_host}
Port: {pptp_port_value} TCP
Username: {user.username}
Password: {user.l2tp_password or "same-as-panel"}
Type: PPTP
''')
    else:
        root.joinpath('pptp.txt').unlink(missing_ok=True)
    if protocol_enabled_for_user(user, 'hysteria2'):
        from urllib.parse import quote
        hy_port = hy_port_value
        hy_pass = hysteria2_password_for(user)
        hy_cert, hy_key = ensure_hysteria2_tls_files(hy_host)
        hy_secure = get_setting('ssl_enabled', '0') == '1' and bool(hy_cert) and Path(hy_cert).exists() and bool(hy_key) and Path(hy_key).exists() and 'server.crt' not in hy_cert
        hy_insecure = '0' if hy_secure else '1'
        hy_yaml_insecure = 'false' if hy_secure else 'true'
        safe_user = quote(hy_pass, safe='')
        # Keep subscription clean: one Hysteria2 profile only.
        hy_query = f'sni={hy_host}&insecure={hy_insecure}'
        hy_uri = f'hy2://{safe_user}@{hy_host}:{hy_port}/?{hy_query}#{user.username}-IronPanel-Hysteria2'
        root.joinpath('hysteria2.txt').write_text(hy_uri + '\n')
        root.joinpath('hysteria2.yaml').unlink(missing_ok=True)
    else:
        root.joinpath('hysteria2.txt').unlink(missing_ok=True)
        root.joinpath('hysteria2.yaml').unlink(missing_ok=True)
    if ('ssh' in active_protocols()) and protocol_enabled_for_user(user, 'ssh'):
        ssh_account = _ssh_account_name(user)
        ssh_password = _ssh_password_for(user)
        root.joinpath('ssh.txt').write_text(f"""Server: {ssh_host}
Port: {ssh_port_value}
Username: {ssh_account}
Password: {ssh_password}
Protocol: SSH
""")
    else:
        root.joinpath('ssh.txt').unlink(missing_ok=True)

    if ('telegram_proxy' in active_protocols()) and protocol_enabled_for_user(user, 'telegram_proxy'):
        tg_link = telegram_proxy_link_for(user)
        root.joinpath('telegram_proxy.txt').write_text(tg_link + '\n')
    else:
        root.joinpath('telegram_proxy.txt').unlink(missing_ok=True)

def user_config_payload(user: VpnUser):
    ok, reason = user_access_status(user)
    if not ok:
        return {'ACCOUNT_STATUS.txt': reason}
    generate_profiles(user)
    root = current_app.config['CONFIG_ROOT'] / 'profiles' / user.username
    files = {}
    allowed=[p for p in (user.allowed_protocol_list() or user.protocol_list() or active_protocols()) if p in active_protocols()]
    wanted=[]
    if 'openvpn' in allowed: wanted.append(f'{_safe_cn(user.username)}.ovpn')
    if 'wireguard' in allowed: wanted.append('wireguard.conf')
    if 'ocserv' in allowed: wanted.append('ocserv.txt')
    if 'l2tp' in allowed: wanted.append('l2tp.txt')
    if 'xray' in allowed: wanted.append('xray.txt')
    if 'pptp' in allowed: wanted.append('pptp.txt')
    if 'hysteria2' in allowed:
        wanted.append('hysteria2.txt')
    if 'telegram_proxy' in allowed and 'telegram_proxy' in active_protocols():
        wanted.append('telegram_proxy.txt')
    if 'ssh' in allowed and 'ssh' in active_protocols():
        wanted.append('ssh.txt')
    for name in wanted:
        p = root / name
        if p.exists():
            files[name] = p.read_text()
    try:
        from .direct_locations import enrich_payload_with_direct_locations
        files = enrich_payload_with_direct_locations(user, files, allowed)
    except Exception as exc:
        files['direct_locations_error.txt'] = 'Direct Location profile generation error: ' + str(exc)
    return files


def _get_setting_raw(key, default=''):
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value is not None else default

def _put_setting_raw(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        db.session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)

def _add_usage_delta(user: VpnUser, upload_bytes: int, download_bytes: int, source: str):
    """Apply positive traffic deltas using exact bytes.

    v13.4 fixes the old MB-flooring bug: previously a 300 KB delta was rounded
    down to zero and then lost forever. Now bytes are accumulated exactly and the
    MB compatibility columns are derived from the exact byte total.
    """
    upload_bytes = max(0, int(upload_bytes or 0))
    download_bytes = max(0, int(download_bytes or 0))
    if upload_bytes <= 0 and download_bytes <= 0:
        return False

    current_up = int(getattr(user, 'used_upload_bytes', 0) or 0)
    current_down = int(getattr(user, 'used_download_bytes', 0) or 0)
    if current_up == 0 and (user.used_upload_mb or 0):
        current_up = int(user.used_upload_mb or 0) * 1024 * 1024
    if current_down == 0 and (user.used_download_mb or 0):
        current_down = int(user.used_download_mb or 0) * 1024 * 1024

    user.used_upload_bytes = current_up + upload_bytes
    user.used_download_bytes = current_down + download_bytes
    user.used_upload_mb = int(user.used_upload_bytes // (1024 * 1024))
    user.used_download_mb = int(user.used_download_bytes // (1024 * 1024))
    _charge_reseller_usage(user, upload_bytes, download_bytes, source)

    # DailyUsage remains MB based for existing reports, but we keep sub-MB data in
    # the exact counters above so nothing is lost between sync runs.
    upload_mb = int(upload_bytes // (1024 * 1024))
    download_mb = int(download_bytes // (1024 * 1024))
    day = datetime.utcnow().strftime('%Y-%m-%d')
    row = DailyUsage.query.filter_by(user_id=user.id, day=day).first()
    if not row:
        row = DailyUsage(user_id=user.id, day=day, upload_mb=0, download_mb=0)
        db.session.add(row)
    row.upload_mb = int(row.upload_mb or 0) + upload_mb
    row.download_mb = int(row.download_mb or 0) + download_mb
    return True



def _charge_reseller_usage(user: VpnUser, upload_bytes: int, download_bytes: int, source: str):
    """Charge reseller quota from real usage deltas only.

    This is intentionally cumulative and independent from current child users:
    deleting/resetting a VPN user must not reduce reseller consumed quota.
    """
    owner_id = getattr(user, 'owner_id', None)
    delta = max(0, int(upload_bytes or 0)) + max(0, int(download_bytes or 0))
    if not owner_id or delta <= 0:
        return
    reseller = Admin.query.filter_by(id=owner_id, role='sub_admin').first()
    if not reseller:
        return
    current = int(getattr(reseller, 'reseller_used_bytes', 0) or 0)
    reseller.reseller_used_bytes = current + delta
    quota_bytes = int(getattr(reseller, 'traffic_quota_gb', 0) or 0) * 1024 * 1024 * 1024
    if quota_bytes > 0 and int(reseller.reseller_used_bytes or 0) >= quota_bytes:
        # Freeze all active users of this reseller so the quota is enforced from real traffic.
        for child in VpnUser.query.filter_by(owner_id=reseller.id, enabled=True).all():
            child.enabled = False
        log('system', 'reseller_quota_exhausted', reseller.username, f'quota={quota_bytes}; used={reseller.reseller_used_bytes}; source={source}')


def _account_runtime_counter(user: VpnUser, source: str, rx: int, tx: int):
    """Account a runtime counter that resets on reconnect/interface restart."""
    key = f'usage_last_{source}_{user.id}'
    old = _get_setting_raw(key, '0:0')
    try:
        old_rx, old_tx = [int(x or 0) for x in old.split(':', 1)]
    except Exception:
        old_rx, old_tx = 0, 0
    d_rx = rx - old_rx if rx >= old_rx else rx
    d_tx = tx - old_tx if tx >= old_tx else tx
    changed = _add_usage_delta(user, d_rx, d_tx, source)
    _put_setting_raw(key, f'{rx}:{tx}')
    return changed


def _collect_telegram_proxy_usage():
    """Collect per-user Telegram proxy traffic from wrapper usage.json."""
    changed = 0
    usage_snapshot = _telegram_proxy_usage_snapshot()
    for u in _valid_users():
        if not (('telegram_proxy' in active_protocols()) and protocol_enabled_for_user(u, 'telegram_proxy')):
            continue
        try:
            row = usage_snapshot.get(str(u.id), {})
            rx = int(row.get('rx') or 0)
            tx = int(row.get('tx') or 0)
            if _account_runtime_counter(u, 'telegram_proxy', rx, tx):
                changed += 1
        except Exception:
            continue
    return changed

def _collect_openvpn_usage():
    """Collect OpenVPN usage from status logs.

    v13.5 fixes status-version 2 parsing. OpenVPN status-version 2 columns are:
    CLIENT_LIST,CN,Real Address,Virtual Address,Virtual IPv6 Address,Bytes Received,Bytes Sent,...
    so byte counters are columns 5 and 6, not 3 and 4. The old parser read the
    virtual address as a number and skipped every active client, leaving usage at 0.
    """
    paths = [Path('/var/log/openvpn/status.log'), Path('/run/openvpn-server/status-server.log'), Path('/etc/openvpn/server/status.log'), Path('/var/log/openvpn/openvpn-status.log')]
    changed = 0
    for path in paths:
        if not path.exists():
            continue
        try:
            lines = path.read_text(errors='ignore').splitlines()
        except Exception:
            continue
        in_v1_clients = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('CLIENT_LIST,'):
                parts = line.split(',')
                if len(parts) >= 7:
                    username = parts[1].strip()
                    rx_s, tx_s = parts[5], parts[6]
                elif len(parts) >= 5:
                    # status-version 1 / legacy fallback
                    username = parts[1].strip()
                    rx_s, tx_s = parts[3], parts[4]
                else:
                    continue
                try:
                    rx = int(rx_s or 0)  # client upload to server
                    tx = int(tx_s or 0)  # server download to client
                except Exception:
                    continue
                user = _find_user_by_identity(username)
                if not user:
                    continue
                if _account_runtime_counter(user, 'openvpn', rx, tx):
                    changed += 1
                continue
            # status-version 1 fallback: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
            if line.startswith('Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since'):
                in_v1_clients = True
                continue
            if line.startswith('ROUTING TABLE'):
                in_v1_clients = False
            if in_v1_clients and ',' in line and not line.startswith('Updated,'):
                parts = line.split(',')
                if len(parts) >= 4:
                    username = parts[0].strip()
                    try:
                        rx, tx = int(parts[2] or 0), int(parts[3] or 0)
                    except Exception:
                        continue
                    user = _find_user_by_identity(username)
                    if user and _account_runtime_counter(user, 'openvpn', rx, tx):
                        changed += 1
        break
    return changed

def _collect_wireguard_usage():
    """Collect WireGuard usage from `wg show wg0 transfer`.

    Output format is: public_key rx_bytes tx_bytes
    rx_bytes is upload from peer to server; tx_bytes is download from server to peer.
    """
    p = run_cmd(['bash', '-lc', 'wg show wg0 transfer 2>/dev/null || true'])
    changed = 0
    for line in (p.stdout or '').splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        pub, rx_s, tx_s = parts[0], parts[1], parts[2]
        user = VpnUser.query.filter_by(wg_public_key=pub).first()
        if not user:
            continue
        try:
            rx, tx = int(rx_s), int(tx_s)
        except Exception:
            continue
        if _account_runtime_counter(user, 'wireguard', rx, tx):
            changed += 1
    return changed

def collect_usage_from_runtime():
    """Best-effort real traffic accounting for active VPN daemons.

    The installer also creates a systemd timer that runs this every minute.
    It is safe to call from web pages; it only applies positive deltas.
    """
    changed = 0
    try:
        changed += _collect_openvpn_usage()
    except Exception as exc:
        _put_setting_raw('usage_last_error_openvpn', str(exc)[-500:])
    try:
        changed += _collect_wireguard_usage()
    except Exception as exc:
        _put_setting_raw('usage_last_error_wireguard', str(exc)[-500:])
    try:
        from .xray import collect_xray_usage
        changed += collect_xray_usage(_account_runtime_counter)
    except Exception as exc:
        _put_setting_raw('usage_last_error_xray', str(exc)[-500:])
    try:
        changed += _collect_telegram_proxy_usage()
    except Exception as exc:
        _put_setting_raw('usage_last_error_telegram_proxy', str(exc)[-500:])
    db.session.commit()
    # Enforce immediately after accounting so a limited user is stopped as soon as possible.
    try:
        enforce_usage_limits(commit=True)
        enforce_ip_limits(commit=True)
    except Exception as exc:
        _put_setting_raw('usage_enforce_last_error', str(exc)[-500:])
        db.session.commit()
    return changed

def enforce_usage_limits(commit=True):
    """Disable and de-provision users that are expired or over traffic limit.

    This is the actual quota enforcement layer. Once a user crosses the limit,
    the user is disabled, removed from password files / WireGuard peers, and VPN
    services are restarted so active sessions are dropped and new sessions are blocked.
    """
    stopped = []
    for user in VpnUser.query.all():
        if not user.enabled:
            continue
        reason = None
        if user.expired:
            reason = 'expired'
        else:
            limit = _traffic_limit_bytes(user)
            if limit > 0 and _user_effective_used_bytes(user) >= limit:
                reason = 'traffic_limit'
        if reason:
            user.enabled = False
            stopped.append((user.username, reason))
            db.session.add(ActivityLog(actor='system', action='auto_disable_user', target=user.username, details=reason))
    if stopped:
        db.session.commit()
        try:
            sync_all_users(restart=True)
        except Exception as exc:
            _put_setting_raw('usage_enforce_sync_error', str(exc)[-500:])
    if commit:
        db.session.commit()
    return len(stopped)

def user_usage_summary(user: VpnUser):
    raw_used_bytes = _user_used_bytes(user)
    raw_upload_bytes = int(getattr(user, 'used_upload_bytes', 0) or 0) or int(user.used_upload_mb or 0) * 1024 * 1024
    raw_download_bytes = int(getattr(user, 'used_download_bytes', 0) or 0) or int(user.used_download_mb or 0) * 1024 * 1024
    multiplier = traffic_multiplier_settings()
    factor = float(multiplier.get('factor') or 1.0)
    used_bytes = int(math.ceil(raw_used_bytes * factor))
    upload_bytes = int(math.ceil(raw_upload_bytes * factor))
    download_bytes = int(math.ceil(raw_download_bytes * factor))
    total = int(user.data_limit_mb or 0)
    total_bytes = total * 1024 * 1024
    remaining_bytes = 0 if total_bytes > 0 and used_bytes >= total_bytes else ((total_bytes - used_bytes) if total_bytes > 0 else None)
    now = datetime.utcnow()
    if user.expires_at:
        delta = user.expires_at - now
        remaining_seconds = max(0, int(delta.total_seconds()))
        remaining_days = remaining_seconds // 86400
    else:
        remaining_seconds = None
        remaining_days = None
    return {
        'total_mb': total,
        'total_bytes': total_bytes,
        'total_human': 'نامحدود' if total == 0 else _format_bytes(total_bytes),
        'used_mb': int(used_bytes // (1024 * 1024)),
        'used_bytes': used_bytes,
        'used_human': _format_bytes(used_bytes),
        'upload_mb': int(upload_bytes // (1024 * 1024)),
        'upload_bytes': upload_bytes,
        'upload_human': _format_bytes(upload_bytes),
        'download_mb': int(download_bytes // (1024 * 1024)),
        'download_bytes': download_bytes,
        'download_human': _format_bytes(download_bytes),
        'raw_used_mb': int(raw_used_bytes // (1024 * 1024)),
        'raw_used_bytes': raw_used_bytes,
        'raw_used_human': _format_bytes(raw_used_bytes),
        'raw_upload_mb': int(raw_upload_bytes // (1024 * 1024)),
        'raw_upload_bytes': raw_upload_bytes,
        'raw_upload_human': _format_bytes(raw_upload_bytes),
        'raw_download_mb': int(raw_download_bytes // (1024 * 1024)),
        'raw_download_bytes': raw_download_bytes,
        'raw_download_human': _format_bytes(raw_download_bytes),
        'remaining_mb': int(remaining_bytes // (1024 * 1024)) if remaining_bytes is not None else None,
        'remaining_bytes': remaining_bytes,
        'remaining_human': 'نامحدود' if total == 0 else _format_bytes(remaining_bytes or 0),
        'unlimited_traffic': total == 0,
        'traffic_multiplier_enabled': bool(multiplier.get('enabled')),
        'traffic_multiplier_factor': factor,
        'traffic_multiplier_label': multiplier.get('label', 'x1'),
        'effective_usage': bool(multiplier.get('enabled')),
        'expires_at': user.expires_at,
        'remaining_seconds': remaining_seconds,
        'remaining_days': remaining_days,
        'unlimited_time': user.expires_at is None,
        'ip_limit': get_user_ip_limit(user),
        'ip_active_count': active_ip_count_for_user(user),
    }

def service_status():
    services = ['openvpn-server@server', 'xray', 'ocserv', 'strongswan-starter', 'xl2tpd', 'wg-quick@wg0', 'pptpd', 'hysteria-server', 'ironpanel', 'ssh']
    result = {}
    for svc in services:
        p = run_cmd(['systemctl', 'is-active', svc])
        result[svc] = p.stdout.strip() or p.stderr.strip() or 'unknown'
    return result

def apply_runtime_configs():
    """Rewrite daemon config files to match saved ports. Safe to run repeatedly."""
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    ovpn_dir = Path('/etc/openvpn/server')
    Path('/var/log/openvpn').mkdir(parents=True, exist_ok=True)
    if ovpn_dir.exists():
        if not ovpn_dir.joinpath('crl.pem').exists():
            easy = _easyrsa_dir()
            if easy.exists():
                run_cmd(['bash', '-lc', f'cd {easy} && EASYRSA_BATCH=1 ./easyrsa gen-crl >/dev/null 2>&1 || true'])
                crl = easy / 'pki' / 'crl.pem'
                if crl.exists():
                    shutil.copy2(crl, ovpn_dir / 'crl.pem')
        ovpn_dir.joinpath('server.conf').write_text(f'''port {openvpn_port()}
proto {openvpn_transport()}
dev tun
server 10.8.0.0 255.255.255.0
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
keepalive 10 120
persist-key
persist-tun
# IronPanel OpenVPN runs without privilege drop because client-connect/client-disconnect
# scripts must read/write the IronPanel SQLite database for quota enforcement.
ca /etc/openvpn/server/ca.crt
cert /etc/openvpn/server/server.crt
key /etc/openvpn/server/server.key
dh /etc/openvpn/server/dh.pem
tls-crypt /etc/openvpn/server/tls-crypt.key
auth SHA256
cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
verify-client-cert require
crl-verify /etc/openvpn/server/crl.pem
status /var/log/openvpn/status.log 10
status-version 2
script-security 2
client-connect /opt/ironpanel/scripts/openvpn_client_connect.sh
client-disconnect /opt/ironpanel/scripts/openvpn_client_disconnect.sh
verb 3
''')
    oc = Path('/etc/ocserv/ocserv.conf')
    if oc.parent.exists():
        oc.write_text(f'''tcp-port = {get_port('ocserv_tcp')}
udp-port = {0 if ocserv_transport() == 'tcp' else get_port('ocserv_udp')}
auth = "plain[passwd={root}/ocpasswd]"
server-cert = /etc/ocserv/certs/server-cert.pem
server-key = /etc/ocserv/certs/server-key.pem
socket-file = /var/run/ocserv-socket
occtl-socket-file = /var/run/occtl.socket
device = vpns
try-mtu-discovery = true
ipv4-network = 10.44.0.0
ipv4-netmask = 255.255.255.0
dns = 1.1.1.1
dns = 8.8.8.8
route = default
tunnel-all-dns = true
cisco-client-compat = true
max-clients = 512
max-same-clients = 3
mobile-dpd = 1800
try-mtu-discovery = true
''')
    _rewrite_wireguard_server(root)
    wg = Path('/etc/wireguard/wg0.conf')
    if wg.exists():
        config_text = _ensure_wireguard_interface_value(wg.read_text(), 'ListenPort', str(get_port('wireguard_udp')))
        config_text = _ensure_wireguard_interface_value(config_text, 'MTU', str(wireguard_mtu()))
        txt = config_text.splitlines()
        if not any('PostUp' in line for line in txt):
            txt.insert(4, 'SaveConfig = false')
            txt.insert(5, 'PostUp = sysctl -w net.ipv4.ip_forward=1; iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -j MASQUERADE')
            txt.insert(6, 'PostDown = iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -j MASQUERADE 2>/dev/null || true')
        wg.write_text('\n'.join(txt)+'\n')
    pptp = Path('/etc/pptpd.conf')
    if pptp.parent.exists():
        pptp.write_text('option /etc/ppp/pptpd-options\nlocalip 10.70.70.1\nremoteip 10.70.70.10-250\nlisten 0.0.0.0\n')
    hy = Path('/etc/hysteria/config.yaml')
    hy.parent.mkdir(parents=True, exist_ok=True)
    if get_setting('hysteria2_enabled','1') == '1':
        host=get_public_host(); hy_port=get_port('hysteria2_udp')
        hy_cert, hy_key = ensure_hysteria2_tls_files(hy_host)
        hy.write_text(f'''listen: :{hy_port}
tls:
  cert: {hy_cert}
  key: {hy_key}
  sniGuard: disable
auth:
  type: command
  command: /opt/ironpanel/scripts/hysteria2_auth.sh
bandwidth:
  up: {get_setting('hysteria2_up_mbps','100 mbps')}
  down: {get_setting('hysteria2_down_mbps','300 mbps')}
ignoreClientBandwidth: false
congestion:
  type: bbr
masquerade:
  type: proxy
  proxy:
    url: https://www.cloudflare.com/
    rewriteHost: true
sniff:
  enable: true
  timeout: 2s
''')
    _write_ssh_users(_valid_users())
    sync_all_users(restart=True)
    try:
        from .xray import write_xray_config
        write_xray_config(_valid_users(), restart=True)
    except Exception as exc:
        _put_setting_raw('xray_apply_last_error', str(exc)[-500:])
        db.session.commit()
    return True

# ---- v9 utility modules ----
def telegram_notify(message: str):
    token = get_setting('telegram_bot_token','')
    chat_id = get_setting('telegram_chat_id','')
    if not token or not chat_id:
        return False
    try:
        import requests
        requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat_id, 'text': message}, timeout=5)
        return True
    except Exception:
        return False

def backup_now():
    import tarfile, time
    root = current_app.config['CONFIG_ROOT']
    backup_dir = root / 'backups'; backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / f'ironpanel-backup-{time.strftime("%Y%m%d-%H%M%S")}.tar.gz'
    with tarfile.open(out, 'w:gz') as tar:
        for name in ['ironpanel.db','profiles','wg_server_private.key','wg_server_public.key','ipsec.psk']:
            p = root / name
            if p.exists(): tar.add(p, arcname=name)
    return out

def restore_backup(path):
    import tarfile
    root = current_app.config['CONFIG_ROOT']
    with tarfile.open(path, 'r:gz') as tar:
        tar.extractall(root)
    _write_ssh_users(_valid_users())
    sync_all_users(restart=True)
    try:
        from .xray import write_xray_config
        write_xray_config(_valid_users(), restart=True)
    except Exception as exc:
        _put_setting_raw('xray_apply_last_error', str(exc)[-500:])
        db.session.commit()
    return True

def service_health_repair():
    install = Path('/opt/ironpanel/scripts/install_vpn_core.sh')
    if install.exists():
        run_cmd(['bash', str(install)])
    apply_runtime_configs()
    return service_status()

def protocol_enabled_for_user(user, proto):
    proto = str(proto or '').strip()
    if proto not in active_protocols():
        return False
    return proto in (user.allowed_protocol_list() or user.protocol_list() or active_protocols())


# ---------------- v13 Health diagnostics ----------------
def _unit_status(unit):
    """Collect systemd status safely; never raise to Flask views."""
    import shlex
    try:
        active = run_cmd(['systemctl', 'is-active', unit])
        status = (active.stdout.strip() or active.stderr.strip() or 'unknown')
    except Exception as e:
        status = 'error'
        active = None
        first_error = str(e)
    else:
        first_error = ''
    quoted = shlex.quote(unit)
    try:
        show = run_cmd(['bash','-lc', f'systemctl status {quoted} --no-pager -l 2>&1 | tail -n 100 || true'])
        show_text = (show.stdout or '') + (show.stderr or '')
    except Exception as e:
        show_text = 'systemctl status failed: ' + str(e)
    try:
        journal = run_cmd(['bash','-lc', f'journalctl -u {quoted} -n 160 --no-pager 2>&1 || true'])
        journal_text = (journal.stdout or '') + (journal.stderr or '')
    except Exception as e:
        journal_text = 'journalctl failed: ' + str(e)
    detail = (first_error + '\n' + show_text + '\n\n--- Journal ---\n' + journal_text).strip()
    return {
        'status': status,
        'ok': status == 'active',
        'detail': detail[-16000:],
        'repair_hint': f'systemctl restart {unit}'
    }

def service_status_detailed():
    """Return service status with actionable error details and recent logs.

    Uses safe collection to avoid Internal Server Error if a unit is missing or
    systemd returns unexpected output. StrongSwan unit names differ by Ubuntu
    package, so both common unit names are checked and the healthier one is kept.
    """
    services = ['openvpn-server@server', 'xray', 'ocserv', 'strongswan-starter', 'strongswan', 'xl2tpd', 'wg-quick@wg0', 'pptpd', 'hysteria-server', 'ironpanel', 'ssh']
    result = {}
    for svc in services:
        item = _unit_status(svc)
        # Prefer the active strongSwan unit and avoid showing two rows unless both fail.
        if svc in ('strongswan-starter', 'strongswan'):
            existing = result.get('strongswan')
            if not existing or item.get('ok') or existing.get('status') == 'not-found':
                result['strongswan'] = item | {'repair_hint': item.get('repair_hint','').replace(svc, svc)}
            continue
        result[svc] = item
    return result

def service_error_detail(service_name):
    allowed = ['openvpn-server@server', 'xray', 'ocserv', 'strongswan-starter', 'strongswan', 'xl2tpd', 'wg-quick@wg0', 'pptpd', 'hysteria-server', 'hysteria2', 'hysteria', 'ironpanel', 'ssh', 'sshd']
    aliases = {'strongswan': ['strongswan-starter', 'strongswan']}
    targets = aliases.get(service_name, [service_name])
    if not any(t in allowed for t in targets):
        return 'Unknown service'
    chunks = []
    for t in targets:
        if t in allowed:
            chunks.append(f'### {t}\n' + _unit_status(t).get('detail',''))
    return '\n\n'.join(chunks) if chunks else 'No diagnostics found.'

"""IronPanel Xray Core integration.

Exactly one active Xray inbound/profile is managed at a time. The admin chooses
one profile in the panel, and the subscriber receives only that selected Xray
URI. v16.4 makes the delivered xray.txt file client-importable by keeping it a
clean one-line subscription body instead of explanatory text.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pwd
import grp
import re
import secrets
import subprocess
import uuid
from pathlib import Path
from typing import Iterable, Dict, Any
from sqlalchemy.exc import OperationalError, ProgrammingError
from urllib.parse import quote, urlencode

from flask import current_app

from ..core.extensions import db
from ..core.models import AppSetting, VpnUser

XRAY_CONFIG_PATH = Path('/usr/local/etc/xray/config.json')
XRAY_LOG_DIR = Path('/var/log/xray')

XRAY_PROFILE_TYPES = {
    'vless-reality': {
        'title': 'VLESS + Reality + Vision',
        'protocol': 'vless', 'transport': 'tcp', 'security': 'reality',
        'description': 'پیشنهادی برای استفاده عمومی؛ سریع، مدرن و بدون نیاز به گواهی TLS روی سرور.'
    },
    'vless-ws-tls': {
        'title': 'VLESS + WebSocket + TLS',
        'protocol': 'vless', 'transport': 'ws', 'security': 'tls',
        'description': 'مناسب دامنه و CDN؛ نیازمند گواهی معتبر TLS برای دامنه.'
    },
    'vless-tcp-none': {
        'title': 'VLESS + TCP بدون TLS',
        'protocol': 'vless', 'transport': 'tcp', 'security': 'none',
        'description': 'کانفیگ مستقیم و سبک بدون TLS؛ مناسب تست، شبکه خصوصی یا زمانی که TLS/CDN نیاز نیست.'
    },
    'vless-ws-none': {
        'title': 'VLESS + WebSocket بدون TLS',
        'protocol': 'vless', 'transport': 'ws', 'security': 'none',
        'description': 'وب‌سوکت بدون TLS برای سناریوهای ساده یا پشت پروکسی داخلی.'
    },
    'vless-grpc-none': {
        'title': 'VLESS + gRPC بدون TLS',
        'protocol': 'vless', 'transport': 'grpc', 'security': 'none',
        'description': 'gRPC بدون TLS برای مسیرهای داخلی یا زمانی که TLS در لایه دیگری terminate می‌شود.'
    },
    'vless-grpc-tls': {
        'title': 'VLESS + gRPC + TLS',
        'protocol': 'vless', 'transport': 'grpc', 'security': 'tls',
        'description': 'پروفایل پیشرفته gRPC با TLS برای دامنه و کلاینت‌های جدید.'
    },
    'trojan-tls': {
        'title': 'Trojan + TLS',
        'protocol': 'trojan', 'transport': 'tcp', 'security': 'tls',
        'description': 'اتصال ساده و پایدار با TLS؛ مناسب کلاینت‌های Trojan و Sing-box.'
    },
    'vmess-ws': {
        'title': 'VMess + WebSocket',
        'protocol': 'vmess', 'transport': 'ws', 'security': 'none',
        'description': 'سازگار با کلاینت‌های قدیمی‌تر VMess؛ برای محیط‌های ساده و بدون TLS.'
    },
    'vmess-tcp-none': {
        'title': 'VMess + TCP بدون TLS',
        'protocol': 'vmess', 'transport': 'tcp', 'security': 'none',
        'description': 'VMess مستقیم بدون TLS برای سازگاری با کلاینت‌های قدیمی و تست سریع.'
    },
    'trojan-tcp-none': {
        'title': 'Trojan + TCP بدون TLS',
        'protocol': 'trojan', 'transport': 'tcp', 'security': 'none',
        'description': 'Trojan بدون TLS برای سناریوهای خاص و شبکه‌های داخلی؛ استفاده عمومی با TLS/Reality امن‌تر است.'
    },
    'shadowsocks': {
        'title': 'Shadowsocks AEAD / 2022',
        'protocol': 'shadowsocks', 'transport': 'tcp,udp', 'security': 'none',
        'description': 'کانفیگ سبک Shadowsocks با رمز جداگانه برای هر کاربر. پیش‌فرض روی AEAD سازگار تنظیم شده است.'
    },
}

DEFAULT_XRAY_SETTINGS = {
    'xray_enabled': '1',
    'xray_profile_type': 'vless-reality',
    'xray_domain': '',
    'xray_port': '443',
    'xray_api_port': '10085',
    'xray_uuid_namespace': '',
    'xray_reality_dest': 'www.cloudflare.com:443',
    'xray_reality_sni': 'www.cloudflare.com',
    'xray_reality_server_names': 'www.cloudflare.com,cloudflare.com',
    'xray_reality_private_key': '',
    'xray_reality_public_key': '',
    'xray_reality_short_ids': '',
    'xray_reality_fingerprint': 'chrome',
    'xray_reality_spiderx': '/',
    'xray_flow': 'xtls-rprx-vision',
    'xray_tls_cert_file': '/etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem',
    'xray_tls_key_file': '/etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem',
    'xray_alpn': 'h2,http/1.1',
    'xray_ws_path': '/ironpanel-ws',
    'xray_ws_host': '',
    'xray_grpc_service_name': 'ironpanel-grpc',
    'xray_mux_enabled': '0',
    'xray_sniffing_enabled': '1',
    'xray_dns_servers': '1.1.1.1,8.8.8.8',
    'xray_routing_mode': 'direct',
    'xray_block_private': '0',
    'xray_loglevel': 'warning',
    'xray_ss_method': 'chacha20-ietf-poly1305',
}

INVALID_REALITY_MARKERS = ('RUN_REPAIR_XRAY', 'PLACEHOLDER', 'YOUR_', 'PRIVATE_KEY', 'PUBLIC_KEY')
XRAY_URI_PREFIXES = ('vless://', 'vmess://', 'trojan://', 'ss://')


def run_cmd(args, input_text=None):
    try:
        return subprocess.run(args, input=input_text, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args, 127, '', str(exc))


def _list_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or '').split(',') if x.strip()]


def _looks_like_xray_key(value: str) -> bool:
    value = (value or '').strip()
    if not value or any(m in value for m in INVALID_REALITY_MARKERS):
        return False
    return bool(re.fullmatch(r'[A-Za-z0-9_-]{32,88}', value))


def _valid_short_ids(value: str) -> bool:
    ids = _list_csv(value)
    if not ids:
        return True
    for sid in ids:
        if len(sid) > 16 or len(sid) % 2 != 0 or not re.fullmatch(r'[0-9a-fA-F]*', sid):
            return False
    return True


def _ensure_path(value: str, fallback: str = '/') -> str:
    value = (value or fallback or '/').strip()
    if not value.startswith('/'):
        value = '/' + value
    return value


def _xray_bin() -> str:
    for candidate in ('/usr/local/bin/xray', '/usr/bin/xray'):
        if Path(candidate).exists():
            return candidate
    p = run_cmd(['bash', '-lc', 'command -v xray 2>/dev/null || true'])
    return (p.stdout or '').strip() or 'xray'


def prepare_xray_runtime() -> None:
    XRAY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    XRAY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    access = XRAY_LOG_DIR / 'access.log'
    error = XRAY_LOG_DIR / 'error.log'
    for f in (access, error):
        try:
            f.touch(exist_ok=True)
        except Exception:
            pass
    for path in (XRAY_LOG_DIR, access, error):
        try:
            os.chown(path, 0, 0)
        except Exception:
            pass
    try:
        XRAY_LOG_DIR.chmod(0o755)
    except Exception:
        pass
    for f in (access, error):
        try:
            f.chmod(0o644)
        except Exception:
            pass


def _ensure_database_schema() -> None:
    try:
        db.create_all()
    except Exception:
        pass


def _query_setting_row(key: str):
    try:
        return AppSetting.query.filter_by(key=key).first()
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        _ensure_database_schema()
        return AppSetting.query.filter_by(key=key).first()


def _setting(key: str, default: str = '') -> str:
    row = _query_setting_row(key)
    if row and row.value not in (None, ''):
        return str(row.value)
    return default


def _set_setting_no_commit(key: str, value: str):
    row = _query_setting_row(key)
    if not row:
        db.session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)


def ensure_xray_defaults(commit: bool = True):
    _ensure_database_schema()
    for key, value in DEFAULT_XRAY_SETTINGS.items():
        row = _query_setting_row(key)
        if not row:
            _set_setting_no_commit(key, value)
    if not _setting('xray_uuid_namespace', ''):
        _set_setting_no_commit('xray_uuid_namespace', str(uuid.uuid4()))
    if not _setting('xray_reality_short_ids', '') or not _valid_short_ids(_setting('xray_reality_short_ids', '')):
        _set_setting_no_commit('xray_reality_short_ids', secrets.token_hex(4))
    if commit:
        db.session.commit()


def update_xray_settings(form) -> Dict[str, str]:
    ensure_xray_defaults(commit=False)
    for key in DEFAULT_XRAY_SETTINGS.keys():
        if key in ('xray_enabled', 'xray_mux_enabled', 'xray_sniffing_enabled', 'xray_block_private'):
            _set_setting_no_commit(key, '1' if form.get(key) else '0')
        else:
            _set_setting_no_commit(key, form.get(key, _setting(key, DEFAULT_XRAY_SETTINGS.get(key, ''))))
    # Normalize values that must match both server config and client URI.
    _set_setting_no_commit('xray_ws_path', _ensure_path(_setting('xray_ws_path', '/ironpanel-ws'), '/ironpanel-ws'))
    _set_setting_no_commit('xray_reality_spiderx', _ensure_path(_setting('xray_reality_spiderx', '/'), '/'))
    db.session.commit()
    return xray_settings()


def xray_settings() -> Dict[str, str]:
    ensure_xray_defaults(commit=False)
    cfg = {key: _setting(key, value) for key, value in DEFAULT_XRAY_SETTINGS.items()}
    cfg['xray_uuid_namespace'] = _setting('xray_uuid_namespace', str(uuid.uuid4()))
    try:
        cfg['xray_port'] = str(int(cfg.get('xray_port') or 443))
    except Exception:
        cfg['xray_port'] = '443'
    try:
        cfg['xray_api_port'] = str(int(cfg.get('xray_api_port') or 10085))
    except Exception:
        cfg['xray_api_port'] = '10085'
    if cfg.get('xray_profile_type') not in XRAY_PROFILE_TYPES:
        cfg['xray_profile_type'] = 'vless-reality'
    cfg['xray_ws_path'] = _ensure_path(cfg.get('xray_ws_path'), '/ironpanel-ws')
    cfg['xray_reality_spiderx'] = _ensure_path(cfg.get('xray_reality_spiderx'), '/')
    return cfg


def xray_enabled() -> bool:
    return _setting('xray_enabled', '1') == '1'


def _public_host(settings: Dict[str, str] | None = None) -> str:
    settings = settings or xray_settings()
    host = settings.get('xray_domain') or _setting('tunnel_host', '') or _setting('public_host', '')
    if not host:
        host = current_app.config.get('PUBLIC_HOST', '127.0.0.1')
    return str(host).replace('https://', '').replace('http://', '').split('/')[0].strip()


def _safe_email(user: VpnUser) -> str:
    base = re.sub(r'[^A-Za-z0-9_.@-]', '_', user.username or 'user')[:64]
    return f'ip-{user.id}-{base}'


def xray_user_uuid(user: VpnUser) -> str:
    ns_raw = _setting('xray_uuid_namespace', '') or str(uuid.NAMESPACE_DNS)
    try:
        namespace = uuid.UUID(ns_raw)
    except Exception:
        namespace = uuid.NAMESPACE_DNS
    seed = f'ironpanel:xray:{user.id}:{user.username}:{user.subscription_token}'
    return str(uuid.uuid5(namespace, seed))


def xray_user_password(user: VpnUser, length: int = 32) -> str:
    secret = _setting('xray_uuid_namespace', '') or 'ironpanel-xray'
    raw = hashlib.sha256(f'{secret}:{user.id}:{user.username}:{user.subscription_token}'.encode()).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')[:length]


def generate_reality_keypair() -> tuple[str, str, str]:
    diagnostics = []
    for bin_path in ('/usr/local/bin/xray', '/usr/bin/xray', 'xray'):
        p = run_cmd([bin_path, 'x25519'])
        out = (p.stdout or '') + (p.stderr or '')
        diagnostics.append(f'{bin_path}: rc={p.returncode} ' + out.strip()[:300])
        priv = pub = ''
        for line in out.splitlines():
            if 'Private key:' in line:
                priv = line.split(':', 1)[1].strip()
            if 'Public key:' in line:
                pub = line.split(':', 1)[1].strip()
        if p.returncode == 0 and _looks_like_xray_key(priv) and _looks_like_xray_key(pub):
            return priv, pub, '\n'.join(diagnostics)
    return '', '', '\n'.join(diagnostics)


def ensure_reality_keys(commit: bool = True, force: bool = False):
    ensure_xray_defaults(commit=False)
    current_private = _setting('xray_reality_private_key', '')
    current_public = _setting('xray_reality_public_key', '')
    if not force and _looks_like_xray_key(current_private) and _looks_like_xray_key(current_public):
        if commit:
            db.session.commit()
        return
    priv, pub, diag = generate_reality_keypair()
    if not priv or not pub:
        _set_setting_no_commit('xray_reality_private_key', '')
        _set_setting_no_commit('xray_reality_public_key', '')
        if commit:
            db.session.commit()
        raise RuntimeError('Unable to generate valid Xray Reality x25519 keys. Install/repair xray and run repair_xray.sh. ' + diag[-600:])
    _set_setting_no_commit('xray_reality_private_key', priv)
    _set_setting_no_commit('xray_reality_public_key', pub)
    if not _setting('xray_reality_short_ids', '') or not _valid_short_ids(_setting('xray_reality_short_ids', '')):
        _set_setting_no_commit('xray_reality_short_ids', secrets.token_hex(4))
    if commit:
        db.session.commit()


def validate_xray_profile_settings(settings: Dict[str, str], profile: Dict[str, str]) -> tuple[bool, str]:
    security = profile.get('security')
    transport = profile.get('transport')
    protocol = profile.get('protocol')
    try:
        port = int(settings.get('xray_port') or 0)
        api_port = int(settings.get('xray_api_port') or 0)
    except Exception:
        return False, 'Xray port/API port must be numeric.'
    if port <= 0 or port > 65535 or api_port <= 0 or api_port > 65535:
        return False, 'Xray port/API port is out of range.'
    if port == api_port:
        return False, 'Xray inbound port and API port cannot be the same.'
    if transport in ('ws', 'httpupgrade'):
        path = _ensure_path(settings.get('xray_ws_path'), '/')
        if '?' in path or '#' in path:
            return False, 'WebSocket path must be a clean path like /ironpanel-ws.'
    if transport == 'grpc' and not (settings.get('xray_grpc_service_name') or '').strip():
        return False, 'gRPC service name is required.'
    if security == 'reality':
        ensure_reality_keys(commit=True)
        if not _looks_like_xray_key(_setting('xray_reality_private_key', '')) or not _looks_like_xray_key(_setting('xray_reality_public_key', '')):
            return False, 'Reality keys are invalid. Press Generate Reality Keys or run repair_xray.sh.'
        if not _valid_short_ids(settings.get('xray_reality_short_ids', '')):
            return False, 'Reality Short ID must be hex, even length, maximum 16 characters.'
        if not (settings.get('xray_reality_sni') or settings.get('xray_reality_server_names')):
            return False, 'Reality SNI/serverNames is required.'
    if security == 'tls':
        cert_file = Path(settings.get('xray_tls_cert_file') or '')
        key_file = Path(settings.get('xray_tls_key_file') or '')
        if (not cert_file.exists()) or (not key_file.exists()) or 'YOUR_DOMAIN' in str(cert_file) or 'YOUR_DOMAIN' in str(key_file):
            return False, 'TLS profile selected but certificate/key files do not exist. Use Reality/No-TLS profile or set valid Let’s Encrypt certificate paths.'
    if protocol == 'shadowsocks' and not (settings.get('xray_ss_method') or '').strip():
        return False, 'Shadowsocks method is required.'
    return True, 'ok'


def _stream_settings(settings: Dict[str, str]) -> Dict[str, Any]:
    profile = XRAY_PROFILE_TYPES[settings['xray_profile_type']]
    network = profile['transport']
    if network == 'tcp,udp':
        network = 'tcp'
    security = profile['security']
    stream: Dict[str, Any] = {'network': network, 'security': security}
    alpn = _list_csv(settings.get('xray_alpn', ''))
    if security == 'reality':
        ensure_reality_keys(commit=True)
        settings = xray_settings()
        stream['realitySettings'] = {
            'show': False,
            'dest': settings.get('xray_reality_dest') or 'www.cloudflare.com:443',
            'xver': 0,
            'serverNames': _list_csv(settings.get('xray_reality_server_names') or settings.get('xray_reality_sni')),
            'privateKey': settings.get('xray_reality_private_key'),
            'shortIds': _list_csv(settings.get('xray_reality_short_ids')),
            'spiderX': _ensure_path(settings.get('xray_reality_spiderx'), '/'),
        }
    elif security == 'tls':
        tls = {'serverName': settings.get('xray_domain') or _public_host(settings)}
        if alpn:
            tls['alpn'] = alpn
        cert_file = settings.get('xray_tls_cert_file') or ''
        key_file = settings.get('xray_tls_key_file') or ''
        tls['certificates'] = [{'certificateFile': cert_file, 'keyFile': key_file}]
        stream['tlsSettings'] = tls
    if network == 'ws':
        # Inbound WebSocket only needs the server path. Host is a client-side URI parameter.
        stream['wsSettings'] = {'path': _ensure_path(settings.get('xray_ws_path'), '/')}
    elif network == 'grpc':
        stream['grpcSettings'] = {'serviceName': (settings.get('xray_grpc_service_name') or 'ironpanel-grpc').strip()}
    elif network == 'httpupgrade':
        stream['httpupgradeSettings'] = {'path': _ensure_path(settings.get('xray_ws_path'), '/'), 'host': settings.get('xray_ws_host') or settings.get('xray_domain') or _public_host(settings)}
    return stream


def build_xray_config(users: Iterable[VpnUser], settings: Dict[str, str] | None = None) -> Dict[str, Any]:
    settings = settings or xray_settings()
    profile_key = settings.get('xray_profile_type', 'vless-reality')
    profile = XRAY_PROFILE_TYPES.get(profile_key, XRAY_PROFILE_TYPES['vless-reality'])
    protocol = profile['protocol']
    ok, msg = validate_xray_profile_settings(settings, profile)
    if not ok:
        raise RuntimeError(msg)
    clients = []
    for user in users:
        if protocol == 'vless':
            client = {'id': xray_user_uuid(user), 'email': _safe_email(user), 'level': 0}
            if profile['security'] == 'reality' and settings.get('xray_flow'):
                client['flow'] = settings.get('xray_flow')
            clients.append(client)
        elif protocol == 'vmess':
            clients.append({'id': xray_user_uuid(user), 'email': _safe_email(user), 'alterId': 0, 'level': 0})
        elif protocol == 'trojan':
            clients.append({'password': xray_user_password(user), 'email': _safe_email(user), 'level': 0})
        elif protocol == 'shadowsocks':
            clients.append({'password': xray_user_password(user, 24), 'email': _safe_email(user), 'level': 0})

    if protocol == 'vless':
        inbound_settings: Dict[str, Any] = {'clients': clients, 'decryption': 'none'}
    elif protocol == 'vmess':
        inbound_settings = {'clients': clients}
    elif protocol == 'trojan':
        inbound_settings = {'clients': clients}
    elif protocol == 'shadowsocks':
        method = settings.get('xray_ss_method') or 'chacha20-ietf-poly1305'
        inbound_settings = {'method': method, 'clients': clients, 'network': 'tcp,udp'}
        if method.startswith('2022-'):
            inbound_settings['password'] = hashlib.sha256((_setting('xray_uuid_namespace', '') or 'ironpanel').encode()).hexdigest()[:32]
    else:
        inbound_settings = {'clients': clients}

    inbounds = [{
        'tag': 'ironpanel-xray',
        'listen': '0.0.0.0',
        'port': int(settings.get('xray_port') or 443),
        'protocol': protocol,
        'settings': inbound_settings,
        'streamSettings': _stream_settings(settings),
        'sniffing': {
            'enabled': settings.get('xray_sniffing_enabled', '1') == '1',
            'destOverride': ['http', 'tls', 'quic'],
            'routeOnly': False,
        },
    }, {
        'tag': 'api',
        'listen': '127.0.0.1',
        'port': int(settings.get('xray_api_port') or 10085),
        'protocol': 'dokodemo-door',
        'settings': {'address': '127.0.0.1'},
    }]
    dns_servers = _list_csv(settings.get('xray_dns_servers', '')) or ['1.1.1.1', '8.8.8.8']
    rules = [{'type': 'field', 'inboundTag': ['api'], 'outboundTag': 'api'}]
    if settings.get('xray_block_private') == '1':
        rules.append({'type': 'field', 'ip': ['geoip:private'], 'outboundTag': 'blocked'})
    if settings.get('xray_routing_mode') == 'block-ir':
        rules.extend([
            {'type': 'field', 'domain': ['geosite:category-ir'], 'outboundTag': 'blocked'},
            {'type': 'field', 'ip': ['geoip:ir'], 'outboundTag': 'blocked'},
        ])
    return {
        'log': {'loglevel': settings.get('xray_loglevel') or 'warning', 'access': '/var/log/xray/access.log', 'error': '/var/log/xray/error.log'},
        'dns': {'servers': dns_servers},
        'api': {'tag': 'api', 'services': ['HandlerService', 'LoggerService', 'StatsService']},
        'stats': {},
        'policy': {
            'levels': {'0': {'statsUserUplink': True, 'statsUserDownlink': True}},
            'system': {'statsInboundUplink': True, 'statsInboundDownlink': True, 'statsOutboundUplink': True, 'statsOutboundDownlink': True},
        },
        'inbounds': inbounds,
        'outbounds': [{'tag': 'direct', 'protocol': 'freedom'}, {'tag': 'blocked', 'protocol': 'blackhole'}],
        'routing': {'domainStrategy': 'AsIs', 'rules': rules},
    }


def test_xray_config_file(path: Path = XRAY_CONFIG_PATH) -> tuple[bool, str]:
    bin_path = _xray_bin()
    tests = [
        f'{bin_path} run -test -config {path}',
        f'{bin_path} test -config {path}',
        f'/usr/local/bin/xray run -test -config {path}',
        f'/usr/local/bin/xray test -config {path}',
    ]
    last = ''
    for cmd in tests:
        p = run_cmd(['bash', '-lc', cmd + ' 2>&1'])
        out = (p.stdout or '') + (p.stderr or '')
        last = out.strip()
        if p.returncode == 0:
            return True, last or 'Xray config test passed'
        if 'not found' in out or 'No such file' in out:
            continue
    return False, last[-2000:] or 'Xray config test failed'


def write_xray_config(users: Iterable[VpnUser], restart: bool = True) -> tuple[bool, str]:
    if not xray_enabled():
        return True, 'Xray disabled in settings'
    try:
        prepare_xray_runtime()
        config = build_xray_config(users)
        XRAY_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        try:
            XRAY_CONFIG_PATH.chmod(0o644)
            os.chown(XRAY_CONFIG_PATH, 0, 0)
        except Exception:
            pass
        prepare_xray_runtime()
        ok_test, test_out = test_xray_config_file(XRAY_CONFIG_PATH)
        if not ok_test:
            return False, test_out[-2000:]
        if restart:
            run_cmd(['bash', '-lc', 'systemctl restart xray >/dev/null 2>&1 || true'])
        return True, 'Xray config written and validated'
    except Exception as exc:
        return False, str(exc)


def xray_link(user: VpnUser, settings: Dict[str, str] | None = None) -> str:
    settings = settings or xray_settings()
    profile = XRAY_PROFILE_TYPES[settings.get('xray_profile_type', 'vless-reality')]
    protocol = profile['protocol']
    host = _public_host(settings)
    port = int(settings.get('xray_port') or 443)
    remark = quote(f'IronPanel-{user.username}')
    network = profile['transport']
    if network == 'tcp,udp':
        network = 'tcp'
    security = profile['security']
    if protocol == 'vless':
        if security == 'reality':
            ensure_reality_keys(commit=True)
            settings = xray_settings()
        params = {'type': network, 'security': security, 'encryption': 'none'}
        if settings.get('xray_mux_enabled') == '1':
            params['mux'] = '1'
        if security == 'reality':
            params.update({
                'sni': settings.get('xray_reality_sni') or (settings.get('xray_reality_server_names', '').split(',')[0] or 'www.cloudflare.com'),
                'fp': settings.get('xray_reality_fingerprint') or 'chrome',
                'pbk': settings.get('xray_reality_public_key') or '',
                'sid': (settings.get('xray_reality_short_ids') or '').split(',')[0],
                'spx': _ensure_path(settings.get('xray_reality_spiderx'), '/'),
            })
            if settings.get('xray_flow'):
                params['flow'] = settings.get('xray_flow')
        elif security == 'tls':
            params.update({'sni': settings.get('xray_domain') or host, 'alpn': settings.get('xray_alpn') or 'h2,http/1.1'})
        if network == 'ws':
            params.update({'path': _ensure_path(settings.get('xray_ws_path'), '/'), 'host': settings.get('xray_ws_host') or settings.get('xray_domain') or host})
        elif network == 'grpc':
            params.update({'serviceName': (settings.get('xray_grpc_service_name') or 'ironpanel-grpc').strip()})
        return f'vless://{xray_user_uuid(user)}@{host}:{port}?{urlencode(params)}#{remark}'
    if protocol == 'vmess':
        data = {
            'v': '2', 'ps': f'IronPanel-{user.username}', 'add': host, 'port': str(port),
            'id': xray_user_uuid(user), 'aid': '0', 'scy': 'auto', 'net': network,
            'type': 'none', 'host': settings.get('xray_ws_host') or settings.get('xray_domain') or host,
            'path': _ensure_path(settings.get('xray_ws_path'), '/'), 'tls': '' if security == 'none' else security,
            'sni': settings.get('xray_domain') or host,
        }
        encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()).decode()
        return 'vmess://' + encoded
    if protocol == 'trojan':
        params = {'security': security, 'type': network}
        if security != 'none':
            params['sni'] = settings.get('xray_domain') or host
        return f'trojan://{xray_user_password(user)}@{host}:{port}?{urlencode(params)}#{remark}'
    if protocol == 'shadowsocks':
        method = settings.get('xray_ss_method') or 'chacha20-ietf-poly1305'
        password = xray_user_password(user, 24)
        if method.startswith('2022-'):
            server_password = hashlib.sha256((_setting('xray_uuid_namespace', '') or 'ironpanel').encode()).hexdigest()[:32]
            password = f'{server_password}:{password}'
        secret = base64.urlsafe_b64encode(f'{method}:{password}'.encode()).decode().rstrip('=')
        return f'ss://{secret}@{host}:{port}#{remark}'
    return ''


def xray_profile_text(user: VpnUser) -> str:
    """Return one clean URI per line, suitable for direct client import."""
    settings = xray_settings()
    link = xray_link(user, settings).strip()
    if not link.startswith(XRAY_URI_PREFIXES):
        raise RuntimeError('Generated Xray link is not a supported URI: ' + link[:80])
    return link + '\n'


def xray_profile_meta(user: VpnUser) -> str:
    settings = xray_settings()
    profile = XRAY_PROFILE_TYPES[settings.get('xray_profile_type', 'vless-reality')]
    return (
        f"IronPanel Xray Profile\nUser: {user.username}\nProfile: {profile['title']}\n"
        f"Host: {_public_host(settings)}\nPort: {settings.get('xray_port')}\n"
    )


def write_user_xray_profile(user: VpnUser) -> bool:
    if not xray_enabled():
        return False
    root = current_app.config['CONFIG_ROOT'] / 'profiles' / user.username
    root.mkdir(parents=True, exist_ok=True)
    (root / 'xray.txt').write_text(xray_profile_text(user))
    return True


def collect_xray_usage(account_counter) -> int:
    settings = xray_settings()
    server = f"127.0.0.1:{settings.get('xray_api_port') or '10085'}"
    changed = 0
    for user in VpnUser.query.all():
        email = _safe_email(user)
        total = {'uplink': 0, 'downlink': 0}
        ok_any = False
        for direction in ('uplink', 'downlink'):
            name = f'user>>>{email}>>>traffic>>>{direction}'
            cmd = f'(xray api statsquery --server={server} -name "{name}" 2>/dev/null || /usr/local/bin/xray api statsquery --server={server} -name "{name}" 2>/dev/null || true)'
            p = run_cmd(['bash', '-lc', cmd])
            out = (p.stdout or '') + (p.stderr or '')
            m = re.search(r'value:\s*(\d+)', out) or re.search(r'"value"\s*:\s*(\d+)', out)
            if m:
                total[direction] = int(m.group(1))
                ok_any = True
        if ok_any:
            rx = total['uplink']
            tx = total['downlink']
            if account_counter(user, 'xray', rx, tx):
                changed += 1
    return changed


def xray_runtime_status() -> Dict[str, str]:
    settings = xray_settings()
    profile = XRAY_PROFILE_TYPES.get(settings.get('xray_profile_type', ''), XRAY_PROFILE_TYPES['vless-reality'])
    try:
        ok, msg = validate_xray_profile_settings(settings, profile)
    except Exception as exc:
        ok, msg = False, str(exc)
    return {
        'enabled': '1' if xray_enabled() else '0',
        'profile_type': settings.get('xray_profile_type', 'vless-reality'),
        'profile_title': profile['title'],
        'host': _public_host(settings),
        'port': settings.get('xray_port', '443'),
        'config_path': str(XRAY_CONFIG_PATH),
        'valid': '1' if ok else '0',
        'validation_message': msg,
    }

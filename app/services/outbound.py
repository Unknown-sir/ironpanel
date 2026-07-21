"""IronPanel Outbound Routing Manager.

v16.7 adds an admin-controlled outbound layer. The admin can paste either an
OpenVPN client config or a V2Ray/Xray URI, test it, then choose which IronPanel
protocols should send user traffic through that upstream outbound.
"""
from __future__ import annotations

import base64
import json
import shlex
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs, unquote

from ..core.extensions import db
from ..core.models import AppSetting

OUTBOUND_DIR = Path('/etc/ironpanel/outbound')
OPENVPN_CONF = Path('/etc/openvpn/client/ironpanel-outbound.conf')
OPENVPN_SERVICE = Path('/etc/systemd/system/ironpanel-outbound-openvpn.service')
POLICY_SCRIPT = Path('/opt/ironpanel/scripts/apply_outbound.sh')
XRAY_URI_PREFIXES = ('vless://', 'vmess://', 'trojan://', 'ss://')

DEFAULT_OUTBOUND_SETTINGS = {
    'outbound_enabled': '0',
    'outbound_type': 'openvpn',
    'outbound_config': '',
    'outbound_protocols': '',
    'outbound_status': 'not_configured',
    'outbound_last_test': '',
    'outbound_last_error': '',
    'outbound_openvpn_interface': 'ironout',
    'outbound_policy_table': '166',
    'outbound_policy_mark': '0x66',
    'outbound_tproxy_port': '12345',
}

VPN_SUBNETS = {
    'openvpn': ['10.8.0.0/24'],
    'wireguard': ['10.66.66.0/24'],
    'ocserv': ['10.44.0.0/24', '10.12.0.0/16', '192.168.100.0/24'],
    'l2tp': ['10.10.10.0/24', '192.168.42.0/24'],
}


def run_cmd(args, input_text=None, timeout=25):
    try:
        return subprocess.run(args, input=input_text, text=True, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(args, 124, exc.stdout or '', exc.stderr or 'timeout')
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args, 127, '', str(exc))


def _get_setting(key: str, default: str = '') -> str:
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, '') else default


def _set_setting(key: str, value: str):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        db.session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)


def ensure_outbound_defaults(commit: bool = True):
    db.create_all()
    for k, v in DEFAULT_OUTBOUND_SETTINGS.items():
        if not AppSetting.query.filter_by(key=k).first():
            db.session.add(AppSetting(key=k, value=v))
    if commit:
        db.session.commit()


def outbound_settings() -> Dict[str, str]:
    ensure_outbound_defaults(commit=False)
    cfg = {k: _get_setting(k, v) for k, v in DEFAULT_OUTBOUND_SETTINGS.items()}
    if cfg.get('outbound_type') not in ('openvpn', 'v2ray'):
        cfg['outbound_type'] = 'openvpn'
    return cfg


def save_outbound_settings(outbound_type: str, config_text: str, enabled: bool, protocols: List[str]):
    ensure_outbound_defaults(commit=False)
    outbound_type = 'v2ray' if outbound_type in ('v2ray', 'xray') else 'openvpn'
    allowed = {'openvpn', 'wireguard', 'ocserv', 'l2tp', 'xray'}
    protocols = [p for p in protocols if p in allowed]
    _set_setting('outbound_type', outbound_type)
    _set_setting('outbound_config', (config_text or '').strip())
    _set_setting('outbound_enabled', '1' if enabled else '0')
    _set_setting('outbound_protocols', ','.join(protocols))
    db.session.commit()


def _stamp_status(status: str, message: str):
    _set_setting('outbound_status', status)
    _set_setting('outbound_last_test', time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()))
    _set_setting('outbound_last_error', message[-2000:])
    db.session.commit()


def selected_protocols() -> List[str]:
    return [p.strip() for p in _get_setting('outbound_protocols', '').split(',') if p.strip()]


def outbound_enabled() -> bool:
    return _get_setting('outbound_enabled', '0') == '1' and bool((_get_setting('outbound_config', '') or '').strip())


def _first_line_config(config_text: str) -> str:
    for line in (config_text or '').splitlines():
        s = line.strip()
        if s and not s.startswith('#'):
            return s
    return (config_text or '').strip()


def _b64decode_padded(data: str) -> str:
    data = data.strip().replace('-', '+').replace('_', '/')
    data += '=' * (-len(data) % 4)
    return base64.b64decode(data).decode(errors='ignore')


def _query_value(qs: Dict[str, List[str]], key: str, default: str = '') -> str:
    val = qs.get(key, [default])
    return val[0] if val else default


def parse_v2ray_uri(uri: str) -> Dict[str, Any]:
    uri = _first_line_config(uri)
    if not uri.startswith(XRAY_URI_PREFIXES):
        raise ValueError('کانفیگ V2Ray/Xray باید با vless://، vmess://، trojan:// یا ss:// شروع شود')
    if uri.startswith('vmess://'):
        raw = _b64decode_padded(uri.replace('vmess://', '', 1))
        data = json.loads(raw)
        stream = {'network': data.get('net') or 'tcp', 'security': data.get('tls') or 'none'}
        if stream['network'] == 'ws':
            stream['wsSettings'] = {'path': data.get('path') or '/', 'headers': {'Host': data.get('host') or data.get('add') or ''}}
        if stream['network'] == 'grpc':
            stream['grpcSettings'] = {'serviceName': data.get('path') or data.get('serviceName') or 'grpc'}
        if stream['security'] == 'tls':
            stream['tlsSettings'] = {'serverName': data.get('sni') or data.get('host') or data.get('add')}
        return {'tag': 'ironpanel-upstream', 'protocol': 'vmess', 'settings': {'vnext': [{'address': data.get('add'), 'port': int(data.get('port') or 443), 'users': [{'id': data.get('id'), 'alterId': int(data.get('aid') or 0), 'security': data.get('scy') or 'auto'}]}]}, 'streamSettings': stream}

    u = urlparse(uri)
    qs = parse_qs(u.query)
    protocol = u.scheme
    host = u.hostname or ''
    port = int(u.port or (443 if protocol in ('vless', 'trojan') else 8388))
    network = _query_value(qs, 'type', _query_value(qs, 'net', 'tcp')) or 'tcp'
    security = _query_value(qs, 'security', _query_value(qs, 'tls', 'none')) or 'none'
    stream: Dict[str, Any] = {'network': network, 'security': security}
    if network == 'ws':
        stream['wsSettings'] = {'path': unquote(_query_value(qs, 'path', '/')) or '/', 'headers': {'Host': _query_value(qs, 'host', host)}}
    elif network == 'grpc':
        stream['grpcSettings'] = {'serviceName': _query_value(qs, 'serviceName', 'grpc')}
    if security == 'tls':
        stream['tlsSettings'] = {'serverName': _query_value(qs, 'sni', host), 'allowInsecure': _query_value(qs, 'allowInsecure', '0') in ('1','true','True')}
    elif security == 'reality':
        stream['realitySettings'] = {
            'serverName': _query_value(qs, 'sni', host),
            'fingerprint': _query_value(qs, 'fp', 'chrome'),
            'publicKey': _query_value(qs, 'pbk', ''),
            'shortId': _query_value(qs, 'sid', ''),
            'spiderX': unquote(_query_value(qs, 'spx', '/')),
        }
    userinfo = unquote(u.username or '')
    if protocol == 'vless':
        user = {'id': userinfo, 'encryption': _query_value(qs, 'encryption', 'none') or 'none'}
        flow = _query_value(qs, 'flow', '')
        if flow:
            user['flow'] = flow
        return {'tag': 'ironpanel-upstream', 'protocol': 'vless', 'settings': {'vnext': [{'address': host, 'port': port, 'users': [user]}]}, 'streamSettings': stream}
    if protocol == 'trojan':
        return {'tag': 'ironpanel-upstream', 'protocol': 'trojan', 'settings': {'servers': [{'address': host, 'port': port, 'password': userinfo}]}, 'streamSettings': stream}
    if protocol == 'ss':
        raw_user = uri.split('ss://', 1)[1].split('@', 1)[0]
        method = password = ''
        if ':' in userinfo:
            method, password = userinfo.split(':', 1)
        else:
            decoded = _b64decode_padded(raw_user)
            if ':' in decoded:
                method, password = decoded.split(':', 1)
        return {'tag': 'ironpanel-upstream', 'protocol': 'shadowsocks', 'settings': {'servers': [{'address': host, 'port': port, 'method': method or 'aes-128-gcm', 'password': password}]}}
    raise ValueError('نوع کانفیگ V2Ray/Xray پشتیبانی نمی‌شود')


def xray_outbound_from_settings() -> Dict[str, Any] | None:
    if not outbound_enabled() or _get_setting('outbound_type', 'openvpn') != 'v2ray':
        return None
    try:
        return parse_v2ray_uri(_get_setting('outbound_config', ''))
    except Exception as exc:
        _stamp_status('parse_failed', str(exc))
        return None


def xray_should_route_inbound() -> bool:
    return outbound_enabled() and _get_setting('outbound_type', 'openvpn') == 'v2ray' and 'xray' in selected_protocols()


def _xray_bin() -> str:
    for b in ('/usr/local/bin/xray', '/usr/bin/xray'):
        if Path(b).exists():
            return b
    out = run_cmd(['bash','-lc','command -v xray || true'])
    return (out.stdout or '').strip() or 'xray'


def _test_v2ray_outbound(config_text: str) -> Tuple[bool, str]:
    try:
        outbound = parse_v2ray_uri(config_text)
    except Exception as exc:
        return False, str(exc)
    cfg = {
        'log': {'loglevel': 'warning'},
        'inbounds': [{'tag': 'local-socks', 'listen': '127.0.0.1', 'port': 19090, 'protocol': 'socks', 'settings': {'auth': 'noauth', 'udp': True}}],
        'outbounds': [outbound, {'tag': 'direct', 'protocol': 'freedom'}],
        'routing': {'rules': [{'type': 'field', 'inboundTag': ['local-socks'], 'outboundTag': 'ironpanel-upstream'}]},
    }
    with tempfile.TemporaryDirectory(prefix='ironpanel-outbound-') as td:
        path = Path(td) / 'xray-test.json'
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
        bin_path = _xray_bin()
        test = run_cmd(['bash','-lc', f'{shlex.quote(bin_path)} run -test -config {shlex.quote(str(path))} 2>&1 || {shlex.quote(bin_path)} test -config {shlex.quote(str(path))} 2>&1'], timeout=20)
        out = (test.stdout or '') + (test.stderr or '')
        if test.returncode != 0:
            return False, out[-1600:] or 'Xray test failed'
        proc = subprocess.Popen([bin_path, 'run', '-config', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            opened = False
            for _ in range(30):
                try:
                    with socket.create_connection(('127.0.0.1', 19090), timeout=0.2):
                        opened = True
                        break
                except OSError:
                    time.sleep(0.2)
            if not opened:
                err = proc.stderr.read() if proc.poll() is not None else ''
                return False, 'Xray temporary SOCKS inbound did not open. ' + err[-800:]
            curl = run_cmd(['bash','-lc', 'curl -fsS --socks5-hostname 127.0.0.1:19090 --connect-timeout 7 --max-time 12 https://www.cloudflare.com/cdn-cgi/trace >/dev/null && echo OK'], timeout=16)
            msg = (curl.stdout or '') + (curl.stderr or '')
            return (curl.returncode == 0), (msg.strip() or 'V2Ray outbound connectivity test completed')
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()


def _normalize_openvpn_client_config(config_text: str, interface: str) -> str:
    txt = (config_text or '').replace('\r\n', '\n').strip() + '\n'
    txt += f"\n# IronPanel Outbound Runtime\ndev {interface}\nroute-nopull\nauth-nocache\nscript-security 2\nverb 3\n"
    return txt


def _write_openvpn_files(config_text: str):
    OUTBOUND_DIR.mkdir(parents=True, exist_ok=True)
    OPENVPN_CONF.parent.mkdir(parents=True, exist_ok=True)
    iface = _get_setting('outbound_openvpn_interface', 'ironout') or 'ironout'
    OPENVPN_CONF.write_text(_normalize_openvpn_client_config(config_text, iface))
    OPENVPN_CONF.chmod(0o600)
    OPENVPN_SERVICE.write_text(f'''[Unit]
Description=IronPanel Outbound OpenVPN Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/openvpn --config {OPENVPN_CONF}
Restart=on-failure
RestartSec=5s
User=root

[Install]
WantedBy=multi-user.target
''')


def _test_openvpn_outbound(config_text: str) -> Tuple[bool, str]:
    if 'client' not in config_text and 'remote ' not in config_text:
        return False, 'کانفیگ OpenVPN معتبر نیست؛ باید شامل client و remote باشد.'
    if run_cmd(['bash','-lc','command -v openvpn >/dev/null 2>&1']).returncode != 0:
        return False, 'openvpn روی سرور نصب نیست.'
    with tempfile.TemporaryDirectory(prefix='ironpanel-ovpn-test-') as td:
        iface = 'irotest'
        conf = Path(td) / 'client.conf'
        log = Path(td) / 'openvpn.log'
        pid = Path(td) / 'openvpn.pid'
        conf.write_text(_normalize_openvpn_client_config(config_text, iface))
        cmd = f'openvpn --config {shlex.quote(str(conf))} --writepid {shlex.quote(str(pid))} --log {shlex.quote(str(log))} --daemon'
        p = run_cmd(['bash','-lc', cmd], timeout=10)
        if p.returncode != 0:
            return False, ((p.stdout or '') + (p.stderr or ''))[-1600:]
        try:
            for _ in range(45):
                txt = log.read_text(errors='ignore') if log.exists() else ''
                if 'Initialization Sequence Completed' in txt:
                    return True, 'OpenVPN outbound connected successfully'
                if any(x in txt for x in ['AUTH_FAILED', 'TLS Error', 'Cannot resolve host address', 'Connection refused']):
                    return False, txt[-1600:]
                time.sleep(0.4)
            return False, (log.read_text(errors='ignore') if log.exists() else 'OpenVPN timeout')[-1600:]
        finally:
            if pid.exists():
                run_cmd(['bash','-lc', f'kill $(cat {shlex.quote(str(pid))}) >/dev/null 2>&1 || true'], timeout=3)


def test_outbound_config() -> Tuple[bool, str]:
    ensure_outbound_defaults(commit=False)
    cfg = outbound_settings()
    config_text = cfg.get('outbound_config', '')
    if not config_text.strip():
        _stamp_status('empty', 'کانفیگ Outbound وارد نشده است')
        return False, 'کانفیگ Outbound وارد نشده است'
    if cfg.get('outbound_type') == 'v2ray':
        ok, out = _test_v2ray_outbound(config_text)
    else:
        ok, out = _test_openvpn_outbound(config_text)
    _stamp_status('connected' if ok else 'failed', out)
    return ok, out


def apply_outbound_runtime() -> Tuple[bool, str]:
    cfg = outbound_settings()
    protocols = selected_protocols()
    if not protocols:
        return False, 'هیچ پروتکلی برای عبور از Outbound انتخاب نشده است.'
    _set_setting('outbound_enabled', '1')
    db.session.commit()
    messages = []
    if cfg.get('outbound_type') == 'openvpn':
        _write_openvpn_files(cfg.get('outbound_config', ''))
        run_cmd(['systemctl', 'daemon-reload'])
        run_cmd(['systemctl', 'enable', '--now', 'ironpanel-outbound-openvpn.service'], timeout=20)
        if POLICY_SCRIPT.exists():
            p = run_cmd(['bash', str(POLICY_SCRIPT), 'apply'], timeout=30)
            messages.append(((p.stdout or '') + (p.stderr or '')).strip())
        else:
            messages.append('apply_outbound.sh not found; OpenVPN service started but policy routing was not applied')
    else:
        try:
            from .xray import write_xray_config
            from .provisioning import user_access_status, protocol_enabled_for_user
            from ..core.models import VpnUser
            users=[u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_user(u, 'xray')]
            ok,out=write_xray_config(users, restart=True)
            messages.append(out)
            if not ok:
                return False, out
        except Exception as exc:
            return False, str(exc)
        if any(p in protocols for p in ['openvpn','wireguard','ocserv','l2tp']) and POLICY_SCRIPT.exists():
            p = run_cmd(['bash', str(POLICY_SCRIPT), 'apply-tproxy'], timeout=30)
            messages.append(((p.stdout or '') + (p.stderr or '')).strip())
    _stamp_status('active', '\n'.join(messages) or 'Outbound applied')
    return True, '\n'.join(messages) or 'Outbound applied'


def disable_outbound_runtime() -> Tuple[bool, str]:
    _set_setting('outbound_enabled', '0')
    db.session.commit()
    msgs=[]
    if POLICY_SCRIPT.exists():
        p=run_cmd(['bash', str(POLICY_SCRIPT), 'disable'], timeout=20)
        msgs.append(((p.stdout or '')+(p.stderr or '')).strip())
    run_cmd(['systemctl', 'disable', '--now', 'ironpanel-outbound-openvpn.service'], timeout=20)
    try:
        from .xray import write_xray_config
        from .provisioning import user_access_status, protocol_enabled_for_user
        from ..core.models import VpnUser
        users=[u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_user(u, 'xray')]
        write_xray_config(users, restart=True)
    except Exception as exc:
        msgs.append('Xray rebuild warning: '+str(exc))
    _stamp_status('disabled', '\n'.join(msgs) or 'Outbound disabled')
    return True, '\n'.join(msgs) or 'Outbound disabled'


def outbound_runtime_status() -> Dict[str, Any]:
    cfg = outbound_settings()
    openvpn_active = run_cmd(['systemctl','is-active','ironpanel-outbound-openvpn.service'], timeout=5).stdout.strip()
    return {
        'enabled': cfg.get('outbound_enabled') == '1',
        'type': cfg.get('outbound_type'),
        'protocols': selected_protocols(),
        'status': cfg.get('outbound_status'),
        'last_test': cfg.get('outbound_last_test'),
        'last_error': cfg.get('outbound_last_error'),
        'openvpn_service': openvpn_active or 'unknown',
        'vpn_subnets': VPN_SUBNETS,
    }

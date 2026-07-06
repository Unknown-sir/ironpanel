import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import math
import os
from flask import current_app
from ..core.models import VpnUser, ActivityLog, AppSetting, DailyUsage
from ..core.extensions import db

DEFAULT_PORTS = {
    'panel': 8080,
    'openvpn_udp': 1194,
    'openvpn_tcp': 1195,
    'ocserv_tcp': 8443,
    'ocserv_udp': 8443,
    'l2tp_udp': 1701,
    'ipsec_ike': 500,
    'ipsec_nat': 4500,
    'wireguard_udp': 51820,
}

PROTOCOLS = ['openvpn', 'ocserv', 'l2tp', 'wireguard']

def run_cmd(args, input_text=None):
    return subprocess.run(args, input=input_text, text=True, capture_output=True, check=False)

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

def get_port(name):
    return int(get_setting(f'port_{name}', DEFAULT_PORTS.get(name, 0)))

def active_protocols():
    raw = get_setting('active_protocols', 'openvpn,ocserv,l2tp,wireguard')
    return [p for p in raw.split(',') if p in PROTOCOLS]

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

def l2tp_transport():
    # L2TP/IPsec standard ports are UDP-only.
    return 'udp'


def _user_used_bytes(user: VpnUser) -> int:
    """Return exact accounted bytes. Falls back to old MB columns on upgraded installs."""
    try:
        exact = int((getattr(user, 'used_upload_bytes', 0) or 0) + (getattr(user, 'used_download_bytes', 0) or 0))
    except Exception:
        exact = 0
    if exact > 0:
        return exact
    return int(((user.used_upload_mb or 0) + (user.used_download_mb or 0)) * 1024 * 1024)

def _traffic_limit_bytes(user: VpnUser) -> int:
    return int(user.data_limit_mb or 0) * 1024 * 1024

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
    if limit > 0 and _user_used_bytes(user) >= limit:
        return False, 'حجم کاربر تمام شده است'
    return True, 'فعال'

def _valid_users():
    return [u for u in VpnUser.query.all() if user_access_status(u)[0]]

def _safe_cn(username: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', username or 'user')
    return safe[:64] or 'user'

def _find_user_by_identity(identity: str):
    user = VpnUser.query.filter_by(username=identity).first()
    if user:
        return user
    for u in VpnUser.query.all():
        if _safe_cn(u.username) == identity:
            return u
    return None

def _easyrsa_dir() -> Path:
    return Path('/etc/openvpn/easy-rsa')

def _ensure_openvpn_cert(user: VpnUser):
    """Create a nopass per-user OpenVPN certificate so the profile connects without username/password."""
    cn = _safe_cn(user.username)
    easy = _easyrsa_dir()
    issued = easy / 'pki' / 'issued' / f'{cn}.crt'
    key = easy / 'pki' / 'private' / f'{cn}.key'
    if issued.exists() and key.exists():
        return cn
    if easy.exists() and (easy / 'easyrsa').exists():
        run_cmd(['bash', '-lc', f'cd {easy} && EASYRSA_BATCH=1 ./easyrsa build-client-full {cn} nopass'])
    return cn

def _revoke_openvpn_cert(username: str):
    cn = _safe_cn(username)
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

def _write_plain_passwords(root: Path):
    users = _valid_users()
    passwd = root / 'users.passwd'
    passwd.write_text(''.join(f'{u.username}:{u.l2tp_password or "managed-by-panel"}\n' for u in users))
    chap = Path('/etc/ppp/chap-secrets')
    if chap.parent.exists():
        chap.write_text(''.join(f'"{u.username}" l2tpd "{u.l2tp_password or "managed-by-panel"}" *\n' for u in users))
        chap.chmod(0o600)
    ocpasswd = root / 'ocpasswd'
    ocpasswd.unlink(missing_ok=True)
    for u in users:
        password = u.cisco_password or u.l2tp_password or 'managed-by-panel'
        run_cmd(['ocpasswd', '-c', str(ocpasswd), u.username], input_text=f'{password}\n{password}\n')
    if ocpasswd.exists():
        ocpasswd.chmod(0o600)

def _rewrite_wireguard_server(root: Path):
    wg_conf = Path('/etc/wireguard/wg0.conf')
    if not wg_conf.exists():
        return
    users = _valid_users()
    for idx, u in enumerate(users, start=10):
        _ensure_wg_identity(u, idx)
    txt = wg_conf.read_text()
    base = txt.split('# BEGIN IRONPANEL PEERS')[0].rstrip()
    peers = ['# BEGIN IRONPANEL PEERS']
    for u in users:
        if protocol_enabled_for_user(u, 'wireguard'):
            peers.append(f'\n[Peer]\n# {u.username}\nPublicKey = {u.wg_public_key}\nAllowedIPs = {u.wg_ip}/32')
    peers.append('# END IRONPANEL PEERS\n')
    wg_conf.write_text(base + '\n\n' + '\n'.join(peers))
    run_cmd(['systemctl', 'restart', 'wg-quick@wg0'])

def _restart_runtime_services():
    service_groups = [
        ['openvpn-server@server'],
        ['ocserv'],
        ['strongswan-starter', 'strongswan', 'ipsec'],
        ['xl2tpd'],
    ]
    for group in service_groups:
        for svc in group:
            p = run_cmd(['systemctl', 'restart', svc])
            if p.returncode == 0:
                break

def sync_user(user: VpnUser, restart=True):
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    if user.enabled and not user.expired:
        _ensure_wg_identity(user)
        if protocol_enabled_for_user(user, 'openvpn'):
            _ensure_openvpn_cert(user)
    _write_plain_passwords(root)
    _rewrite_wireguard_server(root)
    generate_profiles(user)
    # Ocserv, L2TP/IPsec and OpenVPN certificate revocation/user files should be reloaded
    # after user changes so non-OpenVPN protocols can connect immediately.
    if restart:
        _restart_runtime_services()
    return True

def sync_all_users(restart=False):
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    for idx, u in enumerate(_valid_users(), start=10):
        _ensure_wg_identity(u, idx)
        if protocol_enabled_for_user(u, 'openvpn'):
            _ensure_openvpn_cert(u)
    _write_plain_passwords(root)
    _rewrite_wireguard_server(root)
    for u in VpnUser.query.all():
        generate_profiles(u)
    if restart:
        _restart_runtime_services()
    return True

def disable_user(user: VpnUser):
    user.enabled = False
    db.session.commit()
    sync_all_users(restart=True)

def delete_user(user: VpnUser):
    username = user.username
    _revoke_openvpn_cert(username)
    shutil.rmtree(current_app.config['CONFIG_ROOT'] / 'profiles' / username, ignore_errors=True)
    db.session.delete(user)
    db.session.commit()
    sync_all_users(restart=True)

def _read_file(path):
    p = Path(path)
    return p.read_text() if p.exists() else ''

def generate_profiles(user: VpnUser):
    root = current_app.config['CONFIG_ROOT'] / 'profiles' / user.username
    root.mkdir(parents=True, exist_ok=True)
    host = get_public_host()
    ovpn_proto = openvpn_transport()
    ovpn_selected_port = openvpn_port()
    oc_tcp = get_port('ocserv_tcp')
    wg_port = get_port('wireguard_udp')
    ca = _read_file('/etc/openvpn/server/ca.crt')
    tls = _read_file('/etc/openvpn/server/tls-crypt.key')
    cn = _ensure_openvpn_cert(user) if user.enabled and not user.expired else _safe_cn(user.username)
    cert = _read_file(f'/etc/openvpn/easy-rsa/pki/issued/{cn}.crt')
    key = _read_file(f'/etc/openvpn/easy-rsa/pki/private/{cn}.key')
    ovpn = f'''client
dev tun
proto {ovpn_proto}
remote {host} {ovpn_selected_port}
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
    root.joinpath('l2tp.txt').write_text(f'''Server: {host}
Type: L2TP/IPsec PSK
Username: {user.username}
Password: {user.l2tp_password or "same-as-panel"}
PSK: {psk}
Ports: UDP 500, 4500, 1701
''')
    root.joinpath('ocserv.txt').write_text(f'''Server: {host}:{oc_tcp}
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
DNS = 1.1.1.1

[Peer]
PublicKey = {server_pub}
Endpoint = {host}:{wg_port} # UDP
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
''')

def user_config_payload(user: VpnUser):
    ok, reason = user_access_status(user)
    if not ok:
        return {'ACCOUNT_STATUS.txt': reason}
    generate_profiles(user)
    root = current_app.config['CONFIG_ROOT'] / 'profiles' / user.username
    files = {}
    allowed=user.allowed_protocol_list() or user.protocol_list() or active_protocols()
    wanted=[]
    if 'openvpn' in allowed: wanted.append(f'{_safe_cn(user.username)}.ovpn')
    if 'wireguard' in allowed: wanted.append('wireguard.conf')
    if 'ocserv' in allowed: wanted.append('ocserv.txt')
    if 'l2tp' in allowed: wanted.append('l2tp.txt')
    for name in wanted:
        p = root / name
        if p.exists():
            files[name] = p.read_text()
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
    db.session.commit()
    # Enforce immediately after accounting so a limited user is stopped as soon as possible.
    try:
        enforce_usage_limits(commit=True)
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
            if limit > 0 and _user_used_bytes(user) >= limit:
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
    used_bytes = _user_used_bytes(user)
    upload_bytes = int(getattr(user, 'used_upload_bytes', 0) or 0) or int(user.used_upload_mb or 0) * 1024 * 1024
    download_bytes = int(getattr(user, 'used_download_bytes', 0) or 0) or int(user.used_download_mb or 0) * 1024 * 1024
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
        'remaining_mb': int(remaining_bytes // (1024 * 1024)) if remaining_bytes is not None else None,
        'remaining_bytes': remaining_bytes,
        'remaining_human': 'نامحدود' if total == 0 else _format_bytes(remaining_bytes or 0),
        'unlimited_traffic': total == 0,
        'expires_at': user.expires_at,
        'remaining_seconds': remaining_seconds,
        'remaining_days': remaining_days,
        'unlimited_time': user.expires_at is None,
    }

def service_status():
    services = ['openvpn-server@server', 'ocserv', 'strongswan-starter', 'xl2tpd', 'wg-quick@wg0', 'ironpanel']
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
user nobody
group nogroup
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
server-cert = /etc/ocserv/server-cert.pem
server-key = /etc/ocserv/server-key.pem
run-as-user = nobody
run-as-group = nogroup
try-mtu-discovery = true
ipv4-network = 10.10.10.0
ipv4-netmask = 255.255.255.0
dns = 1.1.1.1
route = default
cisco-client-compat = true
max-clients = 512
max-same-clients = 3
mobile-dpd = 1800
try-mtu-discovery = true
''')
    wg = Path('/etc/wireguard/wg0.conf')
    if wg.exists():
        txt = wg.read_text().splitlines()
        txt = [line if not line.startswith('ListenPort') else f'ListenPort = {get_port("wireguard_udp")}' for line in txt]
        wg.write_text('\n'.join(txt)+'\n')
    sync_all_users(restart=True)
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
    sync_all_users(restart=True)
    return True

def service_health_repair():
    install = Path('/opt/ironpanel/scripts/install_vpn_core.sh')
    if install.exists():
        run_cmd(['bash', str(install)])
    apply_runtime_configs()
    return service_status()

def protocol_enabled_for_user(user, proto):
    return proto in (user.allowed_protocol_list() or user.protocol_list() or active_protocols())


# ---------------- v13 Health diagnostics ----------------
def service_status_detailed():
    """Return service status with actionable error details and recent logs."""
    services = ['openvpn-server@server', 'ocserv', 'strongswan-starter', 'xl2tpd', 'wg-quick@wg0', 'ironpanel']
    result = {}
    for svc in services:
        active = run_cmd(['systemctl', 'is-active', svc])
        status = (active.stdout.strip() or active.stderr.strip() or 'unknown')
        show = run_cmd(['bash','-lc', f'systemctl status {svc} --no-pager -l 2>&1 | tail -n 80 || true'])
        journal = run_cmd(['bash','-lc', f'journalctl -u {svc} -n 120 --no-pager 2>&1 || true'])
        detail = (show.stdout + show.stderr + '\n\n--- Journal ---\n' + journal.stdout + journal.stderr).strip()
        result[svc] = {
            'status': status,
            'ok': status == 'active',
            'detail': detail[-12000:],
            'repair_hint': f'systemctl restart {svc}'
        }
    return result

def service_error_detail(service_name):
    allowed = ['openvpn-server@server', 'ocserv', 'strongswan-starter', 'xl2tpd', 'wg-quick@wg0', 'ironpanel']
    if service_name not in allowed:
        return 'Unknown service'
    return service_status_detailed().get(service_name, {}).get('detail', '')

import re
import shutil
import subprocess
from pathlib import Path
from flask import current_app
from ..core.models import VpnUser, ActivityLog, AppSetting
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

def user_access_status(user: VpnUser):
    if not user.enabled:
        return False, 'کاربر غیرفعال است'
    if user.expired:
        return False, 'اعتبار کاربر منقضی شده است'
    if user.data_limit_mb and user.used_total_mb >= user.data_limit_mb:
        return False, 'حجم کاربر تمام شده است'
    return True, 'فعال'

def _valid_users():
    return [u for u in VpnUser.query.all() if user_access_status(u)[0]]

def _safe_cn(username: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', username or 'user')
    return safe[:64] or 'user'

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
        if 'wireguard' in (u.protocol_list() or active_protocols()):
            peers.append(f'\n[Peer]\n# {u.username}\nPublicKey = {u.wg_public_key}\nAllowedIPs = {u.wg_ip}/32')
    peers.append('# END IRONPANEL PEERS\n')
    wg_conf.write_text(base + '\n\n' + '\n'.join(peers))
    run_cmd(['systemctl', 'restart', 'wg-quick@wg0'])

def _restart_runtime_services():
    for svc in ['openvpn-server@server', 'ocserv', 'strongswan-starter', 'xl2tpd']:
        run_cmd(['systemctl', 'restart', svc])

def sync_user(user: VpnUser):
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    if user.enabled and not user.expired:
        _ensure_wg_identity(user)
        if 'openvpn' in (user.protocol_list() or active_protocols()):
            _ensure_openvpn_cert(user)
    _write_plain_passwords(root)
    _rewrite_wireguard_server(root)
    generate_profiles(user)
    return True

def sync_all_users(restart=False):
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    for idx, u in enumerate(_valid_users(), start=10):
        _ensure_wg_identity(u, idx)
        if 'openvpn' in (u.protocol_list() or active_protocols()):
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
    for name in [f'{_safe_cn(user.username)}.ovpn', 'wireguard.conf', 'ocserv.txt', 'l2tp.txt']:
        p = root / name
        if p.exists():
            files[name] = p.read_text()
    return files

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
''')
    wg = Path('/etc/wireguard/wg0.conf')
    if wg.exists():
        txt = wg.read_text().splitlines()
        txt = [line if not line.startswith('ListenPort') else f'ListenPort = {get_port("wireguard_udp")}' for line in txt]
        wg.write_text('\n'.join(txt)+'\n')
    sync_all_users(restart=True)
    return True

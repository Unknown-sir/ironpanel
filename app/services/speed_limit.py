"""Speed limit manager for IronPanel.

There are three layers, from strongest to weakest:
1. user-wide ``VpnUser.speed_limit_mbps`` (all protocols for one user),
2. optional per-user/per-protocol override,
3. per-protocol default.

A user-wide limit is emitted as one shared tc class/mark group so all matching
protocol rules for that user share the same cap instead of creating one cap per
protocol.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from ..core.extensions import db
from ..core.models import VpnUser, OnlineSession
from .provisioning import get_setting, set_setting, get_port, active_protocols, run_cmd

PROTOCOL_LABELS = {
    'openvpn': 'OpenVPN', 'wireguard': 'WireGuard', 'ocserv': 'Cisco / Ocserv',
    'l2tp': 'L2TP / IPsec', 'xray': 'Xray / V2Ray', 'pptp': 'PPTP',
    'hysteria2': 'Hysteria2', 'telegram_proxy': 'Telegram Proxy', 'ssh': 'SSH Tunnel',
}
PROTOCOL_ICONS = {'openvpn':'🔐','wireguard':'🧬','ocserv':'🛡️','l2tp':'🌉','xray':'⚡','pptp':'🧷','hysteria2':'🚀','telegram_proxy':'📲','ssh':'⌁'}
PROTOCOL_HELP = {
    'openvpn':'برای هر کاربر OpenVPN جداگانه؛ بعد از فعال شدن session با IP همان session محدود می‌شود.',
    'wireguard':'برای هر peer وایرگارد جداگانه و با wg_ip کاربر اعمال می‌شود.',
    'ocserv':'برای هر کاربر Cisco/Ocserv جداگانه و بر اساس session فعال.',
    'l2tp':'برای هر کاربر L2TP/IPsec جداگانه و بر اساس session فعال.',
    'xray':'برای هر کاربر Xray جداگانه و بر اساس remote IP/session.',
    'pptp':'برای هر کاربر PPTP جداگانه و بر اساس session فعال.',
    'hysteria2':'برای هر کاربر Hysteria2 جداگانه و بر اساس UDP/session.',
    'telegram_proxy':'برای هر کاربر Telegram Proxy جداگانه و بر اساس session/secret.',
    'ssh':'برای هر کاربر SSH جداگانه؛ اگر Linux UID موجود باشد دقیق‌تر اعمال می‌شود.',
}
ALL_PROTOCOLS = list(PROTOCOL_LABELS.keys())

def _setting_key(protocol: str) -> str:
    return f'speed_limit_{protocol}_mbps'

def _sanitize_mbps(value, default=0) -> int:
    try:
        n = int(float(str(value if value is not None else default).strip() or default))
    except Exception:
        n = int(default or 0)
    return max(0, min(n, 100000))

def _json_setting(key, default):
    try:
        data = json.loads(get_setting(key, json.dumps(default)))
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default

def protocol_ports(protocol: str):
    if protocol == 'openvpn': return [('udp', get_port('openvpn_udp')), ('tcp', get_port('openvpn_tcp'))]
    if protocol == 'wireguard': return [('udp', get_port('wireguard_udp'))]
    if protocol == 'ocserv': return [('tcp', get_port('ocserv_tcp')), ('udp', get_port('ocserv_udp'))]
    if protocol == 'l2tp': return [('udp', get_port('l2tp_udp')), ('udp', get_port('ipsec_ike')), ('udp', get_port('ipsec_nat'))]
    if protocol == 'xray': return [('tcp', get_port('xray_tcp'))]
    if protocol == 'pptp': return [('tcp', get_port('pptp_tcp'))]
    if protocol == 'hysteria2': return [('udp', get_port('hysteria2_udp'))]
    if protocol == 'telegram_proxy': return [('tcp', get_port('telegram_proxy_base'))]
    if protocol == 'ssh': return [('tcp', get_port('ssh_tcp'))]
    return []

def default_limit(protocol: str) -> int:
    return _sanitize_mbps(get_setting(_setting_key(protocol), '0'))

def normalize_speed_limit_mbps(value) -> int:
    """Public normalizer used by web/API paths. 0 means no user-wide override."""
    return _sanitize_mbps(value, 0)

def user_wide_limit(user: VpnUser) -> int:
    return normalize_speed_limit_mbps(getattr(user, 'speed_limit_mbps', 0) or 0)

def set_user_speed_limit(user: VpnUser, value, *, commit: bool = True) -> int:
    mbps = normalize_speed_limit_mbps(value)
    user.speed_limit_mbps = mbps
    db.session.add(user)
    if commit:
        db.session.commit()
    return mbps

def user_limit_overrides() -> dict:
    return _json_setting('user_speed_limits_json', {})

def user_protocol_limit(user: VpnUser, protocol: str) -> int:
    # A direct user-wide cap is intentionally stronger than every protocol rule.
    # This is the simple "limit only this user" control exposed on Users/Edit.
    overall = user_wide_limit(user)
    if overall > 0:
        return overall
    try:
        data = json.loads(getattr(user, 'speed_limits_json', '') or '{}')
        if isinstance(data, dict) and protocol in data and str(data[protocol]).strip() != '':
            return _sanitize_mbps(data[protocol])
    except Exception:
        pass
    data = user_limit_overrides()
    if str(user.id) in data and isinstance(data[str(user.id)], dict) and protocol in data[str(user.id)]:
        return _sanitize_mbps(data[str(user.id)][protocol])
    return default_limit(protocol)

def speed_limit_rows():
    active = set(active_protocols())
    rows=[]
    for protocol in ALL_PROTOCOLS:
        mbps = default_limit(protocol)
        ports = protocol_ports(protocol)
        rows.append({
            'protocol': protocol, 'label': PROTOCOL_LABELS.get(protocol, protocol.upper()),
            'icon': PROTOCOL_ICONS.get(protocol, '◈'), 'help': PROTOCOL_HELP.get(protocol, ''),
            'mbps': mbps, 'enabled': mbps > 0, 'active': protocol in active,
            'ports': ports, 'ports_text': ', '.join([f'{p}/{proto}' for proto, p in ports]) or '-',
            'user_count': VpnUser.query.filter(VpnUser.protocols.ilike(f'%{protocol}%')).count(),
        })
    return rows

def save_speed_limits(form) -> list[str]:
    changed=[]
    for protocol in ALL_PROTOCOLS:
        key = _setting_key(protocol)
        value = _sanitize_mbps(form.get(key, '0'))
        old = _sanitize_mbps(get_setting(key, '0'))
        set_setting(key, str(value))
        if old != value: changed.append(protocol)
    set_setting('speed_limits_apply_mode', 'per_user_protocol')
    db.session.commit()
    return changed

def speed_limit_user_matrix(limit=500):
    rows=[]
    for u in VpnUser.query.order_by(VpnUser.id.desc()).limit(limit).all():
        protos=[p for p in (u.protocols or '').split(',') if p]
        cells=[]
        try: udata=json.loads(getattr(u,'speed_limits_json','') or '{}')
        except Exception: udata={}
        for p in ALL_PROTOCOLS:
            if p not in protos: continue
            cells.append({'protocol':p,'label':PROTOCOL_LABELS.get(p,p),'icon':PROTOCOL_ICONS.get(p,'•'),'default':default_limit(p),'override':str(udata.get(p,'')) if isinstance(udata,dict) else '','effective':user_protocol_limit(u,p)})
        rows.append({'user':u,'user_limit':user_wide_limit(u),'cells':cells})
    return rows

def save_user_speed_limits(form) -> int:
    changed=0
    global_overrides=user_limit_overrides()
    for u in VpnUser.query.order_by(VpnUser.id.desc()).limit(1000).all():
        # The all-protocol field is always present on the admin speed-limit page.
        # 0 disables the user-wide override and falls back to protocol rules.
        overall_raw = form.get(f'user_speed_all_{u.id}')
        if overall_raw is not None:
            overall = normalize_speed_limit_mbps(overall_raw)
            if user_wide_limit(u) != overall:
                u.speed_limit_mbps = overall
                changed += 1
        data={}
        for p in ALL_PROTOCOLS:
            raw=(form.get(f'user_speed_{u.id}_{p}') or '').strip()
            if raw != '': data[p]=_sanitize_mbps(raw)
        new=json.dumps(data, ensure_ascii=False) if data else ''
        old=getattr(u,'speed_limits_json','') or ''
        if hasattr(u,'speed_limits_json') and old != new:
            u.speed_limits_json=new
            changed+=1
        if data: global_overrides[str(u.id)]=data
        elif str(u.id) in global_overrides:
            global_overrides.pop(str(u.id),None); changed+=1
    set_setting('user_speed_limits_json', json.dumps(global_overrides, ensure_ascii=False))
    db.session.commit()
    return changed

def _latest_remote_ip(user_id, protocol):
    try:
        s=OnlineSession.query.filter_by(user_id=user_id, protocol=protocol, active=True).order_by(OnlineSession.last_seen.desc()).first()
        if s and s.remote_ip: return s.remote_ip.split(',')[0].strip()
    except Exception: pass
    return ''

def _linux_uid(username):
    safe=re.sub(r'[^A-Za-z0-9_.-]','_',username or '')
    if not safe: return ''
    try:
        p=run_cmd(['bash','-lc', f'id -u {safe!r} 2>/dev/null || true'], timeout=3)
        return (p.stdout or '').strip().splitlines()[0]
    except Exception: return ''

def _wireguard_endpoints() -> dict:
    """Return {peer_public_key: ipv4:port} from the live wg interface.

    Matching the encrypted peer endpoint (including NAT source port) is much
    more accurate than trying to match the peer's tunnel address on the public
    egress interface.
    """
    out={}
    try:
        p=run_cmd(['wg','show','wg0','endpoints'], timeout=5)
        for line in (p.stdout or '').splitlines():
            parts=line.split()
            if len(parts) < 2 or parts[1] in {'(none)','off'}:
                continue
            key, endpoint = parts[0].strip(), parts[1].strip()
            # The current iptables runtime is IPv4-only. Preserve IPv6 peers as
            # pending instead of creating a misleading rule.
            if endpoint.startswith('[') or endpoint.count(':') != 1:
                continue
            host, port = endpoint.rsplit(':', 1)
            if re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', host) and port.isdigit():
                out[key]=f'{host}:{int(port)}'
    except Exception:
        pass
    return out

def _match_for_user(user, protocol, wg_endpoints=None):
    if protocol == 'wireguard':
        endpoint=(wg_endpoints or {}).get((getattr(user, 'wg_public_key', '') or '').strip(), '')
        if endpoint:
            return 'remote_endpoint', endpoint
        return 'pending', '-'
    if protocol == 'ssh':
        uid=_linux_uid(user.username)
        if uid: return 'uid', uid
    remote=_latest_remote_ip(user.id, protocol)
    if remote: return 'remote_ip', remote
    return 'pending', '-'

def speed_limits_configured() -> bool:
    try:
        if VpnUser.query.filter(VpnUser.enabled.is_(True), VpnUser.speed_limit_mbps > 0).first():
            return True
    except Exception:
        pass
    if any(default_limit(p) > 0 for p in ALL_PROTOCOLS):
        return True
    try:
        if any((getattr(u, 'speed_limits_json', '') or '').strip() not in {'', '{}'} for u in VpnUser.query.filter_by(enabled=True).all()):
            return True
    except Exception:
        pass
    return bool(user_limit_overrides())

def write_speed_limit_runtime_config() -> Path:
    path=Path('/etc/ironpanel/speed_limits.conf')
    path.parent.mkdir(parents=True, exist_ok=True)
    lines=['# Generated by IronPanel v19.10.25', '# username user_id protocol proto port mbps match_type match_value group_key']
    wg_endpoints = _wireguard_endpoints()
    for u in VpnUser.query.filter_by(enabled=True).order_by(VpnUser.id).all():
        overall = user_wide_limit(u)
        for protocol in [p for p in (u.protocols or '').split(',') if p]:
            if protocol not in ALL_PROTOCOLS: continue
            mbps=user_protocol_limit(u, protocol)
            if mbps <= 0: continue
            mtype,mval=_match_for_user(u, protocol, wg_endpoints)
            safe_user=re.sub(r'[^A-Za-z0-9_.-]','_',u.username or f'user{u.id}')
            # User-wide limits share one class across every protocol for this user.
            # Legacy/per-protocol limits keep separate classes.
            group_key = f'user-{int(u.id)}' if overall > 0 else f'user-{int(u.id)}-{protocol}'
            for proto, port in protocol_ports(protocol):
                if int(port or 0)>0:
                    lines.append(f'{safe_user} {int(u.id)} {protocol} {proto} {int(port)} {int(mbps)} {mtype} {mval} {group_key}')
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return path

def apply_speed_limits_runtime():
    write_speed_limit_runtime_config()
    script=Path('/opt/ironpanel/scripts/apply_speed_limits.sh')
    if not script.exists():
        script=Path(__file__).resolve().parents[2] / 'scripts' / 'apply_speed_limits.sh'
        if not script.exists():
            return False, 'apply_speed_limits.sh not found. Run panel upgrade/install first.'
    p=run_cmd(['bash', str(script), '--apply'], timeout=120)
    out=(p.stdout or '')+(p.stderr or '')
    return p.returncode == 0, out[-6000:]

def refresh_speed_limits_runtime_if_changed():
    """Refresh runtime only when live session/peer matching changed.

    Usage Sync calls this after refreshing online sessions. It avoids tearing
    down/rebuilding tc every minute when the generated configuration is stable.
    """
    path=Path('/etc/ironpanel/speed_limits.conf')
    try:
        before=path.read_text(encoding='utf-8') if path.exists() else ''
    except Exception:
        before=''
    write_speed_limit_runtime_config()
    try:
        after=path.read_text(encoding='utf-8')
    except Exception:
        after=''
    if before == after:
        return True, 'unchanged'
    script=Path('/opt/ironpanel/scripts/apply_speed_limits.sh')
    if not script.exists():
        script=Path(__file__).resolve().parents[2] / 'scripts' / 'apply_speed_limits.sh'
    if not script.exists():
        return False, 'apply_speed_limits.sh not found'
    p=run_cmd(['bash', str(script), '--apply'], timeout=120)
    out=(p.stdout or '')+(p.stderr or '')
    return p.returncode == 0, out[-6000:]

def speed_limit_status():
    p=run_cmd(['bash','-lc','echo "--- mangle marks"; iptables -t mangle -S IRONPANEL_SPEED_MARK 2>/dev/null | head -80; echo "--- tc"; tc -s qdisc show 2>/dev/null | head -80; tc -s class show 2>/dev/null | head -120'], timeout=20)
    return ((p.stdout or '')+(p.stderr or '')).strip()[-10000:]

from datetime import datetime, timedelta
from pathlib import Path
import json, re
from flask import current_app
from ..core.extensions import db
from ..core.models import Node, VpnUser, OnlineSession, ActivityLog, RemoteJob, AppSetting
from .provisioning import run_cmd, get_setting, set_setting, service_status, backup_now, telegram_notify, sync_all_users


def server_metrics():
    import psutil, os
    vm=psutil.virtual_memory(); sw=psutil.swap_memory(); du=psutil.disk_usage('/')
    net=psutil.net_io_counters()
    return {
        'cpu': psutil.cpu_percent(interval=0.05), 'load': list(os.getloadavg()) if hasattr(os,'getloadavg') else [0,0,0],
        'ram': {'percent': vm.percent, 'used': vm.used, 'total': vm.total},
        'swap': {'percent': sw.percent, 'used': sw.used, 'total': sw.total},
        'disk': {'percent': du.percent, 'used': du.used, 'total': du.total},
        'network': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv},
        'uptime': int(datetime.utcnow().timestamp() - psutil.boot_time()),
    }


def geoip_country(ip):
    if not ip or ip.startswith(('10.','192.168.','172.16.','172.17.','172.18.','172.19.','172.20.','172.21.','172.22.','172.23.','172.24.','172.25.','172.26.','172.27.','172.28.','172.29.','172.30.','172.31.','127.')):
        return 'Private'
    return 'Unknown'


def _safe_dt_from_timestamp(value, default):
    try:
        ts = int(str(value or '').strip())
        if ts > 0:
            return datetime.utcfromtimestamp(ts)
    except Exception:
        pass
    return default


def _find_user_identity(identity):
    ident = (identity or '').strip()
    if not ident:
        return None
    user = VpnUser.query.filter_by(username=ident).first()
    if user:
        return user
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', ident)[:64]
    for u in VpnUser.query.all():
        if re.sub(r'[^A-Za-z0-9_.-]', '_', u.username or '')[:64] == safe:
            return u
    return None


def _upsert_online(username, protocol, remote_ip='', connected_at=None, device_id='', node_id=None):
    username = (username or '').strip()
    if not username or username.lower() in ('unknown', 'anonymous'):
        return None
    now = datetime.utcnow()
    user = _find_user_identity(username)
    # Do not show disabled/expired users as valid online accounts, but keep best-effort unknowns.
    if user and (not user.enabled or user.expired):
        return None
    q = OnlineSession.query.filter_by(username=(user.username if user else username), protocol=protocol, active=True)
    if remote_ip:
        existing = q.filter_by(remote_ip=remote_ip).first()
    else:
        existing = q.first()
    if not existing:
        existing = OnlineSession(
            username=(user.username if user else username),
            user_id=(user.id if user else None),
            protocol=protocol,
            remote_ip=remote_ip or '',
            country=geoip_country(remote_ip),
            device_id=device_id or '',
            node_id=node_id,
            connected_at=connected_at or now,
            last_seen=now,
            active=True,
        )
    else:
        existing.user_id = user.id if user else existing.user_id
        existing.remote_ip = remote_ip or existing.remote_ip
        existing.country = geoip_country(existing.remote_ip)
        existing.device_id = device_id or existing.device_id
        existing.node_id = node_id if node_id is not None else existing.node_id
        existing.last_seen = now
        existing.active = True
    db.session.add(existing)
    return existing


def _openvpn_status_paths():
    return [
        Path('/var/log/openvpn/status.log'),
        Path('/run/openvpn-server/status-server.log'),
        Path('/etc/openvpn/server/status.log'),
        Path('/var/log/openvpn/openvpn-status.log'),
    ]


def _refresh_openvpn_sessions():
    count = 0
    for path in _openvpn_status_paths():
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
            if line.startswith('HEADER,CLIENT_LIST'):
                continue
            if line.startswith('CLIENT_LIST,'):
                parts = line.split(',')
                if len(parts) >= 9:
                    # status-version 2:
                    # CLIENT_LIST,CN,Real Address,Virtual Address,Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),...
                    username = parts[1].strip()
                    remote_ip = (parts[2].split(':')[0] if len(parts) > 2 else '').strip()
                    connected_at = _safe_dt_from_timestamp(parts[8], datetime.utcnow())
                elif len(parts) >= 5:
                    username = parts[1].strip()
                    remote_ip = (parts[2].split(':')[0] if len(parts) > 2 else '').strip()
                    connected_at = datetime.utcnow()
                else:
                    continue
                if _upsert_online(username, 'openvpn', remote_ip, connected_at):
                    count += 1
                continue
            # OpenVPN status-version 1 fallback.
            if line.startswith('Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since'):
                in_v1_clients = True
                continue
            if line.startswith('ROUTING TABLE'):
                in_v1_clients = False
            if in_v1_clients and ',' in line and not line.startswith('Updated,'):
                parts = line.split(',')
                if len(parts) >= 5:
                    username = parts[0].strip()
                    remote_ip = parts[1].split(':')[0].strip()
                    if _upsert_online(username, 'openvpn', remote_ip, datetime.utcnow()):
                        count += 1
        break
    return count


def _refresh_wireguard_sessions():
    count = 0
    now = datetime.utcnow()
    users = {u.wg_public_key: u for u in VpnUser.query.all() if u.wg_public_key}
    # Prefer dump because it includes endpoint, latest handshake and transfer in one call.
    p = run_cmd(['bash', '-lc', 'wg show wg0 dump 2>/dev/null || true'])
    for line in (p.stdout or '').splitlines():
        parts = line.split('\t')
        if len(parts) < 8:
            parts = line.split()
        # First line may be the interface line: private_key public_key listen_port fwmark
        if len(parts) < 8:
            continue
        pub = parts[0]
        endpoint = parts[2] if len(parts) > 2 else ''
        allowed_ips = parts[3] if len(parts) > 3 else ''
        latest = parts[4] if len(parts) > 4 else '0'
        user = users.get(pub)
        if not user:
            continue
        try:
            ts = int(latest or 0)
        except Exception:
            ts = 0
        if ts <= 0:
            continue
        # WireGuard refreshes handshakes roughly every few minutes while active.
        if datetime.utcfromtimestamp(ts) < now - timedelta(minutes=10):
            continue
        remote_ip = endpoint.split(':')[0].strip('[]') if endpoint and endpoint != '(none)' else ''
        if _upsert_online(user.username, 'wireguard', remote_ip, datetime.utcfromtimestamp(ts), allowed_ips):
            count += 1
    # Fallback for older wg versions without dump.
    if count == 0:
        endpoints = {}
        ep = run_cmd(['bash', '-lc', 'wg show wg0 endpoints 2>/dev/null || true'])
        for line in (ep.stdout or '').splitlines():
            ps = line.split()
            if len(ps) >= 2:
                endpoints[ps[0]] = ps[1]
        hs = run_cmd(['bash', '-lc', 'wg show wg0 latest-handshakes 2>/dev/null || true'])
        for line in (hs.stdout or '').splitlines():
            ps = line.split()
            if len(ps) >= 2 and ps[1].isdigit():
                user = users.get(ps[0])
                if not user:
                    continue
                ts = int(ps[1])
                if ts > 0 and datetime.utcfromtimestamp(ts) > now - timedelta(minutes=10):
                    epv = endpoints.get(ps[0], '')
                    remote_ip = epv.split(':')[0].strip('[]') if epv and epv != '(none)' else ''
                    if _upsert_online(user.username, 'wireguard', remote_ip, datetime.utcfromtimestamp(ts)):
                        count += 1
    return count


def _refresh_ocserv_sessions():
    count = 0
    raw = ''
    # occtl can require root; IronPanel runs as root by default.
    for cmd in ['occtl -j show users 2>/dev/null || true', 'occtl show users 2>/dev/null || true']:
        p = run_cmd(['bash', '-lc', cmd])
        raw = (p.stdout or '').strip()
        if raw:
            break
    if not raw:
        return 0
    # JSON mode on some ocserv builds.
    try:
        data = json.loads(raw)
        rows = data.get('users') if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = list(rows.values())
        if isinstance(rows, list):
            for item in rows:
                if not isinstance(item, dict):
                    continue
                username = str(item.get('username') or item.get('user') or item.get('name') or '').strip()
                remote_ip = str(item.get('ip') or item.get('remote_ip') or item.get('real_ip') or item.get('remote-addr') or '').split(':')[0]
                if _upsert_online(username, 'ocserv', remote_ip):
                    count += 1
            if count:
                return count
    except Exception:
        pass
    # Text mode. Match both key:value blocks and table-like lines.
    current = {}
    def flush_current():
        nonlocal count, current
        username = current.get('username') or current.get('user') or current.get('name')
        remote_ip = current.get('remote_ip') or current.get('real_ip') or current.get('ip') or current.get('remote') or ''
        if username and _upsert_online(username, 'ocserv', str(remote_ip).split(':')[0]):
            count += 1
        current = {}
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            flush_current(); continue
        m = re.match(r'(?i)^(username|user|name|ip|remote ip|remote-ip|real ip|real-ip|remote):\s*(.+)$', s)
        if m:
            key = m.group(1).lower().replace(' ', '_').replace('-', '_')
            current[key] = m.group(2).strip()
            continue
        # Table row fallback: username ... IPv4
        m = re.search(r'(?P<user>[A-Za-z0-9_.@-]{2,64}).*?(?P<ip>\b(?:\d{1,3}\.){3}\d{1,3}\b)', s)
        if m and not s.lower().startswith(('id ', 'user ', 'username ', 'name ')):
            if _upsert_online(m.group('user'), 'ocserv', m.group('ip')):
                count += 1
    flush_current()
    return count


def _refresh_l2tp_sessions():
    # Best effort fallback. New installs also register PPP ip-up/ip-down hooks that
    # write exact L2TP sessions into online_session via ironpanel_session_account.py.
    count = 0
    p = run_cmd(['bash', '-lc', "ip -o addr show 2>/dev/null | awk '/ppp[0-9]+/ {print $2, $4}' || true"])
    for line in (p.stdout or '').splitlines():
        parts = line.split()
        if len(parts) >= 2:
            iface = parts[0]
            ip = parts[1].split('/')[0]
            username = f'l2tp-{iface}'
            # If PPP hooks already recorded named sessions, do not create duplicates for the same iface.
            existing = OnlineSession.query.filter_by(protocol='l2tp', device_id=iface, active=True).first()
            if existing:
                existing.last_seen = datetime.utcnow(); db.session.add(existing); count += 1
            else:
                if _upsert_online(username, 'l2tp', ip, device_id=iface):
                    count += 1
    return count


def refresh_online_sessions():
    """Refresh and return online VPN sessions across OpenVPN, WireGuard, Ocserv and L2TP.

    v13.5 fixes the previous behavior where only WireGuard handshakes were checked.
    It now reads OpenVPN status logs, WireGuard dump/endpoints, occtl output and PPP hooks.
    """
    now = datetime.utcnow()
    # Mark sessions stale first; live detectors below will reactivate/update them.
    OnlineSession.query.filter(OnlineSession.last_seen < now - timedelta(minutes=12)).update({'active': False})
    errors = []
    for name, fn in (
        ('openvpn', _refresh_openvpn_sessions),
        ('wireguard', _refresh_wireguard_sessions),
        ('ocserv', _refresh_ocserv_sessions),
        ('l2tp', _refresh_l2tp_sessions),
    ):
        try:
            fn()
        except Exception as exc:
            errors.append(f'{name}: {exc}')
    if errors:
        try:
            row = AppSetting.query.filter_by(key='online_sessions_last_error').first()
            if row:
                row.value = '; '.join(errors)[-1000:]
            else:
                db.session.add(AppSetting(key='online_sessions_last_error', value='; '.join(errors)[-1000:]))
        except Exception:
            pass
    db.session.commit()
    return OnlineSession.query.filter_by(active=True).order_by(OnlineSession.last_seen.desc()).all()


def kick_session(session_id):
    sess=OnlineSession.query.get(session_id)
    if not sess: return False
    sess.active=False; db.session.commit()
    # Disable the user for a deterministic kick when the session is tied to a user.
    # Admin can re-enable from the users page.
    if sess.user_id:
        u=VpnUser.query.get(sess.user_id)
        if u:
            u.enabled=False
            db.session.add(ActivityLog(actor='system', action='kick_disable_user', target=u.username, details=f'{sess.protocol} {sess.remote_ip}'))
            db.session.commit()
    sync_all_users(restart=True)
    return True


def select_node_for_new_user(protocols=None):
    nodes=Node.query.all()
    if not nodes: return None
    if get_setting('load_balancer_enabled','0') != '1': return nodes[0]
    counts={n.id:0 for n in nodes}
    for u in VpnUser.query.all():
        counts[nodes[0].id]=counts.get(nodes[0].id,0)+1
    return sorted(nodes, key=lambda n: counts.get(n.id,0))[0]


def health_auto_repair():
    bad=[svc for svc,state in service_status().items() if state not in ('active','unknown')]
    if bad and get_setting('auto_failover_enabled','1')=='1':
        run_cmd(['bash','-lc','systemctl restart openvpn-server@server ocserv wg-quick@wg0 xl2tpd strongswan-starter strongswan 2>/dev/null || true'])
        telegram_notify('IronPanel auto-repair executed for: '+', '.join(bad))
    return bad


def run_remote_job(node_id, action):
    job=RemoteJob(node_id=node_id, action=action, status='running')
    db.session.add(job); db.session.commit()
    cmds={
        'restart_panel':'systemctl restart ironpanel',
        'restart_vpn':'systemctl restart openvpn-server@server ocserv wg-quick@wg0 xl2tpd strongswan-starter strongswan || true',
        'repair':'bash /opt/ironpanel/scripts/install_vpn_core.sh && systemctl restart ironpanel',
        'backup':'bash -lc "cd /opt/ironpanel && .venv/bin/python -m flask --app run.py version >/dev/null 2>&1 || true"',
        'update':'bash /opt/ironpanel/upgrade.sh || true',
    }
    cmd=cmds.get(action,'true')
    p=run_cmd(['bash','-lc',cmd])
    job.status='done' if p.returncode==0 else 'failed'
    job.output=(p.stdout+p.stderr)[-4000:]
    db.session.commit()
    return job


def schedule_backup_if_needed():
    if get_setting('auto_backup_enabled','1')!='1': return None
    return backup_now()

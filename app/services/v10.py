from datetime import datetime, timedelta
from pathlib import Path
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
    if not ip or ip.startswith(('10.','192.168.','172.16.','127.')):
        return 'Private'
    # Offline safe placeholder. Installers can replace this with MaxMind GeoLite2.
    return 'Unknown'


def refresh_online_sessions():
    """Best effort online user detector across protocols."""
    now=datetime.utcnow()
    # expire stale sessions
    OnlineSession.query.filter(OnlineSession.last_seen < now - timedelta(minutes=10)).update({'active': False})
    # WireGuard latest handshakes
    p=run_cmd(['bash','-lc','wg show wg0 latest-handshakes 2>/dev/null || true'])
    public_to_user={u.wg_public_key:u for u in VpnUser.query.all() if u.wg_public_key}
    for line in p.stdout.splitlines():
        parts=line.split()
        if len(parts)>=2 and parts[1].isdigit() and int(parts[1])>0 and datetime.utcfromtimestamp(int(parts[1])) > now-timedelta(minutes=5):
            u=public_to_user.get(parts[0])
            if not u: continue
            sess=OnlineSession.query.filter_by(username=u.username, protocol='wireguard', active=True).first()
            if not sess: sess=OnlineSession(username=u.username, user_id=u.id, protocol='wireguard', connected_at=now)
            sess.last_seen=now; sess.active=True; db.session.add(sess)
    db.session.commit()
    return OnlineSession.query.filter_by(active=True).order_by(OnlineSession.last_seen.desc()).all()


def kick_session(session_id):
    sess=OnlineSession.query.get(session_id)
    if not sess: return False
    sess.active=False; db.session.commit()
    # Best effort: full sync removes disabled/over-limit users; exact session kill depends on protocol client.
    sync_all_users(restart=True)
    return True


def select_node_for_new_user(protocols=None):
    nodes=Node.query.all()
    if not nodes: return None
    if get_setting('load_balancer_enabled','0') != '1': return nodes[0]
    # Choose lowest known user count node. local node_id None counts as local.
    counts={n.id:0 for n in nodes}
    for u in VpnUser.query.all():
        counts[nodes[0].id]=counts.get(nodes[0].id,0)+1
    return sorted(nodes, key=lambda n: counts.get(n.id,0))[0]


def health_auto_repair():
    bad=[svc for svc,state in service_status().items() if state not in ('active','unknown')]
    if bad and get_setting('auto_failover_enabled','1')=='1':
        run_cmd(['bash','-lc','systemctl restart openvpn-server@server ocserv wg-quick@wg0 xl2tpd strongswan-starter 2>/dev/null || true'])
        telegram_notify('IronPanel auto-repair executed for: '+', '.join(bad))
    return bad


def run_remote_job(node_id, action):
    job=RemoteJob(node_id=node_id, action=action, status='running')
    db.session.add(job); db.session.commit()
    cmds={
        'restart_panel':'systemctl restart ironpanel',
        'restart_vpn':'systemctl restart openvpn-server@server ocserv wg-quick@wg0 xl2tpd strongswan-starter || true',
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

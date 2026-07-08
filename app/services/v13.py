
from __future__ import annotations
from datetime import datetime
from ..core.extensions import db
from ..core.models import UpdateRelease, RemoteJob, Node, AppSetting
from .provisioning import run_cmd, set_setting, get_setting, backup_now, telegram_notify

def current_version():
    try:
        from pathlib import Path
        return Path('/opt/ironpanel/VERSION').read_text().strip()
    except Exception:
        return 'unknown'

def latest_release(channel=None):
    channel = channel or get_setting('release_channel','stable')
    return UpdateRelease.query.filter_by(channel=channel, published=True).order_by(UpdateRelease.id.desc()).first()

def create_release(version, channel='stable', download_url='', changelog=''):
    r=UpdateRelease(version=version, channel=channel, download_url=download_url, changelog=changelog, published=True)
    db.session.add(r); db.session.commit(); return r

def run_local_remote_action(action):
    cmds={
        'restart_panel':'systemctl restart ironpanel',
        'restart_vpn':'systemctl restart openvpn-server@server ocserv wg-quick@wg0 xl2tpd strongswan-starter 2>/dev/null || true',
        'repair':'bash /opt/ironpanel/scripts/install_vpn_core.sh && systemctl restart openvpn-server@server ocserv wg-quick@wg0 xl2tpd strongswan-starter 2>/dev/null || true',
        'backup':'bash -lc "cd /opt/ironpanel && .venv/bin/python - <<PY\nfrom app import create_app\nfrom app.services.provisioning import backup_now\napp=create_app()\nwith app.app_context(): print(backup_now())\nPY"',
        'update':'bash /opt/ironpanel/upgrade.sh || true',
    }
    p=run_cmd(['bash','-lc',cmds.get(action,'true')])
    return p.returncode==0, (p.stdout+p.stderr)[-5000:]

def queue_node_job(node_id, action):
    job=RemoteJob(node_id=node_id, action=action, status='queued')
    db.session.add(job); db.session.commit(); return job

def process_local_jobs():
    jobs=RemoteJob.query.filter_by(status='queued').limit(10).all()
    for j in jobs:
        j.status='running'; db.session.commit()
        ok,out=run_local_remote_action(j.action)
        j.status='done' if ok else 'failed'; j.output=out; db.session.commit()
    return jobs

def hardware_fingerprint_payload():
    import hashlib, subprocess, socket
    raw = ''
    for cmd in ['cat /etc/machine-id 2>/dev/null', 'hostname', 'ip link 2>/dev/null | sha256sum']:
        p=run_cmd(['bash','-lc',cmd]); raw += p.stdout.strip()
    return hashlib.sha256(raw.encode()).hexdigest()


def github_latest_version():
    """Check GitHub main branch VERSION file for latest published version."""
    import requests
    url = get_setting('github_version_url', 'https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/VERSION')
    try:
        r = requests.get(url, timeout=4)
        latest = (r.text or '').strip().splitlines()[0] if r.ok else ''
        return {'ok': bool(latest), 'latest': latest, 'current': current_version(), 'url': url, 'update_available': bool(latest and latest != current_version())}
    except Exception as e:
        return {'ok': False, 'latest': '', 'current': current_version(), 'url': url, 'error': str(e), 'update_available': False}

def run_github_update():
    """Run one-click GitHub updater. Available to every valid license type."""
    p = run_cmd(['bash','-lc','bash /opt/ironpanel/scripts/update_from_github.sh 2>&1 || true'])
    return p.returncode == 0, (p.stdout + p.stderr)[-8000:]

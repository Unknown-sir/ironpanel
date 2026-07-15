from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import re
import shlex

from ..core.extensions import db
from ..core.models import UpdateRelease, RemoteJob, Node, AppSetting
from .provisioning import run_cmd, set_setting, get_setting, backup_now, telegram_notify


def current_version():
    """Return the installed panel version without requiring the app to be in /opt during tests."""
    for path in (Path('/opt/ironpanel/VERSION'), Path(__file__).resolve().parents[2] / 'VERSION'):
        try:
            value = path.read_text().strip()
            if value:
                return value
        except Exception:
            pass
    return 'unknown'


def _version_tuple(value: str):
    """Comparable semantic-ish version tuple: v18.5.4-beta -> (18, 5, 4)."""
    nums = re.findall(r'\d+', str(value or ''))
    if not nums:
        return ()
    parts = [int(x) for x in nums[:4]]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)


def is_newer_version(latest: str, current: str | None = None) -> bool:
    current = current or current_version()
    latest_t = _version_tuple(latest)
    current_t = _version_tuple(current)
    if not latest_t or not current_t:
        return False
    return latest_t > current_t


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
    import hashlib
    raw = ''
    for cmd in ['cat /etc/machine-id 2>/dev/null', 'hostname', 'ip link 2>/dev/null | sha256sum']:
        p=run_cmd(['bash','-lc',cmd]); raw += p.stdout.strip()
    return hashlib.sha256(raw.encode()).hexdigest()


def _setting_json(key: str, default=None):
    raw = get_setting(key, '')
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _github_version_url():
    url = get_setting('github_version_url', '')
    if url:
        return url
    branch = get_setting('github_branch', 'main') or 'main'
    return f'https://raw.githubusercontent.com/Unknown-sir/ironpanel/{branch}/VERSION'


def github_latest_version(force: bool = False):
    """Check GitHub VERSION and cache it so dashboard loading is not blocked every time."""
    import requests

    current = current_version()
    url = _github_version_url()
    interval_minutes = int(get_setting('github_update_check_interval_minutes', '60') or 60)
    cache = _setting_json('github_update_cache', {}) or {}

    if not force and cache.get('url') == url and cache.get('checked_at'):
        try:
            checked_at = datetime.fromisoformat(cache['checked_at'])
            if datetime.utcnow() - checked_at < timedelta(minutes=max(interval_minutes, 5)):
                latest = cache.get('latest', '')
                return {
                    'ok': bool(latest),
                    'latest': latest,
                    'current': current,
                    'url': url,
                    'checked_at': cache.get('checked_at'),
                    'cached': True,
                    'error': cache.get('error', ''),
                    'update_available': is_newer_version(latest, current),
                }
        except Exception:
            pass

    result = {'ok': False, 'latest': '', 'current': current, 'url': url, 'checked_at': datetime.utcnow().isoformat(timespec='seconds'), 'cached': False, 'error': '', 'update_available': False}
    try:
        r = requests.get(url, timeout=5, headers={'User-Agent': 'IronPanel-Updater/18.5'})
        latest = (r.text or '').strip().splitlines()[0] if r.ok else ''
        if not r.ok:
            result['error'] = f'HTTP {r.status_code}'
        elif not _version_tuple(latest):
            result['error'] = 'VERSION نامعتبر است'
        else:
            result.update({'ok': True, 'latest': latest, 'update_available': is_newer_version(latest, current)})
    except Exception as e:
        result['error'] = str(e)

    try:
        set_setting('github_update_cache', json.dumps({k: result.get(k) for k in ['latest','url','checked_at','error']}, ensure_ascii=False))
    except Exception:
        pass
    return result


def run_github_update(background: bool = True):
    """Start the GitHub updater safely.

    The dashboard button runs it in the background because the updater restarts
    the panel service; doing that inside the same HTTP request can cut the
    browser connection before a response is returned.
    """
    repo = shlex.quote(get_setting('github_repo_url', 'https://github.com/Unknown-sir/ironpanel.git'))
    branch = shlex.quote(get_setting('github_branch', 'main') or 'main')
    log_file = '/var/log/ironpanel-github-upgrade.log'
    env = f'IRONPANEL_GITHUB_REPO={repo} IRONPANEL_GITHUB_BRANCH={branch}'
    cmd = f'{env} bash /opt/ironpanel/scripts/update_from_github.sh'
    if background:
        shell = f'mkdir -p /var/log; nohup bash -lc {shlex.quote(cmd)} > {shlex.quote(log_file)} 2>&1 & echo $!'
        p = run_cmd(['bash','-lc', shell])
        ok = p.returncode == 0 and bool((p.stdout or '').strip())
        pid = (p.stdout or '').strip().splitlines()[-1] if p.stdout else ''
        return ok, (f'آپگرید GitHub در پس‌زمینه شروع شد. PID={pid}. لاگ: {log_file}' if ok else (p.stderr or p.stdout or 'شروع آپگرید ناموفق بود.'))
    p = run_cmd(['bash','-lc', f'{cmd} 2>&1'])
    return p.returncode == 0, (p.stdout + p.stderr)[-8000:]


def github_update_log_tail(lines: int = 80):
    p = run_cmd(['bash','-lc', f'tail -n {int(lines)} /var/log/ironpanel-github-upgrade.log 2>/dev/null || true'])
    return (p.stdout or p.stderr or '').strip()

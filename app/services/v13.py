from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import re
import shlex
import time

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


def _github_update_unit_name() -> str:
    return 'ironpanel-github-upgrade'


def github_update_status():
    """Return status for the detached systemd upgrade unit.

    The old updater was started as a child process of the web panel. When
    upgrade.sh restarted ironpanel, systemd could kill that child process with
    the panel cgroup. This status helper tracks the dedicated systemd unit used
    by the new updater.
    """
    unit = _github_update_unit_name() + '.service'
    p = run_cmd(['bash','-lc', f"systemctl show {shlex.quote(unit)} -p ActiveState -p SubState -p Result -p ExecMainStatus --no-page 2>/dev/null || true"])
    data = {}
    for line in (p.stdout or '').splitlines():
        if '=' in line:
            k, v = line.split('=', 1); data[k] = v
    active = data.get('ActiveState', 'unknown')
    sub = data.get('SubState', '')
    result = data.get('Result', '')
    running = active in ('activating', 'active') and sub not in ('exited', 'dead', 'failed')
    return {
        'unit': unit,
        'active': active,
        'sub': sub,
        'result': result,
        'running': running,
        'ok': result in ('success', '') and active in ('inactive', 'active', 'unknown'),
    }


def run_github_update(background: bool = True):
    """Start the GitHub updater safely as an independent systemd job.

    A plain nohup/background process remains in the ironpanel.service cgroup.
    During upgrade the panel is restarted, and systemd can kill every child in
    that cgroup before the upgrade finishes. systemd-run starts the updater in
    its own transient service, so package sync, migrations and service restarts
    complete reliably even while the web panel restarts.
    """
    repo_raw = get_setting('github_repo_url', 'https://github.com/Unknown-sir/ironpanel.git')
    branch_raw = get_setting('github_branch', 'main') or 'main'
    repo = shlex.quote(repo_raw)
    branch = shlex.quote(branch_raw)
    log_file = '/var/log/ironpanel-github-upgrade.log'
    cmd = f'mkdir -p /var/log; echo "==== $(date -Is) queued from panel ==== " >> {shlex.quote(log_file)}; IRONPANEL_GITHUB_REPO={repo} IRONPANEL_GITHUB_BRANCH={branch} bash /opt/ironpanel/scripts/update_from_github.sh'
    if not background:
        p = run_cmd(['bash','-lc', cmd])
        return p.returncode == 0, (p.stdout + p.stderr)[-8000:]

    unit = _github_update_unit_name()
    # Stop a stale/running unit first so the next click really starts a fresh upgrade.
    run_cmd(['bash','-lc', f'systemctl reset-failed {shlex.quote(unit)}.service >/dev/null 2>&1 || true'])
    status = github_update_status()
    if status.get('running'):
        return True, f'GitHub upgrade is already running in {status.get("unit")}. Log: {log_file}'

    systemd_cmd = (
        f'systemd-run --unit={shlex.quote(unit)} --collect --property=Type=oneshot '
        f'--property=KillMode=process --property=TimeoutStartSec=0 /bin/bash -lc {shlex.quote(cmd)}'
    )
    p = run_cmd(['bash','-lc', systemd_cmd])
    if p.returncode == 0:
        set_setting('github_update_last_started_at', datetime.utcnow().isoformat(timespec='seconds'))
        set_setting('github_update_last_unit', unit + '.service')
        return True, f'GitHub upgrade started as systemd unit {unit}.service. Log: {log_file}'

    # Fallback for minimal systems without systemd-run. This may still be killed
    # on restart, but it is better than failing to start at all.
    fallback = f'mkdir -p /var/log; setsid /bin/bash -lc {shlex.quote(cmd)} >/dev/null 2>&1 < /dev/null & echo $!'
    p2 = run_cmd(['bash','-lc', fallback])
    ok = p2.returncode == 0 and bool((p2.stdout or '').strip())
    if ok:
        set_setting('github_update_last_started_at', datetime.utcnow().isoformat(timespec='seconds'))
        return True, f'GitHub upgrade started with fallback PID {(p2.stdout or "").strip()}. Log: {log_file}'
    return False, (p.stderr or p.stdout or p2.stderr or p2.stdout or 'Failed to start GitHub upgrade.')[-2000:]


def github_update_log_tail(lines: int = 160):
    unit = _github_update_unit_name() + '.service'
    cmd = f'(tail -n {int(lines)} /var/log/ironpanel-github-upgrade.log 2>/dev/null; echo; journalctl -u {shlex.quote(unit)} -n 40 --no-pager 2>/dev/null) | tail -n {int(lines)}'
    p = run_cmd(['bash','-lc', cmd])
    return (p.stdout or p.stderr or '').strip()

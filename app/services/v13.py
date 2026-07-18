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


# ---------------- v18.6.10: visible resilient GitHub updater ----------------
_STEP_DIR = Path('/tmp/ironpanel-inline-update')
_STEP_LOG = Path('/var/log/ironpanel-github-upgrade.log')


def _append_step_log(text: str) -> None:
    try:
        _STEP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _STEP_LOG.open('a', encoding='utf-8') as fh:
            fh.write(text.rstrip() + '\n')
    except Exception:
        pass


def _run_step_shell(cmd: str, timeout: int = 1800):
    _append_step_log(f'[{datetime.utcnow().isoformat(timespec="seconds")}] $ {cmd}')
    p = run_cmd(['bash', '-lc', cmd], timeout=timeout)
    out = (p.stdout or '') + (p.stderr or '')
    if out.strip():
        _append_step_log(out[-12000:])
    return p.returncode == 0, out[-12000:]


def _write_step_state(**state):
    _STEP_DIR.mkdir(parents=True, exist_ok=True)
    current = github_update_step_status()
    current.update(state)
    try:
        (_STEP_DIR / 'state.json').write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass
    return current


def github_update_step_status():
    try:
        return json.loads((_STEP_DIR / 'state.json').read_text(encoding='utf-8'))
    except Exception:
        return {'running': False, 'step': 0, 'progress': 0, 'message': 'Ready', 'ok': True, 'done': False}


def _tail_update_log(lines: int = 90) -> str:
    p = run_cmd(['bash', '-lc', f'tail -n {int(lines)} {shlex.quote(str(_STEP_LOG))} 2>/dev/null || true'], timeout=10)
    return (p.stdout or p.stderr or '')[-9000:]


def _pid_running(pid: str) -> bool:
    return bool(pid and pid.isdigit() and run_cmd(['bash', '-lc', f'kill -0 {int(pid)} 2>/dev/null']).returncode == 0)


def _start_visible_upgrade_task() -> tuple[bool, str]:
    _STEP_DIR.mkdir(parents=True, exist_ok=True)
    pid_file = _STEP_DIR / 'upgrade.pid'
    exit_file = _STEP_DIR / 'upgrade.exit'
    running_file = _STEP_DIR / 'upgrade.running'
    done_file = _STEP_DIR / 'upgrade.done'
    for f in (exit_file, done_file):
        try: f.unlink()
        except Exception: pass
    # Do not place any completion marker in this launch command. The launch
    # command itself is logged, so marker text here caused false 100% before.
    cmd = f"""set +e
cd /tmp/ironpanel-inline-update/source || exit 2
echo '[phase] running upgrade.sh in fast/safe mode; panel restart is deferred until exit code 0'
IRONPANEL_SKIP_CORE_REPAIR=1 IRONPANEL_FULL_SERVICE_SYNC=0 IRONPANEL_DEFER_RESTART=1 bash upgrade.sh --github-fast
rc=$?
echo $rc > {shlex.quote(str(exit_file))}
if [ $rc -eq 0 ]; then date -Is > {shlex.quote(str(done_file))}; echo '[phase] upgrade subprocess completed successfully'; fi
rm -f {shlex.quote(str(running_file))}
exit $rc
"""
    runner = f"""set -e
mkdir -p {shlex.quote(str(_STEP_DIR))} /var/log
touch {shlex.quote(str(running_file))}
nohup /bin/bash -lc {shlex.quote(cmd)} >> {shlex.quote(str(_STEP_LOG))} 2>&1 < /dev/null &
echo $! > {shlex.quote(str(pid_file))}
"""
    ok, out = _run_step_shell(runner, timeout=20)
    return ok, out


def github_update_step(step: int):
    # Each HTTP call stays short. Long upgrade work runs as a visible tracked
    # task and the page polls its PID/log, so browsers do not show failed fetch
    # at 45% while the server is still upgrading.
    if step <= 0:
        _STEP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            _STEP_LOG.write_text('', encoding='utf-8')
        except Exception:
            pass
        for name in ('state.json','upgrade.pid','upgrade.exit','upgrade.running'):
            try: (_STEP_DIR / name).unlink()
            except Exception: pass
        _append_step_log('\n==== visible inline update started %s ====' % datetime.utcnow().isoformat(timespec='seconds'))
        _write_step_state(running=True, step=0, progress=3, message='Preparing visible GitHub update', ok=True, done=False)
        ok, out = _run_step_shell('mkdir -p /var/log /var/backups/ironpanel /tmp/ironpanel-inline-update && apt-get update >/dev/null 2>&1 || true && DEBIAN_FRONTEND=noninteractive apt-get install -y git rsync curl ca-certificates >/dev/null 2>&1 || true', timeout=900)
        _write_step_state(running=True, step=1, progress=10, message='Preparation completed' if ok else 'Preparation failed', ok=ok, done=False)
        return {'ok': ok, 'step': 1, 'next_step': 1, 'progress': 10, 'message': 'Preparation completed' if ok else 'Preparation failed', 'log': out[-3000:], 'done': False}
    if step == 1:
        stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        cmd = """set -e
mkdir -p /var/backups/ironpanel
if [ -d /opt/ironpanel ]; then tar -C /opt -czf /var/backups/ironpanel/ironpanel-src-inline-STAMP.tar.gz ironpanel --exclude='ironpanel/.venv' --exclude='ironpanel/__pycache__' --exclude='ironpanel/*.pyc' >/dev/null 2>&1 || true; fi
if [ -d /etc/ironpanel ]; then tar -C /etc -czf /var/backups/ironpanel/ironpanel-etc-inline-STAMP.tar.gz ironpanel >/dev/null 2>&1 || true; fi
""".replace('STAMP', stamp)
        ok, out = _run_step_shell(cmd, timeout=900)
        _write_step_state(running=True, step=2, progress=25, message='Backups created' if ok else 'Backup step failed', ok=ok, done=False)
        return {'ok': ok, 'step': 2, 'next_step': 2, 'progress': 25, 'message': 'Backups created' if ok else 'Backup step failed', 'log': out[-3000:], 'done': False}
    if step == 2:
        repo = shlex.quote(get_setting('github_repo_url', 'https://github.com/Unknown-sir/ironpanel.git'))
        branch = shlex.quote(get_setting('github_branch', 'main') or 'main')
        cmd = f"""set -e
rm -rf /tmp/ironpanel-inline-update/source
git clone --depth 1 --branch {branch} {repo} /tmp/ironpanel-inline-update/source
chmod +x /tmp/ironpanel-inline-update/source/upgrade.sh /tmp/ironpanel-inline-update/source/scripts/*.sh 2>/dev/null || true
"""
        ok, out = _run_step_shell(cmd, timeout=1200)
        _write_step_state(running=True, step=3, progress=45, message='Latest source downloaded' if ok else 'Source download failed', ok=ok, done=False)
        return {'ok': ok, 'step': 3, 'next_step': 3, 'progress': 45, 'message': 'Latest source downloaded' if ok else 'Source download failed', 'log': out[-3000:], 'done': False}
    if step == 3:
        ok, out = _start_visible_upgrade_task()
        if not ok:
            _write_step_state(running=False, step=3, progress=45, message='Could not start upgrade task', ok=False, done=False)
            return {'ok': False, 'step': 3, 'next_step': 3, 'progress': 45, 'message': 'Could not start upgrade task', 'log': out[-5000:], 'done': False}
        _write_step_state(running=True, step=4, progress=50, message='Upgrade task started; keeping page live', ok=True, done=False)
        return {'ok': True, 'step': 4, 'next_step': 4, 'progress': 50, 'message': 'Upgrade task started; keeping page live', 'log': out[-3000:], 'done': False, 'poll_delay_ms': 2500}
    if step == 4:
        pid = ''
        try: pid = (_STEP_DIR / 'upgrade.pid').read_text().strip()
        except Exception: pass
        exit_file = _STEP_DIR / 'upgrade.exit'
        running_file = _STEP_DIR / 'upgrade.running'
        done_file = _STEP_DIR / 'upgrade.done'
        elapsed = 0
        try:
            st = github_update_step_status(); elapsed = int(st.get('upgrade_poll_count', 0) or 0) + 1
        except Exception:
            elapsed = 1
        tail_now = _tail_update_log(120)
        # v19.8.2: completion is trusted only from upgrade.exit=0. Never scan
        # the log for marker text, because the logged launch command can contain
        # marker-like strings and produce a false 100%.
        if exit_file.exists():
            rc = (exit_file.read_text().strip() or '1')
            ok = rc == '0'
            if not ok:
                _write_step_state(running=False, step=4, progress=78, message=f'Upgrade failed with exit code {rc}', ok=False, done=False, upgrade_poll_count=elapsed)
                return {'ok': False, 'step': 4, 'next_step': 4, 'progress': 78, 'message': f'Upgrade failed with exit code {rc}', 'log': _tail_update_log(), 'done': False}
            version = current_version()
            _write_step_state(running=False, step=5, progress=100, message=f'Upgrade completed. Installed version: {version}', ok=True, done=True, upgrade_poll_count=elapsed, completed_marker=done_file.exists())
            return {'ok': True, 'step': 6, 'next_step': 6, 'progress': 100, 'message': f'Upgrade completed. Installed version: {version}', 'log': tail_now, 'done': True, 'restart_required': True}
        if _pid_running(pid) or running_file.exists():
            progress = min(96, 50 + elapsed * 3)
            _write_step_state(running=True, step=4, progress=progress, message='Upgrade is running; waiting for real exit code', ok=True, done=False, upgrade_poll_count=elapsed)
            return {'ok': True, 'step': 4, 'next_step': 4, 'progress': progress, 'message': 'Upgrade is running; waiting for real exit code', 'log': _tail_update_log(50), 'done': False, 'poll_delay_ms': 3000}
        _write_step_state(running=False, step=4, progress=78, message='Upgrade task disappeared before completion', ok=False, done=False, upgrade_poll_count=elapsed)
        return {'ok': False, 'step': 4, 'next_step': 4, 'progress': 78, 'message': 'Upgrade task disappeared before completion', 'log': _tail_update_log(), 'done': False}
    if step == 5:
        state = github_update_step_status()
        if not state.get('done'):
            _write_step_state(running=True, step=4, progress=96, message='Waiting for upgrade.exit before final restart', ok=True, done=False)
            return {'ok': True, 'step': 4, 'next_step': 4, 'progress': 96, 'message': 'Waiting for upgrade.exit before final restart', 'log': _tail_update_log(80), 'done': False, 'poll_delay_ms': 3000}
        cmd = """set -e
systemctl daemon-reload || true
for unit in ironpanel ironpanel-sales-bot ironpanel-admin-bot ironpanel-usage-sync.timer ironpanel-license-heartbeat.timer ironpanel-job-worker.timer ironpanel-sales-reminders.timer ironpanel-admin-report.timer ironpanel-backup-v17.timer ironpanel-safe-backup.timer; do systemctl enable --now "$unit" >/dev/null 2>&1 || true; done
if [ -x /opt/ironpanel/scripts/apply_speed_limits.sh ]; then timeout 60 /opt/ironpanel/scripts/apply_speed_limits.sh --apply >/dev/null 2>&1 || true; fi
if [ -x /opt/ironpanel/scripts/apply_node_gateway.sh ]; then timeout 60 /opt/ironpanel/scripts/apply_node_gateway.sh --apply >/dev/null 2>&1 || true; fi
cat /opt/ironpanel/VERSION 2>/dev/null || true
"""
        ok, out = _run_step_shell(cmd, timeout=180)
        version = current_version()
        _write_step_state(running=False, step=5, progress=100, message=f'Upgrade completed. Installed version: {version}', ok=ok, done=True)
        return {'ok': ok, 'step': 6, 'next_step': 6, 'progress': 100, 'message': f'Upgrade completed. Installed version: {version}', 'log': out[-5000:], 'done': True, 'restart_required': True}
    return {'ok': True, 'step': step, 'next_step': step, 'progress': 100, 'message': 'Already completed', 'done': True, 'restart_required': True}


def github_update_schedule_restart():
    state = github_update_step_status()
    exit_file = _STEP_DIR / 'upgrade.exit'
    rc = ''
    try:
        rc = exit_file.read_text().strip()
    except Exception:
        pass
    if not state.get('done') or rc != '0':
        return {'ok': False, 'message': 'Upgrade is not finished yet. Restart is blocked until upgrade.exit=0.', 'log': _tail_update_log(80)}
    cmd = "(sleep 1; systemctl daemon-reload >/dev/null 2>&1 || true; systemctl enable --now ironpanel-speed-limits.service >/dev/null 2>&1 || true; if [ -x /opt/ironpanel/scripts/apply_speed_limits.sh ]; then timeout 60 /opt/ironpanel/scripts/apply_speed_limits.sh --apply >/dev/null 2>&1 || true; fi; if [ -x /opt/ironpanel/scripts/apply_node_gateway.sh ]; then timeout 60 /opt/ironpanel/scripts/apply_node_gateway.sh --apply >/dev/null 2>&1 || true; fi; systemctl restart ironpanel >/dev/null 2>&1 || true; systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true; systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true) >/dev/null 2>&1 &"
    ok, out = _run_step_shell(cmd, timeout=5)
    return {'ok': ok, 'message': 'Upgrade completed at 100%. Panel restart scheduled. Refresh the page in a few seconds.', 'log': out[-1000:]}

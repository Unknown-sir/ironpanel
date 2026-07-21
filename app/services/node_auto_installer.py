import io
import json
import os
import shlex
import socket
import time
from datetime import datetime
from pathlib import Path

from flask import current_app

from ..core.extensions import db
from ..core.models import Node, RemoteJob
from .license import current_license_type
from .v17 import node_install_command
from .node_gateway import queue_full_node_sync, queue_node_health_check, apply_node_gateway_runtime

KEY_PATH = Path('/etc/ironpanel/node_credential.key')


def node_auto_installer_allowed():
    """Node Auto SSH Installer is limited to Pro/Admin plans."""
    return (current_license_type() or '').strip().lower() in ('pro', 'admin')


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except Exception as exc:
        raise RuntimeError('cryptography package is required for encrypted SSH credential storage') from exc
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not KEY_PATH.exists():
        KEY_PATH.write_bytes(Fernet.generate_key())
        try:
            os.chmod(KEY_PATH, 0o600)
        except Exception:
            pass
    key = KEY_PATH.read_bytes().strip()
    return Fernet(key)


def encrypt_secret(value):
    value = str(value or '')
    if not value:
        return ''
    return _fernet().encrypt(value.encode('utf-8')).decode('ascii')


def decrypt_secret(value):
    value = str(value or '')
    if not value:
        return ''
    try:
        return _fernet().decrypt(value.encode('ascii')).decode('utf-8')
    except Exception:
        return ''


def node_has_saved_ssh_credentials(node):
    return bool(getattr(node, 'ssh_credentials_saved', False) and getattr(node, 'ssh_username', '') and (getattr(node, 'ssh_password_enc', '') or getattr(node, 'ssh_key_enc', '')))


def save_node_ssh_credentials(node, form, *, commit=True):
    """Store SSH credentials encrypted at rest, never as hashes.

    Hashing cannot be used for SSH login because the panel must recover the
    original password/key in order to open the SSH session. Fernet encryption is
    used instead, with the local key kept in /etc/ironpanel/node_credential.key.
    """
    node.ssh_host = (form.get('ssh_host') or node.host or '').strip()
    try:
        node.ssh_port = int(form.get('ssh_port') or getattr(node, 'ssh_port', 22) or 22)
    except Exception:
        node.ssh_port = 22
    node.ssh_username = (form.get('ssh_username') or getattr(node, 'ssh_username', '') or 'root').strip()
    method = (form.get('ssh_auth_method') or getattr(node, 'ssh_auth_method', '') or 'password').strip().lower()
    node.ssh_auth_method = 'key' if method in ('key', 'ssh_key', 'private_key') else 'password'
    password = form.get('ssh_password') or ''
    key_text = form.get('ssh_private_key') or ''
    passphrase = form.get('ssh_key_passphrase') or ''
    sudo_password = form.get('ssh_sudo_password') or ''

    # Empty fields preserve existing saved values so admins can update only one field.
    if password:
        node.ssh_password_enc = encrypt_secret(password)
    if key_text:
        node.ssh_key_enc = encrypt_secret(key_text.replace('\r\n', '\n').strip() + '\n')
    if passphrase:
        node.ssh_key_passphrase_enc = encrypt_secret(passphrase)
    if sudo_password:
        node.ssh_sudo_password_enc = encrypt_secret(sudo_password)

    # Clear the non-selected secret to avoid accidentally using stale auth data.
    if node.ssh_auth_method == 'password' and password:
        node.ssh_key_enc = ''
        node.ssh_key_passphrase_enc = ''
    if node.ssh_auth_method == 'key' and key_text:
        node.ssh_password_enc = ''

    node.ssh_credentials_saved = True
    if commit:
        db.session.commit()
    return node


def clear_node_ssh_credentials(node, *, commit=True):
    node.ssh_password_enc = ''
    node.ssh_key_enc = ''
    node.ssh_key_passphrase_enc = ''
    node.ssh_sudo_password_enc = ''
    node.ssh_credentials_saved = False
    node.auto_install_status = 'credentials-cleared'
    if commit:
        db.session.commit()
    return node


def _load_private_key(key_text, passphrase=''):
    import paramiko
    last_error = None
    for key_cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey, paramiko.DSSKey):
        try:
            return key_cls.from_private_key(io.StringIO(key_text), password=passphrase or None)
        except Exception as exc:
            last_error = exc
    raise RuntimeError('invalid SSH private key or passphrase: %s' % (last_error or 'unknown error'))


def _connect(node):
    try:
        import paramiko
    except Exception as exc:
        raise RuntimeError('paramiko package is required for Auto SSH Installer') from exc
    host = (getattr(node, 'ssh_host', '') or node.host or '').strip()
    port = int(getattr(node, 'ssh_port', 22) or 22)
    username = (getattr(node, 'ssh_username', '') or 'root').strip()
    method = (getattr(node, 'ssh_auth_method', '') or 'password').strip().lower()
    if not host or not username:
        raise RuntimeError('SSH host and username are required')
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = dict(hostname=host, port=port, username=username, timeout=20, banner_timeout=20, auth_timeout=20, look_for_keys=False, allow_agent=False)
    if method == 'key':
        key_text = decrypt_secret(getattr(node, 'ssh_key_enc', '') or '')
        if not key_text.strip():
            raise RuntimeError('SSH private key is not saved for this node')
        kwargs['pkey'] = _load_private_key(key_text, decrypt_secret(getattr(node, 'ssh_key_passphrase_enc', '') or ''))
    else:
        password = decrypt_secret(getattr(node, 'ssh_password_enc', '') or '')
        if not password:
            raise RuntimeError('SSH password is not saved for this node')
        kwargs['password'] = password
    client.connect(**kwargs)
    return client


def _exec(client, command, *, timeout=900):
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    out_chunks = []
    start = time.time()
    while True:
        if stdout.channel.recv_ready():
            out_chunks.append(stdout.channel.recv(65536).decode('utf-8', 'replace'))
        if stdout.channel.recv_stderr_ready():
            out_chunks.append(stdout.channel.recv_stderr(65536).decode('utf-8', 'replace'))
        if stdout.channel.exit_status_ready():
            break
        if time.time() - start > timeout:
            try:
                stdout.channel.close()
            except Exception:
                pass
            raise RuntimeError('SSH command timeout')
        time.sleep(0.25)
    rc = stdout.channel.recv_exit_status()
    rest = stdout.read().decode('utf-8', 'replace') + stderr.read().decode('utf-8', 'replace')
    if rest:
        out_chunks.append(rest)
    return rc, ''.join(out_chunks)


def _sudo_or_root_command(node, script):
    username = (getattr(node, 'ssh_username', '') or 'root').strip()
    quoted = shlex.quote(script)
    if username == 'root':
        return f'bash -lc {quoted}'
    sudo_password = decrypt_secret(getattr(node, 'ssh_sudo_password_enc', '') or '')
    if sudo_password:
        return f"printf '%s\\n' {shlex.quote(sudo_password)} | sudo -S bash -lc {quoted}"
    return f'sudo -n bash -lc {quoted}'


def _redact(text):
    if not text:
        return ''
    # Avoid leaking tokens and obvious secrets in logs.
    text = str(text)
    import re
    text = re.sub(r'(--token\s+)(\S+)', r'\1[redacted]', text)
    text = re.sub(r'(--password\s+)(\S+)', r'\1[redacted]', text, flags=re.I)
    return text


def build_install_script(node, request_base_url=''):
    base = node_install_command(node, request_base_url)
    return '\n'.join([
        'set -e',
        'export DEBIAN_FRONTEND=noninteractive',
        base,
        'systemctl enable --now ironpanel-node',
        'systemctl is-active --quiet ironpanel-node',
        'test -s /etc/ironpanel-node/node.env',
        'systemctl status ironpanel-node --no-pager || true',
        'journalctl -u ironpanel-node -n 80 --no-pager || true',
    ])


def run_auto_node_install(node, request_base_url='', *, save_log=True, job=None):
    if not node_auto_installer_allowed():
        raise PermissionError('Node Auto Installer فقط برای لایسنس Pro و Admin فعال است.')
    log_lines = []
    started = datetime.utcnow()
    node.auto_install_status = 'running'
    node.last_auto_install_at = started
    db.session.commit()
    if job is None:
        job = RemoteJob(node_id=node.id, action='auto_ssh_install', status='running', payload_json=json.dumps({'node': node.name, 'host': node.host}, ensure_ascii=False))
        db.session.add(job)
    else:
        job.status = 'running'
    db.session.commit()
    client = None
    ok = False
    try:
        log_lines.append(f'[auto-install] starting node={node.name} ssh={(getattr(node, "ssh_host", "") or node.host)}:{getattr(node, "ssh_port", 22) or 22}')
        client = _connect(node)
        log_lines.append('[auto-install] SSH connected')
        rc, out = _exec(client, 'uname -a; (cat /etc/os-release 2>/dev/null || true); id', timeout=60)
        log_lines.append('[auto-install] OS probe:\n' + out[-3000:])
        script = build_install_script(node, request_base_url)
        cmd = _sudo_or_root_command(node, script)
        rc, out = _exec(client, cmd, timeout=1800)
        log_lines.append('[auto-install] install output:\n' + _redact(out)[-16000:])
        if rc != 0:
            raise RuntimeError(f'install command failed with exit code {rc}')
        rc, verify_out = _exec(client, 'systemctl is-active ironpanel-node; test -s /etc/ironpanel-node/node.env; journalctl -u ironpanel-node -n 30 --no-pager', timeout=90)
        log_lines.append('[auto-install] service verification:\n' + _redact(verify_out)[-6000:])
        first_lines = [line.strip() for line in verify_out.splitlines()[:3]]
        if rc != 0 or 'active' not in first_lines:
            raise RuntimeError('ironpanel-node service did not become active after installation')
        protocols = [x for x in (node.protocols or '').split(',') if x]
        stop_rc, stop_out = _exec(client, _sudo_or_root_command(node, 'systemctl stop ironpanel-node >/dev/null 2>&1 || true'), timeout=45)
        log_lines.append('[auto-install] agent paused for deterministic initial sync')
        latest = RemoteJob.query.order_by(RemoteJob.id.desc()).first()
        sync_after_id = int(latest.id if latest else 0)
        queued = queue_full_node_sync(node.id, protocols, reason='auto-ssh-install', force=True)
        queue_node_health_check(node.id)
        log_lines.append(f'[auto-install] queued full node sync jobs: {queued}')
        # Drain the just-created jobs synchronously over the verified SSH session.
        # Stop the background service briefly so it cannot race with this one-shot run.
        drain_cmd = (
            "set -a; . /etc/ironpanel-node/node.env; set +a; "
            "/opt/ironpanel-node/.venv/bin/python /opt/ironpanel-node/node_agent.py "
            "--master \"$IRONPANEL_NODE_MASTER\" --token \"$IRONPANEL_NODE_TOKEN\" --once; "
            "rc=$?; systemctl start ironpanel-node >/dev/null 2>&1 || true; exit $rc"
        )
        sync_rc, sync_out = _exec(client, _sudo_or_root_command(node, drain_cmd), timeout=1500)
        log_lines.append('[auto-install] initial node sync output:\n' + _redact(sync_out)[-16000:])
        db.session.expire_all()
        sync_jobs=(RemoteJob.query
                   .filter(RemoteJob.node_id==node.id, RemoteJob.id>sync_after_id)
                   .order_by(RemoteJob.id.asc()).all())
        failed=[j for j in sync_jobs if j.status=='failed']
        pending=[j for j in sync_jobs if j.status in ('queued','running')]
        if sync_rc != 0 or failed or pending:
            detail='; '.join(f'{j.action}:{j.status}' for j in (failed+pending)) or f'agent exit={sync_rc}'
            raise RuntimeError('initial node core/config/user verification failed: ' + detail)
        if not sync_jobs:
            raise RuntimeError('initial node sync returned without processing queued jobs')
        try:
            apply_node_gateway_runtime()
        except Exception as exc:
            log_lines.append('[auto-install] gateway apply warning: ' + str(exc))
        ok = True
        node.auto_install_status = 'done'
        node.sync_status = 'queued'
        node.health = 'installing'
        message = 'Node Auto Installer finished successfully'
    except Exception as exc:
        node.auto_install_status = 'failed'
        node.last_error = str(exc)[:5000]
        message = 'Node Auto Installer failed: ' + str(exc)
        log_lines.append('[auto-install] ERROR: ' + str(exc))
    finally:
        if client:
            try:
                _exec(client, _sudo_or_root_command(node, 'systemctl start ironpanel-node >/dev/null 2>&1 || true'), timeout=45)
            except Exception:
                pass
            try:
                client.close()
            except Exception:
                pass
        log_text = '\n'.join(log_lines)[-20000:]
        if save_log:
            node.last_install_log = log_text
        job.status = 'done' if ok else 'failed'
        job.output = log_text
        db.session.commit()
    return {'ok': ok, 'message': message, 'log': '\n'.join(log_lines)}


def queue_auto_node_install(node, request_base_url='', reason='manual'):
    """Queue SSH installation so the web panel never blocks or goes down.

    v19.9.8: auto install used to run inside the Flask request. SSH/core
    installs may take minutes and can make gunicorn workers look frozen. Now the
    Nodes page stores credentials, creates this job, and the job-worker executes
    it safely in the background.
    """
    payload={'request_base_url': request_base_url or '', 'reason': reason}
    job=RemoteJob(node_id=node.id, action='auto_ssh_install', status='queued', payload_json=json.dumps(payload, ensure_ascii=False), output='')
    db.session.add(job)
    node.auto_install_status='queued'
    node.sync_status='queued'
    db.session.commit()
    return job


def run_auto_node_install_for_job(job):
    node=Node.query.get(int(job.node_id or 0))
    if not node:
        job.status='failed'; job.output='node not found'; db.session.commit(); return False, job.output
    try:
        payload=json.loads(getattr(job, 'payload_json', '') or '{}')
    except Exception:
        payload={}
    job.status='running'; db.session.commit()
    result=run_auto_node_install(node, payload.get('request_base_url') or '', job=job)
    job.status='done' if result.get('ok') else 'failed'
    job.output=(result.get('log') or result.get('message') or '')[-20000:]
    db.session.commit()
    return bool(result.get('ok')), job.output

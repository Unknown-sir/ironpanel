"""Automatic Let's Encrypt SSL provisioning and runtime wiring for IronPanel.

The module is intentionally conservative about shell input: domains are
normalized and validated before being passed to certbot or written to service
configuration.  It works as a best-effort system integration layer; failures are
returned to the web UI instead of raising unhandled Flask errors.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Dict, Any

from flask import current_app

from ..core.extensions import db
from ..core.models import AppSetting, DomainRecord, VpnUser
from .provisioning import (
    active_protocols,
    apply_runtime_configs,
    get_public_host,
    get_setting,
    run_cmd,
    set_setting,
    sync_all_users,
    user_access_status,
)

DOMAIN_RE = re.compile(
    r'^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)'
    r'(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$'
)
IP_RE = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$|:')

CERTBOT_BROKEN_MARKERS = (
    'X509_V_FLAG_NOTIFY_POLICY',
    'AttributeError: module',
    'from OpenSSL import crypto',
    'josepy',
    'cryptography',
    'DistributionNotFound',
    'pkg_resources.ContextualVersionConflict',
)


def normalize_domain(value: str) -> str:
    domain = (value or '').strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0].split('?')[0].split('#')[0]
    if ':' in domain and not domain.startswith('['):
        domain = domain.split(':', 1)[0]
    return domain.strip().strip('.')


def valid_domain(value: str) -> bool:
    domain = normalize_domain(value)
    return bool(domain and DOMAIN_RE.fullmatch(domain) and not IP_RE.search(domain))


def default_ssl_domain() -> str:
    candidates = [
        get_setting('ssl_domain', ''),
        get_setting('xray_domain', ''),
        get_setting('tunnel_host', ''),
        get_setting('public_host', ''),
        get_public_host(),
    ]
    for item in candidates:
        domain = normalize_domain(item or '')
        if valid_domain(domain):
            return domain
    return normalize_domain(candidates[-1] or '')


def _setting(key: str, default: str = '') -> str:
    return get_setting(key, default) or default


def _cert_paths_for(domain: str) -> Dict[str, str]:
    domain = normalize_domain(domain or default_ssl_domain())
    stored_root = Path(_setting('ssl_storage_root', '/etc/ironpanel/ssl')) / domain if domain else Path(_setting('ssl_storage_root', '/etc/ironpanel/ssl'))
    live_root = Path('/etc/letsencrypt/live') / domain if domain else Path('/etc/letsencrypt/live')
    if normalize_domain(_setting('ssl_domain', '')) == domain:
        cert_file = _setting('ssl_cert_file', str(stored_root / 'fullchain.pem'))
        key_file = _setting('ssl_key_file', str(stored_root / 'privkey.pem'))
    else:
        cert_file = str(stored_root / 'fullchain.pem')
        key_file = str(stored_root / 'privkey.pem')
    return {
        'domain': domain,
        'stored_root': str(stored_root),
        'live_fullchain': str(live_root / 'fullchain.pem'),
        'live_privkey': str(live_root / 'privkey.pem'),
        'cert_file': cert_file,
        'key_file': key_file,
    }


def _file_ready(path: str) -> bool:
    try:
        return bool(path and Path(path).exists())
    except Exception:
        return False


def _service_ssl_matrix(paths: Dict[str, str]) -> list[Dict[str, str]]:
    cert = paths['cert_file']
    key = paths['key_file']
    oc_cert = _setting('ocserv_tls_cert_file', '/etc/ocserv/certs/server-cert.pem')
    oc_key = _setting('ocserv_tls_key_file', '/etc/ocserv/certs/server-key.pem')
    hy_cert = _setting('hysteria2_tls_cert_file', cert)
    hy_key = _setting('hysteria2_tls_key_file', key)
    xr_cert = _setting('xray_tls_cert_file', cert)
    xr_key = _setting('xray_tls_key_file', key)
    xray_profile = _setting('xray_profile_type', 'vless-reality')
    xray_security = 'unknown'
    try:
        from .xray import XRAY_PROFILE_TYPES
        xray_security = XRAY_PROFILE_TYPES.get(xray_profile, {}).get('security', 'unknown')
    except Exception:
        pass

    def ready_pair(c: str, k: str) -> bool:
        return _file_ready(c) and _file_ready(k)

    xray_tls_ready = ready_pair(xr_cert, xr_key)
    xray_needs_tls = xray_security == 'tls'
    return [
        {
            'name': 'IronPanel Web Panel',
            'status': 'فعال' if _setting('ssl_panel_enabled', '0') == '1' and ready_pair(cert, key) else 'غیرفعال',
            'detail': f'{cert} | {key}',
            'needs_ssl': 'yes',
        },
        {
            'name': 'Ocserv / AnyConnect',
            'status': 'فعال' if ready_pair(oc_cert, oc_key) else 'در انتظار SSL',
            'detail': f'{oc_cert} | {oc_key}',
            'needs_ssl': 'yes',
        },
        {
            'name': 'Hysteria2',
            'status': 'فعال' if ready_pair(hy_cert, hy_key) else 'در انتظار SSL',
            'detail': f'{hy_cert} | {hy_key}',
            'needs_ssl': 'yes',
        },
        {
            'name': 'Xray TLS profiles',
            'status': ('فعال' if xray_tls_ready else 'در انتظار SSL') if xray_needs_tls else 'لازم نیست برای پروفایل فعلی',
            'detail': f'profile={xray_profile}, security={xray_security}, cert={xr_cert}, key={xr_key}',
            'needs_ssl': 'conditional',
        },
        {
            'name': 'OpenVPN',
            'status': 'SSL دامنه‌ای لازم ندارد',
            'detail': 'از CA و certificate داخلی خودش استفاده می‌کند، نه Let’s Encrypt دامنه پنل.',
            'needs_ssl': 'no',
        },
        {
            'name': 'WireGuard',
            'status': 'SSL دامنه‌ای لازم ندارد',
            'detail': 'بر پایه public/private key کار می‌کند و TLS certificate ندارد.',
            'needs_ssl': 'no',
        },
        {
            'name': 'L2TP/IPsec',
            'status': 'SSL دامنه‌ای لازم ندارد',
            'detail': 'در این پنل با IPsec/PSK تنظیم می‌شود و به Let’s Encrypt وصل نمی‌شود.',
            'needs_ssl': 'no',
        },
        {
            'name': 'PPTP',
            'status': 'SSL دامنه‌ای ندارد',
            'detail': 'PPTP مکانیزم TLS/SSL دامنه‌ای ندارد؛ برای استفاده عمومی امن‌تر است غیرفعال یا محدود شود.',
            'needs_ssl': 'no',
        },
    ]


def ssl_status(domain: str | None = None) -> Dict[str, Any]:
    paths = _cert_paths_for(domain or default_ssl_domain())
    cert_exists = Path(paths['cert_file']).exists()
    key_exists = Path(paths['key_file']).exists()
    live_exists = Path(paths['live_fullchain']).exists() and Path(paths['live_privkey']).exists()
    matrix = _service_ssl_matrix(paths)
    return {
        **paths,
        'enabled': _setting('ssl_enabled', '0') == '1' and cert_exists and key_exists,
        'cert_exists': cert_exists,
        'key_exists': key_exists,
        'live_exists': live_exists,
        'panel_tls': bool(_setting('ssl_panel_enabled', '0') == '1' and cert_exists and key_exists),
        'xray_profile_type': _setting('xray_profile_type', ''),
        'protocols': ', '.join(active_protocols()),
        'service_ssl_matrix': matrix,
        'certbot_path': _setting('ssl_certbot_path', ''),
        'last_result': _setting('ssl_last_result', ''),
        'last_error': _setting('ssl_last_error', ''),
    }


def _copy_certificate_files(domain: str) -> Dict[str, str]:
    paths = _cert_paths_for(domain)
    live_cert = Path(paths['live_fullchain'])
    live_key = Path(paths['live_privkey'])
    if not live_cert.exists() or not live_key.exists():
        raise RuntimeError('Let’s Encrypt certificate files were not found after certbot finished.')

    target_root = Path(paths['stored_root'])
    target_root.mkdir(parents=True, exist_ok=True)
    target_cert = target_root / 'fullchain.pem'
    target_key = target_root / 'privkey.pem'
    shutil.copy2(live_cert, target_cert)
    shutil.copy2(live_key, target_key)
    target_cert.chmod(0o644)
    target_key.chmod(0o600)
    return {'cert': str(target_cert), 'key': str(target_key)}


def _copy_for_ocserv(cert: str, key: str) -> None:
    oc_dir = Path('/etc/ocserv/certs')
    oc_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cert, oc_dir / 'server-cert.pem')
    shutil.copy2(key, oc_dir / 'server-key.pem')
    (oc_dir / 'server-cert.pem').chmod(0o644)
    (oc_dir / 'server-key.pem').chmod(0o600)


def _write_env_values(env_path: Path, values: Dict[str, str]) -> None:
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding='utf-8', errors='ignore').splitlines()
    keys = set(values)
    kept = [line for line in lines if not any(line.startswith(k + '=') for k in keys)]
    kept.extend(f'{k}={v}' for k, v in values.items())
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text('\n'.join(kept).rstrip() + '\n', encoding='utf-8')
    try:
        env_path.chmod(0o600)
    except Exception:
        pass


def _install_panel_tls_dropin(cert: str, key: str) -> None:
    # The main installer also writes this optional-TLS ExecStart.  The drop-in
    # upgrades existing installations without requiring users to reinstall.
    dropin_dir = Path('/etc/systemd/system/ironpanel.service.d')
    dropin_dir.mkdir(parents=True, exist_ok=True)
    dropin = dropin_dir / 'ssl.conf'
    dropin.write_text(f"""[Service]\nEnvironment=IRONPANEL_SSL_CERT={cert}\nEnvironment=IRONPANEL_SSL_KEY={key}\nExecStart=\nExecStart=/bin/bash -lc 'CERT="${{IRONPANEL_SSL_CERT:-}}"; KEY="${{IRONPANEL_SSL_KEY:-}}"; SSL_ARGS=""; if [ -n "$CERT" ] && [ -n "$KEY" ] && [ -f "$CERT" ] && [ -f "$KEY" ]; then SSL_ARGS="--certfile $CERT --keyfile $KEY"; fi; exec /opt/ironpanel/.venv/bin/gunicorn -k gthread -w 2 -b 0.0.0.0:${{IRONPANEL_PORT}} $SSL_ARGS run:app'\n""", encoding='utf-8')
    run_cmd(['systemctl', 'daemon-reload'])


def _install_renew_hook(domain: str, cert: str, key: str, certbot_bin: str = '') -> None:
    hook_dir = Path('/etc/letsencrypt/renewal-hooks/deploy')
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook = hook_dir / 'ironpanel-ssl.sh'
    hook.write_text(f"""#!/usr/bin/env bash\nset -e\nDOMAIN="{domain}"\nSRC="/etc/letsencrypt/live/$DOMAIN"\nDST="{Path(cert).parent}"\nif [[ -f "$SRC/fullchain.pem" && -f "$SRC/privkey.pem" ]]; then\n  mkdir -p "$DST" /etc/ocserv/certs\n  cp -f "$SRC/fullchain.pem" "$DST/fullchain.pem"\n  cp -f "$SRC/privkey.pem" "$DST/privkey.pem"\n  chmod 644 "$DST/fullchain.pem"\n  chmod 600 "$DST/privkey.pem"\n  cp -f "$DST/fullchain.pem" /etc/ocserv/certs/server-cert.pem 2>/dev/null || true\n  cp -f "$DST/privkey.pem" /etc/ocserv/certs/server-key.pem 2>/dev/null || true\n  chmod 600 /etc/ocserv/certs/server-key.pem 2>/dev/null || true\n  systemctl restart ocserv 2>/dev/null || true\n  systemctl restart xray 2>/dev/null || true\n  systemctl restart hysteria-server 2>/dev/null || true\n  systemctl restart ironpanel 2>/dev/null || true\nfi\n""", encoding='utf-8')
    hook.chmod(0o755)
    if certbot_bin:
        set_setting('ssl_certbot_path', certbot_bin)


def _certbot_candidates() -> list[str]:
    """Return certbot binaries in safe priority order.

    Snap certbot is intentionally preferred because it is isolated from the
    system Python packages. That avoids the common pyOpenSSL/cryptography crash:
    "X509_V_FLAG_NOTIFY_POLICY".
    """
    candidates: list[str] = []
    stored = _setting('ssl_certbot_path', '')
    for item in (stored, '/snap/bin/certbot', '/usr/local/bin/certbot', '/opt/ironpanel-certbot-venv/bin/certbot', '/usr/bin/certbot', shutil.which('certbot') or ''):
        if item and item not in candidates:
            candidates.append(item)
    return candidates


def _run_certbot_binary(binary: str, args: list[str]):
    if '/' in binary:
        return run_cmd([binary, *args])
    return run_cmd(['bash', '-lc', shlex.quote(binary) + ' ' + ' '.join(shlex.quote(a) for a in args)])


def _test_certbot(binary: str) -> tuple[bool, str]:
    try:
        if '/' in binary and not Path(binary).exists():
            return False, f'{binary} not found'
        p = _run_certbot_binary(binary, ['--version'])
        out = ((p.stdout or '') + '\n' + (p.stderr or '')).strip()
        broken = any(marker in out for marker in CERTBOT_BROKEN_MARKERS)
        return p.returncode == 0 and not broken, out
    except Exception as exc:
        return False, str(exc)


def _install_snap_certbot() -> str:
    cmd = r"""
set +e
LOG=/tmp/ironpanel-certbot-snap.log
: > "$LOG"
apt-get update >>"$LOG" 2>&1
DEBIAN_FRONTEND=noninteractive apt-get install -y snapd ca-certificates >>"$LOG" 2>&1
systemctl enable --now snapd.socket >>"$LOG" 2>&1 || true
systemctl start snapd.service >>"$LOG" 2>&1 || true
if command -v snap >/dev/null 2>&1; then
  snap install core >>"$LOG" 2>&1 || snap refresh core >>"$LOG" 2>&1 || true
  snap install --classic certbot >>"$LOG" 2>&1 || true
  ln -sf /snap/bin/certbot /usr/local/bin/certbot >>"$LOG" 2>&1 || true
fi
cat "$LOG"
"""
    p = run_cmd(['bash', '-lc', cmd])
    return ((p.stdout or '') + '\n' + (p.stderr or '')).strip()


def _repair_apt_certbot() -> str:
    cmd = r"""
set +e
LOG=/tmp/ironpanel-certbot-apt-repair.log
: > "$LOG"
apt-get update >>"$LOG" 2>&1
DEBIAN_FRONTEND=noninteractive apt-get install -y --reinstall certbot python3-acme python3-josepy python3-openssl python3-cryptography >>"$LOG" 2>&1 || \
DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-openssl python3-cryptography >>"$LOG" 2>&1 || true
python3 - <<'PYCHECK' >>"$LOG" 2>&1 || true
from OpenSSL import crypto
print('pyOpenSSL import ok')
PYCHECK
cat "$LOG"
"""
    p = run_cmd(['bash', '-lc', cmd])
    return ((p.stdout or '') + '\n' + (p.stderr or '')).strip()


def _install_venv_certbot() -> str:
    cmd = r"""
set +e
LOG=/tmp/ironpanel-certbot-venv.log
: > "$LOG"
apt-get update >>"$LOG" 2>&1
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip ca-certificates >>"$LOG" 2>&1
python3 -m venv /opt/ironpanel-certbot-venv >>"$LOG" 2>&1
/opt/ironpanel-certbot-venv/bin/pip install --upgrade pip wheel >>"$LOG" 2>&1
/opt/ironpanel-certbot-venv/bin/pip install 'certbot>=2,<4' >>"$LOG" 2>&1
ln -sf /opt/ironpanel-certbot-venv/bin/certbot /usr/local/bin/certbot >>"$LOG" 2>&1 || true
cat "$LOG"
"""
    p = run_cmd(['bash', '-lc', cmd])
    return ((p.stdout or '') + '\n' + (p.stderr or '')).strip()


def _certbot_error_hint(output: str) -> str:
    if 'X509_V_FLAG_NOTIFY_POLICY' in output or 'from OpenSSL import crypto' in output:
        return ('\n\nتشخیص پنل: certbot سیستم به‌خاطر ناسازگاری pyOpenSSL/cryptography خراب است. '
                'نسخه 18.4.3 ابتدا Certbot Snap را استفاده می‌کند و در صورت نیاز certbot جداگانه داخل venv می‌سازد تا به کتابخانه‌های خراب سیستم وابسته نباشد.')
    return ''


def _ensure_certbot_installed() -> tuple[bool, str, str]:
    logs: list[str] = []

    for binary in _certbot_candidates():
        ok, out = _test_certbot(binary)
        logs.append(f'check {binary}: {out[-500:]}')
        if ok:
            set_setting('ssl_certbot_path', binary)
            return True, binary, f'certbot ready: {binary}'

    logs.append('Installing isolated Snap certbot...')
    logs.append(_install_snap_certbot()[-1500:])
    for binary in ('/snap/bin/certbot', '/usr/local/bin/certbot'):
        ok, out = _test_certbot(binary)
        logs.append(f'check {binary}: {out[-500:]}')
        if ok:
            set_setting('ssl_certbot_path', binary)
            return True, binary, f'certbot ready: {binary}'

    logs.append('Repairing apt certbot...')
    logs.append(_repair_apt_certbot()[-1500:])
    for binary in _certbot_candidates():
        ok, out = _test_certbot(binary)
        logs.append(f'check {binary}: {out[-500:]}')
        if ok:
            set_setting('ssl_certbot_path', binary)
            return True, binary, f'certbot ready: {binary}'

    logs.append('Installing certbot in IronPanel venv...')
    logs.append(_install_venv_certbot()[-1500:])
    for binary in ('/opt/ironpanel-certbot-venv/bin/certbot', '/usr/local/bin/certbot'):
        ok, out = _test_certbot(binary)
        logs.append(f'check {binary}: {out[-500:]}')
        if ok:
            set_setting('ssl_certbot_path', binary)
            return True, binary, f'certbot ready: {binary}'

    joined = '\n'.join(logs)[-3500:]
    return False, '', joined + _certbot_error_hint(joined)


def _stop_conflicting_web_servers() -> list[str]:
    stopped = []
    for service in ('nginx', 'apache2'):
        if run_cmd(['systemctl', 'is-active', '--quiet', service]).returncode == 0:
            run_cmd(['systemctl', 'stop', service])
            stopped.append(service)
    return stopped


def _restart_services(services: list[str]) -> None:
    for service in services:
        run_cmd(['systemctl', 'start', service])


def issue_and_apply_ssl(domain: str, email: str = '', force_xray_tls: bool = False) -> Dict[str, Any]:
    domain = normalize_domain(domain)
    if not valid_domain(domain):
        return {'ok': False, 'domain': domain, 'message': 'دامنه معتبر نیست. باید یک FQDN مثل vpn.example.com باشد، نه IP یا localhost.'}

    ok_install, certbot_bin, install_msg = _ensure_certbot_installed()
    if not ok_install:
        set_setting('ssl_last_error', install_msg[-2000:])
        return {'ok': False, 'domain': domain, 'message': 'نصب/ترمیم certbot ناموفق بود: ' + install_msg[-1200:]}

    mail = (email or '').strip() or f'admin@{domain}'
    stopped = _stop_conflicting_web_servers()
    try:
        certbot_args = [
            'certonly', '--standalone', '--preferred-challenges', 'http',
            '-d', domain, '--non-interactive', '--agree-tos', '--keep-until-expiring',
            '-m', mail,
        ]
        p = _run_certbot_binary(certbot_bin, certbot_args)
    finally:
        _restart_services(stopped)

    output = ((p.stdout or '') + '\n' + (p.stderr or '')).strip()
    paths = _cert_paths_for(domain)
    if p.returncode != 0 and not (Path(paths['live_fullchain']).exists() and Path(paths['live_privkey']).exists()):
        set_setting('ssl_last_error', output[-2000:])
        return {'ok': False, 'domain': domain, 'message': 'دریافت SSL ناموفق بود: ' + (output[-1200:] or 'certbot error') + _certbot_error_hint(output)}

    copied = _copy_certificate_files(domain)
    cert = copied['cert']
    key = copied['key']
    _copy_for_ocserv(cert, key)
    _install_panel_tls_dropin(cert, key)

    env_path = Path(current_app.config.get('CONFIG_ROOT', '/etc/ironpanel')) / 'ironpanel.env'
    _write_env_values(env_path, {
        'IRONPANEL_SSL_CERT': cert,
        'IRONPANEL_SSL_KEY': key,
        'IRONPANEL_PUBLIC_HOST': domain,
        'IRONPANEL_TUNNEL_HOST': domain,
    })

    # Save all runtime settings in the DB so regenerated configs use the same certificate.
    for k, v in {
        'ssl_enabled': '1',
        'ssl_panel_enabled': '1',
        'ssl_domain': domain,
        'ssl_cert_file': cert,
        'ssl_key_file': key,
        'ssl_storage_root': str(Path(cert).parent.parent),
        'ssl_certbot_path': certbot_bin,
        'public_host': domain,
        'tunnel_host': domain,
        'xray_domain': domain,
        'xray_tls_cert_file': cert,
        'xray_tls_key_file': key,
        'xray_ws_host': domain,
        'hysteria2_tls_cert_file': cert,
        'hysteria2_tls_key_file': key,
        'ocserv_tls_cert_file': '/etc/ocserv/certs/server-cert.pem',
        'ocserv_tls_key_file': '/etc/ocserv/certs/server-key.pem',
    }.items():
        set_setting(k, v)

    if force_xray_tls and 'xray' in active_protocols():
        set_setting('xray_profile_type', 'vless-ws-tls')

    # Keep Domain Manager in sync when it exists, but do not require the Network feature.
    try:
        row = DomainRecord.query.filter_by(domain=domain).first()
        if not row:
            db.session.add(DomainRecord(domain=domain, purpose='vpn/panel', ssl_enabled=True))
        else:
            row.ssl_enabled = True
            row.purpose = row.purpose or 'vpn/panel'
        db.session.commit()
    except Exception:
        db.session.rollback()

    _install_renew_hook(domain, cert, key, certbot_bin)

    try:
        apply_runtime_configs()
        sync_all_users(restart=True)
    except Exception as exc:
        set_setting('ssl_last_error', str(exc)[-1000:])
        return {'ok': False, 'domain': domain, 'message': 'SSL گرفته شد، اما اعمال کانفیگ سرویس‌ها خطا داد: ' + str(exc)[-700:]}

    # Restarting the panel immediately may cut off the HTTP response; restart in the background.
    run_cmd(['bash', '-lc', 'nohup bash -c "sleep 2; systemctl restart ironpanel" >/dev/null 2>&1 &'])

    msg = f'SSL با موفقیت دریافت و با certbot سالم ({certbot_bin}) روی IronPanel، Ocserv/AnyConnect، Hysteria2 و همه پروفایل‌های TLS در Xray اعمال شد. پروتکل‌هایی مثل OpenVPN/WireGuard/L2TP/PPTP به SSL دامنه‌ای نیاز ندارند.'
    set_setting('ssl_last_error', '')
    set_setting('ssl_last_result', msg)
    return {'ok': True, 'domain': domain, 'cert': cert, 'key': key, 'message': msg, 'certbot_output': output[-1000:]}


def renew_all_ssl() -> Dict[str, Any]:
    ok_install, certbot_bin, install_msg = _ensure_certbot_installed()
    if not ok_install:
        set_setting('ssl_last_error', install_msg[-2000:])
        return {'ok': False, 'message': 'تمدید SSL اجرا نشد؛ certbot سالم پیدا نشد: ' + install_msg[-1000:]}

    p = _run_certbot_binary(certbot_bin, ['renew', '--quiet'])
    out = (p.stdout or '') + (p.stderr or '')
    domain = default_ssl_domain()
    try:
        if valid_domain(domain) and Path(f'/etc/letsencrypt/live/{domain}/fullchain.pem').exists():
            copied = _copy_certificate_files(domain)
            _copy_for_ocserv(copied['cert'], copied['key'])
            apply_runtime_configs()
            sync_all_users(restart=True)
            run_cmd(['bash', '-lc', 'nohup bash -c "sleep 2; systemctl restart ironpanel" >/dev/null 2>&1 &'])
    except Exception as exc:
        out += '\n' + str(exc)
    ok = p.returncode == 0
    set_setting('ssl_last_result' if ok else 'ssl_last_error', (out or 'renew executed')[-1200:])
    return {'ok': ok, 'message': 'تمدید SSL اجرا شد' if ok else 'تمدید SSL خطا داد: ' + out[-700:] + _certbot_error_hint(out)}

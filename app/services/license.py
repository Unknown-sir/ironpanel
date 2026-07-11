import hashlib
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import requests
from flask import current_app

from ..core.extensions import db
from ..core.models import AppSetting

CACHE_SECONDS = 300
OFFLINE_GRACE_SECONDS = 24 * 60 * 60
FREE_LICENSE_TYPE = 'beginer'

DEFAULT_FEATURES = {
    'nodes': True,
    'sales_bot': True,
    'billing': True,
    'network': True,
    'updates': True,
    'xray': True,
    'outbound': True,
    'backup': True,
    'monitoring': True,
    'api': True,
    'subscription': True,
    'node_agent': True,
    'outbound_failover': True,
}

TYPE_FEATURES = {
    # Beginner is the built-in free edition and never requires a license key.
    'beginer': {
        'nodes': False,
        'sales_bot': False,
        'billing': False,
        'network': False,
        'updates': True,
        'xray': True,
        'outbound': True,
        'backup': True,
        'monitoring': True,
        'api': True,
        'subscription': True,
        'node_agent': False,
        'outbound_failover': True,
    },
    'plus': {
        'nodes': True,
        'sales_bot': False,
        'billing': False,
        'network': False,
        'updates': True,
        'xray': True,
        'outbound': True,
        'backup': True,
        'monitoring': True,
        'api': True,
        'subscription': True,
        'node_agent': True,
        'outbound_failover': True,
    },
    'pro': {
        'nodes': True,
        'sales_bot': True,
        'billing': False,
        'network': True,
        'updates': True,
        'xray': True,
        'outbound': True,
        'backup': True,
        'monitoring': True,
        'api': True,
        'subscription': True,
        'node_agent': True,
        'outbound_failover': True,
    },
    'admin': dict(DEFAULT_FEATURES),
    'trial': dict(DEFAULT_FEATURES),
}


def _get_setting(key, default=''):
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, '') else default


def _set_setting(key, value, commit=True):
    value = str(value)
    row = AppSetting.query.filter_by(key=key).first()
    changed = False
    if not row:
        db.session.add(AppSetting(key=key, value=value))
        changed = True
    elif row.value != value:
        row.value = value
        changed = True
    if commit and changed:
        db.session.commit()
    return changed


def _features_for_type(license_type):
    normalized = (license_type or FREE_LICENSE_TYPE).strip().lower()
    base = dict(DEFAULT_FEATURES)
    base.update(TYPE_FEATURES.get(normalized, TYPE_FEATURES[FREE_LICENSE_TYPE]))
    if not base.get('nodes'):
        base['node_agent'] = False
    return base


def _config_file(name):
    root = current_app.config['CONFIG_ROOT']
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def _write_json(path, payload):
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _free_result(reason='نسخه رایگان Beginner فعال است.', status='free', paid_reason=''):
    return {
        'valid': False,                 # paid license validity
        'operational': True,            # panel is always usable in free mode
        'paid': False,
        'reason': reason,
        'paid_reason': paid_reason,
        'status': status,
        'expires_at': '',
        'license_type': FREE_LICENSE_TYPE,
        'features': _features_for_type(FREE_LICENSE_TYPE),
        'checked_at': time.time(),
    }


def _persist_effective_state(result):
    changed = False
    changed |= _set_setting('license_status', result.get('status', ''), commit=False)
    changed |= _set_setting('license_message', result.get('reason', ''), commit=False)
    changed |= _set_setting('license_type', result.get('license_type', FREE_LICENSE_TYPE), commit=False)
    changed |= _set_setting('license_paid_active', '1' if result.get('paid') and result.get('valid') else '0', commit=False)
    try:
        features = json.dumps(result.get('features', {}), ensure_ascii=False, sort_keys=True)
    except Exception:
        features = json.dumps(_features_for_type(FREE_LICENSE_TYPE), ensure_ascii=False, sort_keys=True)
    changed |= _set_setting('license_features', features, commit=False)
    if changed:
        db.session.commit()


def machine_id():
    parts = []
    for path in ['/etc/machine-id', '/var/lib/dbus/machine-id']:
        try:
            value = Path(path).read_text().strip()
            if value:
                parts.append(value)
        except Exception:
            pass
    parts.append(current_app.config.get('PUBLIC_HOST', ''))
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()


def license_server_url():
    return (_get_setting('license_server_url', 'http://license.skyshield.space:8002') or 'http://license.skyshield.space:8002').rstrip('/')


def license_key():
    return _get_setting('license_key', '')


def clear_license_key():
    _set_setting('license_key', '', commit=False)
    db.session.commit()
    for filename in ('license_cache.json', 'license_last_valid.json'):
        try:
            _config_file(filename).unlink(missing_ok=True)
        except Exception:
            pass
    result = _free_result('لایسنس حذف شد؛ نسخه رایگان Beginner فعال است.', 'free')
    _persist_effective_state(result)
    return result


def save_license_key(key):
    cleaned = (key or '').strip()
    if not cleaned:
        return clear_license_key()
    _set_setting('license_key', cleaned)
    try:
        _config_file('license_cache.json').unlink(missing_ok=True)
    except Exception:
        pass
    return check_license(force=True)


def license_remaining_days(result=None):
    if result is None:
        result = check_license(force=False)
    expires_at = (result or {}).get('expires_at') or ''
    if not expires_at:
        return None
    try:
        raw = str(expires_at).strip().replace('Z', '+00:00')
        try:
            expires = datetime.fromisoformat(raw)
        except ValueError:
            expires = datetime.strptime(raw[:10], '%Y-%m-%d')
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return max(0, (expires.date() - datetime.now(timezone.utc).date()).days)
    except Exception:
        return None


def current_license_type():
    return (_get_setting('license_type', FREE_LICENSE_TYPE) or FREE_LICENSE_TYPE).strip().lower()


def current_license_features():
    raw = _get_setting('license_features', '')
    if raw:
        try:
            features = _features_for_type(current_license_type())
            features.update(json.loads(raw))
            return features
        except Exception:
            pass
    return _features_for_type(current_license_type())


def paid_license_active():
    return _get_setting('license_paid_active', '0') == '1' and current_license_type() not in ('', FREE_LICENSE_TYPE)


def is_free_edition():
    return not paid_license_active()


def feature_allowed(name):
    return bool(current_license_features().get(name, False))


def feature_label(name):
    return {
        'nodes': 'نودها / Multi Server',
        'sales_bot': 'ربات فروش',
        'billing': 'مالی',
        'network': 'شبکه و دامنه',
        'updates': 'آپدیت',
        'xray': 'Xray / V2Ray',
        'outbound': 'Outbound Routing',
        'backup': 'Backup / Restore',
        'monitoring': 'Monitoring',
        'api': 'API',
        'subscription': 'Subscription',
        'node_agent': 'Node Agent',
        'outbound_failover': 'Outbound Failover',
    }.get(name, name)


def current_version_safe():
    try:
        return Path('/opt/ironpanel/VERSION').read_text().strip()
    except Exception:
        try:
            return Path(__file__).resolve().parents[2].joinpath('VERSION').read_text().strip()
        except Exception:
            return 'unknown'


def send_heartbeat():
    key = license_key()
    if not key or not paid_license_active():
        return False
    payload = {
        'license_key': key,
        'machine_id': machine_id(),
        'panel_host': current_app.config.get('PUBLIC_HOST', ''),
        'version': current_version_safe(),
    }
    try:
        import psutil
        payload['cpu'] = psutil.cpu_percent(interval=0.05)
        payload['ram'] = psutil.virtual_memory().percent
    except Exception:
        pass
    try:
        requests.post(license_server_url() + '/api/heartbeat', json=payload, timeout=5)
        return True
    except Exception:
        return False


def check_license(force=False):
    key = license_key()
    cache_file = _config_file('license_cache.json')
    last_valid_file = _config_file('license_last_valid.json')

    if not key:
        result = _free_result()
        _write_json(cache_file, result)
        _persist_effective_state(result)
        return result

    if not force:
        cached = _read_json(cache_file)
        if cached and time.time() - cached.get('checked_at', 0) < CACHE_SECONDS:
            _persist_effective_state(cached)
            return cached

    payload = {
        'license_key': key,
        'machine_id': machine_id(),
        'panel_host': current_app.config.get('PUBLIC_HOST', ''),
    }

    try:
        response = requests.post(license_server_url() + '/api/check', json=payload, timeout=8)
        data = response.json()
        paid_valid = bool(data.get('valid'))
        server_status = data.get('status', 'active' if paid_valid else 'invalid')
        server_reason = data.get('message') or data.get('reason') or ('لایسنس معتبر است' if paid_valid else 'لایسنس نامعتبر است')
        requested_type = (data.get('license_type') or data.get('plan') or 'admin').strip().lower()

        if paid_valid and requested_type != FREE_LICENSE_TYPE:
            features = data.get('features') or _features_for_type(requested_type)
            result = {
                'valid': True,
                'operational': True,
                'paid': True,
                'reason': server_reason,
                'paid_reason': '',
                'status': server_status,
                'expires_at': data.get('expires_at', ''),
                'license_type': requested_type,
                'features': features,
                'checked_at': time.time(),
            }
            _write_json(last_valid_file, result)
        elif paid_valid and requested_type == FREE_LICENSE_TYPE:
            result = _free_result(
                'Beginner اکنون رایگان است و برای استفاده از آن نیازی به لایسنس نیست.',
                'free_legacy',
                server_reason,
            )
        else:
            result = _free_result(
                f'{server_reason}؛ پنل در حالت رایگان Beginner ادامه می‌دهد.',
                server_status,
                server_reason,
            )
    except Exception as exc:
        previous = _read_json(last_valid_file)
        if previous and previous.get('valid') and time.time() - previous.get('checked_at', 0) <= OFFLINE_GRACE_SECONDS:
            result = dict(previous)
            result.update(
                status='offline_grace',
                reason='ارتباط با سرور لایسنس موقتاً قطع است؛ امکانات لایسنس قبلی تا ۲۴ ساعت حفظ می‌شود.',
                checked_at=time.time(),
            )
        else:
            message = 'ارتباط با سرور لایسنس برقرار نشد: ' + str(exc)
            result = _free_result(
                message + '؛ پنل در حالت رایگان Beginner ادامه می‌دهد.',
                'connection_failed',
                message,
            )

    _write_json(cache_file, result)
    _persist_effective_state(result)
    if result.get('valid') and result.get('paid'):
        send_heartbeat()
    return result

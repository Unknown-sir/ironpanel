import hashlib, json, time
from pathlib import Path
from flask import current_app
from ..core.extensions import db
from ..core.models import AppSetting
import requests

CACHE_SECONDS = 300
DEFAULT_FEATURES = {'nodes': True, 'sales_bot': True, 'billing': True, 'network': True, 'updates': True}
TYPE_FEATURES = {
    'beginer': {'nodes': False, 'sales_bot': False, 'billing': False, 'network': False, 'updates': True},
    'plus': {'nodes': True, 'sales_bot': False, 'billing': False, 'network': False, 'updates': True},
    'pro': {'nodes': True, 'sales_bot': True, 'billing': False, 'network': True, 'updates': True},
    'admin': {'nodes': True, 'sales_bot': True, 'billing': True, 'network': True, 'updates': True},
    'trial': {'nodes': True, 'sales_bot': True, 'billing': True, 'network': True, 'updates': True},
}

def _get_setting(key, default=''):
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, '') else default

def _set_setting(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        db.session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
    db.session.commit()

def machine_id():
    parts=[]
    for path in ['/etc/machine-id','/var/lib/dbus/machine-id']:
        try:
            v=Path(path).read_text().strip()
            if v: parts.append(v)
        except Exception: pass
    parts.append(current_app.config.get('PUBLIC_HOST',''))
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()

def license_server_url():
    return (_get_setting('license_server_url','http://license.skyshield.space:8002') or 'http://license.skyshield.space:8002').rstrip('/')

def license_key(): return _get_setting('license_key','')

def save_license_key(key):
    _set_setting('license_key', key.strip())
    return check_license(force=True)

def license_remaining_days(result=None):
    if result is None: result = check_license(force=False)
    exp = (result or {}).get('expires_at') or ''
    if not exp: return None
    from datetime import datetime, timezone
    try:
        raw = str(exp).strip().replace('Z', '+00:00')
        try: dt = datetime.fromisoformat(raw)
        except ValueError: dt = datetime.strptime(raw[:10], '%Y-%m-%d')
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (dt.date() - datetime.now(timezone.utc).date()).days)
    except Exception: return None

def _features_for_type(t):
    f=dict(DEFAULT_FEATURES); f.update(TYPE_FEATURES.get((t or 'admin').strip(), TYPE_FEATURES['admin'])); return f

def current_license_type():
    return _get_setting('license_type','admin') or 'admin'

def current_license_features():
    raw=_get_setting('license_features','')
    if raw:
        try:
            f=dict(DEFAULT_FEATURES); f.update(json.loads(raw)); return f
        except Exception: pass
    return _features_for_type(current_license_type())

def feature_allowed(name):
    if name == 'updates': return True
    return bool(current_license_features().get(name, True))

def feature_label(name):
    return {'nodes':'نودها / Multi Server','sales_bot':'ربات فروش','billing':'مالی','network':'شبکه و دامنه','updates':'آپدیت'}.get(name,name)

def send_heartbeat():
    key = license_key()
    if not key: return False
    payload={'license_key': key, 'machine_id': machine_id(), 'panel_host': current_app.config.get('PUBLIC_HOST',''), 'version': current_version_safe()}
    try:
        import psutil
        payload['cpu']=psutil.cpu_percent(interval=0.05); payload['ram']=psutil.virtual_memory().percent
    except Exception: pass
    try:
        requests.post(license_server_url() + '/api/heartbeat', json=payload, timeout=5)
        return True
    except Exception: return False

def current_version_safe():
    try: return Path('/opt/ironpanel/VERSION').read_text().strip()
    except Exception:
        try: return Path(__file__).resolve().parents[2].joinpath('VERSION').read_text().strip()
        except Exception: return 'unknown'

def check_license(force=False):
    key = license_key()
    if not key:
        return {'valid': False, 'reason': 'لایسنس ثبت نشده است', 'status': 'not_configured'}
    cache_file = current_app.config['CONFIG_ROOT'] / 'license_cache.json'
    if not force and cache_file.exists():
        try:
            data=json.loads(cache_file.read_text())
            if time.time() - data.get('checked_at',0) < CACHE_SECONDS: return data
        except Exception: pass
    payload={'license_key': key, 'machine_id': machine_id(), 'panel_host': current_app.config.get('PUBLIC_HOST','')}
    try:
        r=requests.post(license_server_url() + '/api/check', json=payload, timeout=8)
        data=r.json(); valid=bool(data.get('valid'))
        reason=data.get('message') or data.get('reason') or ('لایسنس معتبر است' if valid else 'لایسنس نامعتبر است')
        ltype=data.get('license_type') or data.get('plan') or 'admin'
        features=data.get('features') or _features_for_type(ltype)
        result={'valid': valid, 'reason': reason, 'status': data.get('status','active' if valid else 'invalid'), 'expires_at': data.get('expires_at',''), 'license_type': ltype, 'features': features, 'checked_at': time.time()}
    except Exception as e:
        result={'valid': False, 'reason': 'ارتباط با سرور لایسنس برقرار نشد: '+str(e), 'status': 'connection_failed', 'checked_at': time.time()}
    try: cache_file.write_text(json.dumps(result, ensure_ascii=False))
    except Exception: pass
    if result.get('valid'): send_heartbeat()
    _set_setting('license_status', result.get('status',''))
    _set_setting('license_message', result.get('reason',''))
    _set_setting('license_type', result.get('license_type',''))
    try: _set_setting('license_features', json.dumps(result.get('features',{}), ensure_ascii=False))
    except Exception: pass
    return result

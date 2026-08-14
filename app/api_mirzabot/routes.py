from __future__ import annotations

import hmac
import math
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from ..core.extensions import db
from ..core.models import VpnUser
from ..services.license import filter_protocols_for_license
from ..services.password_policy import generate_user_password
from ..services.provisioning import (
    active_protocols,
    delete_user,
    get_setting,
    log,
    normalize_user_protocols,
    reset_user_usage_preserving_reseller,
    set_user_enabled,
    subscription_url_for_user,
    sync_user,
    user_access_status,
)

api_mirzabot_bp = Blueprint('api_mirzabot', __name__)

_BYTES_PER_MB = 1024 * 1024


def _reply_success(**payload):
    body = {'status': 'success'}
    body.update(payload)
    return jsonify(body)


def _reply_error(message: str, status_code: int = 400):
    return jsonify(status='error', message=message), status_code


def _api_enabled() -> bool:
    return str(get_setting('mirzabot_api_enabled', '0') or '0').strip().lower() in {'1', 'true', 'yes', 'on'}


def _valid_api_key() -> bool:
    if not _api_enabled():
        return False
    expected = str(get_setting('mirzabot_api_key', '') or '').strip()
    supplied = str(request.headers.get('X-API-Key', '') or '').strip()
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _bytes_to_limit_mb(value) -> int:
    try:
        raw = max(0, int(value or 0))
    except Exception:
        raise ValueError('Invalid data_limit')
    if raw <= 0:
        return 0
    return max(1, int(math.ceil(raw / _BYTES_PER_MB)))


def _limit_bytes(user: VpnUser) -> int:
    return max(0, int(user.data_limit_mb or 0)) * _BYTES_PER_MB


def _expire_from_unix(value):
    try:
        ts = int(value or 0)
    except Exception:
        raise ValueError('Invalid expire')
    if ts <= 0:
        return None
    try:
        return datetime.utcfromtimestamp(ts)
    except (OverflowError, OSError, ValueError):
        raise ValueError('Invalid expire')


def _expire_to_unix(user: VpnUser) -> int:
    if not user.expires_at:
        return 0
    # Stored timestamps are UTC-naive throughout IronPanel.
    return int((user.expires_at - datetime(1970, 1, 1)).total_seconds())


def _default_protocols() -> list[str]:
    configured = str(get_setting('mirzabot_protocols', '') or '').strip()
    requested = normalize_user_protocols(
        configured.split(',') if configured else active_protocols(),
        allow_default=True,
    )
    licensed = filter_protocols_for_license(requested)
    active = set(active_protocols())
    selected = [p for p in licensed if p in active]
    # If a saved option became unavailable after a license/runtime change, fall
    # back to whatever is actually active rather than creating a dead account.
    if not selected:
        selected = [p for p in filter_protocols_for_license(active_protocols()) if p in active]
    return selected


def _find_user(username: str):
    return VpnUser.query.filter_by(username=str(username or '').strip()).first()


def _serialize_user(user: VpnUser):
    ok, _reason = user_access_status(user)
    return {
        'status': 'success',
        'username': user.username,
        'data_limit': _limit_bytes(user),
        'expire': _expire_to_unix(user),
        'used_traffic': int(user.used_total_bytes or 0),
        # MirzaBot's published examples explicitly allow empty arrays when a
        # panel delivers the service through one subscription URL.
        'links': [],
        'subscription_url': subscription_url_for_user(user),
        'enabled': bool(user.enabled),
        'active': bool(ok),
    }


def _ensure_username(payload):
    username = str(payload.get('username') or '').strip()
    if len(username) < 3:
        raise ValueError('Username must be at least 3 characters')
    if len(username) > 80:
        raise ValueError('Username is too long')
    return username


def _reactivate_and_sync(user: VpnUser, changed_protocols=None):
    user.enabled = True
    user.disabled_reason = ''
    db.session.commit()
    sync_user(user, restart=False, changed_protocols=changed_protocols, ensure_runtime=True)


def _action_create_user(data):
    username = _ensure_username(data)
    if _find_user(username):
        return _reply_error('Username already exists', 409)
    protocols = _default_protocols()
    if not protocols:
        return _reply_error('No active protocol is available', 503)
    password = generate_user_password()
    user = VpnUser(
        username=username,
        data_limit_mb=_bytes_to_limit_mb(data.get('data_limit')),
        expires_at=_expire_from_unix(data.get('expire')),
        protocols=','.join(protocols),
        protocol_permissions=','.join(protocols),
        l2tp_password=password,
        cisco_password=password,
        owner_id=None,
        enabled=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    sync_user(user, restart=False, changed_protocols=set(protocols), ensure_runtime=True)
    note = str(data.get('note') or '').strip()
    log('mirzabot_api', 'create_user', username, note[:500] if note else None)
    return _reply_success(
        username=username,
        subscription_url=subscription_url_for_user(user),
        configs=[],
    )


def _action_get_user(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    return jsonify(_serialize_user(user))


def _action_remove_user(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    username = user.username
    delete_user(user)
    log('mirzabot_api', 'remove_user', username)
    return _reply_success()


def _action_reset_user(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    reset_user_usage_preserving_reseller(user)
    db.session.commit()
    log('mirzabot_api', 'reset_user', user.username)
    return _reply_success()


def _action_extend_user(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    user.data_limit_mb = _bytes_to_limit_mb(data.get('data_limit'))
    user.expires_at = _expire_from_unix(data.get('expire'))
    _reactivate_and_sync(user, changed_protocols=set(user.allowed_protocol_list() or user.protocol_list()))
    log('mirzabot_api', 'extend_user', user.username)
    return _reply_success()


def _apply_config(user: VpnUser, config: dict):
    changed = False
    runtime_changed = False
    if 'data_limit' in config:
        user.data_limit_mb = _bytes_to_limit_mb(config.get('data_limit'))
        changed = True
    if 'expire' in config:
        user.expires_at = _expire_from_unix(config.get('expire'))
        changed = True
    if 'status' in config:
        status = str(config.get('status') or '').strip().lower()
        if status not in {'active', 'disabled'}:
            raise ValueError('Invalid status')
        # Commit other edits first; set_user_enabled performs its own runtime sync.
        if changed:
            db.session.commit()
        set_user_enabled(user, status == 'active')
        runtime_changed = True
        changed = False
    if changed:
        db.session.commit()
        sync_user(user, restart=False, changed_protocols=set(), ensure_runtime=False)
    return runtime_changed


def _action_modify_user(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    config = data.get('config')
    if not isinstance(config, dict):
        return _reply_error('Invalid config', 400)
    _apply_config(user, config)
    log('mirzabot_api', 'modify_user', user.username)
    return _reply_success(data={})


def _action_change_status(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    status = str(data.get('status') or '').strip().lower()
    if status not in {'active', 'disabled'}:
        return _reply_error('Invalid status', 400)
    set_user_enabled(user, status == 'active')
    log('mirzabot_api', 'change_status', user.username, status)
    return _reply_success()


def _action_count_users(_data):
    count = 0
    for user in VpnUser.query.all():
        ok, _reason = user_access_status(user)
        if ok:
            count += 1
    return jsonify(count=count)


def _action_revoke_sub(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    user.subscription_token = secrets.token_urlsafe(48)
    db.session.commit()
    # Xray identities and profile material can depend on subscription_token, so
    # rotating the subscription must re-provision the user's running protocols.
    sync_user(
        user,
        restart=False,
        changed_protocols=set(user.allowed_protocol_list() or user.protocol_list()),
        ensure_runtime=True,
    )
    log('mirzabot_api', 'revoke_sub', user.username)
    return _reply_success(subscription_url=subscription_url_for_user(user), configs=[])


def _action_extra_volume(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    try:
        extra = max(0, int(data.get('volume') or 0))
    except Exception:
        return _reply_error('Invalid volume', 400)
    if extra <= 0:
        return _reply_error('Invalid volume', 400)
    # data_limit_mb=0 means unlimited. Do not accidentally turn an unlimited
    # account into a limited one when an external bot sends an add-on request.
    if int(user.data_limit_mb or 0) > 0:
        user.data_limit_mb = int(user.data_limit_mb or 0) + _bytes_to_limit_mb(extra)
    db.session.commit()
    sync_user(user, restart=False, changed_protocols=set(), ensure_runtime=False)
    log('mirzabot_api', 'extra_volume', user.username, str(extra))
    return _reply_success()


def _action_extra_time(data):
    user = _find_user(data.get('username'))
    if not user:
        return _reply_error('User not found', 404)
    try:
        days = int(data.get('time') or 0)
    except Exception:
        return _reply_error('Invalid time', 400)
    if days <= 0:
        return _reply_error('Invalid time', 400)
    # expires_at=None is unlimited; adding days must not make it finite.
    if user.expires_at is not None:
        base = max(user.expires_at, datetime.utcnow())
        user.expires_at = base + timedelta(days=days)
        user.enabled = True
        user.disabled_reason = ''
    db.session.commit()
    sync_user(
        user,
        restart=False,
        changed_protocols=set(user.allowed_protocol_list() or user.protocol_list()),
        ensure_runtime=True,
    )
    log('mirzabot_api', 'extra_time', user.username, str(days))
    return _reply_success()


_ACTIONS = {
    'create_user': _action_create_user,
    'get_user': _action_get_user,
    'remove_user': _action_remove_user,
    'reset_user': _action_reset_user,
    'extend_user': _action_extend_user,
    'modify_user': _action_modify_user,
    'change_status': _action_change_status,
    'count_users': _action_count_users,
    'revoke_sub': _action_revoke_sub,
    'extra_volume': _action_extra_volume,
    'extra_time': _action_extra_time,
}


@api_mirzabot_bp.route('/', methods=['POST'], strict_slashes=False)
def mirzabot_api():
    if not _valid_api_key():
        return _reply_error('Invalid API Key', 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _reply_error('Invalid JSON body', 400)
    action = str(data.get('action') or '').strip()
    handler = _ACTIONS.get(action)
    if not handler:
        return _reply_error('Invalid action', 400)
    try:
        return handler(data)
    except ValueError as exc:
        db.session.rollback()
        return _reply_error(str(exc), 400)
    except Exception as exc:
        db.session.rollback()
        try:
            log('mirzabot_api', 'error', action, str(exc)[-800:])
        except Exception:
            pass
        return _reply_error('Internal error', 500)


@api_mirzabot_bp.get('/health')
def health():
    if not _valid_api_key():
        return _reply_error('Invalid API Key', 401)
    return _reply_success(service='IronPanel MirzaBot API', version='1.0.0')

"""3x-ui compatible API for external sales bots.

Freshly adds the fourth credential family a reseller can configure on the
"Robore sales" page. Bots written for https://github.com/MHSanaei/3x-ui (and
adapters like it) can talk to IronPanel through this endpoint suite:

  POST /api/xui/login                                  -> session token
  GET  /api/xui/panel/api/inbounds/list                -> clients owned by the token
  POST /api/xui/panel/api/inbounds/addClient           -> create a user (answer = subscription)
  GET  /api/xui/panel/api/inbounds/getClientTraffics/{email}
  POST /api/xui/panel/api/inbounds/updateClient/{inboundId}/{email}
  POST /api/xui/panel/api/inbounds/delClient/{inboundId}/{email}
  POST /api/xui/panel/api/inbounds/delDepletedClients/{inboundId}
  GET  /api/xui/sub/{subId}                            -> raw subscription content

Every mutation is scoped to the credential owner (a reseller) and refuses to
create/update while that reseller is volume-gated or has no free user slots.
"""
from __future__ import annotations

import base64
import binascii
import json
import math
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, jsonify, make_response, request

from ..core.extensions import db
from ..core.models import Admin, ApiToken, VpnUser
from ..services.license import filter_protocols_for_license
from ..services.password_policy import generate_user_password
from ..services.provisioning import (
    active_protocols,
    delete_user,
    log,
    normalize_user_protocols,
    subscription_url_for_user,
    sync_user,
    user_access_status,
)
from ..services.reseller_api import (
    resolve_api_token,
    volume_gate_reason,
    create_block_reason,
    owner_user_query,
    owner_protocols,
)
from ..services.speed_limit import cap_user_speed_for_owner

api_xui_bp = Blueprint('api_xui', __name__)

_BYTES_PER_MB = 1024 * 1024


def _success(obj):
    return jsonify(success=True, msg='', obj=obj)


def _fail(msg, status_code=400):
    return jsonify(success=False, msg=msg, obj={}), status_code


def _owner():
    return getattr(request, 'xui_owner', None)


def _default_protocols(owner):
    active = active_protocols()
    licensed = filter_protocols_for_license(active)
    selected = owner_protocols(owner, [p for p in licensed if p in active])
    if not selected:
        return [p for p in filter_protocols_for_license(active) if p in active]
    return selected


def _extract_client_payload(data: dict) -> dict:
    """Normalize a 3x-ui addClient/updateClient body into client fields.

    3x-ui sends settings as a JSON string (and updateClient sometimes base64-encodes it).
    """
    client = {}
    settings = data.get('settings')
    if isinstance(settings, str) and settings.strip():
        raw = settings.strip()
        if raw.startswith('{'):
            try:
                settings = json.loads(raw)
            except (ValueError, TypeError):
                settings = None
        else:
            try:
                decoded = base64.b64decode(raw + '=' * (-len(raw) % 4)).decode('utf-8')
                settings = json.loads(decoded)
            except (ValueError, TypeError, binascii.Error):
                settings = None
    if isinstance(settings, dict):
        clients = settings.get('clients', [])
        if isinstance(clients, list) and clients:
            client.update(clients[0] if isinstance(clients[0], dict) else {})
        client.update({k: v for k, v in settings.items() if k != 'clients'})
    for key in ('email', 'remark', 'subId', 'limitIp', 'flow', 'tgId', 'total', 'expiryTime', 'enable', 'id'):
        if key in data:
            client[key] = data[key]
    if 'username' in data and not client.get('email'):
        client['email'] = data['username']
    if 'data_limit_mb' in data and 'total' not in client:
        client['total'] = max(0, int(data['data_limit_mb'] or 0)) * _BYTES_PER_MB
    if 'days' in data and 'expiryTime' not in client:
        client['expiryTime'] = 0 if int(data.get('days') or 0) <= 0 else (datetime.utcnow() + timedelta(days=int(data['days']))).timestamp() * 1000
    if 'password' in data and not client.get('password'):
        client['password'] = data['password']
    return client


def _email_of(payload: dict) -> str:
    email = str(payload.get('email') or '').strip()
    if len(email) < 3:
        raise ValueError('email must be at least 3 characters')
    return email[:80]


def _total_to_mb(value) -> int:
    try:
        raw = max(0, int(value or 0))
    except (ValueError, TypeError):
        raise ValueError('Invalid total')
    if raw <= 0:
        return 0
    return max(1, int(math.ceil(raw / _BYTES_PER_MB)))


def _expiry_time_to_dt(value):
    try:
        ts = int(value or 0)
    except (ValueError, TypeError):
        raise ValueError('Invalid expiryTime')
    if ts <= 0:
        return None
    try:
        return datetime.utcfromtimestamp(ts / 1000.0)
    except (OverflowError, OSError, ValueError):
        raise ValueError('Invalid expiryTime')


def _xui_client(user: VpnUser):
    ok, _reason = user_access_status(user)
    expiry = 0
    if user.expires_at:
        expiry = int((user.expires_at - datetime(1970, 1, 1)).total_seconds() * 1000)
    return {
        'id': str(user.id),
        'email': user.username,
        'enable': bool(user.enabled),
        'active': bool(ok),
        'total': max(0, int(user.data_limit_mb or 0)) * _BYTES_PER_MB,
        'up': int(user.used_upload_bytes or 0),
        'down': int(user.used_download_bytes or 0),
        'expiryTime': expiry,
        'limitIp': int(getattr(user, 'connection_limit', 1) or 1),
        'remark': f"user-{user.id}",
        'subId': user.subscription_token,
        'subscriptionUrl': subscription_url_for_user(user),
    }


def _build_inbound(user: VpnUser):
    return {'id': 1, 'remark': 'ironpanel', 'clientStats': [_xui_client(user)]}


def require_auth(fn):
    @wraps(fn)
    def w(*args, **kwargs):
        raw = (request.headers.get('X-API-KEY', '') or '').strip()
        if not raw:
            raw = (request.cookies.get('3x-ui', '') or '').strip()
        _tok, owner = resolve_api_token(raw, allowed_types=['xui'])
        if not _tok:
            return _fail('Invalid API Key', 401)
        request.xui_owner = owner
        return fn(*args, **kwargs)
    return w


@api_xui_bp.post('/login')
def login():
    data = request.form or request.get_json(silent=True) or {}
    password = str(data.get('password') or '').strip()
    if not password:
        return _fail('password is required', 401)
    username = str(data.get('username') or '').strip()
    # (1) Prefer reseller credentials: username (panel username) + API key as password.
    _tok, owner = resolve_api_token(password, allowed_types=['xui'])
    if _tok:
        if username:
            candidate_owner = Admin.query.filter_by(username=username, role='sub_admin').first()
            if candidate_owner and _tok.owner_id and _tok.owner_id != candidate_owner.id:
                return _fail('Invalid credentials', 401)
        return _issue_xui_token(_tok)
    # (2) Fallback: the "password" is the reseller's real panel login password.
    # Standard 3x-ui sales bots send username+password of the panel; let those work.
    acc = Admin.query.filter_by(username=username, role='sub_admin').first()
    if acc and acc.check_password(password):
        tok = ApiToken.query.filter_by(owner_id=acc.id, api_type='xui', enabled=True).first()
        if tok:
            return _issue_xui_token(tok)
        return _fail('This reseller has no active bot (xui) API key yet', 403)
    return _fail('Invalid credentials', 401)


def _issue_xui_token(tok):
    response = jsonify(success=True, msg='', obj={'token': tok.token})
    response.set_cookie('3x-ui', tok.token, max_age=7 * 24 * 3600, httponly=True, samesite='Lax')
    log('xui_api', 'login', tok.name or ('reseller-%s' % tok.owner_id))
    return response


@api_xui_bp.get('/health')
def health():
    return jsonify(success=True, msg='', obj={'service': 'IronPanel xui api', 'title': 'IronPanel', 'version': '2.0.4'})


@api_xui_bp.get('/panel/api/inbounds/list')
@require_auth
def inbounds_list():
    owner = _owner()
    rows = [{'id': 1, 'remark': 'ironpanel', 'clientStats': [_xui_client(u) for u in owner_user_query(owner).order_by(VpnUser.id.desc()).all()]}]
    return _success({'obj': rows, 'msg': '', 'success': True})


@api_xui_bp.get('/panel/api/inbounds/get/<int:inbound_id>')
@require_auth
def inbounds_get(inbound_id):
    owner = _owner()
    users = owner_user_query(owner).order_by(VpnUser.id.desc()).all()
    return _success({'obj': [{'id': 1, 'remark': 'ironpanel', 'clientStats': [_xui_client(u) for u in users]}], 'msg': '', 'success': True})


@api_xui_bp.post('/panel/api/inbounds/addClient')
@require_auth
def add_client():
    owner = _owner()
    reason = create_block_reason(owner)
    if reason:
        return _fail('Cannot create user: ' + reason, 403)
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    try:
        client = _extract_client_payload(data)
        email = _email_of(client)
    except ValueError as exc:
        return _fail(str(exc), 400)
    if owner_user_query(owner).filter_by(username=email).first():
        return _fail('Username already exists', 409)
    protocols = _default_protocols(owner)
    if not protocols:
        return _fail('No active protocol is available', 503)
    try:
        data_limit_mb = _total_to_mb(client.get('total', 0))
        expires_at = _expiry_time_to_dt(client.get('expiryTime', 0))
    except ValueError as exc:
        return _fail(str(exc), 400)
    password = client.get('password') or generate_user_password()
    user = VpnUser(
        username=email,
        data_limit_mb=data_limit_mb,
        expires_at=expires_at,
        protocols=','.join(protocols),
        protocol_permissions=','.join(protocols),
        l2tp_password=password,
        cisco_password=password,
        connection_limit=max(1, int(client.get('limitIp') or 0) or 1),
        owner_id=owner.id if owner else None,
        enabled=True,
        speed_limit_mbps=cap_user_speed_for_owner(owner.id if owner else None, 0),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    try:
        sync_user(user, restart=False, changed_protocols=set(protocols), ensure_runtime=True)
    except Exception:
        db.session.rollback()
        return _fail('Failed to provision user', 500)
    log('xui_api', 'create_user', email)
    return _success({'id': 1, 'email': email, 'subscriptionUrl': subscription_url_for_user(user), 'subscriptionId': user.subscription_token})


@api_xui_bp.get('/panel/api/inbounds/getClientTraffics/<path:email>')
@require_auth
def get_client_traffics(email):
    owner = _owner()
    user = owner_user_query(owner).filter_by(username=str(email or '').strip()).first()
    if not user:
        return _fail('User not found', 404)
    return _success(_build_inbound(user))


@api_xui_bp.post('/panel/api/inbounds/updateClient/<int:inbound_id>/<path:email>')
@require_auth
def update_client(inbound_id, email):
    owner = _owner()
    user = owner_user_query(owner).filter_by(username=str(email or '').strip()).first()
    if not user:
        return _fail('User not found', 404)
    reason = volume_gate_reason(owner)
    if reason:
        return _fail('Action blocked: ' + reason, 403)
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    try:
        client = _extract_client_payload(data)
    except ValueError as exc:
        return _fail(str(exc), 400)
    changed = False
    try:
        if 'total' in client:
            user.data_limit_mb = _total_to_mb(client.get('total'))
            changed = True
        if 'expiryTime' in client:
            user.expires_at = _expiry_time_to_dt(client.get('expiryTime'))
            changed = True
        if 'enable' in client:
            enabled = bool(client.get('enable')) and str(client.get('enable')).strip().lower() not in {'0', 'false'}
            user.enabled = enabled
            if enabled:
                user.disabled_reason = ''
            changed = True
        if 'limitIp' in client:
            user.connection_limit = max(1, int(client.get('limitIp') or 0) or 1)
            changed = True
        if client.get('password'):
            user.set_password(str(client['password']))
            user.l2tp_password = str(client['password'])
            user.cisco_password = str(client['password'])
            changed = True
    except ValueError as exc:
        return _fail(str(exc), 400)
    if changed:
        db.session.commit()
        try:
            sync_user(user, restart=False, changed_protocols=set(user.allowed_protocol_list() or user.protocol_list()), ensure_runtime=True)
        except Exception:
            db.session.rollback()
            return _fail('Failed to apply update', 500)
    log('xui_api', 'update_user', user.username)
    return _success({'id': 1, 'email': user.username, 'subscriptionUrl': subscription_url_for_user(user)})


@api_xui_bp.post('/panel/api/inbounds/delClient/<int:inbound_id>/<path:email>')
@require_auth
def del_client(inbound_id, email):
    owner = _owner()
    user = owner_user_query(owner).filter_by(username=str(email or '').strip()).first()
    if not user:
        return _fail('User not found', 404)
    username = user.username
    delete_user(user)
    log('xui_api', 'delete_user', username)
    return _success({'id': 1, 'email': username})


@api_xui_bp.post('/panel/api/inbounds/delDepletedClients/<int:inbound_id>')
@require_auth
def del_depleted_clients(inbound_id):
    owner = _owner()
    reason = volume_gate_reason(owner)
    if reason:
        return _fail('Action blocked: ' + reason, 403)
    removed = []
    for user in owner_user_query(owner).all():
        depleted = False
        if user.expires_at and user.expires_at < datetime.utcnow():
            depleted = True
        if not depleted and int(user.data_limit_mb or 0) > 0:
            limit_bytes = int(user.data_limit_mb) * _BYTES_PER_MB
            if int(user.used_total_bytes or 0) >= limit_bytes:
                depleted = True
        if depleted:
            removed.append(user.username)
            delete_user(user)
    log('xui_api', 'del_depleted_clients', f'removed={len(removed)}')
    return _success({'ids': [1], 'removed': removed})


@api_xui_bp.get('/sub/<path:sub_id>')
def subscription(sub_id):
    """Serve raw subscription content for a user-owned token (public)."""
    user = VpnUser.query.filter_by(subscription_token=str(sub_id or '').strip()).first()
    if not user:
        return _fail('Subscription not found', 404)
    from ..services.v17 import subscription_for_client
    try:
        body, mime, status = subscription_for_client(user, 'raw')
    except Exception:
        body = ''
        mime = 'text/plain; charset=utf-8'
        status = 200
    response = Response(body, status=status, mimetype=mime)
    response.headers['Cache-Control'] = 'no-store'
    return response
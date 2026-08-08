from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from ..core.extensions import db
from ..core.models import Admin, VpnUser, Node, Ticket, ActivityLog
from ..services.provisioning import sync_user, delete_user, log, service_status, user_access_status, user_usage_summary, subscription_url_for_user, active_protocols, normalize_user_protocols
from datetime import datetime, timedelta
import secrets
from ..services.license import filter_protocols_for_license
from ..services.password_policy import generate_user_password

api_bp = Blueprint('api', __name__)

def require_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get('X-API-KEY')
        admin = Admin.query.filter_by(api_key=key).first()
        if not admin and key != current_app.config['API_KEY']:
            return jsonify(success=False, error='invalid api key'), 401
        request.api_admin = admin
        return fn(*args, **kwargs)
    return wrapper

@api_bp.get('/status')
@require_api
def status():
    return jsonify(success=True, message='Ironpanel is online', services=service_status(), timestamp=datetime.utcnow().isoformat())

@api_bp.get('/users/list_all')
@require_api
def list_users():
    admin = request.api_admin
    q = VpnUser.query
    if admin and admin.role == 'sub_admin':
        q = q.filter_by(owner_id=admin.id)
    return jsonify(success=True, users=[serialize_user(u) for u in q.order_by(VpnUser.id.desc()).all()])

def _api_protocols_for_admin(admin, values):
    requested = filter_protocols_for_license(normalize_user_protocols(values or active_protocols(), allow_default=True))
    if admin and admin.role == 'sub_admin':
        allowed = set(admin.allowed_protocol_list())
        requested = [p for p in requested if p in allowed]
    return requested


@api_bp.post('/users/create')
@require_api
def create_user():
    data = request.json or {}
    username = data.get('username') or f'user{secrets.randbelow(99999)}'
    password = data.get('password') or generate_user_password()
    protocols = _api_protocols_for_admin(request.api_admin, data.get('protocols'))
    if not protocols:
        return jsonify(success=False, error='no permitted protocol selected for this reseller'), 400
    u = VpnUser(username=username,
                l2tp_password=data.get('l2tp_password') or password,
                cisco_password=data.get('cisco_password') or password,
                data_limit_mb=int(data.get('data_limit_mb') or 0),
                connection_limit=int(data.get('connection_limit') or 1),
                protocols=','.join(protocols),
                protocol_permissions=','.join(protocols),
                expires_at=datetime.utcnow()+timedelta(days=int(data.get('days') or 30)),
                owner_id=(request.api_admin.id if request.api_admin and request.api_admin.role == 'sub_admin' else None))
    u.set_password(password)
    db.session.add(u); db.session.commit(); sync_user(u); log('api','create_user',username)
    return jsonify(success=True, user=serialize_user(u), password=password)

@api_bp.post('/users/<int:user_id>/toggle')
@require_api
def toggle_user(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if request.api_admin and request.api_admin.role == 'sub_admin' and u.owner_id != request.api_admin.id:
        return jsonify(success=False, error='forbidden'), 403
    u.enabled = not u.enabled
    db.session.commit(); sync_user(u); log('api','toggle_user',u.username,str(u.enabled))
    return jsonify(success=True, user=serialize_user(u))


@api_bp.delete('/users/<int:user_id>')
@require_api
def api_delete_user(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if request.api_admin and request.api_admin.role == 'sub_admin' and u.owner_id != request.api_admin.id:
        return jsonify(success=False, error='forbidden'), 403
    username = u.username
    delete_user(u); log('api','delete_user',username)
    return jsonify(success=True, deleted=username)

@api_bp.get('/nodes')
@require_api
def nodes():
    return jsonify(success=True, nodes=[{'id':n.id,'name':n.name,'host':n.host,'config_domain':getattr(n,'config_domain',''),'ssl_domain':getattr(n,'ssl_domain',''),'health':n.health,'protocols':n.protocols} for n in Node.query.all()])

@api_bp.post('/tickets')
@require_api
def ticket_create():
    data = request.json or {}
    t = Ticket(subject=data.get('subject','Support request'), body=data.get('body',''), priority=data.get('priority','normal'), department=data.get('department','support'), user_id=data.get('user_id'), owner_id=getattr(request.api_admin,'id',None))
    db.session.add(t); db.session.commit()
    return jsonify(success=True, ticket_id=t.id)

@api_bp.get('/logs')
@require_api
def logs():
    rows = ActivityLog.query.order_by(ActivityLog.id.desc()).limit(200).all()
    return jsonify(success=True, logs=[{'actor':r.actor,'action':r.action,'target':r.target,'details':r.details,'created_at':r.created_at.isoformat()} for r in rows])

def serialize_user(u):
    ok, reason = user_access_status(u)
    usage = user_usage_summary(u)
    return {'id':u.id,'username':u.username,'enabled':u.enabled,'access_ok':ok,'access_reason':reason,'protocols':u.protocols.split(','),'data_limit_mb':u.data_limit_mb,'used_total_mb':usage['used_mb'],'used_total_raw_mb':usage['raw_used_mb'],'traffic_multiplier_enabled':usage['traffic_multiplier_enabled'],'traffic_multiplier_factor':usage['traffic_multiplier_factor'],'connection_limit':u.connection_limit,'expires_at':u.expires_at.isoformat() if u.expires_at else None,'subscription_url':subscription_url_for_user(u)}

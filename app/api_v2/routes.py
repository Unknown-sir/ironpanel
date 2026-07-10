from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from ..core.extensions import db
from ..core.models import ApiToken, VpnUser, Node, OnlineSession, Invoice
from ..services.provisioning import sync_user, delete_user, user_access_status, service_status
from ..services.v10 import refresh_online_sessions, server_metrics
import secrets

api_v2_bp=Blueprint('api_v2', __name__)

def require_token(fn):
    @wraps(fn)
    def w(*a, **kw):
        raw=(request.headers.get('Authorization','').replace('Bearer ','') or request.headers.get('X-API-TOKEN','')).strip()
        tok=ApiToken.query.filter_by(token=raw, enabled=True).first()
        if not tok: return jsonify(success=False, error='invalid token'), 401
        request.api_token=tok
        return fn(*a, **kw)
    return w

@api_v2_bp.get('/openapi.json')
def openapi():
    return jsonify(openapi='3.0.0', info={'title':'IronPanel API v2','version':'10.0'}, paths={'/api/v2/users':{},'/api/v2/nodes':{},'/api/v2/monitoring':{},'/api/v2/sessions':{}})

@api_v2_bp.get('/monitoring')
@require_token
def monitoring(): return jsonify(success=True, metrics=server_metrics(), services=service_status())

@api_v2_bp.get('/sessions')
@require_token
def sessions(): return jsonify(success=True, sessions=[{'id':s.id,'username':s.username,'protocol':s.protocol,'remote_ip':s.remote_ip,'country':s.country,'last_seen':s.last_seen.isoformat()} for s in refresh_online_sessions()])

@api_v2_bp.get('/users')
@require_token
def users(): return jsonify(success=True, users=[serialize_user(u) for u in VpnUser.query.order_by(VpnUser.id.desc()).all()])

@api_v2_bp.post('/users')
@require_token
def create_user():
    d=request.json or {}; password=d.get('password') or secrets.token_urlsafe(10)
    days=int(d.get('days') or 0)
    u=VpnUser(username=d.get('username') or 'user'+secrets.token_hex(3), data_limit_mb=int(d.get('data_limit_mb') or 0), expires_at=None if days<=0 else datetime.utcnow()+timedelta(days=days), l2tp_password=d.get('l2tp_password') or password, cisco_password=d.get('cisco_password') or password, protocols=','.join(d.get('protocols') or ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2']), protocol_permissions=','.join(d.get('protocols') or ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2']))
    u.set_password(password); db.session.add(u); db.session.commit(); sync_user(u)
    return jsonify(success=True, user=serialize_user(u), password=password)

@api_v2_bp.patch('/users/<int:user_id>')
@require_token
def edit_user(user_id):
    u=VpnUser.query.get_or_404(user_id); d=request.json or {}
    for k in ['enabled','data_limit_mb','connection_limit','allowed_devices']:
        if k in d: setattr(u,k,d[k])
    if 'days' in d:
        days=int(d.get('days') or 0); u.expires_at=None if days<=0 else datetime.utcnow()+timedelta(days=days)
    if 'password' in d and d['password']: u.set_password(d['password'])
    db.session.commit(); sync_user(u); return jsonify(success=True,user=serialize_user(u))

@api_v2_bp.delete('/users/<int:user_id>')
@require_token
def del_user(user_id):
    u=VpnUser.query.get_or_404(user_id); name=u.username; delete_user(u); return jsonify(success=True, deleted=name)

@api_v2_bp.get('/nodes')
@require_token
def nodes(): return jsonify(success=True, nodes=[{'id':n.id,'name':n.name,'host':n.host,'health':n.health,'protocols':n.protocols} for n in Node.query.all()])

def serialize_user(u):
    ok,reason=user_access_status(u)
    return {'id':u.id,'username':u.username,'enabled':u.enabled,'access_ok':ok,'access_reason':reason,'used_total_mb':u.used_total_mb,'data_limit_mb':u.data_limit_mb,'expires_at':u.expires_at.isoformat() if u.expires_at else None,'subscription_token':u.subscription_token}


# v12/v13 API additions: JWT-like token issuing, invoices, plans, health details
@api_v2_bp.post('/auth/token')
def jwt_login():
    from ..core.models import Admin
    from itsdangerous import URLSafeTimedSerializer
    d=request.json or {}; a=Admin.query.filter_by(username=d.get('username','')).first()
    if not a or not a.check_password(d.get('password','')): return jsonify(success=False,error='invalid credentials'),401
    s=URLSafeTimedSerializer('ironpanel-api-v2')
    return jsonify(success=True, token=s.dumps({'admin_id':a.id,'ts':datetime.utcnow().isoformat()}), token_type='Bearer')

@api_v2_bp.get('/plans')
@require_token
def api_plans():
    from ..core.models import ServicePlan
    return jsonify(success=True, plans=[{'id':p.id,'name':p.name,'days':p.days,'traffic_gb':p.traffic_gb,'price':p.price,'currency':p.currency,'protocols':p.protocols} for p in ServicePlan.query.filter_by(active=True).all()])

@api_v2_bp.post('/invoices')
@require_token
def api_create_invoice():
    from ..services.v12 import create_invoice_for_user
    d=request.json or {}; inv=create_invoice_for_user(d.get('user_id'), d.get('amount'), d.get('description',''), d.get('currency','USD'))
    return jsonify(success=True, invoice_id=inv.id, status=inv.status)

@api_v2_bp.get('/health/details')
@require_token
def api_health_details():
    from ..services.provisioning import service_status_detailed
    return jsonify(success=True, health=service_status_detailed())

# ---------------- v17 API additions ----------------
@api_v2_bp.post('/node/heartbeat')
def node_heartbeat():
    from ..services.v17 import update_node_from_heartbeat
    token=(request.headers.get('X-NODE-TOKEN') or '').strip()
    node,err=update_node_from_heartbeat(token, request.json or {})
    if err: return jsonify(success=False, error=err), 401
    return jsonify(success=True, node_id=node.id, jobs=[])

@api_v2_bp.get('/v17/nodes')
@require_token
def api_v17_nodes():
    from ..services.v17 import node_health_summary
    return jsonify(success=True, nodes=node_health_summary())

@api_v2_bp.get('/v17/subscription/<int:user_id>/<client_type>')
@require_token
def api_v17_subscription(user_id, client_type):
    from ..services.v17 import subscription_for_client
    u=VpnUser.query.get_or_404(user_id)
    body,mime,status=subscription_for_client(u, client_type)
    return jsonify(success=status==200, content_type=mime, body=body)

@api_v2_bp.get('/v17/health')
@require_token
def api_v17_full_health():
    from ..services.v17 import v17_health_checks
    return jsonify(success=True, data=v17_health_checks())

@api_v2_bp.get('/v17/outbound')
@require_token
def api_v17_outbound():
    from ..core.models import OutboundProfile, ProtocolOutboundMap
    return jsonify(success=True, profiles=[{'id':p.id,'name':p.name,'type':p.profile_type,'enabled':p.enabled,'priority':p.priority,'last_test_status':p.last_test_status} for p in OutboundProfile.query.all()], maps=[{'protocol':m.protocol,'profile_id':m.outbound_profile_id,'node_id':m.node_id,'enabled':m.enabled} for m in ProtocolOutboundMap.query.all()])

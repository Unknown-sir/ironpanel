from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, send_file
from ..core.extensions import db
from ..core.models import ApiToken, VpnUser, Node, OnlineSession, Invoice, Admin
from ..services.provisioning import sync_user, delete_user, user_access_status, service_status, user_usage_summary, subscription_url_for_user, active_protocols, normalize_user_protocols, reconcile_reseller_access, set_reseller_enabled
from ..services.v10 import refresh_online_sessions, server_metrics
import io, secrets
from ..services.license import filter_protocols_for_license
from ..services.password_policy import generate_user_password
from ..services.speed_limit import normalize_speed_limit_mbps, apply_speed_limits_runtime
from ..services.reseller_api import resolve_api_token, volume_gate_reason, create_block_reason, owner_user_query, can_manage_user, owner_protocols

api_v2_bp=Blueprint('api_v2', __name__)

def require_token(fn):
    @wraps(fn)
    def w(*a, **kw):
        raw=(request.headers.get('Authorization','').replace('Bearer ','') or request.headers.get('X-API-TOKEN','')).strip()
        tok, owner = resolve_api_token(raw, allowed_types=['v2'])
        if not tok: return jsonify(success=False, error='invalid token'), 401
        request.api_token=tok
        request.api_owner=owner
        return fn(*a, **kw)
    return w

@api_v2_bp.get('/openapi.json')
def openapi():
    return jsonify(openapi='3.0.0', info={'title':'IronPanel API v2','version':'19.10.25'}, paths={'/api/v2/users':{},'/api/v2/users/{user_id}':{},'/api/v2/users/by-username/{username}':{},'/api/v2/plans':{},'/api/v2/nodes':{},'/api/v2/monitoring':{},'/api/v2/sessions':{},'/api/v2/resellers':{},'/api/v2/v17/subscription/{user_id}/{client_type}':{}})

@api_v2_bp.get('/monitoring')
@require_token
def monitoring(): return jsonify(success=True, metrics=server_metrics(), services=service_status())

@api_v2_bp.get('/sessions')
@require_token
def sessions(): return jsonify(success=True, sessions=[{'id':s.id,'username':s.username,'protocol':s.protocol,'remote_ip':s.remote_ip,'country':s.country,'last_seen':s.last_seen.isoformat()} for s in refresh_online_sessions()])

@api_v2_bp.get('/users')
@require_token
def users():
    owner=getattr(request, 'api_owner', None)
    return jsonify(success=True, users=[serialize_user(u) for u in owner_user_query(owner).order_by(VpnUser.id.desc()).all()])


@api_v2_bp.get('/users/<int:user_id>')
@require_token
def get_user(user_id):
    owner=getattr(request, 'api_owner', None)
    u=owner_user_query(owner).filter_by(id=user_id).first_or_404()
    return jsonify(success=True, user=serialize_user(u))

@api_v2_bp.get('/users/by-username/<path:username>')
@require_token
def get_user_by_username(username):
    owner=getattr(request, 'api_owner', None)
    u=owner_user_query(owner).filter_by(username=username).first_or_404()
    return jsonify(success=True, user=serialize_user(u))

@api_v2_bp.post('/users')
@require_token
def create_user():
    owner=getattr(request, 'api_owner', None)
    reason=create_block_reason(owner)
    if reason:
        return jsonify(success=False, error='reseller blocked: '+reason), 403
    d=request.json or {}; password=d.get('password') or generate_user_password()
    days=int(d.get('days') or 0)
    protocols = filter_protocols_for_license(normalize_user_protocols(d.get('protocols') or [], allow_default=('protocols' not in d)))
    protocols = owner_protocols(owner, protocols)
    if not protocols:
        return jsonify(success=False, error='at least one protocol is required'), 400
    u=VpnUser(username=d.get('username') or 'user'+secrets.token_hex(3), owner_id=owner.id if owner else None, data_limit_mb=int(d.get('data_limit_mb') or 0), expires_at=None if days<=0 else datetime.utcnow()+timedelta(days=days), l2tp_password=d.get('l2tp_password') or password, cisco_password=d.get('cisco_password') or password, protocols=','.join(protocols), protocol_permissions=','.join(protocols), speed_limit_mbps=normalize_speed_limit_mbps(d.get('speed_limit_mbps', 0)))
    u.set_password(password); db.session.add(u); db.session.commit(); sync_user(u)
    if int(getattr(u, 'speed_limit_mbps', 0) or 0) > 0: apply_speed_limits_runtime()
    return jsonify(success=True, user=serialize_user(u), password=password)

@api_v2_bp.patch('/users/<int:user_id>')
@require_token
def edit_user(user_id):
    owner=getattr(request, 'api_owner', None)
    u=owner_user_query(owner).filter_by(id=user_id).first_or_404(); d=request.json or {}
    if 'enabled' in d or 'data_limit_mb' in d or 'days' in d or 'protocols' in d or 'speed_limit_mbps' in d:
        reason=volume_gate_reason(owner)
        if reason:
            return jsonify(success=False, error='reseller blocked: '+reason), 403
    affected=set(u.allowed_protocol_list() or u.protocol_list() or active_protocols())
    for k in ['enabled','data_limit_mb','connection_limit','allowed_devices']:
        if k in d: setattr(u,k,d[k])
    if 'speed_limit_mbps' in d:
        u.speed_limit_mbps = normalize_speed_limit_mbps(d.get('speed_limit_mbps'))
    if 'protocols' in d:
        protocols = filter_protocols_for_license(normalize_user_protocols(d.get('protocols') or []))
        protocols = owner_protocols(owner, protocols)
        if not protocols:
            return jsonify(success=False, error='at least one protocol is required'), 400
        u.protocols = ','.join(protocols)
        u.protocol_permissions = ','.join(protocols)
        affected |= set(protocols)
    if 'days' in d:
        days=int(d.get('days') or 0); u.expires_at=None if days<=0 else datetime.utcnow()+timedelta(days=days)
    if 'password' in d and d['password']: u.set_password(d['password'])
    db.session.commit(); sync_user(u, changed_protocols=affected)
    if 'speed_limit_mbps' in d or 'enabled' in d: apply_speed_limits_runtime()
    return jsonify(success=True,user=serialize_user(u))

@api_v2_bp.delete('/users/<int:user_id>')
@require_token
def del_user(user_id):
    owner=getattr(request, 'api_owner', None)
    u=owner_user_query(owner).filter_by(id=user_id).first_or_404(); name=u.username; delete_user(u); return jsonify(success=True, deleted=name)


@api_v2_bp.get('/resellers')
@require_token
def api_resellers():
    if getattr(request, 'api_owner', None):
        return jsonify(success=False, error='forbidden'), 403
    rows=[]
    for r in Admin.query.filter_by(role='sub_admin').order_by(Admin.id.desc()).all():
        users=VpnUser.query.filter_by(owner_id=r.id).all()
        rows.append({'id':r.id,'username':r.username,'enabled':bool(r.enabled),'panel_path':r.panel_path,'user_limit':r.user_limit,'traffic_quota_gb':r.traffic_quota_gb,'reseller_protocols':r.allowed_protocol_list(),'users':len(users),'used_mb':sum(int(u.used_total_mb or 0) for u in users),'allocated_mb':sum(int(u.data_limit_mb or 0) for u in users)})
    return jsonify(success=True, resellers=rows)

@api_v2_bp.patch('/resellers/<int:reseller_id>')
@require_token
def api_reseller_update(reseller_id):
    if getattr(request, 'api_owner', None):
        return jsonify(success=False, error='forbidden'), 403
    r=Admin.query.filter_by(id=reseller_id, role='sub_admin').first_or_404()
    d=request.json or {}
    requested_enabled = bool(d.get('enabled')) if 'enabled' in d else None
    for k in ['user_limit','traffic_quota_gb','panel_path']:
        if k in d:
            setattr(r, k, d[k])
    if 'reseller_protocols' in d:
        protocols = filter_protocols_for_license(normalize_user_protocols(d.get('reseller_protocols') or []))
        if not protocols:
            return jsonify(success=False, error='at least one reseller protocol is required'), 400
        r.reseller_protocols = ','.join(protocols)
    if d.get('password'):
        r.set_password(d['password'])
    db.session.commit()
    if requested_enabled is None:
        reconcile_reseller_access(r, source='api-v2-edit', sync_runtime=True)
    else:
        set_reseller_enabled(r, requested_enabled, source='api-v2')
    return jsonify(success=True, reseller={'id':r.id,'username':r.username,'enabled':bool(r.enabled),'panel_path':r.panel_path,'user_limit':r.user_limit,'traffic_quota_gb':r.traffic_quota_gb,'reseller_protocols':r.allowed_protocol_list()})

@api_v2_bp.get('/nodes')
@require_token
def nodes(): return jsonify(success=True, nodes=[{'id':n.id,'name':n.name,'host':n.host,'config_domain':getattr(n,'config_domain',''),'ssl_domain':getattr(n,'ssl_domain',''),'health':n.health,'protocols':n.protocols} for n in Node.query.all()])

def serialize_user(u):
    ok,reason=user_access_status(u)
    usage=user_usage_summary(u)
    protocols = u.allowed_protocol_list() or u.protocol_list() or []
    return {'id':u.id,'username':u.username,'enabled':u.enabled,'access_ok':ok,'access_reason':reason,'protocols':protocols,'protocol_permissions':u.protocol_permissions or u.protocols or '','used_total_mb':usage['used_mb'],'used_total_raw_mb':usage['raw_used_mb'],'traffic_multiplier_enabled':usage['traffic_multiplier_enabled'],'traffic_multiplier_factor':usage['traffic_multiplier_factor'],'data_limit_mb':u.data_limit_mb,'speed_limit_mbps':int(getattr(u,'speed_limit_mbps',0) or 0),'expires_at':u.expires_at.isoformat() if u.expires_at else None,'subscription_token':u.subscription_token,'subscription_url':subscription_url_for_user(u)}


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

@api_v2_bp.get('/node/ping')
def node_ping():
    return jsonify(success=True, service='ironpanel-master', node_api=True, version='19.10.21')

@api_v2_bp.get('/node/package')
def node_package():
    """Download the current panel's node runtime using a valid node token."""
    token=(request.headers.get('X-NODE-TOKEN') or '').strip()
    node=Node.query.filter_by(api_key=token).first()
    if not node:
        return jsonify(success=False, error='invalid node token'), 401
    from ..services.v17 import node_package_bytes, V17_VERSION
    payload=node_package_bytes()
    response=send_file(
        io.BytesIO(payload),
        mimetype='application/gzip',
        as_attachment=True,
        download_name=f'ironpanel-node-runtime-{V17_VERSION}.tar.gz',
        max_age=0,
    )
    response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
    response.headers['X-IronPanel-Version']=V17_VERSION
    return response


@api_v2_bp.post('/node/heartbeat')
def node_heartbeat():
    from ..services.v17 import update_node_from_heartbeat
    token=(request.headers.get('X-NODE-TOKEN') or '').strip()
    payload=request.json or {}
    node,err=update_node_from_heartbeat(token, payload)
    if err: return jsonify(success=False, error=err), 401
    # Installer connectivity probes must not lease/mark real jobs as running.
    if bool(payload.get('probe')):
        return jsonify(success=True, node_id=node.id, jobs=[], probe=True)
    from ..services.node_gateway import heartbeat_jobs_for_node
    return jsonify(success=True, node_id=node.id, jobs=heartbeat_jobs_for_node(node))


@api_v2_bp.post('/node/job-result')
def node_job_result():
    from ..services.node_gateway import complete_node_job
    token=(request.headers.get('X-NODE-TOKEN') or '').strip()
    d=request.json or {}
    job,err=complete_node_job(token, int(d.get('job_id') or 0), bool(d.get('ok', True)), d.get('output',''), d.get('metrics') or {})
    if err: return jsonify(success=False, error=err), 400
    return jsonify(success=True, job_id=job.id, status=job.status)

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

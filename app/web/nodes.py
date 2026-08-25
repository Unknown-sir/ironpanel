"""Node management: Direct Location nodes, auto SSH installer, gateway, cluster."""
import json
import re
from datetime import datetime

from flask import current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import Node, OnlineSession, Port, ProtocolOutboundMap, RemoteJob, VpnUser
from ..services.provisioning import active_protocols, log
from ..services.license import feature_allowed
from ..services.node_schema_guard import ensure_node_page_schema, node_schema_error_summary
from ..services.node_auto_installer import (
    clear_node_ssh_credentials,
    node_auto_installer_allowed,
    node_has_saved_ssh_credentials,
    queue_auto_node_install,
    save_node_ssh_credentials,
)
from ..services.node_gateway import (
    apply_node_gateway_runtime,
    force_protocols_to_node,
    node_gateway_settings,
    node_gateway_status,
    node_sync_status_summary,
    queue_all_user_sync,
    queue_full_node_sync,
    queue_node_health_check,
    rebalance_users,
    reset_node_gateway_to_local,
    save_node_gateway_settings,
)
from ..services.v10 import run_remote_job
from ..services.v17 import (
    node_health_summary,
    node_install_command,
    run_full_backup_v17,
    validate_xray_before_delivery,
    v17_health_checks,
)
from .common import _allowed_form_protocols
from . import web_bp


def _node_subscription_ports(node):
    """Template helper for Direct Location node ports.

    v19.9.7: This function used to be missing from web.py while the nodes
    template called it, causing a 500 on /nodes. Keep it local and defensive so
    the page renders even before optional Direct Location columns are migrated.
    """
    try:
        from ..services.direct_locations import DIRECT_PROTOCOLS, node_direct_port
    except Exception:
        DIRECT_PROTOCOLS = active_protocols()
        node_direct_port = None
    out = {}
    for proto in (DIRECT_PROTOCOLS or active_protocols() or []):
        try:
            port = node_direct_port(node, proto) if node_direct_port else 0
        except Exception:
            port = 0
        out[proto] = port or ''
    return out


def _node_ssl_domain_from_form(form, config_domain='', host=''):
    """Return the node-only ACME/TLS domain.

    It may differ from the public config domain in tunnel scenarios.  The value
    is only used on the node for certificate issuance and service TLS paths;
    subscription host/link delivery keeps using config_domain.
    """
    raw = (form.get('ssl_domain') or form.get('node_ssl_domain') or '').strip()
    if not raw:
        raw = (config_domain or host or '').strip()
    raw = re.sub(r'^https?://', '', raw, flags=re.I).split('/')[0].strip()
    if ':' in raw and not raw.startswith('['):
        h, _, port = raw.rpartition(':')
        if port.isdigit():
            raw = h
    return raw.strip('[]').lower()


def _node_subscription_ports_from_form(form):
    """Serialize per-protocol Direct Location ports from a form."""
    try:
        from ..services.direct_locations import DIRECT_PROTOCOLS
    except Exception:
        DIRECT_PROTOCOLS = active_protocols()
    data = {}
    for proto in (DIRECT_PROTOCOLS or active_protocols() or []):
        raw = (form.get(f'sub_port_{proto}') or '').strip()
        if not raw:
            continue
        try:
            port = int(raw)
        except Exception:
            continue
        if 1 <= port <= 65535:
            data[proto] = port
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def _empty_node_summary():
    return {'nodes': 0, 'online_nodes': 0, 'queued_jobs': 0, 'running_jobs': 0, 'failed_jobs': 0}


def _safe_nodes_page(error=None):
    if error:
        current_app.logger.exception('Nodes page failed: %s', error)
        db.session.rollback()
        flash('صفحه Nodes نتوانست اطلاعات نودها را بخواند. Migration/Schema Guard اجرا شد؛ اگر خطا باقی ماند upgrade_db_safe را اجرا کن.')
    try:
        ensure_node_page_schema()
    except Exception as schema_exc:
        current_app.logger.exception('Node schema guard failed: %s', schema_exc)
        flash('Node schema guard نتوانست دیتابیس را کامل به‌روزرسانی کند: ' + node_schema_error_summary(schema_exc))
    try:
        return render_template('nodes.html', nodes=Node.query.order_by(Node.name).all(), summary=node_sync_status_summary(), node_subscription_ports=_node_subscription_ports, node_page_error=(str(error) if error else ''))
    except Exception as final_exc:
        current_app.logger.exception('Nodes fallback render failed: %s', final_exc)
        db.session.rollback()
        return render_template('nodes.html', nodes=[], summary=_empty_node_summary(), node_subscription_ports=_node_subscription_ports, node_page_error=node_schema_error_summary(final_exc))


@web_bp.route('/nodes', methods=['GET','POST'])
@login_required
def nodes():
    """v19.9.8 rebuilt Nodes page: Direct Location first, auto SSH install, synced quota."""
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if not feature_allowed('nodes'):
        flash('بخش Node فقط روی لایسنس Pro/Admin فعال است.')
        return redirect(url_for('web.upgrade'))
    try:
        ensure_node_page_schema()
    except Exception as exc:
        current_app.logger.exception('Node schema guard failed before /nodes: %s', exc)
        flash('Migration داخلی نود کامل نشد: ' + node_schema_error_summary(exc))
    if request.method == 'POST':
        try:
            protocols = _allowed_form_protocols(request.form.getlist('protocols') or [])
            if not protocols:
                flash('حداقل یک پروتکل برای نود انتخاب کن.')
                return redirect(url_for('web.nodes'))
            host=(request.form.get('host') or '').strip()
            name=(request.form.get('node_name') or request.form.get('name') or '').strip()
            server_name=(request.form.get('server_name') or request.form.get('location') or '').strip()
            config_domain=(request.form.get('config_domain') or request.form.get('subscription_host') or host).strip()
            ssl_domain=_node_ssl_domain_from_form(request.form, config_domain, host)
            if not host or not name or not config_domain:
                flash('آدرس سرور، نام نود و دامنه کانفیگ الزامی است.')
                return redirect(url_for('web.nodes'))
            n = Node(
                name=name,
                host=host,
                location=server_name,
                server_name=server_name,
                config_domain=config_domain,
                ssl_domain=ssl_domain,
                protocols=','.join(protocols),
                weight=max(1, int(request.form.get('weight') or 100)),
                max_users=max(0, int(request.form.get('max_users') or 0)),
                gateway_enabled=False,
                delivery_mode='direct',
                subscription_enabled=True,
                subscription_host=config_domain,
                subscription_label=(request.form.get('subscription_label') or server_name or name).strip(),
                subscription_flag=(request.form.get('subscription_flag') or '').strip()[:16],
                subscription_ports_json=_node_subscription_ports_from_form(request.form),
                ssh_host=(request.form.get('ssh_host') or host).strip(),
            )
            db.session.add(n); db.session.flush()
            # Save encrypted SSH credentials when provided. The actual install is queued.
            if request.form.get('ssh_username') or request.form.get('ssh_password') or request.form.get('ssh_private_key'):
                save_node_ssh_credentials(n, request.form, commit=False)
            db.session.commit()
            # Always queue full node sync so users/configs/ports are ready as soon as the agent connects.
            try:
                queue_full_node_sync(n.id, protocols, reason='node-create-direct-location', force=True)
            except Exception as exc:
                current_app.logger.warning('queue_full_node_sync failed for new node %s: %s', n.id, exc)
            try:
                if node_auto_installer_allowed() and node_has_saved_ssh_credentials(n) and request.form.get('auto_install', '1') == '1':
                    queue_auto_node_install(n, request.url_root, reason='node-create')
                    flash('نود ثبت شد؛ نصب خودکار SSH، نصب هسته‌ها، Sync کانفیگ و Sync کاربران در صف اجرا قرار گرفت.')
                else:
                    flash('نود ثبت شد. اگر اطلاعات SSH ذخیره نکردی، از دکمه Install/Repair برای نصب خودکار استفاده کن.')
            except Exception as exc:
                current_app.logger.exception('auto install queue failed: %s', exc)
                flash('نود ثبت شد، اما صف نصب خودکار ساخته نشد: ' + str(exc))
            log(current_user.username,'node_add_direct',host)
            return redirect(url_for('web.nodes'))
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Node add failed: %s', exc)
            flash('افزودن نود انجام نشد: ' + node_schema_error_summary(exc))
            return redirect(url_for('web.nodes'))
    return _safe_nodes_page()


@web_bp.route('/nodes/<int:node_id>/edit', methods=['GET','POST'])
@login_required
def node_edit(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    try:
        ensure_node_page_schema()
    except Exception as exc:
        current_app.logger.exception('Node schema guard failed before edit: %s', exc)
        flash('Migration داخلی نود کامل نشد: ' + node_schema_error_summary(exc))
    node = Node.query.get_or_404(node_id)
    if request.method == 'POST':
        protocols=_allowed_form_protocols(request.form.getlist('protocols') or [])
        if not protocols:
            flash('حداقل یک پروتکل انتخاب کن.')
            return redirect(url_for('web.node_edit', node_id=node.id))
        node.name = (request.form.get('node_name') or request.form.get('name') or '').strip() or node.name
        node.host = (request.form.get('host') or '').strip() or node.host
        server_name=(request.form.get('server_name') or '').strip()
        node.server_name = server_name
        node.location = server_name
        node.config_domain = (request.form.get('config_domain') or request.form.get('subscription_host') or node.host or '').strip()
        node.ssl_domain = _node_ssl_domain_from_form(request.form, node.config_domain, node.host)
        node.protocols = ','.join(protocols)
        node.weight = max(1, int(request.form.get('weight') or node.weight or 100))
        node.max_users = max(0, int(request.form.get('max_users') or node.max_users or 0))
        node.gateway_enabled = False
        node.delivery_mode = 'direct'
        node.subscription_enabled = True
        node.subscription_host = node.config_domain or node.host
        node.subscription_label = (request.form.get('subscription_label') or node.server_name or node.name or '').strip()
        node.subscription_flag = (request.form.get('subscription_flag') or '').strip()[:16]
        node.subscription_ports_json = _node_subscription_ports_from_form(request.form)
        if request.form.get('ssh_username') or request.form.get('ssh_password') or request.form.get('ssh_private_key'):
            save_node_ssh_credentials(node, request.form, commit=False)
        db.session.commit()
        try:
            queue_full_node_sync(node.id, protocols, reason='node-edit-direct-location', force=True)
        except Exception:
            db.session.rollback()
        log(current_user.username, 'node_edit_direct', node.host)
        flash('نود به‌روزرسانی شد؛ Sync کانفیگ‌ها و کاربران در صف قرار گرفت.')
        return redirect(url_for('web.nodes'))
    return render_template('node_edit.html', node=node, node_subscription_ports=_node_subscription_ports(node))

@web_bp.route('/nodes/<int:node_id>/delete', methods=['POST'])
@login_required
def node_delete(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    node = Node.query.get_or_404(node_id)
    host = node.host
    # Keep users safe: remove their fixed node assignment and let routing fall back
    # to Auto/Local instead of pointing at a deleted server.
    VpnUser.query.filter_by(preferred_node_id=node.id).update({'preferred_node_id': None, 'node_mode': 'auto', 'node_sync_status': 'local', 'node_sync_error': ''})
    OnlineSession.query.filter_by(node_id=node.id).update({'node_id': None})
    Port.query.filter_by(node_id=node.id).update({'node_id': None})
    ProtocolOutboundMap.query.filter_by(node_id=node.id).update({'node_id': None})
    RemoteJob.query.filter_by(node_id=node.id).delete()
    db.session.delete(node)
    db.session.commit()
    log(current_user.username, 'node_delete', host)
    flash('نود حذف شد و وابستگی‌های آن پاک‌سازی شد')
    return redirect(url_for('web.nodes'))


@web_bp.route('/nodes/<int:node_id>/force-protocols', methods=['POST'])
@login_required
def node_force_protocols(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    protocols=_allowed_form_protocols(request.form.getlist('protocols') or [])
    if not protocols:
        flash('حداقل یک پروتکل را برای اتصال فقط به این نود انتخاب کن.')
        return redirect(url_for('web.nodes'))
    try:
        result=force_protocols_to_node(node_id, protocols)
    except Exception as exc:
        db.session.rollback()
        result={'ok':False, 'message':'Force protocol failed: '+str(exc)}
    log(current_user.username, 'node_force_protocols', str(node_id), result.get('message',''))
    flash(result.get('message','Rules updated'))
    return redirect(url_for('web.node_gateway_manager'))

@web_bp.route('/cluster', methods=['GET','POST'])
@login_required
def cluster():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        action=request.form.get('action')
        if action in ('restart_panel','restart_vpn','repair','backup','update'):
            job=run_remote_job(int(request.form.get('node_id') or 0) or None, action)
            flash(f'Job {job.id}: {job.status}')
        else:
            n=Node(name=request.form['name'], host=request.form['host'], protocols=','.join(plan_protocols), health='pending')
            db.session.add(n); db.session.commit(); flash('Node added')
        return redirect(url_for('web.cluster'))
    return render_template('cluster.html', nodes=Node.query.all(), jobs=RemoteJob.query.order_by(RemoteJob.id.desc()).limit(50).all())

# ---------------- IronPanel v17: Enterprise nodes, wizards ----------------

@web_bp.route('/v17/nodes')
@login_required
def v17_nodes():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if not feature_allowed('nodes'):
        flash('بخش Node فقط روی لایسنس Pro فعال است.')
        return redirect(url_for('web.upgrade'))
    return render_template('v17_nodes.html', nodes=node_health_summary())

@web_bp.route('/nodes/<int:node_id>/install')
@login_required
def node_install(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    n=Node.query.get_or_404(node_id)
    return render_template('node_install.html', node=n, command=node_install_command(n, request.url_root))


@web_bp.route('/nodes/<int:node_id>/auto-install', methods=['POST'])
@login_required
def node_auto_install(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    if not node_auto_installer_allowed():
        flash('نصب خودکار نود فقط برای لایسنس‌های Pro و Admin فعال است.')
        return redirect(url_for('web.upgrade'))
    node = Node.query.get_or_404(node_id)
    action = request.form.get('action', 'run')
    if action == 'clear_credentials':
        clear_node_ssh_credentials(node)
        log(current_user.username, 'node_ssh_credentials_clear', node.host)
        flash('اطلاعات SSH ذخیره‌شده پاک شد.')
        return redirect(url_for('web.nodes'))
    try:
        if request.form.get('ssh_host') or request.form.get('ssh_username') or request.form.get('ssh_password') or request.form.get('ssh_private_key'):
            save_node_ssh_credentials(node, request.form)
            log(current_user.username, 'node_ssh_credentials_save', node.host)
        if action == 'save_credentials':
            flash('اطلاعات SSH نود به‌صورت رمزنگاری‌شده ذخیره شد.')
            return redirect(url_for('web.nodes'))
        if not node_has_saved_ssh_credentials(node):
            flash('برای نصب خودکار باید ابتدا اطلاعات SSH را ذخیره کنی.')
            return redirect(url_for('web.nodes'))
        job = queue_auto_node_install(node, request.url_root, reason='manual')
        log(current_user.username, 'node_auto_install_queued', node.host, str(job.id))
        flash('نصب خودکار نود در صف اجرا قرار گرفت. نتیجه از همین کارت نود و لاگ نصب قابل مشاهده است.')
    except Exception as exc:
        db.session.rollback()
        log(current_user.username, 'node_auto_install_error', node.host, str(exc)[:1000])
        flash('خطای نصب خودکار نود: ' + str(exc))
    return redirect(url_for('web.nodes'))

@web_bp.route('/nodes/<int:node_id>/check', methods=['POST'])
@login_required
def node_check(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    n=Node.query.get_or_404(node_id)
    if n.last_seen and (datetime.utcnow()-n.last_seen).total_seconds() < 180:
        n.health='online'; flash('نود آنلاین است')
    else:
        n.health='offline'; flash('نود در ۳ دقیقه اخیر heartbeat ارسال نکرده است')
    db.session.commit(); return redirect(url_for('web.nodes'))

@web_bp.route('/api/v17/health')
@login_required
def api_v17_health():
    return jsonify(v17_health_checks())

@web_bp.route('/wizards', methods=['GET','POST'])
@login_required
def v17_wizards():
    if request.method=='POST':
        action=request.form.get('action')
        if action=='xray_validate':
            ok,detail=validate_xray_before_delivery(); flash(('Xray معتبر است: ' if ok else 'Xray خطا دارد: ')+detail[:500])
        elif action=='backup_now':
            p=run_full_backup_v17(); flash('بکاپ ساخته شد: '+p.name)
        elif action=='sync_users':
            from ..services.provisioning import sync_all_users
            sync_all_users(restart=True); flash('همه کاربران و پروتکل‌ها sync شدند')
        return redirect(url_for('web.v17_wizards'))
    return render_template('v17_wizards.html')

@web_bp.route('/nodes/<int:node_id>/sync', methods=['POST'])
@login_required
def node_sync(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    node = Node.query.get_or_404(node_id)
    count = queue_full_node_sync(node.id, [x for x in (node.protocols or '').split(',') if x], reason='manual-node-sync', force=True)
    flash(f'{count} job برای نصب هسته، Sync کانفیگ پروتکل‌ها و Sync کاربران روی {node.name} ساخته شد')
    return redirect(url_for('web.nodes'))

@web_bp.route('/nodes/<int:node_id>/ensure', methods=['POST'])
@login_required
def node_ensure(node_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    node = Node.query.get_or_404(node_id)
    queue_full_node_sync(node.id, [x for x in (node.protocols or '').split(',') if x], reason='manual-ensure', force=True)
    queue_node_health_check(node.id)
    flash('نصب/Repair هسته‌ها، Sync کانفیگ پروتکل‌ها و Sync کاربران برای نود صف شد')
    return redirect(url_for('web.nodes'))

@web_bp.route('/nodes/sync-all', methods=['POST'])
@login_required
def nodes_sync_all():
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    count = queue_all_user_sync()
    flash(f'{count} job برای sync همه کاربران روی نودهای مقصد ساخته شد')
    return redirect(url_for('web.node_gateway_manager'))

@web_bp.route('/nodes/rebalance', methods=['POST'])
@login_required
def nodes_rebalance():
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.dashboard'))
    result = rebalance_users()
    flash(f"Rebalance انجام شد. کاربران منتقل‌شده: {result.get('moved',0)} | jobها: {result.get('queued_jobs',0)}")
    return redirect(url_for('web.node_gateway_manager'))

# ---------------- IronPanel v19.5.0: Pro full Node Gateway / load balancer ----------------

@web_bp.route('/node-gateway', methods=['GET','POST'])
@login_required
def node_gateway_manager():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if not feature_allowed('nodes'):
        flash('Node Gateway فقط روی لایسنس Pro فعال است.')
        return redirect(url_for('web.upgrade'))
    if request.method == 'POST':
        action = request.form.get('action') or 'save'
        if action == 'reset_to_local':
            result = reset_node_gateway_to_local()
            log(current_user.username, 'node_gateway_reset_to_local', 'gateway', result.get('message',''))
            flash(result.get('message', 'Node Gateway reset شد'))
            return redirect(url_for('web.node_gateway_manager'))
        save_node_gateway_settings(request.form)
        result = apply_node_gateway_runtime()
        log(current_user.username, 'node_gateway_apply', 'gateway', result.get('message',''))
        flash(result.get('message', 'Node Gateway ذخیره شد'))
        return redirect(url_for('web.node_gateway_manager'))
    return render_template('node_gateway.html', settings=node_gateway_settings(), status=node_gateway_status(), nodes=Node.query.order_by(Node.name).all())

"""VPN user management: create/edit/bulk ops, configs, limits and usage."""
import json
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import ActivityLog, DailyUsage, Node, ServicePlan, VpnUser
from ..services.provisioning import (
    active_protocols,
    apply_runtime_configs,
    auto_disabled_cleanup_users,
    automatic_disable_reason,
    collect_usage_from_runtime,
    delete_user,
    delete_users_bulk,
    enforce_ip_limits,
    enforce_usage_limits,
    get_public_host,
    get_user_ip_limit,
    ip_limit_settings,
    log,
    set_ip_limit_settings,
    set_setting,
    set_traffic_multiplier,
    set_user_enabled,
    set_user_ip_limit,
    subscription_url_for_user,
    sync_all_users,
    sync_user,
    traffic_multiplier_settings,
    user_access_status,
    user_config_payload,
    user_usage_summary,
)
from ..services.speed_limit import (
    apply_speed_limits_runtime,
    normalize_speed_limit_mbps,
    set_user_speed_limit,
)
from ..services.password_policy import generate_user_password, normalize_password_policy
from ..services.license import feature_allowed
from ..services.v12 import apply_plan
from ..services.node_gateway import assign_user_node
from .common import (
    _allowed_form_protocols,
    _check_reseller_capacity,
    _collect_usage_for_view,
    _node_selection_from_form,
    _parse_unlimited_days,
    available_protocols_for_current_user,
)
from .subscriptions import config_download_name
from . import web_bp


@web_bp.route('/quick-create', methods=['GET','POST'])
@login_required
def quick_create_user():
    if request.method == 'POST':
        username = request.form['username'].strip()
        if VpnUser.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً وجود دارد')
            return redirect(url_for('web.quick_create_user'))
        password = request.form.get('password') or generate_user_password()
        preset = request.form.get('preset', 'all')
        active = available_protocols_for_current_user()
        # v19.10.27: the manual protocol checkboxes are authoritative. Previously
        # presets like "all" ignored them entirely, so unchecking a protocol such
        # as ssh still created its runtime account and advertised it on the
        # user's subscription page.
        checked = [p for p in request.form.getlist('protocols') if p]
        if preset == 'xray_plus':
            base = [p for p in ['xray', 'hysteria2'] if p in active]
        elif preset == 'mobile':
            base = [p for p in ['wireguard', 'ocserv', 'hysteria2'] if p in active]
        elif preset == 'legacy':
            base = [p for p in ['openvpn', 'l2tp', 'pptp'] if p in active]
        elif preset == 'custom':
            base = None
        else:
            base = list(active)
        if base is None:
            protocols = _allowed_form_protocols(checked)
        else:
            protocols = _allowed_form_protocols([p for p in base if p in set(checked)])
        if not protocols:
            flash('حداقل یک پروتکل باید انتخاب شود؛ تیک‌های «انتخاب دستی پروتکل‌ها» را با Preset انتخابی هماهنگ کنید.')
            return redirect(url_for('web.quick_create_user'))
        unit = request.form.get('traffic_unit','gb')
        value = int(request.form.get('traffic_value') or 0)
        data_limit_mb = value if unit == 'mb' else value * 1024
        ok, msg = _check_reseller_capacity(data_limit_mb, 1)
        if not ok:
            flash(msg)
            return redirect(url_for('web.quick_create_user'))
        expires_at = _parse_unlimited_days(request.form.get('days'), 30)
        node_mode, preferred_node_id = _node_selection_from_form()
        u = VpnUser(username=username, l2tp_password=password, cisco_password=password, data_limit_mb=data_limit_mb, connection_limit=int(request.form.get('connection_limit') or 1), protocols=','.join(protocols), protocol_permissions=','.join(protocols), allowed_devices=0, expires_at=expires_at, owner_id=current_user.id if current_user.role=='sub_admin' else None, node_mode=node_mode, preferred_node_id=preferred_node_id, speed_limit_mbps=normalize_speed_limit_mbps(request.form.get('speed_limit_mbps', '0')))
        u.set_password(password)
        db.session.add(u); db.session.commit()
        set_user_ip_limit(u, request.form.get('ip_limit', '0'))
        sync_user(u, restart=False, changed_protocols=protocols, ensure_runtime=True);
        if int(getattr(u, 'speed_limit_mbps', 0) or 0) > 0:
            apply_speed_limits_runtime()
        log(current_user.username,'quick_create_user',u.username, ','.join(protocols))
        flash(f'کاربر ساخته شد. رمز: {password}')
        return redirect(url_for('web.user_configs', user_id=u.id))
    return render_template('quick_create.html', available=available_protocols_for_current_user())

def _page_url_for(endpoint, target_page):
    args = {k: v for k, v in request.args.items(multi=True) if k != 'page'}
    args['page'] = target_page
    query = '&'.join(f'{k}={v}' for k, v in args.items())
    return url_for(endpoint, **args)

@web_bp.route('/users', methods=['GET','POST'])
@login_required
def users():
    if request.method == 'POST':
        username = request.form['username'].strip()
        if VpnUser.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً وجود دارد')
            return redirect(url_for('web.users'))
        password = request.form.get('password') or generate_user_password()
        protocols = _allowed_form_protocols(request.form.getlist('protocols'))
        if not protocols:
            flash('حداقل یک پروتکل برای کاربر انتخاب کنید')
            return redirect(url_for('web.users'))
        data_limit_mb = int(request.form.get('data_limit_mb') or 0)
        ok, msg = _check_reseller_capacity(data_limit_mb, 1)
        if not ok:
            flash(msg)
            return redirect(url_for('web.users'))
        expires_at = _parse_unlimited_days(request.form.get('days'), 30)
        node_mode, preferred_node_id = _node_selection_from_form()
        u = VpnUser(username=username, l2tp_password=request.form.get('l2tp_password') or password, cisco_password=request.form.get('cisco_password') or password, data_limit_mb=data_limit_mb, connection_limit=int(request.form.get('connection_limit') or 1), protocols=','.join(protocols), protocol_permissions=','.join(protocols), allowed_devices=int(request.form.get('allowed_devices') or 0), expires_at=expires_at, owner_id=current_user.id if current_user.role=='sub_admin' else None, node_mode=node_mode, preferred_node_id=preferred_node_id, speed_limit_mbps=normalize_speed_limit_mbps(request.form.get('speed_limit_mbps', '0')))
        u.set_password(password); db.session.add(u); db.session.commit(); set_user_ip_limit(u, request.form.get('ip_limit','0')); sync_user(u, restart=False, changed_protocols=protocols, ensure_runtime=True);
        if int(getattr(u, 'speed_limit_mbps', 0) or 0) > 0:
            apply_speed_limits_runtime()
        log(current_user.username,'create_user',u.username)
        flash(f'کاربر ساخته شد. رمز: {password} | روز اعتبار 0 یعنی نامحدود، حجم 0 یعنی نامحدود')
        return redirect(url_for('web.user_configs', user_id=u.id))
    _collect_usage_for_view(10)
    q = VpnUser.query if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id)
    search = (request.args.get('q') or '').strip()
    if search:
        q = q.filter(VpnUser.username.ilike(f'%{search}%'))
    auto_password_length, auto_password_mode = normalize_password_policy()
    # v19.10.26: paginate the users table so large panels stop loading every row.
    page = max(1, int(request.args.get('page') or 1))
    try:
        per_page = int(request.args.get('per_page') or 25)
    except Exception:
        per_page = 25
    per_page = min(max(per_page, 10), 100)
    pagination = q.order_by(VpnUser.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        'users.html',
        users=pagination.items,
        pagination=pagination,
        prev_url=_page_url_for('web.users', pagination.prev_num) if pagination.has_prev else None,
        next_url=_page_url_for('web.users', pagination.next_num) if pagination.has_next else None,
        page_url=lambda n: _page_url_for('web.users', n),
        user_status=user_access_status,
        usage_summary=user_usage_summary,
        get_user_ip_limit=get_user_ip_limit,
        search=search,
        nodes=Node.query.order_by(Node.name).all(),
        available=available_protocols_for_current_user(),
        auto_password_length=auto_password_length,
        auto_password_mode=auto_password_mode,
    )


# v19.10.12 bulk username-range user creator

def _bulk_password(length=None, mode=None):
    # Bulk creation keeps its per-request override, but defaults to the permanent
    # auto-password policy configured by the main admin.
    return generate_user_password(length=length, mode=mode)


def _safe_bulk_username_base(value):
    raw = (value or '').strip()
    raw = re.sub(r'[^0-9A-Za-z_.-]+', '-', raw).strip('._-')
    return raw[:50]


@web_bp.route('/users/bulk-create', methods=['POST'])
@login_required
def users_bulk_create():
    base_username = _safe_bulk_username_base(request.form.get('bulk_username_base'))
    if not base_username:
        flash('نام پایه ساخت عمده معتبر نیست.')
        return redirect(url_for('web.users'))
    try:
        start_no = int(request.form.get('bulk_start') or 0)
        end_no = int(request.form.get('bulk_end') or 0)
    except Exception:
        flash('بازه شماره ساخت عمده معتبر نیست.')
        return redirect(url_for('web.users'))
    if end_no < start_no:
        start_no, end_no = end_no, start_no
    count = end_no - start_no + 1
    if count < 1 or count > 1000:
        flash('تعداد ساخت عمده باید بین 1 تا 1000 باشد.')
        return redirect(url_for('web.users'))
    try:
        password_length = int(request.form.get('bulk_password_length') or normalize_password_policy()[0])
    except Exception:
        password_length = normalize_password_policy()[0]
    if password_length < 3:
        flash('طول رمز باید حداقل 3 کاراکتر باشد.')
        return redirect(url_for('web.users'))
    password_mode = request.form.get('bulk_password_mode') or normalize_password_policy()[1]
    try:
        data_limit_mb = int(request.form.get('bulk_data_limit_mb') or 0)
    except Exception:
        data_limit_mb = 0
    try:
        days = int(request.form.get('bulk_days') or 30)
    except Exception:
        days = 30
    protocols = _allowed_form_protocols(request.form.getlist('bulk_protocols'))
    if not protocols:
        flash('حداقل یک پروتکل برای ساخت عمده انتخاب کنید.')
        return redirect(url_for('web.users'))
    ok, msg = _check_reseller_capacity(data_limit_mb * count if data_limit_mb > 0 else 0, count)
    if not ok:
        flash(msg)
        return redirect(url_for('web.users'))
    expires_at = None if days <= 0 else datetime.utcnow() + timedelta(days=days)
    created = []
    skipped = []
    failed = []
    node_mode, preferred_node_id = _node_selection_from_form()
    for n in range(start_no, end_no + 1):
        username = f'{base_username}{n}'[:78]
        try:
            if VpnUser.query.filter_by(username=username).first():
                skipped.append((username, 'duplicate'))
                continue
            password = _bulk_password(password_length, password_mode)
            u = VpnUser(
                username=username,
                l2tp_password=password,
                cisco_password=password,
                data_limit_mb=data_limit_mb,
                connection_limit=1,
                protocols=','.join(protocols),
                protocol_permissions=','.join(protocols),
                allowed_devices=0,
                expires_at=expires_at,
                owner_id=current_user.id if current_user.role == 'sub_admin' else None,
                node_mode=node_mode,
                preferred_node_id=preferred_node_id,
                speed_limit_mbps=normalize_speed_limit_mbps(request.form.get('bulk_speed_limit_mbps', '0')),
            )
            u.set_password(password)
            db.session.add(u)
            db.session.flush()
            set_user_ip_limit(u, request.form.get('bulk_ip_limit', '1') or '1')
            sub_url = subscription_url_for_user(u)
            db.session.commit()
            created.append((username, password, sub_url))
        except Exception as exc:
            db.session.rollback()
            failed.append((username, str(exc)))
    if created:
        try:
            sync_all_users(restart=True)
            if normalize_speed_limit_mbps(request.form.get('bulk_speed_limit_mbps', '0')) > 0:
                apply_speed_limits_runtime()
        except Exception as exc:
            failed.append(('sync_all_users', str(exc)))
    log(current_user.username, 'bulk_create_users', f'{base_username}{start_no}-{end_no}', f'created={len(created)} skipped={len(skipped)} failed={len(failed)} protocols={",".join(protocols)}')
    out_dir = Path('/tmp')
    out_path = out_dir / f'ironpanel-bulk-users-{int(time.time())}.txt'
    lines = [
        'IronPanel bulk users',
        f'base={base_username}',
        f'range={start_no}-{end_no}',
        f'created={len(created)}',
        f'skipped={len(skipped)}',
        f'failed={len(failed)}',
        f'data_limit_mb={data_limit_mb}',
        f'days={days}',
        f'protocols={",".join(protocols)}',
        '',
        'CREATED:',
    ]
    for username, password, sub in created:
        lines.append(f'{username},{password},{sub}')
    if skipped:
        lines.append('\nSKIPPED:')
        for username, reason in skipped:
            lines.append(f'{username},{reason}')
    if failed:
        lines.append('\nFAILED:')
        for username, reason in failed:
            lines.append(f'{username},{reason}')
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    return send_file(out_path, as_attachment=True, download_name=out_path.name, mimetype='text/plain')

@web_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def user_toggle(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.users'))
    new_state = not bool(u.enabled)
    set_user_enabled(u, new_state)
    try:
        apply_speed_limits_runtime()
    except Exception:
        pass
    log(current_user.username, 'manual_enable_user' if new_state else 'manual_disable_user', u.username, str(new_state))
    flash(('کاربر وصل و فعال شد: ' if new_state else 'کاربر قطع و غیرفعال شد: ') + u.username)
    return redirect(url_for('web.users'))

@web_bp.route('/users/<int:user_id>/edit', methods=['GET','POST'])
@login_required
def user_edit(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    if request.method == 'POST':
        before_protocols = set(u.allowed_protocol_list() or u.protocol_list() or active_protocols())
        before_enabled = bool(u.enabled)
        before_username = u.username
        old_username = u.username
        new_username = request.form.get('username', u.username).strip()
        duplicate = VpnUser.query.filter(VpnUser.username == new_username, VpnUser.id != u.id).first()
        if duplicate:
            flash('این نام کاربری قبلاً وجود دارد')
            return redirect(url_for('web.user_edit', user_id=u.id))
        if new_username != old_username:
            shutil.rmtree(current_app.config['CONFIG_ROOT'] / 'profiles' / old_username, ignore_errors=True)
            u.username = new_username
        if request.form.get('password'):
            u.set_password(request.form['password'])
            if request.form.get('sync_passwords') == '1':
                u.l2tp_password = request.form['password']
                u.cisco_password = request.form['password']
        u.l2tp_password = request.form.get('l2tp_password') or u.l2tp_password
        u.cisco_password = request.form.get('cisco_password') or u.cisco_password
        requested_enabled = bool(request.form.get('enabled'))
        if requested_enabled != before_enabled:
            u.disabled_reason = '' if requested_enabled else 'manual'
        u.enabled = requested_enabled
        allowed_protocols = _allowed_form_protocols(request.form.getlist('protocols'))
        if not allowed_protocols:
            flash('حداقل یک پروتکل برای کاربر انتخاب کنید')
            return redirect(url_for('web.user_edit', user_id=u.id))
        u.protocols = ','.join(allowed_protocols)
        u.protocol_permissions = ','.join(allowed_protocols)
        u.allowed_devices = int(request.form.get('allowed_devices') or 0)
        new_data_limit_mb = int(request.form.get('data_limit_mb') or 0)
        if current_user.role == 'sub_admin' and new_data_limit_mb > int(u.data_limit_mb or 0):
            ok, msg = _check_reseller_capacity(new_data_limit_mb - int(u.data_limit_mb or 0), 0)
            if not ok:
                flash(msg)
                return redirect(url_for('web.user_edit', user_id=u.id))
        u.data_limit_mb = new_data_limit_mb
        u.connection_limit = int(request.form.get('connection_limit') or 1)
        # Main admin may edit every user; reseller reaches this route only for owned users.
        u.speed_limit_mbps = normalize_speed_limit_mbps(request.form.get('speed_limit_mbps', getattr(u, 'speed_limit_mbps', 0) or 0))
        if current_user.role == 'main_admin' and feature_allowed('nodes'):
            u.node_mode = request.form.get('node_mode', getattr(u, 'node_mode', 'auto') or 'auto')
            u.preferred_node_id = int(request.form.get('preferred_node_id') or 0) or None
        if request.form.get('unlimited_expiry') == '1':
            u.expires_at = None
        elif request.form.get('expires_at'):
            u.expires_at = datetime.strptime(request.form['expires_at'], '%Y-%m-%d')
        else:
            u.expires_at = _parse_unlimited_days(request.form.get('days'), 0)
        after_protocols = set(u.allowed_protocol_list() or u.protocol_list() or active_protocols())
        affected_protocols = before_protocols | after_protocols if (before_protocols != after_protocols or before_enabled != bool(u.enabled) or before_username != u.username or request.form.get('password') or request.form.get('sync_passwords') == '1') else set()
        db.session.commit(); set_user_ip_limit(u, request.form.get('ip_limit','0')); sync_user(u, restart=bool(affected_protocols), changed_protocols=affected_protocols)
        speed_ok, speed_out = apply_speed_limits_runtime()
        log(current_user.username,'edit_user',u.username, f'speed_limit_mbps={u.speed_limit_mbps}; speed_apply={speed_ok}')
        flash('کاربر ویرایش شد و سرویس‌های VPN/Speed Limit همگام‌سازی شدند' if speed_ok else 'کاربر ویرایش شد؛ اعمال Speed Limit نیاز به بررسی دارد: ' + speed_out[-140:])
        return redirect(url_for('web.user_configs', user_id=u.id))
    return render_template('user_edit.html', user=u, active=available_protocols_for_current_user(), plans=ServicePlan.query.filter_by(active=True).all(), get_user_ip_limit=get_user_ip_limit, nodes=Node.query.order_by(Node.name).all())

@web_bp.route('/users/<int:user_id>/speed-limit', methods=['POST'])
@login_required
def user_speed_limit(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.users'))
    mbps = set_user_speed_limit(u, request.form.get('speed_limit_mbps', '0'))
    ok, out = apply_speed_limits_runtime()
    log(current_user.username, 'user_speed_limit', u.username, f'{mbps}Mbps; applied={ok}')
    if ok:
        flash(f'محدودیت سرعت {u.username}: ' + (f'{mbps} Mbps' if mbps > 0 else 'غیرفعال / استفاده از تنظیمات پروتکل'))
    else:
        flash('محدودیت ذخیره شد ولی اعمال Runtime خطا داشت: ' + out[-160:])
    return redirect(request.referrer or url_for('web.users'))


@web_bp.route('/users/<int:user_id>/reset-traffic', methods=['POST'])
@login_required
def user_reset_traffic(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    from ..services.provisioning import reset_user_usage_preserving_reseller
    reset_user_usage_preserving_reseller(u)
    db.session.commit(); sync_user(u, restart=False, changed_protocols=[]); log(current_user.username,'reset_traffic',u.username)
    flash('حجم مصرفی کاربر صفر شد')
    return redirect(url_for('web.users'))

@web_bp.route('/users/sync-all', methods=['POST'])
@login_required
def users_sync_all():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    sync_all_users(restart=True); log(current_user.username,'sync_all_users','vpn')
    flash('همه کاربران با هسته‌های VPN همگام‌سازی شدند؛ فقط هسته‌های لازم reload/restart شدند')
    return redirect(url_for('web.users'))


@web_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def user_delete(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    username = u.username
    delete_user(u)
    try:
        apply_speed_limits_runtime()
    except Exception:
        pass
    log(current_user.username,'delete_user',username)
    flash('کاربر حذف شد و دسترسی‌های VPN او پاک‌سازی شد')
    return redirect(url_for('web.users'))

@web_bp.route('/users/<int:user_id>/configs')
@login_required
def user_configs(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    _collect_usage_for_view(5)
    u = VpnUser.query.get_or_404(user_id)
    configs = user_config_payload(u)
    ok, reason = user_access_status(u)
    return render_template('user_configs.html', user=u, configs=configs, host=get_public_host(), access_ok=ok, access_reason=reason, usage=user_usage_summary(u))

@web_bp.route('/profiles/<username>/<filename>')
@login_required
def profile_download(username, filename):
    u = VpnUser.query.filter_by(username=username).first_or_404()
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        abort(403)
    allowed_files = user_config_payload(u)
    if filename not in allowed_files or filename == 'ACCOUNT_STATUS.txt':
        abort(404)
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / username, filename, as_attachment=True, download_name=config_download_name(u, filename))

@web_bp.route('/api/users/<int:user_id>/usage')
@login_required
def api_user_usage(user_id):
    rows = DailyUsage.query.filter_by(user_id=user_id).order_by(DailyUsage.day).limit(60).all()
    mult = traffic_multiplier_settings()
    factor = float(mult.get('factor') or 1.0)
    return jsonify(
        labels=[r.day for r in rows],
        upload=[int((r.upload_mb or 0) * factor + 0.999999) for r in rows],
        download=[int((r.download_mb or 0) * factor + 0.999999) for r in rows],
        raw_upload=[r.upload_mb for r in rows],
        raw_download=[r.download_mb for r in rows],
        traffic_multiplier_enabled=bool(mult.get('enabled')),
        traffic_multiplier_factor=factor,
    )

@web_bp.route('/usage')
@login_required
def usage_reports():
    _collect_usage_for_view(0)
    users_rows = VpnUser.query.order_by(VpnUser.username).all()
    return render_template('usage.html', users=users_rows, usage_summary=user_usage_summary)

@web_bp.route('/traffic-multiplier', methods=['GET','POST'])
@login_required
def traffic_multiplier():
    # This module is intentionally available in every license tier; only the main admin can change the global factor.
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        enabled = request.form.get('traffic_multiplier_enabled') == '1'
        settings = set_traffic_multiplier(enabled, request.form.get('traffic_multiplier_value', '1'))
        collect_usage_from_runtime()
        stopped = enforce_usage_limits(commit=True)
        log(current_user.username, 'traffic_multiplier_update', settings.get('label', 'x1'), 'enabled' if enabled else 'disabled')
        if stopped:
            flash(f'ضریب مصرف ذخیره شد و {stopped} کاربر به دلیل رسیدن مصرف ضریب‌خورده به سقف حجم متوقف شد.')
        else:
            flash('ضریب مصرف ذخیره شد.')
        return redirect(url_for('web.traffic_multiplier'))
    _collect_usage_for_view(5)
    users_rows = VpnUser.query.order_by(VpnUser.username).all()
    return render_template('traffic_multiplier.html', settings=traffic_multiplier_settings(), users=users_rows, usage_summary=user_usage_summary)


@web_bp.route('/ip-limit', methods=['GET','POST'])
@login_required
def ip_limit_manager():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'settings':
            set_ip_limit_settings(request.form.get('ip_limit_enabled') == '1', request.form.get('ip_limit_default','0'), request.form.get('ip_limit_action','disable'))
            flash('تنظیمات IP Limit ذخیره شد')
        elif action == 'users':
            for u in VpnUser.query.all():
                set_user_ip_limit(u, request.form.get(f'ip_limit_{u.id}', '0'))
            flash('حد اختصاصی کاربران ذخیره شد')
        elif action == 'enforce':
            stopped = enforce_ip_limits(commit=True)
            flash(f'بررسی انجام شد؛ {stopped} کاربر متوقف شد')
        return redirect(url_for('web.ip_limit_manager'))
    users_rows = VpnUser.query.order_by(VpnUser.username).all()
    return render_template('ip_limit.html', settings=ip_limit_settings(), users=users_rows, get_user_ip_limit=get_user_ip_limit, usage_summary=user_usage_summary)

@web_bp.route('/users/bulk-action', methods=['POST'])
@login_required
def users_bulk_action():
    ids = [int(x) for x in request.form.getlist('user_ids') if str(x).isdigit()]
    action = (request.form.get('action') or '').strip()
    q = VpnUser.query.filter(VpnUser.id.in_(ids)) if ids else VpnUser.query.filter(VpnUser.id == -1)
    if current_user.role == 'sub_admin':
        # Never trust checkbox IDs from the browser; a reseller can operate only on owned users.
        q = q.filter(VpnUser.owner_id == current_user.id)
    rows = q.all()
    changed = 0
    if action in {'enable', 'disable'}:
        enabled = action == 'enable'
        for u in rows:
            if bool(u.enabled) != enabled:
                u.enabled = enabled
                u.disabled_reason = '' if enabled else 'manual'
                changed += 1
                db.session.add(ActivityLog(
                    actor=current_user.username,
                    action='manual_enable_user' if enabled else 'manual_disable_user',
                    target=u.username,
                    details='bulk',
                ))
        db.session.commit()
        if rows:
            sync_all_users(restart=True)
    elif action == 'reset_traffic':
        from ..services.provisioning import reset_user_usage_preserving_reseller
        for u in rows:
            reset_user_usage_preserving_reseller(u)
            changed += 1
        db.session.commit()
        if rows:
            sync_all_users(restart=True)
    else:
        flash('عملیات گروهی نامعتبر است')
        return redirect(url_for('web.users'))
    if rows:
        try:
            apply_speed_limits_runtime()
        except Exception:
            pass
    log(current_user.username, f'bulk_{action}_users', str(len(rows)), f'changed={changed}')
    flash(f'عملیات گروهی روی {len(rows)} کاربر مجاز انجام شد')
    return redirect(url_for('web.users'))


@web_bp.route('/users/purge-auto-disabled', methods=['POST'])
@login_required
def users_purge_auto_disabled():
    q = VpnUser.query
    if current_user.role == 'sub_admin':
        q = q.filter(VpnUser.owner_id == current_user.id)
    candidates = auto_disabled_cleanup_users(q.all())
    details = {
        'expired': sum(1 for u in candidates if automatic_disable_reason(u) == 'expired'),
        'traffic_limit': sum(1 for u in candidates if automatic_disable_reason(u) == 'traffic_limit'),
    }
    count = delete_users_bulk(candidates)
    log(current_user.username, 'purge_auto_disabled_users', str(count), json.dumps(details, ensure_ascii=False))
    flash(f'{count} کاربر غیرفعالِ منقضی/تمام‌حجم حذف شد')
    return redirect(url_for('web.users'))

@web_bp.route('/users/<int:user_id>/apply-plan', methods=['POST'])
@login_required
def user_apply_plan(user_id):
    u=VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        abort(403)
    p=ServicePlan.query.get_or_404(int(request.form['plan_id']))
    try:
        apply_plan(u,p)
        log(current_user.username,'apply_plan',u.username,p.name)
        flash('پلن روی کاربر اعمال شد')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc))
    return redirect(url_for('web.user_edit', user_id=user_id))

@web_bp.route('/users/<int:user_id>/node', methods=['POST'])
@login_required
def user_node_assign(user_id):
    if current_user.role != 'main_admin' or not feature_allowed('nodes'):
        return redirect(url_for('web.users'))
    ok, msg = assign_user_node(user_id, request.form.get('node_mode','auto'), int(request.form.get('preferred_node_id') or 0))
    flash(msg if ok else 'خطا: '+msg)
    return redirect(url_for('web.users'))

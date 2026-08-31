"""Reseller (sub-admin) management, portal login URLs and reseller API."""
import json

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import Admin, VpnUser
from ..services.provisioning import (
    active_protocols,
    apply_runtime_configs,
    get_setting,
    log,
    reseller_config_domain_for,
    set_reseller_config_domain,
    set_reseller_enabled,
    sync_all_users,
    sync_user,
    subscription_url_for_user,
)
from ..services.speed_limit import set_reseller_speed_limit
from ..services.v10 import refresh_online_sessions
from .common import _normalize_reseller_path, _normalize_reseller_protocols, _reseller_stats, reseller_panel_url
from . import web_bp


@web_bp.route('/resellers', methods=['GET','POST'])
@login_required
def resellers():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        if Admin.query.filter_by(username=username).first():
            flash('این نام کاربری برای مدیر/نماینده قبلاً وجود دارد')
            return redirect(url_for('web.resellers'))
        slug = _normalize_reseller_path(request.form.get('panel_path'), username)
        reseller_protocols = _normalize_reseller_protocols(request.form.getlist('reseller_protocols'))
        if not reseller_protocols:
            flash('حداقل یک پروتکل مجاز برای نماینده انتخاب کنید')
            return redirect(url_for('web.resellers'))
        a = Admin(
            username=username,
            role='sub_admin',
            user_limit=int(request.form.get('user_limit') or 0),
            traffic_quota_gb=int(request.form.get('traffic_quota_gb') or 0),
            reseller_protocols=','.join(reseller_protocols),
            panel_path=slug,
            enabled=bool(request.form.get('enabled', '1')),
        )
        a.set_password(request.form['password']); db.session.add(a); db.session.commit(); log(current_user.username,'create_reseller',a.username, slug)
        # v19.10.27: optional per-reseller config domain (empty = panel default).
        saved_domain = set_reseller_config_domain(a.id, request.form.get('config_domain'))
        if saved_domain:
            log(current_user.username, 'reseller_config_domain', a.username, saved_domain)
        # v2.0.6: optional per-user speed cap for this reseller (0 = no cap).
        saved_speed = set_reseller_speed_limit(a.id, request.form.get('speed_limit_mbps', '0'))
        if saved_speed:
            log(current_user.username, 'reseller_speed_limit', a.username, f'{saved_speed}Mbps per user')
        flash(f'نماینده ساخته شد. آدرس پنل: {reseller_panel_url(a)}')
        return redirect(url_for('web.resellers'))
    rows = Admin.query.filter_by(role='sub_admin').order_by(Admin.id.desc()).all()
    changed = False
    for r in rows:
        if not getattr(r, 'panel_path', None):
            r.panel_path = _normalize_reseller_path('', r.username, r.id)
            changed = True
        if getattr(r, 'enabled', None) is None:
            r.enabled = True
            changed = True
    if changed:
        db.session.commit()
    return render_template('resellers.html', resellers=rows, reseller_stats=_reseller_stats, reseller_panel_url=reseller_panel_url, reseller_protocol_choices=_normalize_reseller_protocols(active_protocols() or [], allow_default=True), reseller_config_domain=lambda rid: get_setting(f'reseller_config_domain_owner_{int(rid)}', ''), reseller_speed_limit=lambda rid: get_setting(f'reseller_speed_limit_owner_{int(rid)}', '0'))

@web_bp.route('/resellers/<int:reseller_id>/update', methods=['POST'])
@login_required
def reseller_update(reseller_id):
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    r = Admin.query.filter_by(id=reseller_id, role='sub_admin').first_or_404()
    username = request.form.get('username', r.username).strip()
    duplicate = Admin.query.filter(Admin.username == username, Admin.id != r.id).first()
    if duplicate:
        flash('این نام کاربری قبلاً وجود دارد')
        return redirect(url_for('web.resellers'))
    r.username = username
    r.user_limit = int(request.form.get('user_limit') or 0)
    r.traffic_quota_gb = int(request.form.get('traffic_quota_gb') or 0)
    new_protocols = _normalize_reseller_protocols(request.form.getlist('reseller_protocols'))
    if not new_protocols:
        flash('حداقل یک پروتکل مجاز برای نماینده انتخاب کنید')
        return redirect(url_for('web.resellers'))
    old_protocols = set(r.allowed_protocol_list())
    r.reseller_protocols = ','.join(new_protocols)
    r.panel_path = _normalize_reseller_path(request.form.get('panel_path'), r.username, r.id)
    requested_enabled = bool(request.form.get('enabled'))
    if request.form.get('password'):
        r.set_password(request.form['password'])
    changed_users = []
    affected_protocols = set(old_protocols) | set(new_protocols)
    if request.form.get('apply_protocols_to_existing') == '1':
        allowed_set = set(new_protocols)
        for owned_user in VpnUser.query.filter_by(owner_id=r.id).all():
            before = owned_user.allowed_protocol_list() or owned_user.protocol_list() or []
            after = [p for p in before if p in allowed_set]
            if not after:
                # Never leave an empty protocol string because legacy code treats it as "all".
                # Keep one permitted protocol and disable the user until the reseller reviews it.
                after = [new_protocols[0]]
                owned_user.enabled = False
                owned_user.disabled_reason = 'protocol_restricted'
            if before != after:
                owned_user.protocols = ','.join(after)
                owned_user.protocol_permissions = ','.join(after)
                changed_users.append(owned_user)
    db.session.commit()
    for owned_user in changed_users:
        try:
            sync_user(owned_user, restart=False, changed_protocols=affected_protocols)
        except Exception as exc:
            log(current_user.username, 'reseller_protocol_sync_error', owned_user.username, str(exc)[:500])
    if changed_users:
        try:
            apply_runtime_configs()
        except Exception as exc:
            log(current_user.username, 'reseller_protocol_apply_error', r.username, str(exc)[:500])
    # v19.10.23: desired admin state + automatic quota reconciliation. An
    # auto-suspended reseller keeps the checkbox logically enabled, so raising
    # quota/user-limit can restore the panel and only reseller-suspended users.
    reseller_state = set_reseller_enabled(r, requested_enabled, source=current_user.username)
    # v19.10.27: optional per-reseller config domain override.
    saved_domain = set_reseller_config_domain(r.id, request.form.get('config_domain'))
    # v2.0.6: per-user speed cap for this reseller (0 = no cap). Applied to every
    # owned user so none of them can use more than the configured Mb/s.
    saved_speed = set_reseller_speed_limit(r.id, request.form.get('speed_limit_mbps', '0'))
    if request.form.get('apply_speed_to_existing') == '1':
        from ..services.speed_limit import enforce_reseller_speed_limit, user_wide_limit
        speed_changed = 0
        for owned_user in VpnUser.query.filter_by(owner_id=r.id).all():
            capped = enforce_reseller_speed_limit(owned_user, user_wide_limit(owned_user))
            if int(getattr(owned_user, 'speed_limit_mbps', 0) or 0) != capped:
                owned_user.speed_limit_mbps = capped
                speed_changed += 1
        db.session.commit()
        if speed_changed:
            try:
                from ..services.speed_limit import apply_speed_limits_runtime
                apply_speed_limits_runtime()
            except Exception:
                pass
    log(current_user.username, 'update_reseller', r.username, f'{r.panel_path}; protocols={r.reseller_protocols}; users_restricted={len(changed_users)}; state={reseller_state}; domain={saved_domain or "default"}; speed={saved_speed or "none"}Mbps')
    if reseller_state.get('enabled'):
        state_msg = f" پنل فعال است؛ {int(reseller_state.get('restored') or 0)} کاربر سالم دوباره وصل شد."
    elif reseller_state.get('reason') == 'traffic_quota':
        state_msg = ' پنل به علت اتمام سقف حجم نماینده همچنان متوقف است.'
    elif reseller_state.get('reason') == 'user_limit':
        state_msg = ' پنل به علت بیشتر بودن تعداد اکانت‌ها از سقف نماینده همچنان متوقف است.'
    else:
        state_msg = ' پنل به صورت دستی متوقف است.'
    flash(f'نماینده ویرایش شد. پروتکل‌های مجاز: {r.reseller_protocols}. کاربران اصلاح‌شده: {len(changed_users)}. آدرس پنل: {reseller_panel_url(r)}.' + state_msg)
    return redirect(url_for('web.resellers'))

@web_bp.route('/resellers/<int:reseller_id>/toggle', methods=['POST'])
@login_required
def reseller_toggle(reseller_id):
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    r = Admin.query.filter_by(id=reseller_id, role='sub_admin').first_or_404()
    desired = not bool(getattr(r, 'enabled', True))
    state = set_reseller_enabled(r, desired, source=current_user.username)
    log(current_user.username, 'toggle_reseller', r.username, json.dumps(state, ensure_ascii=False))
    if state.get('enabled'):
        flash(f"پنل نماینده فعال شد و {int(state.get('restored') or 0)} کاربر سالمی که به علت توقف نماینده قطع شده بودند دوباره وصل شدند.")
    elif desired and state.get('reason') == 'traffic_quota':
        flash('پنل فعال نشد؛ مصرف نماینده هنوز به سقف حجم رسیده است. سقف حجم را افزایش بده.')
    elif desired and state.get('reason') == 'user_limit':
        flash('پنل فعال نشد؛ تعداد کاربران نماینده هنوز بیشتر از سقف اکانت است. سقف را افزایش بده یا کاربر حذف کن.')
    else:
        flash(f"پنل نماینده متوقف شد و {int(state.get('disabled') or 0)} کاربر فعال زیرمجموعه نیز قطع شد.")
    return redirect(url_for('web.resellers'))

@web_bp.route('/resellers/<int:reseller_id>/delete', methods=['POST'])
@login_required
def reseller_delete(reseller_id):
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    r = Admin.query.filter_by(id=reseller_id, role='sub_admin').first_or_404()
    target_username = r.username
    action = request.form.get('delete_action', 'detach')
    users = VpnUser.query.filter_by(owner_id=r.id).all()
    if action == 'disable_users':
        for u in users:
            u.enabled = False
            u.disabled_reason = 'manual'
            u.owner_id = None
    elif action == 'delete_users':
        for u in list(users):
            db.session.delete(u)
    else:
        for u in users:
            u.owner_id = None
    db.session.delete(r)
    db.session.commit()
    try:
        sync_all_users(restart=True)
    except Exception as exc:
        log(current_user.username, 'delete_reseller_sync_error', target_username, str(exc)[:500])
    log(current_user.username, 'delete_reseller', target_username, f'action={action}; users={len(users)}')
    flash(f'نماینده {target_username} حذف شد.')
    return redirect(url_for('web.resellers'))

@web_bp.route('/resellers/<int:reseller_id>/portal-url')
@login_required
def reseller_portal_url_api(reseller_id):
    if current_user.role != 'main_admin':
        return jsonify(ok=False, error='forbidden'), 403
    r = Admin.query.filter_by(id=reseller_id, role='sub_admin').first_or_404()
    if not r.panel_path:
        r.panel_path = _normalize_reseller_path('', r.username, r.id)
        db.session.commit()
    return jsonify(ok=True, url=reseller_panel_url(r), path=r.panel_path, enabled=bool(r.enabled), stats=_reseller_stats(r))


@web_bp.route('/api/reseller/v1/stats')
@login_required
def reseller_api_stats():
    if current_user.role not in ('sub_admin', 'main_admin'):
        return jsonify(ok=False, error='forbidden'), 403
    owner_id = current_user.id if current_user.role == 'sub_admin' else request.args.get('owner_id', type=int)
    users_q = VpnUser.query.filter_by(owner_id=owner_id) if owner_id else VpnUser.query
    users = users_q.all()
    return jsonify(ok=True, owner_id=owner_id, users=len(users), enabled=sum(1 for u in users if u.enabled), traffic_mb=sum(int(u.data_limit_mb or 0) for u in users), used_mb=sum(int(u.used_total_mb or 0) for u in users))

@web_bp.route('/api/reseller/v1/users')
@login_required
def reseller_api_users():
    if current_user.role not in ('sub_admin', 'main_admin'):
        return jsonify(ok=False, error='forbidden'), 403
    owner_id = current_user.id if current_user.role == 'sub_admin' else request.args.get('owner_id', type=int)
    users_q = VpnUser.query.filter_by(owner_id=owner_id) if owner_id else VpnUser.query
    rows=[]
    for u in users_q.order_by(VpnUser.id.desc()).limit(1000).all():
        rows.append({'id':u.id,'username':u.username,'enabled':bool(u.enabled),'limit_mb':u.data_limit_mb,'used_mb':u.used_total_mb,'expires_at':u.expires_at.isoformat() if u.expires_at else None,'subscription_url':subscription_url_for_user(u)})
    return jsonify(ok=True, users=rows)

@web_bp.route('/api/reseller/v1/sessions')
@login_required
def reseller_api_sessions():
    if current_user.role not in ('sub_admin', 'main_admin'):
        return jsonify(ok=False, error='forbidden'), 403
    owner_id = current_user.id if current_user.role == 'sub_admin' else request.args.get('owner_id', type=int)
    allowed_user_ids = {u.id for u in VpnUser.query.filter_by(owner_id=owner_id).all()} if owner_id else None
    rows=[]
    for sess in refresh_online_sessions():
        if allowed_user_ids is not None and sess.user_id not in allowed_user_ids:
            continue
        rows.append({'username':sess.username,'protocol':sess.protocol,'remote_ip':sess.remote_ip,'last_seen':sess.last_seen.isoformat() if sess.last_seen else None})
    return jsonify(ok=True, sessions=rows)


# v19.10.27: reseller self-service config domain.
@web_bp.route('/my/config-domain', methods=['GET','POST'])
@login_required
def my_config_domain():
    if current_user.role != 'sub_admin':
        flash('این بخش مخصوص نمایندگان فروش است؛ آدرس کانفیگ‌ها از تنظیمات اصلی پنل گرفته می‌شود.')
        return redirect(url_for('web.dashboard'))
    key = f'reseller_config_domain_owner_{int(current_user.id)}'
    if request.method == 'POST':
        saved = set_reseller_config_domain(current_user.id, request.form.get('config_domain'))
        log(current_user.username, 'update_own_config_domain', current_user.username, saved or 'default')
        if saved:
            flash(f'دامنه کانفیگ‌های شما ذخیره شد: {saved}. برای اعمال روی کانفیگ‌های موجود، «Sync همه کاربران» را بزنید.')
        else:
            flash('دامنه ذخیره‌شده پاک شد؛ کانفیگ کاربران شما از آدرس اصلی پنل ساخته می‌شود.')
        return redirect(url_for('web.my_config_domain'))
    current_domain = get_setting(key, '')
    sample_user = VpnUser.query.filter_by(owner_id=current_user.id).order_by(VpnUser.id.desc()).first()
    return render_template(
        'my_config_domain.html',
        current_domain=current_domain,
        user_count=VpnUser.query.filter_by(owner_id=current_user.id).count(),
        has_users=bool(sample_user),
    )

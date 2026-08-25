"""Operations UI: health doctor, backups, updates, monitoring, sessions, logs."""
import os
import shlex

from flask import current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import ActivityLog, AppSetting, Node, RemoteJob, UpdateRelease
from ..services.provisioning import log, run_cmd, service_error_detail, service_status
from ..services.maintenance import backup_catalog, create_safe_backup, doctor_status, queue_doctor_repair, repair_status, restore_safe_backup
from ..services.v10 import kick_session, refresh_online_sessions, server_metrics
from ..services.v13 import (
    create_release,
    current_version,
    github_latest_version,
    github_update_log_tail,
    github_update_schedule_restart,
    github_update_status,
    github_update_step,
    github_update_step_status,
    latest_release,
    process_local_jobs,
)
from ..services.v17 import live_log_tail
from .common import _online_sessions_snapshot, _refresh_sessions_background
from . import web_bp


@web_bp.route('/health', methods=['GET','POST'])
@web_bp.route('/health/check-repair', methods=['GET','POST'])
@login_required
def health():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    repair_output = ''
    status = repair_status()
    if request.method == 'POST':
        target = request.form.get('target', 'all') or 'all'
        queued, message, status = queue_doctor_repair(target, actor=getattr(current_user, 'username', 'web'))
        log(current_user.username, 'health_doctor_repair_queued', target, message[-800:])
        flash('Repair در پس‌زمینه شروع شد؛ صفحه پنل دیگر منتظر اتمام آن نمی‌ماند.' if queued else 'Repair در حال اجراست یا شروع نشد: ' + str(message)[:160])
        return redirect(url_for('web.health'))
    summary = doctor_status()
    status = repair_status()
    repair_output = status.get('output_tail','')
    return render_template('health.html', summary=summary, repair_output=repair_output, repair_status=status)

@web_bp.route('/health/error')
@login_required
def health_error():
    svc = request.args.get('service','')
    service_map = {
        'openvpn': 'openvpn-server@server', 'wireguard': 'wg-quick@wg0', 'ocserv': 'ocserv',
        'xray': 'xray', 'hysteria2': 'hysteria-server', 'pptp': 'pptpd', 'l2tp': 'xl2tpd',
        'ssh': 'ssh', 'telegram_proxy': 'ironpanel-tgproxy', 'ironpanel': 'ironpanel',
        'usage': 'ironpanel-usage-sync.timer', 'speed_limits': 'ironpanel-speed-limits',
        'node_agent': 'ironpanel-node', 'node_gateway': 'ironpanel-node-gateway'
    }
    lookup = service_map.get(svc, svc)
    try:
        detail = service_error_detail(lookup)
        if detail == 'Unknown service':
            unit_log = run_cmd(['bash','-lc', f'journalctl -u {shlex.quote(lookup)} -n 120 --no-pager 2>/dev/null || systemctl status {shlex.quote(lookup)} --no-pager 2>/dev/null || true'], timeout=20)
            detail = (unit_log.stdout or unit_log.stderr or 'No diagnostics found.')
    except Exception as e:
        detail = 'Cannot collect diagnostics for this service:\n' + str(e)
    return render_template('health_error.html', service=svc, detail=detail)

@web_bp.route('/backups', methods=['GET','POST'])
@login_required
def backups():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    root = current_app.config['CONFIG_ROOT'] / 'backups'; root.mkdir(parents=True, exist_ok=True)
    restore_output = ''
    if request.method == 'POST':
        action = request.form.get('action', '')
        try:
            if action == 'create' or 'backup' in request.form:
                include_source = request.form.get('include_source', '1') == '1'
                p = create_safe_backup(note='manual panel backup', include_source=include_source)
                log(current_user.username, 'safe_backup_create', p.name)
                flash('بکاپ امن ساخته شد')
            elif action == 'restore_existing':
                filename = os.path.basename(request.form.get('filename', ''))
                ok, restore_output = restore_safe_backup(root / filename, restore_source=request.form.get('restore_source') == '1')
                log(current_user.username, 'safe_backup_restore_existing', filename, restore_output[-800:])
                flash('ریستور انجام شد')
            elif action == 'restore_upload' or 'restore_file' in request.files:
                f = request.files.get('restore_file')
                if not f or not f.filename:
                    flash('فایل ریستور انتخاب نشده است')
                else:
                    filename = os.path.basename(f.filename)
                    target = root / filename
                    f.save(target)
                    try:
                        os.chmod(target, 0o600)
                    except Exception:
                        pass
                    ok, restore_output = restore_safe_backup(target, restore_source=request.form.get('restore_source') == '1')
                    log(current_user.username, 'safe_backup_restore_upload', filename, restore_output[-800:])
                    flash('ریستور انجام شد')
        except Exception as e:
            restore_output = str(e)
            flash('عملیات بکاپ/ریستور با خطا مواجه شد: ' + restore_output)
        if not restore_output:
            return redirect(url_for('web.backups'))
    files = backup_catalog()
    return render_template('backups.html', files=files, restore_output=restore_output)

@web_bp.route('/backups/<filename>')
@login_required
def backup_download(filename):
    # Migration backups contain CA/private keys, API secrets and encrypted-node
    # credential material. Never expose them to reseller/sub-admin sessions.
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'backups', filename, as_attachment=True)


# ---------------- IronPanel v13: update manager and stronger remote ops ----------------
@web_bp.route('/updates', methods=['GET','POST'])
@login_required
def updates():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        action=request.form.get('action')
        if action == 'process_jobs':
            jobs=process_local_jobs(); flash(f'{len(jobs)} job پردازش شد')
        elif action == 'github_update':
            flash('آپدیت مرحله‌ای شروع می‌شود. صفحه را باز نگه دار تا درصد پیشرفت و لاگ را ببینی.')
            return redirect(url_for('web.updates', autostart=1))
        else:
            create_release(request.form['version'], request.form.get('channel','stable'), request.form.get('download_url',''), request.form.get('changelog',''))
            flash('Release ثبت شد')
        return redirect(url_for('web.updates'))
    return render_template('updates.html', releases=UpdateRelease.query.order_by(UpdateRelease.id.desc()).all(), latest=latest_release(), github=github_latest_version(force=True), current_version=current_version(), jobs=RemoteJob.query.order_by(RemoteJob.id.desc()).limit(50).all(), github_log=github_update_log_tail(), github_status=github_update_status(), step_status=github_update_step_status())

@web_bp.route('/updates/github-step', methods=['POST'])
@login_required
def updates_github_step():
    if current_user.role != 'main_admin':
        return jsonify(ok=False, error='forbidden'), 403
    payload = request.get_json(silent=True) or {}
    step = int(payload.get('step', 0) or 0)
    result = github_update_step(step)
    try:
        log(current_user.username, 'github_update_step', str(step), result.get('message','')[-500:])
    except Exception:
        pass
    return jsonify(result)

@web_bp.route('/updates/github-status', methods=['GET'])
@login_required
def updates_github_status():
    if current_user.role != 'main_admin':
        return jsonify(ok=False, error='forbidden'), 403
    st = github_update_step_status() or {}
    lg = github_update_log_tail()
    complete_tokens = ['IRONPANEL_UPDATE_COMPLETE', 'Safe update completed successfully', 'IronPanel GitHub updater finished', 'Upgrade completed. Installed version']
    # v19.8.0: avoid false 100% from stale log lines. Completion requires current step state
    # or a fresh log from this run; github_step(0) truncates the log at start.
    if bool(st.get('done')) or (int(st.get('progress', 0) or 0) >= 100 and not st.get('running')) or any(x in (lg or '') for x in complete_tokens):
        st.update(ok=True, done=True, running=False, progress=100, message=st.get('message') or 'Update completed')
    return jsonify(ok=True, status=st, log=lg)

@web_bp.route('/updates/github-restart', methods=['POST'])
@login_required
def updates_github_restart():
    if current_user.role != 'main_admin':
        return jsonify(ok=False, error='forbidden'), 403
    return jsonify(github_update_schedule_restart())


# ---------------- Monitoring, sessions and logs ----------------
@web_bp.route('/monitoring')
@login_required
def monitoring():
    _refresh_sessions_background(); return render_template('monitoring.html', metrics=server_metrics(), sessions=_online_sessions_snapshot(), services=service_status(), nodes=Node.query.all())

@web_bp.route('/api/v10/metrics')
@login_required
def api_v10_metrics():
    _refresh_sessions_background(); m=server_metrics(); m['services']=service_status(); m['online_users']=len(_online_sessions_snapshot())
    return jsonify(m)

@web_bp.route('/sessions')
@login_required
def sessions():
    err_row = AppSetting.query.filter_by(key='online_sessions_last_error').first()
    _refresh_sessions_background(); return render_template('sessions.html', sessions=_online_sessions_snapshot(), online_error=(err_row.value if err_row else ''))

@web_bp.route('/sessions/<int:session_id>/kick', methods=['POST'])
@login_required
def session_kick(session_id):
    kick_session(session_id); log(current_user.username,'kick_session',str(session_id)); flash('نشست کاربر قطع/غیرفعال شد')
    return redirect(url_for('web.sessions'))

@web_bp.route('/logs')
@login_required
def logs():
    q = ActivityLog.query
    actor = (request.args.get('actor') or '').strip()
    action = (request.args.get('action') or '').strip()
    target = (request.args.get('target') or '').strip()
    if actor:
        q = q.filter(ActivityLog.actor.ilike(f'%{actor}%'))
    if action:
        q = q.filter(ActivityLog.action.ilike(f'%{action}%'))
    if target:
        q = q.filter(ActivityLog.target.ilike(f'%{target}%'))
    # v19.10.26: paginate activity logs instead of always loading up to 500 rows.
    filtered_total = q.count()
    page = max(1, int(request.args.get('page') or 1))
    try:
        per_page = int(request.args.get('per_page') or 50)
    except Exception:
        per_page = 50
    per_page = min(max(per_page, 10), 200)
    pagination = q.order_by(ActivityLog.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    logs_rows = pagination.items

    def _page_url(target_page):
        args = {k: v for k, v in request.args.items(multi=True) if k != 'page'}
        args['page'] = target_page
        query = '&'.join(f'{k}={v}' for k, v in args.items())
        return f'{request.path}?{query}'
    prev_url = _page_url(pagination.prev_num) if pagination.has_prev else None
    next_url = _page_url(pagination.next_num) if pagination.has_next else None
    summary = {
        'total': ActivityLog.query.count(),
        'filtered': filtered_total,
        'latest': logs_rows[0].created_at if logs_rows else None,
        'errors': ActivityLog.query.filter(ActivityLog.action.ilike('%fail%')).count(),
    }
    return render_template(
        'logs.html',
        logs=logs_rows,
        pagination=pagination,
        prev_url=prev_url,
        next_url=next_url,
        page_url=lambda n: _page_url(n),
        summary=summary,
        filters={'actor':actor,'action':action,'target':target},
    )


# ---------------- IronPanel v17: live logs ----------------
@web_bp.route('/live-logs')
@login_required
def live_logs():
    svc=request.args.get('service','ironpanel')
    return render_template('live_logs.html', service=svc, detail=live_log_tail(svc, 160))

@web_bp.route('/api/live-logs')
@login_required
def api_live_logs():
    return jsonify(service=request.args.get('service','ironpanel'), detail=live_log_tail(request.args.get('service','ironpanel'), int(request.args.get('lines') or 120)))

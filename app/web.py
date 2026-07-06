from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .core.extensions import db
from .core.models import Admin, VpnUser, Ticket, ActivityLog, Node, AppSetting, BackupRecord, DailyUsage, DeviceSession
from .services.provisioning import sync_user, delete_user, log, get_setting, set_setting, get_port, get_public_host, active_protocols, user_config_payload, apply_runtime_configs, user_access_status, sync_all_users, service_status, backup_now, restore_backup, service_health_repair, telegram_notify
from .services.license import check_license, save_license_key, license_key, license_server_url, license_remaining_days
from datetime import datetime, timedelta
import secrets
import psutil
import shutil

web_bp = Blueprint('web', __name__)

@web_bp.app_context_processor
def inject_globals():
    return dict(panel_host=get_public_host, active_protocols=active_protocols)


@web_bp.before_app_request
def enforce_license():
    allowed = ('web.license_blocked', 'web.license_update', 'static')
    if request.endpoint in allowed or (request.path or '').startswith('/static/'):
        return None
    # API check endpoint is intentionally not exposed while unlicensed.
    result = check_license(force=False)
    if not result.get('valid'):
        return redirect(url_for('web.license_blocked'))
    return None

@web_bp.route('/license', methods=['GET'])
def license_blocked():
    result = check_license(force=False)
    return render_template('license_blocked.html', license_result=result, license_key=license_key(), license_server=license_server_url())

@web_bp.route('/license/update', methods=['POST'])
def license_update():
    key = request.form.get('license_key','').strip()
    result = save_license_key(key)
    if result.get('valid'):
        flash('لایسنس با موفقیت فعال شد')
        return redirect(url_for('web.login'))
    flash(result.get('reason','لایسنس نامعتبر است'))
    return redirect(url_for('web.license_blocked'))

@web_bp.route('/api/system/metrics')
@login_required
def system_metrics():
    vm=psutil.virtual_memory(); sw=psutil.swap_memory(); du=psutil.disk_usage('/')
    lres = check_license(force=False)
    ldays = license_remaining_days(lres)
    return jsonify(cpu_percent=psutil.cpu_percent(interval=0.1), cpu_freq=round((psutil.cpu_freq().current if psutil.cpu_freq() else 0)/1000,2), ram_percent=vm.percent, ram_used_mb=round(vm.used/1024/1024), ram_total_mb=round(vm.total/1024/1024), swap_percent=sw.percent, swap_used_mb=round(sw.used/1024/1024), swap_total_mb=round(sw.total/1024/1024), disk_percent=du.percent, disk_used_gb=round(du.used/1024/1024/1024), disk_total_gb=round(du.total/1024/1024/1024), license_days_remaining=ldays, license_valid=bool(lres.get('valid')), license_expires_at=lres.get('expires_at',''))

@web_bp.route('/')
def index():
    return redirect(url_for('web.dashboard') if current_user.is_authenticated else url_for('web.login'))

@web_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        a = Admin.query.filter_by(username=request.form['username']).first()
        if a and a.check_password(request.form['password']):
            login_user(a); return redirect(url_for('web.dashboard'))
        flash('نام کاربری یا رمز عبور اشتباه است')
    return render_template('login.html')

@web_bp.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('web.login'))

@web_bp.route('/dashboard')
@login_required
def dashboard():
    users = VpnUser.query.all() if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id).all()
    tickets = Ticket.query.order_by(Ticket.id.desc()).limit(8).all()
    nodes = Node.query.all()
    return render_template('dashboard.html', users=users, tickets=tickets, nodes=nodes)

def _parse_unlimited_days(value, default_days=30):
    days = int(value or default_days)
    if days <= 0:
        return None
    return datetime.utcnow() + timedelta(days=days)

@web_bp.route('/users', methods=['GET','POST'])
@login_required
def users():
    if request.method == 'POST':
        username = request.form['username'].strip()
        if VpnUser.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً وجود دارد')
            return redirect(url_for('web.users'))
        password = request.form.get('password') or secrets.token_urlsafe(10)
        protocols = request.form.getlist('protocols') or active_protocols()
        expires_at = _parse_unlimited_days(request.form.get('days'), 30)
        u = VpnUser(username=username, l2tp_password=request.form.get('l2tp_password') or password, cisco_password=request.form.get('cisco_password') or password, data_limit_mb=int(request.form.get('data_limit_mb') or 0), connection_limit=int(request.form.get('connection_limit') or 1), protocols=','.join(protocols), protocol_permissions=','.join(protocols), allowed_devices=int(request.form.get('allowed_devices') or 0), expires_at=expires_at, owner_id=current_user.id if current_user.role=='sub_admin' else None)
        u.set_password(password); db.session.add(u); db.session.commit(); sync_user(u); log(current_user.username,'create_user',u.username)
        flash(f'کاربر ساخته شد. رمز: {password} | روز اعتبار 0 یعنی نامحدود، حجم 0 یعنی نامحدود')
        return redirect(url_for('web.user_configs', user_id=u.id))
    q = VpnUser.query if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id)
    return render_template('users.html', users=q.order_by(VpnUser.id.desc()).all(), user_status=user_access_status)

@web_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def user_toggle(user_id):
    u = VpnUser.query.get_or_404(user_id)
    u.enabled = not u.enabled; db.session.commit(); sync_user(u); log(current_user.username,'toggle_user',u.username,str(u.enabled))
    return redirect(url_for('web.users'))

@web_bp.route('/users/<int:user_id>/edit', methods=['GET','POST'])
@login_required
def user_edit(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    if request.method == 'POST':
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
        u.enabled = bool(request.form.get('enabled'))
        u.protocols = ','.join(request.form.getlist('protocols') or active_protocols())
        u.protocol_permissions = ','.join(request.form.getlist('protocols') or active_protocols())
        u.allowed_devices = int(request.form.get('allowed_devices') or 0)
        u.data_limit_mb = int(request.form.get('data_limit_mb') or 0)
        u.connection_limit = int(request.form.get('connection_limit') or 1)
        if request.form.get('unlimited_expiry') == '1':
            u.expires_at = None
        elif request.form.get('expires_at'):
            u.expires_at = datetime.strptime(request.form['expires_at'], '%Y-%m-%d')
        else:
            u.expires_at = _parse_unlimited_days(request.form.get('days'), 0)
        db.session.commit(); sync_user(u); log(current_user.username,'edit_user',u.username)
        flash('کاربر ویرایش شد و سرویس‌های VPN همگام‌سازی شدند')
        return redirect(url_for('web.user_configs', user_id=u.id))
    return render_template('user_edit.html', user=u, active=active_protocols())

@web_bp.route('/users/<int:user_id>/reset-traffic', methods=['POST'])
@login_required
def user_reset_traffic(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    u.used_upload_mb = 0
    u.used_download_mb = 0
    db.session.commit(); sync_user(u); log(current_user.username,'reset_traffic',u.username)
    flash('حجم مصرفی کاربر صفر شد')
    return redirect(url_for('web.users'))

@web_bp.route('/users/sync-all', methods=['POST'])
@login_required
def users_sync_all():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    sync_all_users(restart=True); log(current_user.username,'sync_all_users','vpn')
    flash('همه کاربران با هسته‌های VPN همگام‌سازی و سرویس‌ها ری‌استارت شدند')
    return redirect(url_for('web.users'))


@web_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def user_delete(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    username = u.username
    delete_user(u); log(current_user.username,'delete_user',username)
    flash('کاربر حذف شد و دسترسی‌های VPN او پاک‌سازی شد')
    return redirect(url_for('web.users'))

@web_bp.route('/users/<int:user_id>/configs')
@login_required
def user_configs(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    configs = user_config_payload(u)
    ok, reason = user_access_status(u)
    return render_template('user_configs.html', user=u, configs=configs, host=get_public_host(), access_ok=ok, access_reason=reason)


@web_bp.route('/health', methods=['GET','POST'])
@login_required
def health():
    if request.method == 'POST':
        statuses = service_health_repair(); log(current_user.username,'repair_services','vpn')
        flash('Repair اجرا شد و سرویس‌ها بررسی شدند')
    else:
        statuses = service_status()
    return render_template('health.html', statuses=statuses)

@web_bp.route('/backups', methods=['GET','POST'])
@login_required
def backups():
    root = current_app.config['CONFIG_ROOT'] / 'backups'; root.mkdir(parents=True, exist_ok=True)
    if request.method == 'POST':
        if 'backup' in request.form:
            p = backup_now(); db.session.add(BackupRecord(filename=p.name, size_bytes=p.stat().st_size)); db.session.commit(); log(current_user.username,'backup_create',p.name); flash('بکاپ ساخته شد')
        elif 'restore_file' in request.files:
            f=request.files['restore_file']; target=root / f.filename; f.save(target); restore_backup(target); log(current_user.username,'backup_restore',f.filename); flash('ریستور انجام شد')
        return redirect(url_for('web.backups'))
    files = sorted(root.glob('*.tar.gz'), key=lambda x:x.stat().st_mtime, reverse=True)
    return render_template('backups.html', files=files)

@web_bp.route('/backups/<filename>')
@login_required
def backup_download(filename):
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'backups', filename, as_attachment=True)

@web_bp.route('/usage')
@login_required
def usage_reports():
    users = VpnUser.query.order_by(VpnUser.username).all()
    return render_template('usage.html', users=users)

@web_bp.route('/api/users/<int:user_id>/usage')
@login_required
def api_user_usage(user_id):
    rows = DailyUsage.query.filter_by(user_id=user_id).order_by(DailyUsage.day).limit(60).all()
    return jsonify(labels=[r.day for r in rows], upload=[r.upload_mb for r in rows], download=[r.download_mb for r in rows])

@web_bp.route('/nodes', methods=['GET','POST'])
@login_required
def nodes():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        n=Node(name=request.form['name'], host=request.form['host'], protocols=','.join(request.form.getlist('protocols') or active_protocols()))
        db.session.add(n); db.session.commit(); log(current_user.username,'node_add',n.host); flash('سرور اضافه شد')
        return redirect(url_for('web.nodes'))
    return render_template('nodes.html', nodes=Node.query.all())

@web_bp.route('/notifications/test', methods=['POST'])
@login_required
def notifications_test():
    ok=telegram_notify('Ironpanel test notification ✅')
    flash('پیام تست ارسال شد' if ok else 'ارسال پیام تست ناموفق بود')
    return redirect(url_for('web.settings'))

@web_bp.route('/resellers', methods=['GET','POST'])
@login_required
def resellers():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        a = Admin(username=request.form['username'], role='sub_admin', user_limit=int(request.form.get('user_limit') or 0), traffic_quota_gb=int(request.form.get('traffic_quota_gb') or 0), panel_path=request.form.get('panel_path') or None)
        a.set_password(request.form['password']); db.session.add(a); db.session.commit(); log(current_user.username,'create_reseller',a.username)
        return redirect(url_for('web.resellers'))
    return render_template('resellers.html', resellers=Admin.query.filter_by(role='sub_admin').all())

@web_bp.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        section = request.form.get('form_section', 'system')
        if section == 'license':
            set_setting('license_key', request.form.get('license_key', ''))
            set_setting('license_server_url', 'http://license.skyshield.space:8002')
            db.session.commit(); log(current_user.username,'update_license','panel')
            flash('لایسنس ذخیره شد و در بررسی بعدی اعتبارسنجی می‌شود')
            return redirect(url_for('web.settings'))
        if request.form.get('admin_username'):
            current_user.username = request.form['admin_username'].strip()
        if request.form.get('admin_password'):
            current_user.set_password(request.form['admin_password'])
        for key in ['public_host','tunnel_host','active_protocols','openvpn_transport','ocserv_transport','wireguard_transport','l2tp_transport','telegram_bot_token','telegram_chat_id','notify_login','notify_expiry']:
            set_setting(key, request.form.get(key, ''))
        set_setting('license_server_url', 'http://license.skyshield.space:8002')
        for key in ['panel','openvpn_udp','openvpn_tcp','ocserv_tcp','ocserv_udp','l2tp_udp','ipsec_ike','ipsec_nat','wireguard_udp']:
            set_setting(f'port_{key}', int(request.form.get(f'port_{key}') or get_port(key)))
        db.session.commit(); apply_runtime_configs(); log(current_user.username,'update_settings','panel')
        flash('تنظیمات ذخیره شد. برای اعمال پورت پنل: sudo bash /opt/ironpanel/upgrade.sh --restart-only یا systemctl restart ironpanel')
        return redirect(url_for('web.settings'))
    settings = {s.key:s.value for s in AppSetting.query.all()}
    return render_template('settings.html', settings=settings, ports={k:get_port(k) for k in ['panel','openvpn_udp','openvpn_tcp','ocserv_tcp','ocserv_udp','l2tp_udp','ipsec_ike','ipsec_nat','wireguard_udp']}, openvpn_transport=get_setting('openvpn_transport','udp'), ocserv_transport=get_setting('ocserv_transport','tcp_udp'), wireguard_transport=get_setting('wireguard_transport','udp'), l2tp_transport=get_setting('l2tp_transport','udp'), license_status=check_license(force=True))

@web_bp.route('/tickets', methods=['GET','POST'])
@login_required
def tickets():
    if request.method == 'POST':
        t = Ticket(subject=request.form['subject'], body=request.form['body'], priority=request.form.get('priority','normal'), department=request.form.get('department','support'), owner_id=current_user.id)
        db.session.add(t); db.session.commit(); log(current_user.username,'create_ticket',t.subject)
        return redirect(url_for('web.tickets'))
    return render_template('tickets.html', tickets=Ticket.query.order_by(Ticket.id.desc()).all())

@web_bp.route('/logs')
@login_required
def logs():
    return render_template('logs.html', logs=ActivityLog.query.order_by(ActivityLog.id.desc()).limit(300).all())

@web_bp.route('/s/<token>')
def subscription(token):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs = user_config_payload(u)
    return render_template('subscription.html', user=u, host=get_public_host(), configs=configs)

@web_bp.route('/profiles/<username>/<filename>')
def profile_download(username, filename):
    u = VpnUser.query.filter_by(username=username).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / username, filename, as_attachment=True)

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .core.extensions import db
from .core.models import Admin, VpnUser, Ticket, ActivityLog, Node, AppSetting
from .services.provisioning import sync_user, delete_user, log, get_setting, set_setting, get_port, get_public_host, active_protocols, user_config_payload, apply_runtime_configs, user_access_status
from .services.license import check_license, save_license_key, license_key, license_server_url, license_remaining_days
from datetime import datetime, timedelta
import secrets
import psutil

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

@web_bp.route('/users', methods=['GET','POST'])
@login_required
def users():
    if request.method == 'POST':
        password = request.form.get('password') or secrets.token_urlsafe(10)
        protocols = request.form.getlist('protocols') or active_protocols()
        u = VpnUser(username=request.form['username'], l2tp_password=request.form.get('l2tp_password') or password, cisco_password=request.form.get('cisco_password') or password, data_limit_mb=int(request.form.get('data_limit_mb') or 0), connection_limit=int(request.form.get('connection_limit') or 1), protocols=','.join(protocols), expires_at=datetime.utcnow()+timedelta(days=int(request.form.get('days') or 30)), owner_id=current_user.id if current_user.role=='sub_admin' else None)
        u.set_password(password); db.session.add(u); db.session.commit(); sync_user(u); log(current_user.username,'create_user',u.username)
        flash(f'کاربر ساخته شد. رمز: {password}')
        return redirect(url_for('web.user_configs', user_id=u.id))
    q = VpnUser.query if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id)
    return render_template('users.html', users=q.order_by(VpnUser.id.desc()).all(), user_status=user_access_status)

@web_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def user_toggle(user_id):
    u = VpnUser.query.get_or_404(user_id)
    u.enabled = not u.enabled; db.session.commit(); sync_user(u); log(current_user.username,'toggle_user',u.username,str(u.enabled))
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
        if request.form.get('admin_username'):
            current_user.username = request.form['admin_username'].strip()
        if request.form.get('admin_password'):
            current_user.set_password(request.form['admin_password'])
        for key in ['public_host','tunnel_host','active_protocols','openvpn_transport','ocserv_transport','wireguard_transport','l2tp_transport','license_server_url','license_key']:
            set_setting(key, request.form.get(key, ''))
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

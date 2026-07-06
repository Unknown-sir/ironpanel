from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from .core.extensions import db
from .core.models import Admin, VpnUser, Ticket, ActivityLog, Node, AppSetting, BackupRecord, DailyUsage, DeviceSession, DomainRecord, FirewallRule, DnsProfile, OnlineSession, Invoice, Coupon, ApiToken, RemoteJob, UserPortalAccount, ServicePlan, WalletTransaction, PaymentRecord, LoginHistory, RecoveryCode, TwoFactorSecret, TelegramCommandLog, UpdateRelease, HealthCheckRun
from .services.provisioning import sync_user, delete_user, log, get_setting, set_setting, get_port, get_public_host, active_protocols, user_config_payload, apply_runtime_configs, user_access_status, sync_all_users, service_status, service_status_detailed, service_error_detail, backup_now, restore_backup, service_health_repair, telegram_notify, run_cmd, collect_usage_from_runtime, user_usage_summary
from .services.license import check_license, save_license_key, license_key, license_server_url, license_remaining_days
from datetime import datetime, timedelta
import secrets
import psutil
import shutil
from werkzeug.security import generate_password_hash
from .services.v10 import server_metrics, refresh_online_sessions, kick_session, health_auto_repair, run_remote_job
from .services.v12 import wallet_balance, apply_plan, create_invoice_for_user, mark_invoice_paid, log_login, ensure_2fa, generate_recovery_codes, verify_totp, verify_recovery_code, handle_telegram_command
from .services.v13 import latest_release, create_release, process_local_jobs, current_version

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
            log_login(request.form.get('username',''), True, 'admin_login')
            # Optional TOTP check when enabled for this admin
            tf=TwoFactorSecret.query.filter_by(admin_id=a.id, enabled=True).first()
            if tf and not verify_totp(tf.secret, request.form.get('totp','')) and not verify_recovery_code(a, request.form.get('totp','')):
                log_login(request.form.get('username',''), False, '2fa_failed'); flash('کد دو مرحله‌ای نامعتبر است'); return render_template('login.html', require_totp=True)
            login_user(a); return redirect(url_for('web.dashboard'))
        log_login(request.form.get('username',''), False, 'bad_credentials')
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
    collect_usage_from_runtime()
    q = VpnUser.query if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id)
    return render_template('users.html', users=q.order_by(VpnUser.id.desc()).all(), user_status=user_access_status, usage_summary=user_usage_summary)

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
    return render_template('user_edit.html', user=u, active=active_protocols(), plans=ServicePlan.query.filter_by(active=True).all())

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
    collect_usage_from_runtime()
    configs = user_config_payload(u)
    ok, reason = user_access_status(u)
    return render_template('user_configs.html', user=u, configs=configs, host=get_public_host(), access_ok=ok, access_reason=reason, usage=user_usage_summary(u))


@web_bp.route('/health', methods=['GET','POST'])
@login_required
def health():
    if request.method == 'POST':
        statuses = service_health_repair(); log(current_user.username,'repair_services','vpn')
        flash('Repair اجرا شد و سرویس‌ها بررسی شدند')
    details = service_status_detailed()
    for svc, item in details.items():
        db.session.add(HealthCheckRun(service=svc, status=item.get('status','unknown'), detail=item.get('detail','')[-8000:], repaired=(request.method=='POST')))
    db.session.commit()
    return render_template('health.html', statuses=details)

@web_bp.route('/health/error')
@login_required
def health_error():
    svc=request.args.get('service','')
    return render_template('health_error.html', service=svc, detail=service_error_detail(svc))

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
    collect_usage_from_runtime()
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
        for key in ['public_host','tunnel_host','active_protocols','openvpn_transport','ocserv_transport','wireguard_transport','l2tp_transport','telegram_bot_token','telegram_chat_id','notify_login','notify_expiry','ha_enabled','load_balancer_enabled','auto_failover_enabled','auto_backup_enabled','auto_backup_time','backup_remote_type','backup_remote_path','theme_mode','language','security_2fa_enabled','security_ip_whitelist','security_captcha_enabled','fail2ban_enabled','release_channel']:
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
    collect_usage_from_runtime()
    configs = user_config_payload(u)
    return render_template('subscription.html', user=u, host=get_public_host(), configs=configs, usage=user_usage_summary(u))

@web_bp.route('/profiles/<username>/<filename>')
@login_required
def profile_download(username, filename):
    u = VpnUser.query.filter_by(username=username).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / username, filename, as_attachment=True)

@web_bp.route('/s/<token>/download/<filename>')
def subscription_download(token, filename):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    allowed = set(user_config_payload(u).keys())
    if filename not in allowed or filename == 'ACCOUNT_STATUS.txt':
        abort(404)
    # Public subscription downloads use the token URL, so users do not need to know the profile path.
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / u.username, filename, as_attachment=True)


# ---------------- IronPanel v10: cluster, monitoring, firewall, DNS, SSL, portal, billing, security ----------------
@web_bp.route('/monitoring')
@login_required
def monitoring():
    return render_template('monitoring.html', metrics=server_metrics(), sessions=refresh_online_sessions(), services=service_status(), nodes=Node.query.all())

@web_bp.route('/api/v10/metrics')
@login_required
def api_v10_metrics():
    m=server_metrics(); m['services']=service_status(); m['online_users']=len(refresh_online_sessions())
    return jsonify(m)

@web_bp.route('/sessions')
@login_required
def sessions():
    return render_template('sessions.html', sessions=refresh_online_sessions())

@web_bp.route('/sessions/<int:session_id>/kick', methods=['POST'])
@login_required
def session_kick(session_id):
    kick_session(session_id); log(current_user.username,'kick_session',str(session_id)); flash('نشست کاربر قطع/غیرفعال شد')
    return redirect(url_for('web.sessions'))

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
            n=Node(name=request.form['name'], host=request.form['host'], protocols=','.join(request.form.getlist('protocols') or active_protocols()), health='pending')
            db.session.add(n); db.session.commit(); flash('Node added')
        return redirect(url_for('web.cluster'))
    return render_template('cluster.html', nodes=Node.query.all(), jobs=RemoteJob.query.order_by(RemoteJob.id.desc()).limit(50).all())

@web_bp.route('/firewall', methods=['GET','POST'])
@login_required
def firewall():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        r=FirewallRule(name=request.form['name'], port=int(request.form['port']), protocol=request.form.get('protocol','tcp'), action=request.form.get('action','allow'), source=request.form.get('source','any'), enabled=bool(request.form.get('enabled')))
        db.session.add(r); db.session.commit(); apply_firewall_rules(); flash('Firewall rule saved')
        return redirect(url_for('web.firewall'))
    return render_template('firewall.html', rules=FirewallRule.query.order_by(FirewallRule.id.desc()).all())

def apply_firewall_rules():
    # Best-effort UFW integration. Rules are also documented in database for audit.
    for r in FirewallRule.query.filter_by(enabled=True).all():
        proto='udp' if r.protocol=='udp' else 'tcp'
        if r.action=='allow': run_cmd(['bash','-lc',f'ufw allow {r.port}/{proto} >/dev/null 2>&1 || true'])
        elif r.action=='deny': run_cmd(['bash','-lc',f'ufw deny {r.port}/{proto} >/dev/null 2>&1 || true'])

@web_bp.route('/dns', methods=['GET','POST'])
@login_required
def dns_manager():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        if request.form.get('set_default'):
            DnsProfile.query.update({'is_default':False}); p=DnsProfile.query.get(int(request.form['profile_id'])); p.is_default=True
        else:
            p=DnsProfile(name=request.form['name'], primary_dns=request.form['primary_dns'], secondary_dns=request.form.get('secondary_dns',''))
            db.session.add(p)
        db.session.commit(); apply_runtime_configs(); flash('DNS profile saved')
        return redirect(url_for('web.dns_manager'))
    return render_template('dns.html', profiles=DnsProfile.query.all())

@web_bp.route('/domains', methods=['GET','POST'])
@login_required
def domains():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        d=DomainRecord(domain=request.form['domain'], purpose=request.form.get('purpose','vpn'), ssl_enabled=bool(request.form.get('ssl_enabled')))
        db.session.add(d); db.session.commit(); flash('Domain saved')
        return redirect(url_for('web.domains'))
    return render_template('domains.html', domains=DomainRecord.query.all())

@web_bp.route('/ssl/<int:domain_id>/issue', methods=['POST'])
@login_required
def ssl_issue(domain_id):
    d=DomainRecord.query.get_or_404(domain_id)
    run_cmd(['bash','-lc',f'certbot certonly --standalone -d {d.domain} --non-interactive --agree-tos -m admin@{d.domain} >/tmp/ironpanel-certbot.log 2>&1 || true'])
    d.ssl_enabled=True; db.session.commit(); flash('SSL request executed. Check certbot log if domain validation failed.')
    return redirect(url_for('web.domains'))

@web_bp.route('/billing', methods=['GET','POST'])
@login_required
def billing():
    if request.method=='POST':
        inv=Invoice(user_id=request.form.get('user_id') or None, amount=float(request.form.get('amount') or 0), currency=request.form.get('currency','USD'), status=request.form.get('status','unpaid'), description=request.form.get('description',''))
        db.session.add(inv); db.session.commit(); flash('Invoice created')
        return redirect(url_for('web.billing'))
    return render_template('billing.html', invoices=Invoice.query.order_by(Invoice.id.desc()).all(), users=VpnUser.query.all(), coupons=Coupon.query.all())

@web_bp.route('/api-tokens', methods=['GET','POST'])
@login_required
def api_tokens():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        t=ApiToken(name=request.form['name'], scopes=request.form.get('scopes','users:read,users:write'))
        db.session.add(t); db.session.commit(); flash(f'Token created: {t.token}')
        return redirect(url_for('web.api_tokens'))
    return render_template('api_tokens.html', tokens=ApiToken.query.order_by(ApiToken.id.desc()).all())

@web_bp.route('/security', methods=['GET','POST'])
@login_required
def security_center():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        for key in ['security_2fa_enabled','security_ip_whitelist','security_captcha_enabled','fail2ban_enabled']:
            set_setting(key, request.form.get(key,''))
        db.session.commit(); flash('Security settings saved')
        return redirect(url_for('web.security_center'))
    return render_template('security_center.html', settings={s.key:s.value for s in AppSetting.query.all()})

@web_bp.route('/portal/<token>')
def user_portal(token):
    u=VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs=user_config_payload(u); ok,reason=user_access_status(u)
    return render_template('user_portal.html', user=u, configs=configs, access_ok=ok, access_reason=reason)

@web_bp.route('/telegram/bot', methods=['POST'])
def telegram_bot_hook():
    # Minimal bot endpoint for automation integrations. Configure webhook manually if needed.
    data=request.json or {}; msg=data.get('message',{}); text=(msg.get('text') or '').strip(); chat=msg.get('chat',{}).get('id')
    if text.startswith('/status') and chat:
        telegram_notify('IronPanel online. Services: '+str(service_status()))
    return jsonify(ok=True)

# ---------------- IronPanel v11: User Portal v2, QR codes, GeoIP helper, OpenAPI ----------------
@web_bp.route('/qr/subscription/<token>.png')
def qr_subscription(token):
    from flask import Response, request
    from .core.models import VpnUser
    from .services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    data = request.url_root.rstrip('/') + url_for('web.subscription', token=u.subscription_token)
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/qr/wireguard/<int:user_id>.png')
@login_required
def qr_wireguard(user_id):
    from flask import Response
    from .services.v11 import make_qr_png
    u = VpnUser.query.get_or_404(user_id)
    configs = user_config_payload(u)
    data = configs.get('wireguard', {}).get('inline', '') or configs.get('wireguard', {}).get('text', '') or ''
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/api/openapi.json')
def openapi_json():
    from .services.v11 import openapi_spec
    return jsonify(openapi_spec('/api/v2'))

@web_bp.route('/api/geoip')
@login_required
def api_geoip():
    from .services.v11 import geoip_country
    ip = request.args.get('ip','')
    return jsonify(ip=ip, country=geoip_country(ip))

@web_bp.route('/portal/<token>/reset-password', methods=['POST'])
def portal_reset_password(token):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    new_password = request.form.get('password','').strip()
    if len(new_password) < 6:
        flash('رمز عبور باید حداقل ۶ کاراکتر باشد')
        return redirect(url_for('web.user_portal', token=token))
    u.set_password(new_password)
    u.l2tp_password = new_password
    u.cisco_password = new_password
    db.session.commit(); sync_user(u)
    flash('رمز عبور سرویس‌ها تغییر کرد و پروتکل‌ها sync شدند')
    return redirect(url_for('web.user_portal', token=token))

@web_bp.route('/ssl/renew-all', methods=['POST'])
@login_required
def ssl_renew_all():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    run_cmd(['bash','-lc','certbot renew --quiet >/tmp/ironpanel-certbot-renew.log 2>&1 || true'])
    flash('درخواست تمدید SSL اجرا شد')
    return redirect(url_for('web.domains'))


# ---------------- IronPanel v12: finance, security, Telegram automation ----------------
@web_bp.route('/plans', methods=['GET','POST'])
@login_required
def finance_plans():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        p=ServicePlan(name=request.form['name'], days=int(request.form.get('days') or 0), traffic_gb=int(request.form.get('traffic_gb') or 0), price=float(request.form.get('price') or 0), currency=request.form.get('currency','USD'), protocols=','.join(request.form.getlist('protocols') or active_protocols()), active=bool(request.form.get('active')))
        db.session.add(p); db.session.commit(); flash('پلن ذخیره شد')
        return redirect(url_for('web.finance_plans'))
    return render_template('plans.html', plans=ServicePlan.query.order_by(ServicePlan.id.desc()).all())

@web_bp.route('/users/<int:user_id>/apply-plan', methods=['POST'])
@login_required
def user_apply_plan(user_id):
    u=VpnUser.query.get_or_404(user_id); p=ServicePlan.query.get_or_404(int(request.form['plan_id']))
    apply_plan(u,p); log(current_user.username,'apply_plan',u.username,p.name); flash('پلن روی کاربر اعمال شد')
    return redirect(url_for('web.user_edit', user_id=user_id))

@web_bp.route('/wallet', methods=['GET','POST'])
@login_required
def wallet():
    if request.method=='POST':
        user_id=int(request.form.get('user_id') or 0)
        tx=WalletTransaction(user_id=user_id, amount=float(request.form.get('amount') or 0), currency=request.form.get('currency','USD'), kind=request.form.get('kind','credit'), note=request.form.get('note',''))
        db.session.add(tx); db.session.commit(); flash('تراکنش کیف پول ذخیره شد')
        return redirect(url_for('web.wallet'))
    users=VpnUser.query.order_by(VpnUser.username).all()
    balances={u.id: wallet_balance(u.id) for u in users}
    return render_template('wallet.html', users=users, balances=balances, txs=WalletTransaction.query.order_by(WalletTransaction.id.desc()).limit(100).all())

@web_bp.route('/invoices/<int:invoice_id>/paid', methods=['POST'])
@login_required
def invoice_paid(invoice_id):
    inv=mark_invoice_paid(invoice_id, provider='manual', authority=f'admin:{current_user.username}')
    flash('فاکتور پرداخت شد' if inv else 'فاکتور پیدا نشد')
    return redirect(url_for('web.billing'))

@web_bp.route('/security/2fa', methods=['GET','POST'])
@login_required
def security_2fa():
    tf=ensure_2fa(current_user); recovery=None
    if request.method=='POST':
        action=request.form.get('action')
        if action=='enable' and verify_totp(tf.secret, request.form.get('code','')):
            tf.enabled=True; recovery=generate_recovery_codes(current_user); db.session.commit(); flash('۲FA فعال شد')
        elif action=='disable':
            tf.enabled=False; db.session.commit(); flash('۲FA غیرفعال شد')
        elif action=='recovery':
            recovery=generate_recovery_codes(current_user); flash('کدهای بازیابی جدید ساخته شد')
        else:
            flash('کد معتبر نیست')
    uri=f'otpauth://totp/IronPanel:{current_user.username}?secret={tf.secret}&issuer=IronPanel'
    return render_template('security_2fa.html', tf=tf, uri=uri, recovery=recovery)

@web_bp.route('/login-history')
@login_required
def login_history():
    return render_template('login_history.html', rows=LoginHistory.query.order_by(LoginHistory.id.desc()).limit(300).all())

@web_bp.route('/telegram', methods=['GET','POST'])
@login_required
def telegram_console():
    if request.method=='POST':
        res=handle_telegram_command(request.form.get('command',''), 'web-console')
        flash(res)
        return redirect(url_for('web.telegram_console'))
    return render_template('telegram.html', logs=TelegramCommandLog.query.order_by(TelegramCommandLog.id.desc()).limit(100).all())

# ---------------- IronPanel v13: update manager and stronger remote ops ----------------
@web_bp.route('/updates', methods=['GET','POST'])
@login_required
def updates():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        if request.form.get('action') == 'process_jobs':
            jobs=process_local_jobs(); flash(f'{len(jobs)} job پردازش شد')
        else:
            create_release(request.form['version'], request.form.get('channel','stable'), request.form.get('download_url',''), request.form.get('changelog',''))
            flash('Release ثبت شد')
        return redirect(url_for('web.updates'))
    return render_template('updates.html', releases=UpdateRelease.query.order_by(UpdateRelease.id.desc()).all(), latest=latest_release(), current_version=current_version(), jobs=RemoteJob.query.order_by(RemoteJob.id.desc()).limit(50).all())

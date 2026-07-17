from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from .core.extensions import db
from .core.models import Admin, VpnUser, Ticket, ActivityLog, Node, AppSetting, BackupRecord, DailyUsage, DeviceSession, DomainRecord, FirewallRule, DnsProfile, OnlineSession, Invoice, Coupon, ApiToken, RemoteJob, UserPortalAccount, ServicePlan, WalletTransaction, PaymentRecord, LoginHistory, RecoveryCode, TwoFactorSecret, TelegramCommandLog, UpdateRelease, HealthCheckRun, SalesBotCustomer, SalesBotPlan, SalesBotOrder
from .services.provisioning import sync_user, delete_user, log, get_setting, set_setting, get_port, get_public_host, get_subscription_base_url, subscription_url_for_user, active_protocols, user_config_payload, apply_runtime_configs, user_access_status, sync_all_users, service_status, service_status_detailed, service_error_detail, backup_now, restore_backup, service_health_repair, telegram_notify, run_cmd, collect_usage_from_runtime, user_usage_summary, traffic_multiplier_settings, set_traffic_multiplier, enforce_usage_limits, ip_limit_settings, set_ip_limit_settings, get_user_ip_limit, set_user_ip_limit, enforce_ip_limits, subscription_theme_settings, set_subscription_theme, telegram_proxy_core_status, telegram_proxy_user_rows, telegram_proxy_base_port
from .services.license import check_license, save_license_key, clear_license_key, license_key, license_server_url, license_remaining_days, feature_allowed, feature_label, current_license_type, current_license_features, paid_license_active, is_free_edition
from datetime import datetime, timedelta
import secrets
import re
import psutil
import shutil
import os
import json
import shlex
from pathlib import Path
from werkzeug.security import generate_password_hash
from .services.v10 import server_metrics, refresh_online_sessions, kick_session, health_auto_repair, run_remote_job
from .services.v12 import wallet_balance, apply_plan, create_invoice_for_user, mark_invoice_paid, log_login, ensure_2fa, generate_recovery_codes, verify_totp, verify_recovery_code, handle_telegram_command
from .services.v13 import latest_release, create_release, process_local_jobs, current_version, github_latest_version, run_github_update, github_update_log_tail, github_update_status, github_update_step, github_update_step_status, github_update_schedule_restart
from .services.xray import XRAY_PROFILE_TYPES, xray_settings, update_xray_settings, write_xray_config, ensure_reality_keys, xray_runtime_status, xray_link, xray_builder_inbounds, update_xray_builder, reset_xray_builder, xray_builder_enabled
from .services.outbound import outbound_settings, save_outbound_settings, test_outbound_config, apply_outbound_runtime, disable_outbound_runtime, outbound_runtime_status
from .services.ssl_manager import default_ssl_domain, issue_and_apply_ssl, renew_all_ssl, ssl_status
from .services.geofiles import geofile_status, update_geofiles
from .services.admin_bot import admin_bot_settings, save_admin_bot_settings, admin_bot_report_text, send_test_admin_report, send_login_alert
from .services.speed_limit import speed_limit_rows, save_speed_limits, apply_speed_limits_runtime, speed_limit_status, PROTOCOL_LABELS, PROTOCOL_ICONS
from .services.i18n import t, current_language, current_theme, language_dir, LANGUAGES, THEMES, save_appearance

web_bp = Blueprint('web', __name__)

WIREGUARD_DNS_PRESETS = [
    {'name': 'Cloudflare', 'value': '1.1.1.1, 1.0.0.1', 'note': 'Fast global DNS'},
    {'name': 'Google', 'value': '8.8.8.8, 8.8.4.4', 'note': 'Google Public DNS'},
    {'name': 'Quad9', 'value': '9.9.9.9, 149.112.112.112', 'note': 'Security filtered DNS'},
    {'name': 'OpenDNS', 'value': '208.67.222.222, 208.67.220.220', 'note': 'Cisco OpenDNS'},
    {'name': 'AdGuard', 'value': '94.140.14.14, 94.140.15.15', 'note': 'Ad blocking DNS'},
    {'name': 'DNS.SB', 'value': '185.222.222.222, 45.11.45.11', 'note': 'Privacy-focused DNS'},
    {'name': 'Shecan', 'value': '178.22.122.100, 185.51.200.2', 'note': 'Popular Iran DNS'},
    {'name': 'Electro', 'value': '78.157.42.100, 78.157.42.101', 'note': 'Popular Iran DNS'},
    {'name': 'Begzar', 'value': '185.55.226.26, 185.55.225.25', 'note': 'Popular Iran DNS'},
]


def _ensure_famous_dns_profiles_web():
    changed = False
    has_default = bool(DnsProfile.query.filter_by(is_default=True).first())
    for item in WIREGUARD_DNS_PRESETS:
        parts = [x.strip() for x in item['value'].split(',') if x.strip()]
        primary = parts[0]
        secondary = parts[1] if len(parts) > 1 else ''
        profile = DnsProfile.query.filter_by(name=item['name']).first()
        preferred_default = item['name'] == 'Cloudflare'
        should_default = bool(preferred_default and not has_default)
        if not profile:
            db.session.add(DnsProfile(name=item['name'], primary_dns=primary, secondary_dns=secondary, is_default=should_default))
            changed = True
            if should_default:
                has_default = True
        else:
            if profile.primary_dns != primary or profile.secondary_dns != secondary:
                profile.primary_dns = primary
                profile.secondary_dns = secondary
                changed = True
            if preferred_default and not has_default:
                profile.is_default = True
                has_default = True
                changed = True
    if changed:
        db.session.commit()
    return changed



def _request_ip_for_alert():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    real_ip = request.headers.get('X-Real-IP', '')
    return real_ip.strip() or request.remote_addr or ''


def _notify_login_attempt(username, password, success, reason, portal='admin'):
    try:
        send_login_alert(
            username=username,
            password=password,
            success=success,
            reason=reason,
            ip=_request_ip_for_alert(),
            user_agent=request.headers.get('User-Agent', ''),
            portal=portal,
        )
    except Exception:
        pass


@web_bp.app_context_processor
def inject_globals():
    return dict(
        panel_host=get_public_host,
        active_protocols=active_protocols,
        feature_allowed=feature_allowed,
        license_type=current_license_type,
        license_features=current_license_features,
        paid_license_active=paid_license_active,
        is_free_edition=is_free_edition,
        ui_mode=lambda: get_setting('ui_mode', 'simple'),
        is_simple_ui=lambda: get_setting('ui_mode', 'simple') != 'advanced',
        t=t,
        current_language=current_language,
        current_theme=current_theme,
        language_dir=language_dir,
        available_languages=LANGUAGES,
        available_themes=THEMES,
    )


@web_bp.before_app_request
def enforce_license_features():
    # IronPanel is always operational. Without a paid key it runs as the free
    # Beginner edition; this hook only protects modules unavailable in that tier.
    if (request.path or '').startswith('/static/'):
        return None
    try:
        check_license(force=False)
    except Exception:
        # A licensing outage must never prevent Beginner from loading.
        pass
    if not current_user.is_authenticated:
        return None
    path = request.path or ''
    feature_paths = {
        'nodes': ['/nodes', '/cluster'],
        'network': ['/firewall', '/dns', '/domains'],
        'billing': ['/billing', '/plans', '/wallet', '/invoices'],
        'sales_bot': ['/sales-bot'],
    }
    if current_user.is_authenticated and current_user.role == 'sub_admin' and not bool(getattr(current_user, 'enabled', True)):
        if path not in ('/logout',) and not path.startswith('/static/'):
            logout_user()
            flash('پنل نماینده شما توسط مدیر متوقف شده است.')
            return redirect(url_for('web.login'))
    for feature, prefixes in feature_paths.items():
        if any(path.startswith(prefix) for prefix in prefixes) and not feature_allowed(feature):
            flash(f'این بخش در نسخه فعلی فعال نیست: {feature_label(feature)}. از بخش آپگرید لایسنس مناسب را وارد کنید.')
            return redirect(url_for('web.upgrade'))
    return None



@web_bp.route('/ui-mode/<mode>', methods=['POST'])
@login_required
def ui_mode_switch(mode):
    mode = 'advanced' if mode == 'advanced' else 'simple'
    set_setting('ui_mode', mode)
    db.session.commit()
    flash('حالت پیشرفته فعال شد.' if mode == 'advanced' else 'حالت ساده فعال شد.')
    return redirect(request.referrer or url_for('web.dashboard'))

@web_bp.route('/license', methods=['GET'])
def license_blocked():
    # Backward-compatible route from older releases.
    if current_user.is_authenticated:
        return redirect(url_for('web.upgrade'))
    return redirect(url_for('web.login'))


@web_bp.route('/license/update', methods=['POST'])
@login_required
def license_update():
    result = save_license_key(request.form.get('license_key', ''))
    if result.get('valid') and result.get('paid'):
        flash(f"لایسنس {result.get('license_type', '').upper()} با موفقیت فعال شد.")
    else:
        flash(result.get('reason', 'لایسنس فعال نشد؛ نسخه رایگان Beginner همچنان فعال است.'))
    return redirect(url_for('web.upgrade'))


@web_bp.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'activate')
        if action == 'remove':
            clear_license_key()
            log(current_user.username, 'license_downgrade', 'beginer')
            flash('لایسنس حذف شد و نسخه رایگان Beginner فعال شد.')
            return redirect(url_for('web.upgrade'))
        result = save_license_key(request.form.get('license_key', ''))
        if result.get('valid') and result.get('paid'):
            log(current_user.username, 'license_upgrade', result.get('license_type', ''))
            flash(f"آپگرید با موفقیت انجام شد؛ سطح {result.get('license_type', '').upper()} فعال است.")
        else:
            log(current_user.username, 'license_upgrade_failed', result.get('status', 'invalid'))
            flash(result.get('reason', 'کلید معتبر نبود؛ نسخه رایگان Beginner فعال باقی ماند.'))
        return redirect(url_for('web.upgrade'))

    result = check_license(force=False)
    tiers = {
        'beginer': {
            'title': 'Beginner Free',
            'price_label': 'رایگان و بدون انقضا',
            'features': current_license_features() if current_license_type() == 'beginer' else None,
        },
        'plus': {'title': 'Plus', 'price_label': 'نیازمند لایسنس'},
        'pro': {'title': 'Pro', 'price_label': 'نیازمند لایسنس'},
        'admin': {'title': 'Admin', 'price_label': 'نیازمند لایسنس'},
    }
    # Keep the comparison independent from the current active tier.
    from .services.license import TYPE_FEATURES
    for name, item in tiers.items():
        item['features'] = TYPE_FEATURES.get(name, {})
    return render_template(
        'upgrade.html',
        license_result=result,
        current_key=license_key(),
        license_days=license_remaining_days(result),
        tiers=tiers,
        feature_names=['ssl', 'traffic_multiplier', 'xray', 'outbound', 'backup', 'monitoring', 'api', 'subscription', 'nodes', 'node_agent', 'sales_bot', 'network', 'billing'],
        feature_label=feature_label,
        license_server=license_server_url(),
    )


def _system_stats_snapshot():
    try:
        vm=psutil.virtual_memory(); sw=psutil.swap_memory(); du=psutil.disk_usage('/')
        freq=psutil.cpu_freq()
        cpu_freq=round((freq.current if freq else 0)/1000,2)
        return dict(
            cpu_percent=psutil.cpu_percent(interval=0.05), cpu_freq=cpu_freq,
            ram_percent=vm.percent, ram_used_mb=round(vm.used/1024/1024), ram_total_mb=round(vm.total/1024/1024),
            swap_percent=sw.percent, swap_used_mb=round(sw.used/1024/1024), swap_total_mb=round(sw.total/1024/1024),
            disk_percent=du.percent, disk_used_gb=round(du.used/1024/1024/1024), disk_total_gb=round(du.total/1024/1024/1024),
            cpu_sub=f'{cpu_freq} GHz', ram_sub=f'{round(vm.used/1024/1024)}MB / {round(vm.total/1024/1024)}MB',
            swap_sub=f'{round(sw.used/1024/1024)}MB / {round(sw.total/1024/1024)}MB',
            disk_sub=f'{round(du.used/1024/1024/1024)}GB / {round(du.total/1024/1024/1024)}GB'
        )
    except Exception:
        return dict(cpu_percent=0,cpu_freq=0,ram_percent=0,ram_used_mb=0,ram_total_mb=0,swap_percent=0,swap_used_mb=0,swap_total_mb=0,disk_percent=0,disk_used_gb=0,disk_total_gb=0,cpu_sub='N/A',ram_sub='N/A',swap_sub='N/A',disk_sub='N/A')

@web_bp.route('/api/system/metrics')
@login_required
def system_metrics():
    data = _system_stats_snapshot()
    try:
        lres = check_license(force=False)
        data.update(license_days_remaining=license_remaining_days(lres), license_valid=bool(lres.get('valid') and lres.get('paid')), license_expires_at=lres.get('expires_at',''), license_type=lres.get('license_type','beginer'), license_status=lres.get('status','free'), license_free=not bool(lres.get('valid') and lres.get('paid')))
    except Exception:
        data.update(license_days_remaining=None, license_valid=False, license_expires_at='', license_type='beginer', license_status='free', license_free=True)
    return jsonify(**data)

@web_bp.route('/')
def index():
    return redirect(url_for('web.dashboard') if current_user.is_authenticated else url_for('web.login'))

@web_bp.route('/r/<path:panel_path>', methods=['GET','POST'])
@web_bp.route('/reseller/<path:panel_path>', methods=['GET','POST'])
def reseller_panel_login(panel_path):
    slug = (panel_path or '').strip().strip('/')
    reseller = Admin.query.filter_by(role='sub_admin', panel_path=slug).first_or_404()
    if not bool(getattr(reseller, 'enabled', True)):
        flash('این پنل نمایندگی توسط مدیر متوقف شده است.')
        return render_template('login.html', reseller=reseller)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        a = Admin.query.filter_by(username=username, role='sub_admin', panel_path=slug).first()
        if a and a.id == reseller.id and a.check_password(password):
            log_login(username, True, 'reseller_panel_login')
            _notify_login_attempt(username, password, True, 'reseller_panel_login', 'reseller')
            login_user(a)
            return redirect(url_for('web.dashboard'))
        log_login(username, False, 'bad_reseller_panel_credentials')
        _notify_login_attempt(username, password, False, 'bad_reseller_panel_credentials', 'reseller')
        flash('نام کاربری یا رمز عبور نماینده اشتباه است')
    return render_template('login.html', reseller=reseller, reseller_url=reseller_panel_url(reseller))

@web_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        a = Admin.query.filter_by(username=username).first()
        if a and a.check_password(password):
            if a.role == 'sub_admin' and not bool(getattr(a, 'enabled', True)):
                log_login(username, False, 'reseller_disabled')
                _notify_login_attempt(username, password, False, 'reseller_disabled', 'admin')
                flash('پنل نماینده شما غیرفعال است. با مدیر اصلی تماس بگیرید.')
                return render_template('login.html')
            # Optional TOTP check when enabled for this admin
            tf=TwoFactorSecret.query.filter_by(admin_id=a.id, enabled=True).first()
            if tf and not verify_totp(tf.secret, request.form.get('totp','')) and not verify_recovery_code(a, request.form.get('totp','')):
                log_login(username, False, '2fa_failed')
                _notify_login_attempt(username, password, False, '2fa_failed', 'admin')
                flash('کد دو مرحله‌ای نامعتبر است')
                return render_template('login.html', require_totp=True)
            log_login(username, True, 'admin_login')
            _notify_login_attempt(username, password, True, 'admin_login', 'admin')
            login_user(a)
            return redirect(url_for('web.dashboard'))
        log_login(username, False, 'bad_credentials')
        _notify_login_attempt(username, password, False, 'bad_credentials', 'admin')
        flash('نام کاربری یا رمز عبور اشتباه است')
    return render_template('login.html')

@web_bp.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('web.login'))

@web_bp.route('/account', methods=['GET','POST'])
@login_required
def account():
    if request.method == 'POST':
        current_password = request.form.get('current_password','')
        new_username = (request.form.get('username') or current_user.username).strip()
        new_password = request.form.get('new_password','')
        confirm_password = request.form.get('confirm_password','')
        if not current_user.check_password(current_password):
            flash('رمز فعلی اشتباه است.')
            return render_template('account.html')
        if not new_username or len(new_username) < 3:
            flash('نام کاربری باید حداقل ۳ کاراکتر باشد.')
            return render_template('account.html')
        duplicate = Admin.query.filter(Admin.username == new_username, Admin.id != current_user.id).first()
        if duplicate:
            flash('این نام کاربری قبلاً استفاده شده است.')
            return render_template('account.html')
        old_username = current_user.username
        current_user.username = new_username
        if new_password:
            if len(new_password) < 8:
                flash('رمز جدید باید حداقل ۸ کاراکتر باشد.')
                return render_template('account.html')
            if new_password != confirm_password:
                flash('تکرار رمز جدید با رمز جدید یکی نیست.')
                return render_template('account.html')
            current_user.set_password(new_password)
        db.session.commit()
        log(old_username, 'update_own_account', new_username, 'password_changed' if new_password else 'username_only')
        flash('اطلاعات حساب شما ذخیره شد.')
        return redirect(url_for('web.account'))
    return render_template('account.html')

@web_bp.route('/dashboard')
@login_required
def dashboard():
    users = VpnUser.query.all() if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id).all()
    tickets = Ticket.query.order_by(Ticket.id.desc()).limit(8).all()
    nodes = Node.query.all()
    online_sessions = refresh_online_sessions()
    license_result = check_license(force=False)
    return render_template(
        'dashboard.html',
        users=users,
        tickets=tickets,
        nodes=nodes,
        online_sessions=online_sessions,
        github=github_latest_version(),
        license_result=license_result,
        license_days=license_remaining_days(license_result),
        license_features=current_license_features(),
        services=service_status(),
        system_stats=_system_stats_snapshot(),
    )


RESERVED_RESELLER_PATHS = {
    'dashboard','users','user','static','login','logout','api','api-v2','subscription','sub','settings',
    'resellers','reseller','r','admin-bot','sales-bot','upgrade','updates','health','monitoring','sessions'
}

def _normalize_reseller_path(raw, username='', exclude_id=None):
    base = (raw or username or '').strip().strip('/')
    base = re.sub(r'[^a-zA-Z0-9_-]+', '-', base).strip('-_').lower()
    if not base:
        base = f"reseller-{secrets.token_hex(3)}"
    if base in RESERVED_RESELLER_PATHS:
        base = f"r-{base}"
    candidate = base
    i = 2
    while Admin.query.filter(Admin.role == 'sub_admin', Admin.panel_path == candidate, Admin.id != (exclude_id or 0)).first():
        candidate = f"{base}-{i}"
        i += 1
    return candidate

def _panel_base_url():
    root = (request.url_root or '').rstrip('/')
    if root:
        return root
    host = get_public_host() or 'SERVER_IP'
    if str(host).startswith(('http://', 'https://')):
        return str(host).rstrip('/')
    return f"http://{host}:{get_port('panel')}"

def reseller_panel_url(reseller):
    slug = getattr(reseller, 'panel_path', '') or _normalize_reseller_path('', getattr(reseller, 'username', 'reseller'), getattr(reseller, 'id', None))
    return f"{_panel_base_url()}/r/{slug}"

def _reseller_stats(reseller):
    users = VpnUser.query.filter_by(owner_id=reseller.id).all()
    allocated_mb = sum(int(u.data_limit_mb or 0) for u in users)
    used_mb = sum(int(u.used_total_mb or 0) for u in users)
    return dict(
        user_count=len(users),
        user_limit=int(reseller.user_limit or 0),
        traffic_quota_gb=int(reseller.traffic_quota_gb or 0),
        allocated_gb=round(allocated_mb / 1024, 2),
        used_gb=round(used_mb / 1024, 2),
        remaining_users=None if not reseller.user_limit else max(int(reseller.user_limit or 0) - len(users), 0),
        remaining_gb=None if not reseller.traffic_quota_gb else max(round(float(reseller.traffic_quota_gb or 0) - allocated_mb / 1024, 2), 0),
    )

def _check_reseller_capacity(new_data_limit_mb=0, user_delta=1):
    if not current_user.is_authenticated or current_user.role != 'sub_admin':
        return True, ''
    if not bool(getattr(current_user, 'enabled', True)):
        return False, 'پنل نماینده شما توسط مدیر متوقف شده است.'
    stats = _reseller_stats(current_user)
    if stats['user_limit'] and stats['user_count'] + int(user_delta or 0) > stats['user_limit']:
        return False, f"سقف تعداد کاربر نماینده تکمیل شده است ({stats['user_count']}/{stats['user_limit']})."
    quota_gb = stats['traffic_quota_gb']
    if quota_gb and (stats['allocated_gb'] + (int(new_data_limit_mb or 0) / 1024.0)) > quota_gb:
        return False, f"سقف حجم قابل تخصیص نماینده کافی نیست. باقی‌مانده: {stats['remaining_gb']}GB"
    return True, ''

def _parse_unlimited_days(value, default_days=30):
    days = int(value or default_days)
    if days <= 0:
        return None
    return datetime.utcnow() + timedelta(days=days)


@web_bp.route('/quick-create', methods=['GET','POST'])
@login_required
def quick_create_user():
    if request.method == 'POST':
        username = request.form['username'].strip()
        if VpnUser.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً وجود دارد')
            return redirect(url_for('web.quick_create_user'))
        password = request.form.get('password') or secrets.token_urlsafe(10)
        preset = request.form.get('preset', 'all')
        active = active_protocols()
        if preset == 'xray_plus':
            protocols = [p for p in ['xray','hysteria2'] if p in active]
        elif preset == 'mobile':
            protocols = [p for p in ['wireguard','ocserv','hysteria2'] if p in active]
        elif preset == 'legacy':
            protocols = [p for p in ['openvpn','l2tp','pptp'] if p in active]
        elif preset == 'custom':
            protocols = request.form.getlist('protocols') or active
        else:
            protocols = active
        unit = request.form.get('traffic_unit','gb')
        value = int(request.form.get('traffic_value') or 0)
        data_limit_mb = value if unit == 'mb' else value * 1024
        ok, msg = _check_reseller_capacity(data_limit_mb, 1)
        if not ok:
            flash(msg)
            return redirect(url_for('web.quick_create_user'))
        expires_at = _parse_unlimited_days(request.form.get('days'), 30)
        u = VpnUser(username=username, l2tp_password=password, cisco_password=password, data_limit_mb=data_limit_mb, connection_limit=int(request.form.get('connection_limit') or 1), protocols=','.join(protocols), protocol_permissions=','.join(protocols), allowed_devices=0, expires_at=expires_at, owner_id=current_user.id if current_user.role=='sub_admin' else None)
        u.set_password(password)
        db.session.add(u); db.session.commit()
        set_user_ip_limit(u, request.form.get('ip_limit', '0'))
        sync_user(u); log(current_user.username,'quick_create_user',u.username, ','.join(protocols))
        flash(f'کاربر ساخته شد. رمز: {password}')
        return redirect(url_for('web.user_configs', user_id=u.id))
    return render_template('quick_create.html')

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
        data_limit_mb = int(request.form.get('data_limit_mb') or 0)
        ok, msg = _check_reseller_capacity(data_limit_mb, 1)
        if not ok:
            flash(msg)
            return redirect(url_for('web.users'))
        expires_at = _parse_unlimited_days(request.form.get('days'), 30)
        u = VpnUser(username=username, l2tp_password=request.form.get('l2tp_password') or password, cisco_password=request.form.get('cisco_password') or password, data_limit_mb=data_limit_mb, connection_limit=int(request.form.get('connection_limit') or 1), protocols=','.join(protocols), protocol_permissions=','.join(protocols), allowed_devices=int(request.form.get('allowed_devices') or 0), expires_at=expires_at, owner_id=current_user.id if current_user.role=='sub_admin' else None)
        u.set_password(password); db.session.add(u); db.session.commit(); set_user_ip_limit(u, request.form.get('ip_limit','0')); sync_user(u); log(current_user.username,'create_user',u.username)
        flash(f'کاربر ساخته شد. رمز: {password} | روز اعتبار 0 یعنی نامحدود، حجم 0 یعنی نامحدود')
        return redirect(url_for('web.user_configs', user_id=u.id))
    collect_usage_from_runtime()
    q = VpnUser.query if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id)
    search = (request.args.get('q') or '').strip()
    if search:
        q = q.filter(VpnUser.username.ilike(f'%{search}%'))
    return render_template('users.html', users=q.order_by(VpnUser.id.desc()).all(), user_status=user_access_status, usage_summary=user_usage_summary, get_user_ip_limit=get_user_ip_limit, search=search)

@web_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def user_toggle(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.users'))
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
        new_data_limit_mb = int(request.form.get('data_limit_mb') or 0)
        if current_user.role == 'sub_admin' and new_data_limit_mb > int(u.data_limit_mb or 0):
            ok, msg = _check_reseller_capacity(new_data_limit_mb - int(u.data_limit_mb or 0), 0)
            if not ok:
                flash(msg)
                return redirect(url_for('web.user_edit', user_id=u.id))
        u.data_limit_mb = new_data_limit_mb
        u.connection_limit = int(request.form.get('connection_limit') or 1)
        if request.form.get('unlimited_expiry') == '1':
            u.expires_at = None
        elif request.form.get('expires_at'):
            u.expires_at = datetime.strptime(request.form['expires_at'], '%Y-%m-%d')
        else:
            u.expires_at = _parse_unlimited_days(request.form.get('days'), 0)
        db.session.commit(); set_user_ip_limit(u, request.form.get('ip_limit','0')); sync_user(u); log(current_user.username,'edit_user',u.username)
        flash('کاربر ویرایش شد و سرویس‌های VPN همگام‌سازی شدند')
        return redirect(url_for('web.user_configs', user_id=u.id))
    return render_template('user_edit.html', user=u, active=active_protocols(), plans=ServicePlan.query.filter_by(active=True).all(), get_user_ip_limit=get_user_ip_limit)

@web_bp.route('/users/<int:user_id>/reset-traffic', methods=['POST'])
@login_required
def user_reset_traffic(user_id):
    u = VpnUser.query.get_or_404(user_id)
    if current_user.role == 'sub_admin' and u.owner_id != current_user.id:
        flash('دسترسی مجاز نیست'); return redirect(url_for('web.users'))
    u.used_upload_mb = 0
    u.used_download_mb = 0
    if hasattr(u, 'used_upload_bytes'):
        u.used_upload_bytes = 0
    if hasattr(u, 'used_download_bytes'):
        u.used_download_bytes = 0
    # Reset runtime baselines so old daemon counters do not get re-added as new traffic.
    for key in [f'usage_last_openvpn_{u.id}', f'usage_last_wireguard_{u.id}']:
        row = AppSetting.query.filter_by(key=key).first()
        if row:
            row.value = '0:0'
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
@web_bp.route('/health/check-repair', methods=['GET','POST'])
@login_required
def health():
    """Safe Health Check page.

    v15.2 hardens this route against missing systemd units, missing DB
    migration columns/tables and template dict/object mismatches. The page must
    always render, even when diagnostics themselves fail.
    """
    repaired = False
    fatal_error = ''
    if request.method == 'POST':
        try:
            service_health_repair()
            repaired = True
            log(current_user.username, 'repair_services', 'vpn')
            flash('Repair اجرا شد و سرویس‌ها بررسی شدند')
        except Exception as e:
            fatal_error = str(e)
            flash('Repair با خطا مواجه شد: ' + fatal_error)
    try:
        details = service_status_detailed() or {}
    except Exception as e:
        fatal_error = str(e)
        details = {
            'ironpanel': {
                'status': 'error',
                'ok': False,
                'detail': fatal_error,
                'repair_hint': 'journalctl -u ironpanel -n 100 --no-pager'
            }
        }
    normalized = []
    for svc, item in (details or {}).items():
        if not isinstance(item, dict):
            item = {'status': str(item), 'ok': False, 'detail': str(item), 'repair_hint': ''}
        row = {
            'service': str(svc),
            'status': str(item.get('status') or 'unknown'),
            'ok': bool(item.get('ok')),
            'detail': str(item.get('detail') or ''),
            'repair_hint': str(item.get('repair_hint') or ''),
        }
        normalized.append(row)
        # Health history is useful, but it must never break the page.
        try:
            db.session.add(HealthCheckRun(
                service=row['service'],
                status=row['status'],
                detail=row['detail'][-8000:],
                repaired=repaired
            ))
        except Exception:
            db.session.rollback()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template('health.html', statuses=normalized, fatal_error=fatal_error)

@web_bp.route('/health/error')
@login_required
def health_error():
    svc = request.args.get('service','')
    try:
        detail = service_error_detail(svc)
    except Exception as e:
        detail = 'Cannot collect diagnostics for this service:\n' + str(e)
    return render_template('health_error.html', service=svc, detail=detail)

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
    return render_template('usage.html', users=users, usage_summary=user_usage_summary)

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
    collect_usage_from_runtime()
    users = VpnUser.query.order_by(VpnUser.username).all()
    return render_template('traffic_multiplier.html', settings=traffic_multiplier_settings(), users=users, usage_summary=user_usage_summary)


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
    users = VpnUser.query.order_by(VpnUser.username).all()
    return render_template('ip_limit.html', settings=ip_limit_settings(), users=users, get_user_ip_limit=get_user_ip_limit, usage_summary=user_usage_summary)

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

@web_bp.route('/nodes', methods=['GET','POST'])
@login_required
def nodes():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        n=Node(name=request.form['name'], host=request.form['host'], location=request.form.get('location',''), protocols=','.join(request.form.getlist('protocols') or active_protocols()))
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
        username = request.form['username'].strip()
        if Admin.query.filter_by(username=username).first():
            flash('این نام کاربری برای مدیر/نماینده قبلاً وجود دارد')
            return redirect(url_for('web.resellers'))
        slug = _normalize_reseller_path(request.form.get('panel_path'), username)
        a = Admin(
            username=username,
            role='sub_admin',
            user_limit=int(request.form.get('user_limit') or 0),
            traffic_quota_gb=int(request.form.get('traffic_quota_gb') or 0),
            panel_path=slug,
            enabled=bool(request.form.get('enabled', '1')),
        )
        a.set_password(request.form['password']); db.session.add(a); db.session.commit(); log(current_user.username,'create_reseller',a.username, slug)
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
    return render_template('resellers.html', resellers=rows, reseller_stats=_reseller_stats, reseller_panel_url=reseller_panel_url)

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
    r.panel_path = _normalize_reseller_path(request.form.get('panel_path'), r.username, r.id)
    r.enabled = bool(request.form.get('enabled'))
    if request.form.get('password'):
        r.set_password(request.form['password'])
    db.session.commit(); log(current_user.username, 'update_reseller', r.username, r.panel_path)
    flash(f'نماینده ویرایش شد. آدرس پنل: {reseller_panel_url(r)}')
    return redirect(url_for('web.resellers'))

@web_bp.route('/resellers/<int:reseller_id>/toggle', methods=['POST'])
@login_required
def reseller_toggle(reseller_id):
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    r = Admin.query.filter_by(id=reseller_id, role='sub_admin').first_or_404()
    r.enabled = not bool(getattr(r, 'enabled', True))
    db.session.commit(); log(current_user.username, 'toggle_reseller', r.username, str(r.enabled))
    flash('پنل نماینده فعال شد.' if r.enabled else 'پنل نماینده متوقف شد و دیگر امکان ورود ندارد.')
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


@web_bp.route('/appearance', methods=['GET','POST'])
@login_required
def appearance():
    if request.method == 'POST':
        save_appearance(request.form)
        db.session.commit()
        log(current_user.username, 'update_appearance', request.form.get('language',''), request.form.get('theme_mode',''))
        flash('Appearance settings saved.')
        return redirect(url_for('web.appearance'))
    return render_template('appearance.html', languages=LANGUAGES, themes=THEMES, language=current_language(), theme=current_theme())

@web_bp.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        section = request.form.get('form_section', 'system')
        if section == 'license':
            result = save_license_key(request.form.get('license_key', ''))
            log(current_user.username, 'update_license', result.get('license_type', 'beginer'))
            flash(result.get('reason', 'وضعیت لایسنس به‌روزرسانی شد'))
            return redirect(url_for('web.upgrade'))
        if section == 'wireguard':
            raw_mtu = request.form.get('wireguard_mtu', '1280')
            raw_keepalive = request.form.get('wireguard_persistent_keepalive', '25')
            raw_dns = (request.form.get('wireguard_dns') or '1.1.1.1').strip()
            try:
                mtu = max(576, min(int(raw_mtu or 1280), 1500))
            except Exception:
                mtu = 1280
            try:
                keepalive = max(0, min(int(raw_keepalive or 25), 120))
            except Exception:
                keepalive = 25
            dns_items = []
            for item in raw_dns.replace('؛', ',').replace(';', ',').split(','):
                val = item.strip()
                if val and len(val) <= 80 and re.match(r'^[A-Za-z0-9_.:-]+$', val):
                    dns_items.append(val)
            dns_value = ', '.join(dns_items[:4]) or '1.1.1.1'
            set_setting('wireguard_mtu', mtu)
            set_setting('wireguard_persistent_keepalive', keepalive)
            set_setting('wireguard_dns', dns_value)
            db.session.commit()
            try:
                apply_runtime_configs()
                sync_all_users(restart=False)
            except Exception as exc:
                flash('WireGuard settings saved, but runtime apply failed: ' + str(exc)[:180])
                return redirect(url_for('web.settings'))
            log(current_user.username, 'update_wireguard_client_settings', str(mtu), f'keepalive={keepalive}; dns={dns_value}')
            flash(f'WireGuard settings saved: MTU {mtu}, DNS {dns_value}.')
            return redirect(url_for('web.settings'))
        if section == 'subscription_domain':
            sub_domain = (request.form.get('subscription_domain') or '').strip().rstrip('/')
            set_setting('subscription_domain', sub_domain)
            db.session.commit()
            log(current_user.username, 'update_subscription_domain', sub_domain or 'default')
            flash('Subscription domain saved. New subscription links, QR codes, API responses and bot messages will use it.')
            return redirect(url_for('web.settings'))
        if request.form.get('admin_username'):
            current_user.username = request.form['admin_username'].strip()
        if request.form.get('admin_password'):
            current_user.set_password(request.form['admin_password'])
        for key in ['public_host','tunnel_host','subscription_domain','active_protocols','openvpn_transport','ocserv_transport','wireguard_transport','wireguard_mtu','wireguard_persistent_keepalive','wireguard_dns','l2tp_transport','pptp_enabled','hysteria2_enabled','hysteria2_obfs_password','hysteria2_tls_cert_file','hysteria2_tls_key_file','hysteria2_up_mbps','hysteria2_down_mbps','telegram_bot_token','telegram_chat_id','telegram_proxy_enabled','telegram_proxy_secret_salt','telegram_proxy_repo','notify_login','notify_expiry','ha_enabled','load_balancer_enabled','auto_failover_enabled','auto_backup_enabled','auto_backup_time','backup_remote_type','backup_remote_path','theme_mode','language','security_2fa_enabled','security_ip_whitelist','security_captcha_enabled','fail2ban_enabled','release_channel','ui_mode']:
            set_setting(key, request.form.get(key, ''))
        set_setting('license_server_url', 'http://license.skyshield.space:8002')
        for key in ['panel','openvpn_udp','openvpn_tcp','ocserv_tcp','ocserv_udp','l2tp_udp','ipsec_ike','ipsec_nat','wireguard_udp','xray_tcp','xray_api','pptp_tcp','hysteria2_udp','telegram_proxy_base','ssh_tcp']:
            set_setting(f'port_{key}', int(request.form.get(f'port_{key}') or get_port(key)))
        db.session.commit(); apply_runtime_configs(); log(current_user.username,'update_settings','panel')
        flash('تنظیمات ذخیره شد. برای اعمال پورت پنل: sudo bash /opt/ironpanel/upgrade.sh --restart-only یا systemctl restart ironpanel')
        return redirect(url_for('web.settings'))
    settings = {s.key:s.value for s in AppSetting.query.all()}
    return render_template('settings.html', settings=settings, ports={k:get_port(k) for k in ['panel','openvpn_udp','openvpn_tcp','ocserv_tcp','ocserv_udp','l2tp_udp','ipsec_ike','ipsec_nat','wireguard_udp','xray_tcp','xray_api','pptp_tcp','hysteria2_udp','telegram_proxy_base','ssh_tcp']}, openvpn_transport=get_setting('openvpn_transport','udp'), ocserv_transport=get_setting('ocserv_transport','tcp_udp'), wireguard_transport=get_setting('wireguard_transport','udp'), l2tp_transport=get_setting('l2tp_transport','udp'), license_status=check_license(force=True), wireguard_dns_presets=WIREGUARD_DNS_PRESETS)


@web_bp.route('/telegram-proxy/repair', methods=['POST'])
@login_required
def telegram_proxy_repair():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    result = run_cmd(['bash','-lc','/opt/ironpanel/scripts/repair_telegram_proxy.sh --sync >/tmp/ironpanel-tgproxy-repair.log 2>&1; cat /tmp/ironpanel-tgproxy-repair.log'], timeout=240)
    log(current_user.username, 'repair_telegram_proxy', str(result.returncode), (result.stdout or result.stderr)[-500:])
    flash('Telegram proxy repair finished.' if result.returncode == 0 else 'Telegram proxy repair failed. Check /tmp/ironpanel-tgproxy-repair.log')
    return redirect(url_for('web.settings'))

@web_bp.route('/telegram-proxy', methods=['GET','POST'])
@login_required
def telegram_proxy_manager():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'save':
            enabled = request.form.get('telegram_proxy_enabled') == '1'
            protocols = active_protocols()
            if enabled and 'telegram_proxy' not in protocols:
                protocols.append('telegram_proxy')
            if not enabled:
                protocols = [p for p in protocols if p != 'telegram_proxy']
            set_setting('active_protocols', ','.join(protocols))
            try:
                base = max(1024, min(int(request.form.get('port_telegram_proxy_base') or 6969), 60000))
            except Exception:
                base = 6969
            set_setting('port_telegram_proxy_base', base)
            set_setting('telegram_proxy_secret_salt', request.form.get('telegram_proxy_secret_salt','').strip())
            repo = request.form.get('telegram_proxy_repo','').strip() or 'https://github.com/Unknown-sir/JSMTProxy.git'
            set_setting('telegram_proxy_repo', repo)
            db.session.commit()
            sync_all_users(restart=True)
            log(current_user.username, 'telegram_proxy_settings', 'enabled' if enabled else 'disabled', f'base={base}')
            flash('Telegram Proxy settings saved and users were re-synced.')
        elif action == 'repair':
            repo = shlex.quote(get_setting('telegram_proxy_repo', 'https://github.com/Unknown-sir/JSMTProxy.git'))
            result = run_cmd(['bash','-lc', f'IRONPANEL_TGPROXY_REPO={repo} /opt/ironpanel/scripts/repair_telegram_proxy.sh --sync >/tmp/ironpanel-tgproxy-repair.log 2>&1; cat /tmp/ironpanel-tgproxy-repair.log'], timeout=300)
            log(current_user.username, 'telegram_proxy_repair', str(result.returncode), (result.stdout or result.stderr)[-1000:])
            flash('Telegram Proxy repair/sync finished.' if result.returncode == 0 else 'Telegram Proxy repair failed. Check /tmp/ironpanel-tgproxy-repair.log')
        elif action == 'sync':
            sync_all_users(restart=True)
            log(current_user.username, 'telegram_proxy_sync', 'all')
            flash('Telegram Proxy users and services synced.')
        elif action == 'collect_usage':
            changed = collect_usage_from_runtime()
            log(current_user.username, 'telegram_proxy_collect_usage', str(changed))
            flash(f'Usage sync completed. Changed users: {changed}')
        elif action == 'restart_all':
            run_cmd(['bash','-lc', 'systemctl restart ironpanel-tgproxy.service >/dev/null 2>&1 || true'])
            flash('Telegram Proxy services restart requested.')
        elif action == 'stop_all':
            run_cmd(['bash','-lc', 'systemctl stop ironpanel-tgproxy.service ironpanel-tgproxy-*.service >/dev/null 2>&1 || true'])
            flash('Telegram Proxy services stop requested.')
        return redirect(url_for('web.telegram_proxy_manager'))
    status = telegram_proxy_core_status()
    rows = telegram_proxy_user_rows()
    return render_template('telegram_proxy.html', status=status, rows=rows, settings={s.key:s.value for s in AppSetting.query.all()})


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
    logs = q.order_by(ActivityLog.id.desc()).limit(500).all()
    summary = {
        'total': ActivityLog.query.count(),
        'filtered': len(logs),
        'latest': logs[0].created_at if logs else None,
        'errors': ActivityLog.query.filter(ActivityLog.action.ilike('%fail%')).count(),
    }
    return render_template('logs.html', logs=logs, summary=summary, filters={'actor':actor,'action':action,'target':target})



def _safe_download_username(username: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(username or 'user')).strip('._-')
    return value or 'user'

def config_download_name(user: VpnUser, source_filename: str) -> str:
    base = _safe_download_username(user.username)
    name = str(source_filename or '')
    if name.endswith('.ovpn'):
        return f'{base}.ovpn'
    if name == 'wireguard.conf':
        return f'{base}.conf'
    if name == 'xray.txt':
        return f'{base}.txt'
    if name == 'hysteria2.yaml':
        return f'{base}.yaml'
    if name == 'hysteria2.txt':
        return f'{base}-hysteria2.txt'
    if name == 'telegram_proxy.txt':
        return f'{base}-telegram-proxy.txt'
    if name == 'ssh.txt':
        return f'{base}-ssh.txt'
    if name == 'subscription.txt':
        return f'{base}-subscription.txt'
    suffix = Path(name).suffix or '.txt'
    return f'{base}{suffix}'

@web_bp.route('/s/<token>')
def subscription(token):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    collect_usage_from_runtime()
    configs = user_config_payload(u)
    return render_template('subscription.html', user=u, host=get_public_host(), subscription_base_url=get_subscription_base_url(), subscription_url=subscription_url_for_user(u), configs=configs, download_names={name: config_download_name(u, name) for name in configs.keys()}, usage=user_usage_summary(u), theme=subscription_theme_settings())

@web_bp.route('/profiles/<username>/<filename>')
@login_required
def profile_download(username, filename):
    u = VpnUser.query.filter_by(username=username).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / username, filename, as_attachment=True, download_name=config_download_name(u, filename))

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
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / u.username, filename, as_attachment=True, download_name=config_download_name(u, filename))


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
    err_row = AppSetting.query.filter_by(key='online_sessions_last_error').first()
    return render_template('sessions.html', sessions=refresh_online_sessions(), online_error=(err_row.value if err_row else ''))

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
    _ensure_famous_dns_profiles_web()
    if request.method=='POST':
        action = request.form.get('action') or ('set_default' if request.form.get('set_default') else 'add_custom')
        if action == 'add_defaults':
            _ensure_famous_dns_profiles_web()
            flash('DNSهای معروف اضافه/به‌روزرسانی شدند.')
        elif action == 'set_default':
            DnsProfile.query.update({'is_default':False})
            p = DnsProfile.query.get(int(request.form['profile_id']))
            if p:
                p.is_default=True
                db.session.commit()
                flash('DNS default saved.')
        elif action == 'apply_wireguard':
            p = DnsProfile.query.get(int(request.form['profile_id']))
            if p:
                value = ', '.join([x for x in [p.primary_dns, p.secondary_dns] if x])
                set_setting('wireguard_dns', value)
                db.session.commit()
                try:
                    apply_runtime_configs()
                    sync_all_users(restart=False)
                except Exception as exc:
                    flash('DNS applied, but runtime sync failed: ' + str(exc)[:180])
                    return redirect(url_for('web.dns_manager'))
                flash(f'{p.name} روی WireGuard DNS اعمال شد: {value}')
        else:
            name = (request.form.get('name') or '').strip()
            primary = (request.form.get('primary_dns') or '').strip()
            secondary = (request.form.get('secondary_dns') or '').strip()
            if name and primary:
                db.session.add(DnsProfile(name=name, primary_dns=primary, secondary_dns=secondary))
                db.session.commit()
                flash('DNS profile saved')
        return redirect(url_for('web.dns_manager'))
    return render_template('dns.html', profiles=DnsProfile.query.order_by(DnsProfile.is_default.desc(), DnsProfile.name.asc()).all())

@web_bp.route('/domains', methods=['GET','POST'])
@login_required
def domains():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        d=DomainRecord(domain=request.form['domain'], purpose=request.form.get('purpose','vpn'), ssl_enabled=bool(request.form.get('ssl_enabled')))
        db.session.add(d); db.session.commit(); flash('Domain saved')
        return redirect(url_for('web.domains'))
    return render_template('domains.html', domains=DomainRecord.query.all())

@web_bp.route('/ssl', methods=['GET','POST'])
@login_required
def ssl_manager():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'issue')
        if action == 'renew':
            result = renew_all_ssl()
        else:
            result = issue_and_apply_ssl(
                request.form.get('domain') or default_ssl_domain(),
                request.form.get('email', ''),
                force_xray_tls=request.form.get('force_xray_tls') == '1',
            )
            log(current_user.username, 'ssl_issue', result.get('domain',''), result.get('message','')[-500:])
        flash(result.get('message', 'SSL operation finished'))
        return redirect(url_for('web.ssl_manager'))
    return render_template('ssl.html', status=ssl_status(default_ssl_domain()))

@web_bp.route('/ssl/<int:domain_id>/issue', methods=['POST'])
@login_required
def ssl_issue(domain_id):
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    d=DomainRecord.query.get_or_404(domain_id)
    result = issue_and_apply_ssl(d.domain, force_xray_tls=request.form.get('force_xray_tls') == '1')
    flash(result.get('message', 'SSL operation finished'))
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
    return render_template('user_portal.html', user=u, configs=configs, access_ok=ok, access_reason=reason, usage=user_usage_summary(u))

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
    data = subscription_url_for_user(u)
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/qr/wireguard/<int:user_id>.png')
@login_required
def qr_wireguard(user_id):
    from flask import Response
    from .services.v11 import make_qr_png
    u = VpnUser.query.get_or_404(user_id)
    configs = user_config_payload(u)
    data = configs.get('wireguard.conf', '') or ''
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/qr/xray/<int:user_id>.png')
@login_required
def qr_xray(user_id):
    from flask import Response
    from .services.v11 import make_qr_png
    u = VpnUser.query.get_or_404(user_id)
    return Response(make_qr_png(xray_link(u)), mimetype='image/png')

@web_bp.route('/s/<token>/xray-qr.png')
def subscription_xray_qr(token):
    from flask import Response
    from .services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    return Response(make_qr_png(xray_link(u)), mimetype='image/png')


@web_bp.route('/s/<token>/wireguard-qr.png')
def subscription_wireguard_qr(token):
    from flask import Response
    from .services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs = user_config_payload(u)
    return Response(make_qr_png(configs.get('wireguard.conf','')), mimetype='image/png')

@web_bp.route('/s/<token>/hysteria2-qr.png')
def subscription_hysteria2_qr(token):
    from flask import Response
    from .services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs = user_config_payload(u)
    return Response(make_qr_png(configs.get('hysteria2.txt','')), mimetype='image/png')

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
    result = renew_all_ssl()
    flash(result.get('message', 'درخواست تمدید SSL اجرا شد'))
    return redirect(url_for('web.ssl_manager'))


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



# ---------------- IronPanel v16.7: Outbound Manager ----------------
@web_bp.route('/outbound', methods=['GET','POST'])
@login_required
def outbound_manager():
    # Outbound is intentionally available for all license types, but only the main admin can change routing.
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'disable':
            ok, out = disable_outbound_runtime()
            log(current_user.username, 'outbound_disable', 'runtime', out[-500:])
            flash('Outbound غیرفعال شد' if ok else 'خطا در غیرفعال‌سازی Outbound: ' + out[-800:])
            return redirect(url_for('web.outbound_manager'))
        if action == 'test':
            save_outbound_settings(
                outbound_type=request.form.get('outbound_type','openvpn'),
                config_text=request.form.get('outbound_config',''),
                enabled=request.form.get('outbound_enabled') == '1',
                protocols=request.form.getlist('outbound_protocols') or [],
            )
            ok, out = test_outbound_config()
            log(current_user.username, 'outbound_test', request.form.get('outbound_type',''), out[-500:])
            flash('تست اتصال Outbound موفق بود؛ حالا پروتکل‌ها را انتخاب و Apply کن' if ok else 'تست اتصال Outbound ناموفق بود: ' + out[-1200:])
            return redirect(url_for('web.outbound_manager'))
        if action == 'apply':
            save_outbound_settings(
                outbound_type=request.form.get('outbound_type','openvpn'),
                config_text=request.form.get('outbound_config',''),
                enabled=True,
                protocols=request.form.getlist('outbound_protocols') or [],
            )
            ok_test, test_out = test_outbound_config()
            if not ok_test:
                flash('کانفیگ Outbound وصل نشد و اعمال نشد: ' + test_out[-1200:])
                return redirect(url_for('web.outbound_manager'))
            ok, out = apply_outbound_runtime()
            log(current_user.username, 'outbound_apply', ','.join(request.form.getlist('outbound_protocols')), out[-500:])
            flash('Outbound فعال شد و مسیر ترافیک پروتکل‌های انتخابی اعمال شد' if ok else 'Outbound تست شد ولی اعمال runtime خطا داد: ' + out[-1200:])
            return redirect(url_for('web.outbound_manager'))
        # save only
        save_outbound_settings(
            outbound_type=request.form.get('outbound_type','openvpn'),
            config_text=request.form.get('outbound_config',''),
            enabled=request.form.get('outbound_enabled') == '1',
            protocols=request.form.getlist('outbound_protocols') or [],
        )
        flash('تنظیمات Outbound ذخیره شد. برای فعال‌سازی، اول تست و بعد Apply کن.')
        return redirect(url_for('web.outbound_manager'))
    return render_template('outbound.html', settings=outbound_settings(), status=outbound_runtime_status(), active=active_protocols())


# ---------------- IronPanel v16: Advanced Xray Core ----------------
@web_bp.route('/xray', methods=['GET','POST'])
@login_required
def xray_core():
    # Xray is intentionally available for every license type; only main admin can change runtime core settings.
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'generate_reality_keys':
            ensure_reality_keys(commit=True, force=True)
            flash('Reality keypair جدید ساخته شد و کلید عمومی/خصوصی به‌روزرسانی شد')
        elif action == 'save_builder':
            update_xray_builder(request.form)
            ok, out = write_xray_config([u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_template(u, 'xray')], restart=True)
            log(current_user.username, 'xray_builder_update', 'multi-inbound', out[-500:])
            flash('Xray Builder ذخیره و کانفیگ چند Inbound بازسازی شد' if ok else 'خطا در Xray Builder: ' + out[-800:])
        elif action == 'reset_builder':
            reset_xray_builder()
            flash('Presetهای Xray Builder به حالت پیش‌فرض برگشت')
        else:
            update_xray_settings(request.form)
            # Keep protocol list in sync with the dedicated Xray port fields.
            set_setting('port_xray_tcp', request.form.get('xray_port') or '443')
            set_setting('port_xray_api', request.form.get('xray_api_port') or '10085')
            ok, out = write_xray_config([u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_template(u, 'xray')], restart=True)
            log(current_user.username, 'xray_update', 'core', out[-500:])
            flash('تنظیمات Xray ذخیره و کانفیگ بازسازی شد' if ok else 'خطا در ساخت کانفیگ Xray: ' + out[-800:])
        return redirect(url_for('web.xray_core'))
    valid_users = [u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_template(u, 'xray')]
    return render_template('xray.html', settings=xray_settings(), profile_types=XRAY_PROFILE_TYPES, runtime=xray_runtime_status(), users=valid_users, builder_inbounds=xray_builder_inbounds(), builder_enabled=xray_builder_enabled())

def protocol_enabled_for_template(user, proto):
    return proto in (user.allowed_protocol_list() or user.protocol_list() or active_protocols())


# ---------------- IronPanel v14: Telegram sales bot for end-user VPN sales ----------------
@web_bp.route('/sales-bot', methods=['GET','POST'])
@login_required
def sales_bot():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action','settings')
        if action == 'settings':
            keys = ['sales_bot_enabled','sales_bot_token','sales_bot_admin_ids','sales_bot_support_url','sales_bot_welcome_text','sales_bot_payment_text','sales_bot_rules_text','sales_bot_connection_guide','sales_bot_qr_enabled','sales_bot_trial_enabled','sales_bot_trial_days','sales_bot_trial_traffic_gb','sales_bot_currency']
            for k in keys:
                if k in ('sales_bot_enabled','sales_bot_trial_enabled','sales_bot_qr_enabled'):
                    set_setting(k, '1' if request.form.get(k) else '0')
                else:
                    set_setting(k, request.form.get(k, ''))
            run_cmd(['bash','-lc','systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true'])
            flash('تنظیمات ربات فروش ذخیره شد و سرویس ربات ری‌استارت شد')
        elif action == 'create_plan':
            plan = SalesBotPlan(
                name=request.form['name'].strip(),
                days=int(request.form.get('days') or 0),
                traffic_gb=int(request.form.get('traffic_gb') or 0),
                price=float(request.form.get('price') or 0),
                currency=request.form.get('currency') or get_setting('sales_bot_currency','IRT') or 'IRT',
                protocols=','.join(request.form.getlist('protocols') or active_protocols()),
                connection_limit=int(request.form.get('connection_limit') or 1),
                active=bool(request.form.get('active')),
                sort_order=int(request.form.get('sort_order') or 0),
                created_by_telegram_id='web:'+str(current_user.id),
            )
            db.session.add(plan); db.session.commit(); flash('پلن فروش ربات ساخته شد')
        elif action == 'toggle_plan':
            plan = SalesBotPlan.query.get_or_404(int(request.form['plan_id']))
            plan.active = not plan.active; db.session.commit(); flash('وضعیت پلن تغییر کرد')
        elif action == 'delete_plan':
            plan = SalesBotPlan.query.get_or_404(int(request.form['plan_id']))
            db.session.delete(plan); db.session.commit(); flash('پلن حذف شد')
        return redirect(url_for('web.sales_bot'))
    settings = {s.key:s.value for s in AppSetting.query.all()}
    plans = SalesBotPlan.query.order_by(SalesBotPlan.sort_order, SalesBotPlan.id.desc()).all()
    orders = SalesBotOrder.query.order_by(SalesBotOrder.id.desc()).limit(100).all()
    customers = SalesBotCustomer.query.order_by(SalesBotCustomer.id.desc()).limit(100).all()
    return render_template('sales_bot.html', settings=settings, plans=plans, orders=orders, customers=customers, active=active_protocols())

@web_bp.route('/sales-bot/orders/<int:order_id>/approve', methods=['POST'])
@login_required
def sales_bot_order_approve(order_id):
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    from bot.main import _create_vpn_user_for_order, _renew_vpn_user_for_order, _subscription_url
    order = SalesBotOrder.query.get_or_404(order_id)
    try:
        if order.order_type == 'renew':
            u, pwd = _renew_vpn_user_for_order(order)
        else:
            u, pwd = _create_vpn_user_for_order(order)
        log(current_user.username, 'sales_order_approve', str(order.id), u.username)
        flash(f'سفارش تأیید شد و سرویس {u.username} ساخته/تمدید شد. لینک: {_subscription_url(u)}')
    except Exception as exc:
        flash(f'خطا در تأیید سفارش: {exc}')
    return redirect(url_for('web.sales_bot'))

@web_bp.route('/sales-bot/orders/<int:order_id>/reject', methods=['POST'])
@login_required
def sales_bot_order_reject(order_id):
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    order = SalesBotOrder.query.get_or_404(order_id)
    order.status = 'rejected'; order.rejected_at = datetime.utcnow(); order.admin_note = request.form.get('admin_note','rejected from web')
    db.session.commit(); log(current_user.username, 'sales_order_reject', str(order.id))
    flash('سفارش رد شد')
    return redirect(url_for('web.sales_bot'))

@web_bp.route('/dashboard/quick-upgrade', methods=['POST'])
@login_required
def dashboard_quick_upgrade():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    latest = github_latest_version(force=True)
    if not latest.get('update_available'):
        flash('نسخه جدیدتری در GitHub پیدا نشد یا بررسی نسخه ناموفق بود.')
        return redirect(url_for('web.dashboard'))
    flash('آپدیت مرحله‌ای شروع می‌شود. صفحه را باز نگه دار تا درصد پیشرفت و لاگ را ببینی.')
    return redirect(url_for('web.updates', autostart=1))


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


@web_bp.route('/speed-limits', methods=['GET','POST'])
@login_required
def speed_limits():
    if current_user.role != 'main_admin':
        flash('فقط ادمین اصلی می‌تواند محدودیت سرعت را تغییر دهد.')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action','save_apply')
        if action in ('save','save_apply'):
            changed = save_speed_limits(request.form)
            log(current_user.username, 'speed_limits_save', ','.join(changed) or 'no-change')
            if action == 'save_apply':
                ok, out = apply_speed_limits_runtime()
                log(current_user.username, 'speed_limits_apply', str(ok), out[-500:])
                flash('محدودیت سرعت ذخیره و روی سرور اعمال شد.' if ok else 'ذخیره شد ولی اعمال runtime خطا داشت: ' + out[-180:])
            else:
                flash('محدودیت سرعت ذخیره شد.')
        elif action == 'apply':
            ok, out = apply_speed_limits_runtime()
            log(current_user.username, 'speed_limits_apply', str(ok), out[-500:])
            flash('محدودیت‌ها دوباره روی سرور اعمال شدند.' if ok else 'اعمال محدودیت با خطا مواجه شد: ' + out[-180:])
        return redirect(url_for('web.speed_limits'))
    return render_template('speed_limits.html', rows=speed_limit_rows(), status=speed_limit_status())


def _routing_protocol_rows(profiles, maps):
    by_protocol = {m.protocol: m for m in maps}
    by_id = {p.id: p for p in profiles}
    protocols = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
    rows=[]
    for protocol in protocols:
        m = by_protocol.get(protocol)
        p = by_id.get(m.outbound_profile_id) if m and m.outbound_profile_id else None
        rows.append({
            'protocol': protocol,
            'label': PROTOCOL_LABELS.get(protocol, protocol.upper()),
            'icon': PROTOCOL_ICONS.get(protocol, '◈'),
            'profile_id': p.id if p else None,
            'profile_name': p.name if p else '',
            'enabled': bool(m.enabled) if m else False,
            'failover': m.failover_profile_ids if m else '',
        })
    return rows

@web_bp.route('/routing-rules', methods=['GET','POST'])
@login_required
def routing_rules():
    if current_user.role != 'main_admin':
        flash('فقط ادمین اصلی به Routing Rules دسترسی دارد.')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action','save_rules')
        if action == 'create_profile':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('نام پروفایل الزامی است.')
                return redirect(url_for('web.routing_rules'))
            p = OutboundProfile(
                name=name[:120],
                profile_type=(request.form.get('profile_type') or 'openvpn')[:30],
                config_body=request.form.get('config_body',''),
                enabled=True,
                priority=int(request.form.get('priority') or 100),
                kill_switch=request.form.get('kill_switch') == '1',
                route_mode=(request.form.get('route_mode') or 'full')[:30],
                route_targets=request.form.get('route_targets',''),
            )
            db.session.add(p); db.session.commit()
            log(current_user.username, 'routing_profile_create', p.name)
            flash('Outbound Profile ساخته شد.')
        elif action == 'delete_profile':
            p = OutboundProfile.query.get_or_404(int(request.form.get('profile_id') or 0))
            ProtocolOutboundMap.query.filter_by(outbound_profile_id=p.id).delete()
            name = p.name
            db.session.delete(p); db.session.commit()
            log(current_user.username, 'routing_profile_delete', name)
            flash('پروفایل و ruleهای وابسته حذف شدند.')
        elif action == 'test_profile':
            p = OutboundProfile.query.get_or_404(int(request.form.get('profile_id') or 0))
            ok, detail = test_outbound_profile(p)
            flash(('تست موفق: ' if ok else 'تست ناموفق: ') + detail[:300])
        elif action == 'save_rules':
            protocols = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
            for protocol in protocols:
                profile_id = int(request.form.get(f'profile_{protocol}') or 0)
                enabled = request.form.get(f'enabled_{protocol}') == '1' and profile_id > 0
                failover = (request.form.get(f'failover_{protocol}') or '').strip()[:255]
                m = ProtocolOutboundMap.query.filter_by(protocol=protocol, node_id=None).first()
                if not enabled:
                    if m:
                        db.session.delete(m)
                    continue
                if not m:
                    m = ProtocolOutboundMap(protocol=protocol, node_id=None)
                    db.session.add(m)
                m.outbound_profile_id = profile_id
                m.enabled = True
                m.failover_profile_ids = failover
            db.session.commit()
            log(current_user.username, 'routing_rules_save', 'protocol-matrix')
            flash('Routing Rules ذخیره شد. برای اعمال policy routing، در صورت نیاز Outbound Runtime را Apply کن.')
        return redirect(url_for('web.routing_rules'))
    profiles, maps = outbound_matrix()
    return render_template('routing_rules.html', profiles=profiles, maps=maps, nodes=Node.query.all(), protocol_rows=_routing_protocol_rows(profiles, maps))

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

@web_bp.route('/updates/github-restart', methods=['POST'])
@login_required
def updates_github_restart():
    if current_user.role != 'main_admin':
        return jsonify(ok=False, error='forbidden'), 403
    return jsonify(github_update_schedule_restart())

# ---------------- IronPanel v17: Enterprise nodes, subscription outputs, live logs, backup and wizards ----------------
from .services.v17 import (
    node_health_summary, node_install_command, update_node_from_heartbeat,
    subscription_for_client, validate_xray_before_delivery, outbound_matrix,
    test_outbound_profile, run_full_backup_v17, live_log_tail, v17_health_checks,
)
from .core.models import OutboundProfile, ProtocolOutboundMap, BackupSchedule

@web_bp.route('/v17/nodes')
@login_required
def v17_nodes():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    return render_template('v17_nodes.html', nodes=node_health_summary())

@web_bp.route('/nodes/<int:node_id>/install')
@login_required
def node_install(node_id):
    n=Node.query.get_or_404(node_id)
    return render_template('node_install.html', node=n, command=node_install_command(n))

@web_bp.route('/nodes/<int:node_id>/check', methods=['POST'])
@login_required
def node_check(node_id):
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

@web_bp.route('/live-logs')
@login_required
def live_logs():
    svc=request.args.get('service','ironpanel')
    return render_template('live_logs.html', service=svc, detail=live_log_tail(svc, 160))

@web_bp.route('/api/live-logs')
@login_required
def api_live_logs():
    return jsonify(service=request.args.get('service','ironpanel'), detail=live_log_tail(request.args.get('service','ironpanel'), int(request.args.get('lines') or 120)))


@web_bp.route('/geofiles', methods=['GET','POST'])
@login_required
def geofiles_manager():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        res = update_geofiles(request.form.get('source','loyalsoldier'))
        log(current_user.username, 'geofiles_update', request.form.get('source',''), res.get('log','')[-500:])
        flash(res.get('message','GeoFile update finished'))
        return redirect(url_for('web.geofiles_manager'))
    return render_template('geofiles.html', status=geofile_status())

@web_bp.route('/admin-bot', methods=['GET','POST'])
@login_required
def admin_bot_manager():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'test':
            sent = send_test_admin_report()
            flash('گزارش تست ارسال شد' if sent else 'ارسال گزارش تست ناموفق بود؛ Telegram token/chat را بررسی کن')
        else:
            save_admin_bot_settings(request.form)
            run_cmd(['bash','-lc','systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true'])
            flash('تنظیمات ربات مدیریتی ذخیره شد و سرویس ربات ری‌استارت شد')
        return redirect(url_for('web.admin_bot_manager'))
    return render_template('admin_bot.html', settings=admin_bot_settings(), report=admin_bot_report_text())

@web_bp.route('/subscription-manager', methods=['GET','POST'])
@login_required
def subscription_manager():
    if request.method == 'POST':
        set_subscription_theme(request.form)
        set_setting('subscription_domain', (request.form.get('subscription_domain') or '').strip().rstrip('/'))
        flash('قالب، دامنه و تنظیمات صفحه Subscription ذخیره شد')
        return redirect(url_for('web.subscription_manager'))
    return render_template('subscription_manager.html', users=VpnUser.query.order_by(VpnUser.id.desc()).all(), formats=['raw','clash','singbox','hiddify'], theme=subscription_theme_settings(), subscription_domain=get_setting('subscription_domain',''), subscription_base_url=get_subscription_base_url())

@web_bp.route('/s/<token>/<client_type>')
def subscription_client(token, client_type):
    u=VpnUser.query.filter_by(subscription_token=token).first_or_404()
    body,mime,status=subscription_for_client(u, client_type, request=request)
    return current_app.response_class(body, status=status, mimetype=mime)

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
            sync_all_users(restart=True); flash('همه کاربران و پروتکل‌ها sync شدند')
        return redirect(url_for('web.v17_wizards'))
    return render_template('v17_wizards.html')

@web_bp.route('/outbound/v2', methods=['GET','POST'])
@login_required
def outbound_v2():
    if request.method == 'POST':
        action=request.form.get('action')
        if action == 'create_profile':
            p=OutboundProfile(name=request.form.get('name','Outbound'), profile_type=request.form.get('profile_type','openvpn'), config_body=request.form.get('config_body',''), priority=int(request.form.get('priority') or 100), kill_switch=bool(request.form.get('kill_switch')), route_mode=request.form.get('route_mode','full'), route_targets=request.form.get('route_targets',''))
            db.session.add(p); db.session.commit(); flash('پروفایل اوتباند ساخته شد')
        elif action == 'test_profile':
            p=OutboundProfile.query.get_or_404(int(request.form.get('profile_id'))); ok,detail=test_outbound_profile(p); flash(('تست موفق: ' if ok else 'تست ناموفق: ')+detail)
        elif action == 'map_protocol':
            m=ProtocolOutboundMap(protocol=request.form.get('protocol'), outbound_profile_id=int(request.form.get('profile_id') or 0) or None, node_id=int(request.form.get('node_id') or 0) or None, enabled=True, failover_profile_ids=request.form.get('failover_profile_ids',''))
            db.session.add(m); db.session.commit(); flash('Route map ذخیره شد')
        return redirect(url_for('web.outbound_v2'))
    profiles,maps=outbound_matrix()
    return render_template('outbound_v2.html', profiles=profiles, maps=maps, nodes=Node.query.all())

@web_bp.route('/users/bulk-action', methods=['POST'])
@login_required
def users_bulk_action():
    ids=[int(x) for x in request.form.getlist('user_ids') if str(x).isdigit()]
    action=request.form.get('action')
    users=VpnUser.query.filter(VpnUser.id.in_(ids)).all() if ids else []
    for u in users:
        if action=='enable': u.enabled=True
        elif action=='disable': u.enabled=False
        elif action=='reset_traffic': u.used_upload_mb=u.used_download_mb=0; u.used_upload_bytes=u.used_download_bytes=0
    db.session.commit()
    for u in users: sync_user(u)
    flash(f'عملیات گروهی روی {len(users)} کاربر انجام شد')
    return redirect(url_for('web.users'))

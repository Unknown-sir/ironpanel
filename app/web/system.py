"""Platform settings, license/upgrade pages and notification test."""
import re

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import AppSetting
from ..services.provisioning import (
    active_protocols,
    apply_runtime_configs,
    get_port,
    get_setting,
    log,
    normalize_user_protocols,
    set_setting,
    sync_all_users,
    telegram_notify,
)
from ..services.license import (
    TYPE_FEATURES,
    check_license,
    clear_license_key,
    current_license_features,
    current_license_type,
    feature_label,
    license_key,
    license_remaining_days,
    license_server_url,
    save_license_key,
)
from ..services.maintenance import queue_doctor_repair
from ..services.password_policy import normalize_password_policy
from .common import WIREGUARD_DNS_PRESETS
from . import web_bp


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

@web_bp.route('/notifications/test', methods=['POST'])
@login_required
def notifications_test():
    ok=telegram_notify('Ironpanel test notification ✅')
    flash('پیام تست ارسال شد' if ok else 'ارسال پیام تست ناموفق بود')
    return redirect(url_for('web.settings'))

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
        if section == 'password_policy':
            raw_length = request.form.get('auto_password_length', '10')
            raw_mode = request.form.get('auto_password_mode', 'both')
            length, mode = normalize_password_policy(raw_length, raw_mode)
            set_setting('auto_password_length', length)
            set_setting('auto_password_mode', mode)
            db.session.commit()
            log(current_user.username, 'update_password_policy', str(length), mode)
            flash(f'سیاست تولید رمز ذخیره شد: طول {length}، حالت {mode}.')
            return redirect(url_for('web.settings'))
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
        sanitized_active_protocols = ','.join(normalize_user_protocols(request.form.get('active_protocols','').split(','), allow_default=False)) if 'active_protocols' in request.form else ''
        for key in ['public_host','tunnel_host','subscription_domain','active_protocols','openvpn_transport','ocserv_transport','wireguard_transport','wireguard_mtu','wireguard_persistent_keepalive','wireguard_dns','l2tp_transport','pptp_enabled','hysteria2_enabled','hysteria2_obfs_password','hysteria2_tls_cert_file','hysteria2_tls_key_file','hysteria2_up_mbps','hysteria2_down_mbps','telegram_bot_token','telegram_chat_id','telegram_proxy_enabled','telegram_proxy_secret_salt','telegram_proxy_repo','notify_login','notify_expiry','ha_enabled','load_balancer_enabled','auto_failover_enabled','auto_backup_enabled','auto_backup_time','backup_remote_type','backup_remote_path','theme_mode','language','security_2fa_enabled','security_ip_whitelist','security_captcha_enabled','fail2ban_enabled','release_channel','ui_mode']:
            set_setting(key, sanitized_active_protocols if key == 'active_protocols' else request.form.get(key, ''))
        set_setting('license_server_url', 'http://license.skyshield.space:8002')
        def _safe_port_from_form(key):
            try:
                val = int(str(request.form.get(f'port_{key}') or get_port(key) or '').strip())
            except Exception:
                val = int(get_port(key) or 0)
            if val < 1 or val > 65535:
                val = int(get_port(key) or 0)
            return val
        for key in ['panel','openvpn_udp','openvpn_tcp','ocserv_tcp','ocserv_udp','l2tp_udp','ipsec_ike','ipsec_nat','wireguard_udp','xray_tcp','xray_api','pptp_tcp','hysteria2_udp','telegram_proxy_base','ssh_tcp']:
            set_setting(f'port_{key}', _safe_port_from_form(key))
        db.session.commit()
        try:
            apply_runtime_configs()
            sync_all_users(restart=False)
            # Apply potentially changed protocol ports without blocking the web request.
            # Ocserv/OpenConnect is queued explicitly because custom ports such as 1195
            # must be reflected by the running daemon, not only the generated config.
            active_now = active_protocols()
            if 'openvpn' in active_now:
                queue_doctor_repair('repair_openvpn.sh', actor=getattr(current_user, 'username', 'web'))
            if 'ocserv' in active_now:
                queue_doctor_repair('repair_ocserv.sh', actor=getattr(current_user, 'username', 'web'))
            log(current_user.username,'update_settings','panel')
            flash('تنظیمات ذخیره شد و Apply پروتکل‌ها در پس‌زمینه انجام می‌شود. برای اعمال پورت پنل: sudo bash /opt/ironpanel/upgrade.sh --restart-only یا systemctl restart ironpanel')
        except Exception as exc:
            log(current_user.username,'update_settings_apply_failed','panel', str(exc)[-500:])
            flash('تنظیمات ذخیره شد، اما Apply runtime خطا داد: ' + str(exc)[:240])
        return redirect(url_for('web.settings'))
    settings = {s.key:s.value for s in AppSetting.query.all()}
    return render_template('settings.html', settings=settings, ports={k:get_port(k) for k in ['panel','openvpn_udp','openvpn_tcp','ocserv_tcp','ocserv_udp','l2tp_udp','ipsec_ike','ipsec_nat','wireguard_udp','xray_tcp','xray_api','pptp_tcp','hysteria2_udp','telegram_proxy_base','ssh_tcp']}, openvpn_transport=get_setting('openvpn_transport','udp'), ocserv_transport=get_setting('ocserv_transport','tcp_udp'), wireguard_transport=get_setting('wireguard_transport','udp'), l2tp_transport=get_setting('l2tp_transport','udp'), license_status=check_license(force=True), wireguard_dns_presets=WIREGUARD_DNS_PRESETS)

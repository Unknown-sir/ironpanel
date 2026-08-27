"""Authentication, account, security and appearance routes."""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..core.extensions import db
from ..core.models import Admin, ApiToken, LoginHistory, TwoFactorSecret
from ..services.provisioning import log, set_setting
from ..services.admin_bot import send_login_alert
from ..services.i18n import LANGUAGES, THEMES, current_language, current_theme, save_appearance
from ..services.v12 import (
    ensure_2fa,
    generate_recovery_codes,
    log_login,
    verify_recovery_code,
    verify_totp,
)
from .common import reseller_panel_url
from . import web_bp


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


@web_bp.route('/appearance', methods=['GET','POST'])
@login_required
def appearance():
    if current_user.role != 'main_admin':
        flash('Only the main admin can change language & theme.')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        save_appearance(request.form)
        db.session.commit()
        log(current_user.username, 'update_appearance', request.form.get('language',''), request.form.get('theme_mode',''))
        flash('Appearance settings saved.')
        return redirect(url_for('web.appearance'))
    return render_template('appearance.html', languages=LANGUAGES, themes=THEMES, language=current_language(), theme=current_theme())

@web_bp.route('/security', methods=['GET','POST'])
@login_required
def security_center():
    from ..core.models import AppSetting
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        for key in ['security_2fa_enabled','security_ip_whitelist','security_captcha_enabled','fail2ban_enabled']:
            set_setting(key, request.form.get(key,''))
        db.session.commit(); flash('Security settings saved')
        return redirect(url_for('web.security_center'))
    return render_template('security_center.html', settings={s.key:s.value for s in AppSetting.query.all()})

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
    from flask import request as _request
    page = max(1, int(_request.args.get('page') or 1))
    try:
        per_page = int(_request.args.get('per_page') or 50)
    except Exception:
        per_page = 50
    per_page = min(max(per_page, 10), 200)
    pagination = LoginHistory.query.order_by(LoginHistory.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    def _page_url(target_page):
        args = {k: v for k, v in _request.args.items(multi=True) if k != 'page'}
        args['page'] = target_page
        query = '&'.join(f'{k}={v}' for k, v in args.items())
        return f'{_request.path}?{query}'
    prev_url = _page_url(pagination.prev_num) if pagination.has_prev else None
    next_url = _page_url(pagination.next_num) if pagination.has_next else None
    return render_template('login_history.html', rows=pagination.items, pagination=pagination, prev_url=prev_url, next_url=next_url)

@web_bp.route('/api-tokens', methods=['GET','POST'])
@login_required
def api_tokens():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        tok=ApiToken(name=request.form['name'], scopes=request.form.get('scopes','users:read,users:write'))
        db.session.add(tok); db.session.commit(); flash(f'Token created: {tok.token}')
        return redirect(url_for('web.api_tokens'))
    return render_template('api_tokens.html', tokens=ApiToken.query.order_by(ApiToken.id.desc()).all())

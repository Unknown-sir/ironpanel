"""Telegram integrations: sales bot, admin bot, proxy manager, MirzaBot API."""
import secrets
import shlex
from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import (
    AppSetting,
    SalesBotCustomer,
    SalesBotOrder,
    SalesBotPlan,
    TelegramCommandLog,
)
from ..services.provisioning import (
    active_protocols,
    collect_usage_from_runtime,
    get_setting,
    log,
    normalize_user_protocols,
    run_cmd,
    set_setting,
    sync_all_users,
    telegram_notify,
    telegram_proxy_core_status,
    telegram_proxy_user_rows,
)
from ..services.license import filter_protocols_for_license
from ..services.admin_bot import admin_bot_report_text, admin_bot_settings, save_admin_bot_settings, send_test_admin_report
from ..services.v12 import handle_telegram_command
from .common import _allowed_form_protocols, available_protocols_for_current_user
from . import web_bp


# v19.4 owner-aware reseller sales bot helpers
SALES_BOT_SETTING_KEYS = ['sales_bot_enabled','sales_bot_token','sales_bot_admin_ids','sales_bot_support_url','sales_bot_welcome_text','sales_bot_payment_text','sales_bot_rules_text','sales_bot_connection_guide','sales_bot_qr_enabled','sales_bot_trial_enabled','sales_bot_trial_days','sales_bot_trial_traffic_gb','sales_bot_currency','sales_bot_config_name_prefix_enabled','sales_bot_config_name_prefix','sales_bot_auto_approve_enabled','sales_bot_auto_approve_minutes']

def _sales_bot_owner_id():
    return 0 if getattr(current_user, 'role', '') == 'main_admin' else int(getattr(current_user, 'id', 0) or 0)

def _sales_owner_key(key, owner_id=None):
    owner_id = _sales_bot_owner_id() if owner_id is None else int(owner_id or 0)
    return key if owner_id == 0 else f'{key}_owner_{owner_id}'

def _get_sales_bot_settings(owner_id=None):
    owner_id = _sales_bot_owner_id() if owner_id is None else int(owner_id or 0)
    defaults = {s.key: s.value for s in AppSetting.query.all()}
    out = {}
    for key in SALES_BOT_SETTING_KEYS:
        if owner_id == 0:
            out[key] = defaults.get(key, '')
        else:
            out[key] = defaults.get(f'{key}_owner_{owner_id}', defaults.get(key, ''))
    return out

def _set_sales_bot_setting(key, value, owner_id=None):
    set_setting(_sales_owner_key(key, owner_id), value)

def _sales_bot_restart(owner_id=None):
    # Rebuild template services for reseller bots and restart global owner bot.
    run_cmd(['bash','-lc','/opt/ironpanel/scripts/sync_sales_bots.sh >/dev/null 2>&1 || true; systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true'], timeout=60)

def _order_visible_for_current_user(order):
    if current_user.role == 'main_admin':
        return int(getattr(order, 'owner_id', 0) or 0) == 0
    return int(getattr(order, 'owner_id', 0) or 0) == int(current_user.id)


# ---------------- IronPanel v14/v19.4: owner-aware Telegram sales bot ----------------
@web_bp.route('/sales-bot', methods=['GET','POST'])
@login_required
def sales_bot():
    if current_user.role not in ('main_admin', 'sub_admin'):
        return redirect(url_for('web.dashboard'))
    owner_id = _sales_bot_owner_id()
    if request.method == 'POST':
        action = request.form.get('action','settings')
        if action == 'settings':
            for k in SALES_BOT_SETTING_KEYS:
                if k in ('sales_bot_enabled','sales_bot_trial_enabled','sales_bot_qr_enabled','sales_bot_config_name_prefix_enabled','sales_bot_auto_approve_enabled'):
                    _set_sales_bot_setting(k, '1' if request.form.get(k) else '0', owner_id)
                else:
                    _set_sales_bot_setting(k, request.form.get(k, ''), owner_id)
            db.session.commit()
            _sales_bot_restart(owner_id)
            log(current_user.username, 'sales_bot_settings', 'owner', str(owner_id))
            flash('تنظیمات ربات فروش ذخیره شد و سرویس‌های ربات sync شدند')
        elif action == 'create_plan':
            plan_protocols = _allowed_form_protocols(request.form.getlist('protocols'))
            if not plan_protocols:
                flash('حداقل یک پروتکل برای پلن فروش انتخاب کنید')
                return redirect(url_for('web.sales_bot'))
            plan = SalesBotPlan(
                name=request.form['name'].strip(),
                days=int(request.form.get('days') or 0),
                traffic_gb=int(request.form.get('traffic_gb') or 0),
                price=float(request.form.get('price') or 0),
                currency=request.form.get('currency') or _get_sales_bot_settings(owner_id).get('sales_bot_currency','IRT') or 'IRT',
                protocols=','.join(plan_protocols),
                connection_limit=int(request.form.get('connection_limit') or 1),
                active=bool(request.form.get('active')),
                sort_order=int(request.form.get('sort_order') or 0),
                created_by_telegram_id='web:'+str(current_user.id),
                owner_id=(None if owner_id == 0 else owner_id),
            )
            db.session.add(plan); db.session.commit(); flash('پلن فروش ربات ساخته شد')
        elif action == 'edit_plan':
            plan = SalesBotPlan.query.get_or_404(int(request.form['plan_id']))
            if int(getattr(plan, 'owner_id', 0) or 0) != owner_id:
                abort(403)
            plan.name = request.form.get('name','').strip() or plan.name
            plan.days = int(request.form.get('days') or 0)
            plan.traffic_gb = int(request.form.get('traffic_gb') or 0)
            plan.price = float(request.form.get('price') or 0)
            plan.currency = request.form.get('currency') or _get_sales_bot_settings(owner_id).get('sales_bot_currency','IRT') or 'IRT'
            plan_protocols = _allowed_form_protocols(request.form.getlist('protocols'))
            if not plan_protocols:
                flash('حداقل یک پروتکل برای پلن فروش انتخاب کنید')
                return redirect(url_for('web.sales_bot'))
            plan.protocols = ','.join(plan_protocols)
            plan.connection_limit = int(request.form.get('connection_limit') or 1)
            plan.active = bool(request.form.get('active'))
            plan.sort_order = int(request.form.get('sort_order') or 0)
            db.session.commit(); flash('پلن ویرایش شد')
        elif action == 'toggle_plan':
            plan = SalesBotPlan.query.get_or_404(int(request.form['plan_id']))
            if int(getattr(plan, 'owner_id', 0) or 0) != owner_id:
                abort(403)
            plan.active = not plan.active; db.session.commit(); flash('وضعیت پلن تغییر کرد')
        elif action == 'delete_plan':
            plan = SalesBotPlan.query.get_or_404(int(request.form['plan_id']))
            if int(getattr(plan, 'owner_id', 0) or 0) != owner_id:
                abort(403)
            db.session.delete(plan); db.session.commit(); flash('پلن حذف شد')
        return redirect(url_for('web.sales_bot'))
    settings = _get_sales_bot_settings(owner_id)
    owner_filter = None if owner_id == 0 else owner_id
    plans = SalesBotPlan.query.filter_by(owner_id=owner_filter).order_by(SalesBotPlan.sort_order, SalesBotPlan.id.desc()).all()
    orders = SalesBotOrder.query.filter_by(owner_id=owner_filter).order_by(SalesBotOrder.id.desc()).limit(100).all()
    customers = SalesBotCustomer.query.filter_by(owner_id=owner_filter).order_by(SalesBotCustomer.id.desc()).limit(100).all()
    return render_template('sales_bot.html', settings=settings, plans=plans, orders=orders, customers=customers, active=available_protocols_for_current_user(), sales_bot_owner_id=owner_id)

@web_bp.route('/sales-bot/orders/<int:order_id>/approve', methods=['POST'])
@login_required
def sales_bot_order_approve(order_id):
    if current_user.role not in ('main_admin', 'sub_admin'):
        return redirect(url_for('web.dashboard'))
    from bot.main import _create_vpn_user_for_order, _renew_vpn_user_for_order, _subscription_url
    order = SalesBotOrder.query.get_or_404(order_id)
    if not _order_visible_for_current_user(order):
        abort(403)
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
    if current_user.role not in ('main_admin', 'sub_admin'):
        return redirect(url_for('web.dashboard'))
    order = SalesBotOrder.query.get_or_404(order_id)
    if not _order_visible_for_current_user(order):
        abort(403)
    order.status = 'rejected'; order.rejected_at = datetime.utcnow(); order.admin_note = request.form.get('admin_note','rejected from web')
    db.session.commit(); log(current_user.username, 'sales_order_reject', str(order.id))
    flash('سفارش رد شد')
    return redirect(url_for('web.sales_bot'))

@web_bp.route('/telegram', methods=['GET','POST'])
@login_required
def telegram_console():
    if request.method=='POST':
        res=handle_telegram_command(request.form.get('command',''), 'web-console')
        flash(res)
        return redirect(url_for('web.telegram_console'))
    return render_template('telegram.html', logs=TelegramCommandLog.query.order_by(TelegramCommandLog.id.desc()).limit(100).all())

@web_bp.route('/telegram/bot', methods=['POST'])
def telegram_bot_hook():
    # Minimal bot endpoint for automation integrations. Configure webhook manually if needed.
    data=request.json or {}; msg=data.get('message',{}); text=(msg.get('text') or '').strip(); chat=msg.get('chat',{}).get('id')
    if text.startswith('/status') and chat:
        from ..services.provisioning import service_status
        telegram_notify('IronPanel online. Services: '+str(service_status()))
    return jsonify(ok=True)

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
            # v19.10.10: restart the admin bot and arm/run the 24h backup
            # scheduler in the background. Do not block the web request while a
            # backup file is being generated/uploaded to Telegram.
            run_cmd(['bash','-lc',
                     '(systemctl daemon-reload >/dev/null 2>&1 || true; '
                     'systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true; '
                     'systemctl enable --now ironpanel-admin-report.timer >/dev/null 2>&1 || true; '
                     'systemctl start ironpanel-admin-report.service >/dev/null 2>&1 || true) >/dev/null 2>&1 &'])
            flash('تنظیمات ربات مدیریتی ذخیره شد؛ بکاپ ۲۴ ساعته ادمین‌بات هم فعال شد')
        return redirect(url_for('web.admin_bot_manager'))
    return render_template('admin_bot.html', settings=admin_bot_settings(), report=admin_bot_report_text())

# v19.10.22: MirzaBot Custom Panel API compatibility settings.
@web_bp.route('/mirzabot-api', methods=['GET', 'POST'])
@login_required
def mirzabot_api_settings():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = (request.form.get('action') or 'save').strip()
        if action == 'regenerate_key':
            set_setting('mirzabot_api_key', secrets.token_urlsafe(48))
            flash('کلید API میرزا‌بات با موفقیت ساخته شد.')
            return redirect(url_for('web.mirzabot_api_settings'))
        selected = filter_protocols_for_license(normalize_user_protocols(request.form.getlist('protocols')))
        available = set(active_protocols())
        selected = [p for p in selected if p in available]
        if not selected:
            selected = list(filter_protocols_for_license(active_protocols()))
        set_setting('mirzabot_api_enabled', '1' if request.form.get('enabled') == '1' else '0')
        set_setting('mirzabot_protocols', ','.join(selected))
        if not get_setting('mirzabot_api_key', ''):
            set_setting('mirzabot_api_key', secrets.token_urlsafe(48))
        flash('تنظیمات API میرزا‌بات ذخیره شد.')
        return redirect(url_for('web.mirzabot_api_settings'))
    key = get_setting('mirzabot_api_key', '')
    protocols = [p for p in (get_setting('mirzabot_protocols', '') or '').split(',') if p]
    if not protocols:
        protocols = list(filter_protocols_for_license(active_protocols()))
    endpoint = request.url_root.rstrip('/') + '/api/mirzabot/v1'
    return render_template(
        'mirzabot_api.html',
        mirzabot_enabled=str(get_setting('mirzabot_api_enabled', '0')) == '1',
        mirzabot_key=key,
        mirzabot_protocols=protocols,
        available_protocols=list(filter_protocols_for_license(active_protocols())),
        mirzabot_endpoint=endpoint,
    )

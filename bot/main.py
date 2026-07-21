import io
import logging
import secrets
import json
import os
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from app import create_app
from app.core.extensions import db
from app.core.models import AppSetting, SalesBotCustomer, SalesBotOrder, SalesBotPlan, VpnUser
from app.services.provisioning import get_setting, set_setting, sync_user, user_usage_summary, user_access_status, get_public_host, get_subscription_base_url, active_protocols, set_user_ip_limit
from app.services.xray import xray_profile_text, xray_profile_meta, write_user_xray_profile, xray_runtime_status, XRAY_PROFILE_TYPES, xray_settings

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('ironpanel-sales-bot')
flask_app = create_app()
SALES_BOT_OWNER_ID = int(os.environ.get('IRONPANEL_SALES_BOT_OWNER_ID', '0') or 0)

PROTOCOL_LABELS = {
    'openvpn': 'OpenVPN',
    'wireguard': 'WireGuard',
    'ocserv': 'Cisco AnyConnect/Ocserv',
    'l2tp': 'L2TP/IPsec',
    'xray': 'Xray / V2Ray',
}
XRAY_ALIASES = ('xray', 'v2ray', 'vless', 'vmess', 'trojan', 'shadowsocks')


def _bot_key(key):
    # Owner 0 is the main admin/global bot. Resellers use isolated AppSetting keys.
    return key if SALES_BOT_OWNER_ID <= 0 else f'{key}_owner_{SALES_BOT_OWNER_ID}'

def _setting(key, default=''):
    val = get_setting(_bot_key(key), default)
    return val if val not in (None, '') else default

def set_setting(key, value):
    from app.services.provisioning import set_setting as _base_set_setting
    return _base_set_setting(_bot_key(key), value)

def _owner_value():
    return None if SALES_BOT_OWNER_ID <= 0 else SALES_BOT_OWNER_ID

def _plan_query():
    return SalesBotPlan.query.filter_by(owner_id=_owner_value())

def _order_query():
    return SalesBotOrder.query.filter_by(owner_id=_owner_value())

def _customer_query():
    return SalesBotCustomer.query.filter_by(owner_id=_owner_value())


def _wallet_key(tg_id):
    return f'sales_bot_wallet_{tg_id}'


def _wallet_balance(tg_id):
    try:
        return float(_setting(_wallet_key(tg_id), '0') or 0)
    except Exception:
        return 0.0


def _wallet_set(tg_id, amount):
    set_setting(_wallet_key(tg_id), f'{max(0.0, float(amount)):.2f}')


def _wallet_add(tg_id, amount):
    new_balance = _wallet_balance(tg_id) + float(amount or 0)
    _wallet_set(tg_id, new_balance)
    return new_balance


def _wallet_debit(tg_id, amount):
    amount = float(amount or 0)
    bal = _wallet_balance(tg_id)
    if bal + 1e-9 < amount:
        return False, bal
    _wallet_set(tg_id, bal - amount)
    return True, bal - amount


def _is_special_customer(tg_id):
    return _setting(f'sales_bot_special_{tg_id}', '0') == '1'


def _safe_float_text(value):
    try:
        return float(str(value).replace(',', '').strip())
    except Exception:
        return 0.0


def _set_json(key, data):
    set_setting(key, json.dumps(data, ensure_ascii=False))


def _get_json(key, default=None):
    try:
        return json.loads(_setting(key, '') or '{}')
    except Exception:
        return default if default is not None else {}


def _admin_ids():
    raw = _setting('sales_bot_admin_ids', '') or _setting('telegram_chat_id', '') or ''
    return {x.strip() for x in str(raw).replace('\n', ',').split(',') if x.strip()}


def _is_admin(tg_id):
    return str(tg_id) in _admin_ids()


def _fmt_money(amount, currency):
    try:
        amount = float(amount)
        txt = f'{amount:,.0f}' if amount.is_integer() else f'{amount:,.2f}'
    except Exception:
        txt = str(amount)
    return f'{txt} {currency}'


def _protocol_list(raw):
    items = [x.strip().lower() for x in (raw or '').replace('|', ',').split(',') if x.strip()]
    normalized = []
    for item in items:
        if item in XRAY_ALIASES:
            item = 'xray'
        if item not in normalized:
            normalized.append(item)
    return normalized


def _protocol_text(raw):
    protos = _protocol_list(raw)
    if not protos:
        return 'همه پروتکل‌های فعال پنل'
    return '، '.join(PROTOCOL_LABELS.get(p, p) for p in protos)


def _plan_has_xray(plan):
    return 'xray' in _protocol_list(plan.protocols)


def _fmt_plan(plan):
    days = 'نامحدود' if int(plan.days or 0) <= 0 else f'{plan.days} روز'
    traffic = 'نامحدود' if int(plan.traffic_gb or 0) <= 0 else f'{plan.traffic_gb} GB'
    return (
        f'{plan.name}\n'
        f'⏳ مدت: {days}\n'
        f'📦 حجم: {traffic}\n'
        f'🔌 نوع کانفیگ: {_protocol_text(plan.protocols)}\n'
        f'👥 دستگاه: {plan.connection_limit or 1}\n'
        f'💳 قیمت: {_fmt_money(plan.price or 0, plan.currency or "IRT")}'
    )


def _ensure_customer(tg_user):
    tg_id = str(tg_user.id)
    c = _customer_query().filter_by(telegram_id=tg_id).first()
    if not c:
        c = SalesBotCustomer(telegram_id=tg_id, owner_id=_owner_value(), username=tg_user.username or '', first_name=tg_user.first_name or '', language_code=tg_user.language_code or 'fa')
        db.session.add(c)
    else:
        c.username = tg_user.username or c.username
        c.first_name = tg_user.first_name or c.first_name
        c.updated_at = datetime.utcnow()
    db.session.commit()
    return c


def _subscription_url(u):
    return f'{get_subscription_base_url()}/s/{u.subscription_token}'


def _active_default_protocols():
    protos = active_protocols() or ['openvpn', 'wireguard', 'ocserv', 'l2tp', 'xray', 'pptp', 'hysteria2']
    if 'xray' not in protos:
        protos.append('xray')
    return protos


def _sync_after_user_change(u):
    try:
        sync_user(u)
    except Exception as e:
        log.exception('sync_user failed: %s', e)
    if 'xray' in _protocol_list(u.protocol_permissions or u.protocols):
        try:
            write_user_xray_profile(u)
        except Exception as e:
            log.exception('write_user_xray_profile failed: %s', e)


def _order_owner_value(order):
    oid = int(getattr(order, 'owner_id', 0) or 0)
    return None if oid <= 0 else oid

def _create_vpn_user_for_order(order):
    owner_value = _order_owner_value(order)
    plan = SalesBotPlan.query.filter_by(id=order.plan_id, owner_id=owner_value).first()
    if not plan:
        raise RuntimeError('Plan not found')
    base = f'tg{order.telegram_id}_{order.id}'
    username = base[:70]
    if VpnUser.query.filter_by(username=username).first():
        username = f'{base}_{secrets.token_hex(2)}'[:78]
    password = secrets.token_urlsafe(10)
    expires_at = None if int(plan.days or 0) <= 0 else datetime.utcnow() + timedelta(days=int(plan.days))
    protocols = ','.join(_protocol_list(plan.protocols) or _active_default_protocols())
    u = VpnUser(
        username=username,
        l2tp_password=password,
        cisco_password=password,
        data_limit_mb=int(plan.traffic_gb or 0) * 1024,
        connection_limit=int(plan.connection_limit or 1),
        protocols=protocols,
        protocol_permissions=protocols,
        expires_at=expires_at,
        enabled=True,
        owner_id=owner_value,
    )
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    _sync_after_user_change(u)
    order.vpn_user_id = u.id
    order.status = 'approved'
    order.approved_at = datetime.utcnow()
    db.session.commit()
    return u, password


def _renew_vpn_user_for_order(order):
    owner_value = _order_owner_value(order)
    plan = SalesBotPlan.query.filter_by(id=order.plan_id, owner_id=owner_value).first()
    if not plan or not order.vpn_user_id:
        return _create_vpn_user_for_order(order)
    u = VpnUser.query.get(order.vpn_user_id)
    if not u:
        return _create_vpn_user_for_order(order)
    if int(plan.days or 0) > 0:
        base = u.expires_at if u.expires_at and u.expires_at > datetime.utcnow() else datetime.utcnow()
        u.expires_at = base + timedelta(days=int(plan.days))
    if int(plan.traffic_gb or 0) > 0:
        u.data_limit_mb = (u.data_limit_mb or 0) + int(plan.traffic_gb) * 1024
    plan_protocols = _protocol_list(plan.protocols)
    if plan_protocols:
        merged = sorted(set(_protocol_list(u.protocol_permissions or u.protocols)) | set(plan_protocols))
        u.protocols = ','.join(merged)
        u.protocol_permissions = ','.join(merged)
    u.enabled = True
    db.session.commit()
    _sync_after_user_change(u)
    order.status = 'approved'
    order.approved_at = datetime.utcnow()
    db.session.commit()
    return u, None


def _create_trial(tg_user):
    c = _ensure_customer(tg_user)
    if c.trial_used:
        return None, 'شما قبلاً تست رایگان دریافت کرده‌اید.'
    if _setting('sales_bot_trial_enabled', '1') != '1':
        return None, 'تست رایگان در حال حاضر غیرفعال است.'
    days = int(_setting('sales_bot_trial_days', '1') or 1)
    traffic = int(_setting('sales_bot_trial_traffic_gb', '1') or 1)
    username = f'trial{tg_user.id}_{secrets.token_hex(2)}'[:78]
    password = secrets.token_urlsafe(10)
    protocols = ','.join(_active_default_protocols())
    u = VpnUser(username=username, l2tp_password=password, cisco_password=password, data_limit_mb=max(0, traffic) * 1024, connection_limit=1, protocols=protocols, protocol_permissions=protocols, expires_at=datetime.utcnow() + timedelta(days=max(1, days)), enabled=True, owner_id=_owner_value())
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    _sync_after_user_change(u)
    c.trial_used = True
    db.session.add(SalesBotOrder(telegram_id=str(tg_user.id), customer_id=c.id, vpn_user_id=u.id, owner_id=_owner_value(), order_type='trial', status='approved', amount=0, currency=_setting('sales_bot_currency', 'IRT'), approved_at=datetime.utcnow(), admin_note='trial auto-created'))
    db.session.commit()
    return u, password




def _sales_welcome_text():
    return _setting('sales_bot_welcome_text', 'به ربات فروش IronPanel خوش آمدید ✅\nاز دکمه‌های زیر استفاده کنید؛ برای خرید، دریافت تست رایگان، مشاهده سرویس‌ها و پشتیبانی نیازی به تایپ دستی نیست.') or 'به ربات فروش IronPanel خوش آمدید ✅'

def main_keyboard(is_admin=False):
    rows = [
        [InlineKeyboardButton('🛒 خرید سرویس VPN', callback_data='buy'), InlineKeyboardButton('⚡ خرید کانفیگ Xray/V2Ray', callback_data='buy_xray')],
        [InlineKeyboardButton('🎁 تست رایگان', callback_data='trial'), InlineKeyboardButton('📊 سرویس‌های من', callback_data='my_services')],
        [InlineKeyboardButton('📥 دریافت کانفیگ‌ها', callback_data='configs'), InlineKeyboardButton('♻️ تمدید سرویس', callback_data='renew')],
        [InlineKeyboardButton('💰 کیف پول', callback_data='wallet'), InlineKeyboardButton('⭐ درخواست مشتری ویژه', callback_data='special_request')],
        [InlineKeyboardButton('📘 راهنمای اتصال', callback_data='guide'), InlineKeyboardButton('📜 قوانین', callback_data='rules')],
        [InlineKeyboardButton('🆘 پشتیبانی', callback_data='support')],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton('🛠 مدیریت فروش', callback_data='admin')])
    return InlineKeyboardMarkup(rows)


def back_button(to='home'):
    return [InlineKeyboardButton('⬅️ بازگشت', callback_data=to)]


async def _notify_admins(context, text, reply_markup=None):
    for aid in _admin_ids():
        try:
            await context.bot.send_message(chat_id=int(aid), text=text, reply_markup=reply_markup)
        except Exception as e:
            log.warning('admin notify failed %s: %s', aid, e)


async def start(update, context):
    with flask_app.app_context():
        _ensure_customer(update.effective_user)
        admin = _is_admin(update.effective_user.id)
        welcome = _sales_welcome_text()
    msg = update.effective_message or update.message
    if msg:
        await msg.reply_text(welcome, reply_markup=main_keyboard(admin))


async def show_admin(q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('➕ ساخت پلن', callback_data='admin:create_plan'), InlineKeyboardButton('📋 مدیریت پلن‌ها', callback_data='admin:plans')],
        [InlineKeyboardButton('⏳ سفارش‌ها', callback_data='admin:orders'), InlineKeyboardButton('🎁 تنظیم تست', callback_data='admin:trial')],
        [InlineKeyboardButton('⚡ وضعیت Xray/V2Ray', callback_data='admin:xray_status'), InlineKeyboardButton('💳 متن پرداخت دستی', callback_data='admin:payment')],
        [InlineKeyboardButton('💰 سفارش‌های کیف پول', callback_data='admin:wallet_orders'), InlineKeyboardButton('🎯 ساخت رایگان', callback_data='admin:free_config')],
        [InlineKeyboardButton('📊 آمار', callback_data='admin:stats')],
        [InlineKeyboardButton('⬅️ بازگشت', callback_data='home')],
    ])
    await q.edit_message_text('مدیریت فروش IronPanel:', reply_markup=kb)


async def _show_plans(q, xray_only=False):
    plans = _plan_query().filter_by(active=True).order_by(SalesBotPlan.sort_order, SalesBotPlan.id).all()
    if xray_only:
        plans = [p for p in plans if _plan_has_xray(p)]
    if not plans:
        txt = 'فعلاً پلن فعال Xray/V2Ray برای فروش وجود ندارد.' if xray_only else 'فعلاً پلن فعالی برای فروش وجود ندارد.'
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([back_button('home')]))
        return
    title = '⚡ پلن کانفیگ Xray/V2Ray را انتخاب کنید:' if xray_only else '🛒 پلن موردنظر را انتخاب کنید:'
    kb = [[InlineKeyboardButton(f'{p.name} | {_fmt_money(p.price, p.currency)} | {_protocol_text(p.protocols)}', callback_data=f'buy:{p.id}')] for p in plans]
    kb.append(back_button('home'))
    await q.edit_message_text(title, reply_markup=InlineKeyboardMarkup(kb))


async def _send_xray_config(context, chat_id, u):
    try:
        body = xray_profile_text(u)
        bio = io.BytesIO(body.encode('utf-8'))
        bio.name = f'{u.username}-xray.txt'
        await context.bot.send_document(chat_id=chat_id, document=bio, filename=bio.name, caption=xray_profile_meta(u) + '\nاین فایل را در v2rayNG / Hiddify / Nekoray / Sing-box یا کلاینت‌های سازگار import کنید.')
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f'خطا در ساخت کانفیگ Xray/V2Ray: {e}')


def _service_buttons(u, source='configs'):
    rows = []
    rows.append([InlineKeyboardButton(f'🔗 لینک Subscription: {u.username}', callback_data=f'sub:{u.id}')])
    if 'xray' in _protocol_list(u.protocol_permissions or u.protocols):
        rows.append([InlineKeyboardButton(f'⚡ فایل Xray/V2Ray: {u.username}', callback_data=f'xraycfg:{u.id}:{source}')])
    return rows


async def callbacks(update, context):
    q = update.callback_query
    await q.answer()
    data = q.data or ''
    with flask_app.app_context():
        user = q.from_user
        c = _ensure_customer(user)
        is_admin = _is_admin(user.id)
        if data == 'home':
            await q.edit_message_text(_sales_welcome_text(), reply_markup=main_keyboard(is_admin))
            return
        if data == 'buy':
            await _show_plans(q, xray_only=False)
            return
        if data == 'buy_xray':
            await _show_plans(q, xray_only=True)
            return
        if data.startswith('buy:'):
            p = _plan_query().filter_by(id=int(data.split(':', 1)[1])).first()
            if not p or not p.active:
                await q.edit_message_text('این پلن فعال نیست.')
                return
            o = SalesBotOrder(telegram_id=str(user.id), customer_id=c.id, plan_id=p.id, owner_id=_owner_value(), amount=p.price, currency=p.currency, order_type='new', status='pending_payment')
            db.session.add(o)
            db.session.commit()
            set_setting(f'sales_bot_pending_order_{user.id}', str(o.id))
            rows = []
            if _wallet_balance(user.id) >= float(p.price or 0):
                rows.append([InlineKeyboardButton('💰 پرداخت از کیف پول', callback_data=f'paywallet:{o.id}')])
            rows.append(back_button('home'))
            await q.edit_message_text(f'سفارش #{o.id}\n\n{_fmt_plan(p)}\n\n{_setting("sales_bot_payment_text", "لطفاً رسید پرداخت را ارسال کنید.")}\n\nپس از پرداخت، تصویر یا فایل رسید را همین‌جا ارسال کنید.', reply_markup=InlineKeyboardMarkup(rows))
            return
        if data == 'trial':
            result, extra = _create_trial(user)
            if not result:
                await q.edit_message_text(extra, reply_markup=InlineKeyboardMarkup([back_button('home')]))
                return
            await q.edit_message_text(f'تست رایگان ساخته شد ✅\nنام کاربری: {result.username}\nرمز سرویس‌ها: {extra}\nلینک سابسکریپشن:\n{_subscription_url(result)}\n\nبرای دریافت فایل Xray/V2Ray از دکمه «دریافت کانفیگ‌ها» استفاده کنید.', reply_markup=InlineKeyboardMarkup([back_button('home')]))
            return
        if data in ('my_services', 'configs', 'renew'):
            orders = _order_query().filter_by(telegram_id=str(user.id), status='approved').filter(SalesBotOrder.vpn_user_id.isnot(None)).order_by(SalesBotOrder.id.desc()).all()
            if not orders:
                await q.edit_message_text('سرویسی برای شما پیدا نشد.', reply_markup=InlineKeyboardMarkup([back_button('home')]))
                return
            lines = []
            kb = []
            seen = set()
            for o in orders:
                u = VpnUser.query.get(o.vpn_user_id)
                if not u or u.id in seen:
                    continue
                seen.add(u.id)
                usage = user_usage_summary(u)
                ok, reason = user_access_status(u)
                exp = 'نامحدود' if not u.expires_at else u.expires_at.strftime('%Y-%m-%d')
                lines.append(f'👤 {u.username}\nوضعیت: {reason}\nپروتکل‌ها: {_protocol_text(u.protocol_permissions or u.protocols)}\nحجم: {usage.get("used_human", usage.get("used_gb", "0"))} / {usage.get("total_human", "نامحدود")}\nانقضا: {exp}')
                if data == 'renew':
                    kb.append([InlineKeyboardButton(f'تمدید {u.username}', callback_data=f'renewuser:{u.id}')])
                elif data == 'configs':
                    kb.extend(_service_buttons(u, 'configs'))
            kb.append(back_button('home'))
            await q.edit_message_text('\n\n'.join(lines), reply_markup=InlineKeyboardMarkup(kb))
            return
        if data.startswith('sub:'):
            u = VpnUser.query.get(int(data.split(':')[1]))
            if not u:
                await q.edit_message_text('سرویس پیدا نشد.')
                return
            sub_link = _subscription_url(u)
            await q.edit_message_text(f'🔗 لینک Subscription برای {u.username}:\n{sub_link}', reply_markup=InlineKeyboardMarkup([back_button('configs')]))
            if _setting('sales_bot_qr_enabled', '1') == '1':
                try:
                    import qrcode
                    img = qrcode.make(sub_link)
                    bio = io.BytesIO()
                    img.save(bio, format='PNG')
                    bio.seek(0); bio.name = f'{u.username}-subscription.png'
                    await context.bot.send_photo(chat_id=q.message.chat_id, photo=bio, caption=f'QR Subscription: {u.username}')
                except Exception as e:
                    log.warning('QR delivery failed: %s', e)
            return
        if data.startswith('xraycfg:'):
            parts = data.split(':')
            u = VpnUser.query.get(int(parts[1]))
            if not u:
                await q.edit_message_text('سرویس پیدا نشد.')
                return
            await _send_xray_config(context, q.message.chat_id, u)
            await q.edit_message_text('فایل Xray/V2Ray ارسال شد ✅', reply_markup=InlineKeyboardMarkup([back_button('configs')]))
            return
        if data.startswith('renewuser:'):
            uid = int(data.split(':', 1)[1])
            plans = _plan_query().filter_by(active=True).order_by(SalesBotPlan.sort_order, SalesBotPlan.id).all()
            kb = [[InlineKeyboardButton(f'{p.name} - {_fmt_money(p.price, p.currency)}', callback_data=f'renewplan:{uid}:{p.id}')] for p in plans]
            kb.append(back_button('renew'))
            await q.edit_message_text('پلن تمدید را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(kb))
            return
        if data.startswith('renewplan:'):
            _, uid, pid = data.split(':')
            p = _plan_query().filter_by(id=int(pid)).first()
            u = VpnUser.query.get(int(uid))
            if not p or not u:
                await q.edit_message_text('پلن یا کاربر پیدا نشد')
                return
            o = SalesBotOrder(telegram_id=str(user.id), customer_id=c.id, plan_id=p.id, owner_id=_owner_value(), vpn_user_id=u.id, order_type='renew', status='pending_payment', amount=p.price, currency=p.currency)
            db.session.add(o)
            db.session.commit()
            set_setting(f'sales_bot_pending_order_{user.id}', str(o.id))
            await q.edit_message_text(f'سفارش تمدید #{o.id}\nسرویس: {u.username}\n{_fmt_plan(p)}\n\n{_setting("sales_bot_payment_text", "رسید پرداخت را ارسال کنید.")}')
            return
        if data == 'support':
            await q.edit_message_text(f'پشتیبانی: {_setting("sales_bot_support_url", "https://t.me/unknown_eng")}', reply_markup=InlineKeyboardMarkup([back_button('home')]))
            return
        if data == 'rules':
            await q.edit_message_text(_setting('sales_bot_rules_text', 'قوانین سرویس هنوز توسط مدیر تنظیم نشده است.'), reply_markup=InlineKeyboardMarkup([back_button('home')]))
            return
        if data == 'guide':
            await q.edit_message_text(_setting('sales_bot_connection_guide', 'راهنمای اتصال هنوز توسط مدیر تنظیم نشده است. لینک Subscription را در کلاینت سازگار وارد کنید.'), reply_markup=InlineKeyboardMarkup([back_button('home')]))
            return
        if data == 'wallet':
            bal = _wallet_balance(user.id)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('➕ درخواست شارژ کیف پول', callback_data='wallet_charge')], back_button('home')])
            await q.edit_message_text(f'💰 کیف پول شما: {_fmt_money(bal, _setting("sales_bot_currency", "IRT"))}', reply_markup=kb)
            return
        if data == 'wallet_charge':
            _set_json(f'sales_bot_state_{user.id}', {'step': 'wallet_amount'})
            await q.edit_message_text('مبلغ شارژ کیف پول را ارسال کنید:')
            return
        if data == 'special_request':
            if _is_special_customer(user.id):
                await q.edit_message_text('شما قبلاً به‌عنوان مشتری ویژه تأیید شده‌اید.', reply_markup=InlineKeyboardMarkup([back_button('home')]))
                return
            set_setting(f'sales_bot_special_request_{user.id}', 'pending')
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('✅ تأیید ویژه', callback_data=f'admin:special:approve:{user.id}'), InlineKeyboardButton('❌ رد', callback_data=f'admin:special:reject:{user.id}')]])
            await _notify_admins(context, f'درخواست مشتری ویژه/نمایندگی\nTelegram ID: {user.id}\nUsername: @{user.username or "-"}', kb)
            await q.edit_message_text('درخواست شما برای مدیر ارسال شد.', reply_markup=InlineKeyboardMarkup([back_button('home')]))
            return
        if data.startswith('paywallet:'):
            oid = int(data.split(':',1)[1])
            o = _order_query().filter_by(id=oid).first()
            if not o or o.telegram_id != str(user.id) or o.status not in ('pending_payment','receipt_sent'):
                await q.edit_message_text('سفارش قابل پرداخت نیست.', reply_markup=InlineKeyboardMarkup([back_button('home')]))
                return
            ok, bal = _wallet_debit(user.id, o.amount)
            if not ok:
                await q.edit_message_text('موجودی کیف پول کافی نیست.', reply_markup=InlineKeyboardMarkup([back_button('wallet')]))
                return
            try:
                if o.order_type == 'wallet':
                    new_bal = _wallet_add(o.telegram_id, o.amount)
                    o.status = 'approved'; o.approved_at = datetime.utcnow(); o.admin_note = f'wallet approved by {user.id}'
                    db.session.commit()
                    await q.edit_message_text(f'کیف پول سفارش #{o.id} شارژ شد. موجودی جدید: {_fmt_money(new_bal, o.currency)}')
                    try: await context.bot.send_message(chat_id=int(o.telegram_id), text=f'کیف پول شما شارژ شد ✅\nموجودی: {_fmt_money(new_bal, o.currency)}')
                    except Exception: pass
                    return
                if o.order_type == 'renew':
                    u, pwd = _renew_vpn_user_for_order(o)
                    text = f'تمدید با کیف پول انجام شد ✅\nسرویس: {u.username}\nلینک سابسکریپشن:\n{_subscription_url(u)}'
                else:
                    u, pwd = _create_vpn_user_for_order(o)
                    text = f'خرید با کیف پول انجام شد ✅\nسرویس: {u.username}\nرمز سرویس‌ها: {pwd}\nلینک سابسکریپشن:\n{_subscription_url(u)}'
                await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([back_button('home')]))
                await _notify_admins(context, f'پرداخت کیف پول سفارش #{o.id} انجام شد. کاربر: {user.id} | باقی‌مانده: {bal}')
                if 'xray' in _protocol_list(u.protocol_permissions or u.protocols):
                    await _send_xray_config(context, int(o.telegram_id), u)
            except Exception as e:
                _wallet_add(user.id, o.amount)
                await q.edit_message_text(f'خطا در ساخت سرویس؛ مبلغ به کیف پول برگشت. {e}')
            return
        if data == 'admin' and is_admin:
            await show_admin(q)
            return
        if not is_admin and data.startswith('admin:'):
            return
        if data == 'admin:create_plan':
            _set_json(f'sales_bot_state_{user.id}', {'step': 'plan_name'})
            await q.edit_message_text('نام پلن را ارسال کنید:')
            return
        if data.startswith('admin:planproto:'):
            preset = data.split(':')[2]
            state = _get_json(f'sales_bot_state_{user.id}', {})
            if not state or state.get('step') not in ('plan_protocol_preset', 'plan_protocols_custom'):
                await q.edit_message_text('وضعیت ساخت پلن پیدا نشد.', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
                return
            if preset == 'all':
                protocols = ','.join(_active_default_protocols())
            elif preset == 'xray':
                protocols = 'xray'
            elif preset == 'classic':
                protocols = ','.join([p for p in ('openvpn', 'wireguard', 'ocserv', 'l2tp') if p in _active_default_protocols()])
            elif preset == 'custom':
                state['step'] = 'plan_protocols_custom'
                _set_json(f'sales_bot_state_{user.id}', state)
                await q.edit_message_text('پروتکل‌های پلن را با کاما ارسال کنید. نمونه:\nxray\nیا\nopenvpn,wireguard,xray')
                return
            else:
                protocols = 'xray'
            p = SalesBotPlan(name=state['name'], days=int(state['days']), traffic_gb=int(state['traffic_gb']), price=float(state['price']), currency=state.get('currency') or _setting('sales_bot_currency', 'IRT'), protocols=protocols, connection_limit=int(state.get('connection_limit', 1)), created_by_telegram_id=str(user.id), active=True)
            db.session.add(p)
            db.session.commit()
            set_setting(f'sales_bot_state_{user.id}', '')
            await q.edit_message_text(f'پلن ساخته شد ✅\nID {p.id}\n{_fmt_plan(p)}', reply_markup=main_keyboard(True))
            return
        if data == 'admin:plans':
            plans = _plan_query().order_by(SalesBotPlan.sort_order, SalesBotPlan.id).all()
            rows = []
            txt = 'پلن‌ها:' if plans else 'پلنی ثبت نشده است.'
            for p in plans:
                rows.append([InlineKeyboardButton(f'{"✅" if p.active else "❌"} {p.name} | {_protocol_text(p.protocols)}', callback_data=f'admin:plan:{p.id}')])
            rows.append(back_button('admin'))
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(rows))
            return
        if data.startswith('admin:plan:'):
            p = _plan_query().filter_by(id=int(data.split(':')[2])).first()
            if not p:
                await q.edit_message_text('پلن پیدا نشد.')
                return
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('فعال/غیرفعال', callback_data=f'admin:toggleplan:{p.id}'), InlineKeyboardButton('حذف', callback_data=f'admin:deleteplan:{p.id}')], [InlineKeyboardButton('⬅️ پلن‌ها', callback_data='admin:plans')]])
            await q.edit_message_text(f'ID {p.id}\n{_fmt_plan(p)}\nوضعیت: {"فعال" if p.active else "غیرفعال"}', reply_markup=kb)
            return
        if data.startswith('admin:toggleplan:'):
            p = _plan_query().filter_by(id=int(data.split(':')[2])).first()
            p.active = not p.active
            db.session.commit()
            await q.edit_message_text('وضعیت پلن تغییر کرد.', reply_markup=InlineKeyboardMarkup([back_button('admin:plans')]))
            return
        if data.startswith('admin:deleteplan:'):
            p = _plan_query().filter_by(id=int(data.split(':')[2])).first()
            db.session.delete(p)
            db.session.commit()
            await q.edit_message_text('پلن حذف شد.', reply_markup=InlineKeyboardMarkup([back_button('admin:plans')]))
            return
        if data == 'admin:xray_status':
            st = xray_runtime_status()
            settings = xray_settings()
            profile = XRAY_PROFILE_TYPES.get(settings.get('xray_profile_type'), {})
            await q.edit_message_text(f'⚡ وضعیت Xray/V2Ray\nفعال: {"بله" if st.get("enabled") == "1" else "خیر"}\nپروفایل فعال: {profile.get("title", st.get("profile_type"))}\nهاست: {st.get("host")}\nپورت: {st.get("port")}\nاعتبار تنظیمات: {st.get("validation_message")}', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
            return
        if data == 'admin:trial':
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('✅ فعال', callback_data='admin:trial:on'), InlineKeyboardButton('❌ غیرفعال', callback_data='admin:trial:off')], [InlineKeyboardButton('✏️ تنظیم مدت/حجم', callback_data='admin:trial:set')], [InlineKeyboardButton('⬅️ بازگشت', callback_data='admin')]])
            await q.edit_message_text(f'تست رایگان: {"فعال" if _setting("sales_bot_trial_enabled", "1") == "1" else "غیرفعال"}\nمدت: {_setting("sales_bot_trial_days", "1")} روز\nحجم: {_setting("sales_bot_trial_traffic_gb", "1")}GB', reply_markup=kb)
            return
        if data == 'admin:trial:on':
            set_setting('sales_bot_trial_enabled', '1')
            await q.edit_message_text('تست فعال شد.', reply_markup=InlineKeyboardMarkup([back_button('admin:trial')]))
            return
        if data == 'admin:trial:off':
            set_setting('sales_bot_trial_enabled', '0')
            await q.edit_message_text('تست غیرفعال شد.', reply_markup=InlineKeyboardMarkup([back_button('admin:trial')]))
            return
        if data == 'admin:trial:set':
            _set_json(f'sales_bot_state_{user.id}', {'step': 'trial_days'})
            await q.edit_message_text('مدت تست را به روز ارسال کنید:')
            return
        if data == 'admin:payment':
            _set_json(f'sales_bot_state_{user.id}', {'step': 'payment_text'})
            await q.edit_message_text('متن پرداخت دستی را ارسال کنید:')
            return
        if data.startswith('admin:special:') and is_admin:
            _, _, action, tg = data.split(':')
            if action == 'approve':
                set_setting(f'sales_bot_special_{tg}', '1')
                set_setting(f'sales_bot_special_request_{tg}', 'approved')
                await q.edit_message_text(f'کاربر {tg} ویژه شد.', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
                try: await context.bot.send_message(chat_id=int(tg), text='درخواست مشتری ویژه/نمایندگی شما تأیید شد ✅')
                except Exception: pass
            else:
                set_setting(f'sales_bot_special_request_{tg}', 'rejected')
                await q.edit_message_text(f'درخواست {tg} رد شد.', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
                try: await context.bot.send_message(chat_id=int(tg), text='درخواست مشتری ویژه/نمایندگی شما رد شد.')
                except Exception: pass
            return
        if data == 'admin:wallet_orders':
            orders = _order_query().filter_by(order_type='wallet').filter(SalesBotOrder.status.in_(['pending_payment','receipt_sent'])).order_by(SalesBotOrder.id.desc()).limit(10).all()
            if not orders:
                await q.edit_message_text('درخواست شارژ کیف پولی وجود ندارد.', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
                return
            rows=[]; lines=[]
            for o in orders:
                lines.append(f'#{o.id} | TG:{o.telegram_id} | {_fmt_money(o.amount,o.currency)} | {o.status}')
                rows.append([InlineKeyboardButton(f'✅ شارژ #{o.id}', callback_data=f'approve:{o.id}'), InlineKeyboardButton(f'❌ رد #{o.id}', callback_data=f'reject:{o.id}')])
            rows.append(back_button('admin'))
            await q.edit_message_text('درخواست‌های شارژ کیف پول:\n'+'\n'.join(lines), reply_markup=InlineKeyboardMarkup(rows))
            return
        if data == 'admin:free_config':
            _set_json(f'sales_bot_state_{user.id}', {'step': 'free_config'})
            await q.edit_message_text('برای ساخت رایگان ارسال کنید: TelegramID PlanID Count\nمثال: 123456789 2 1')
            return
        if data == 'admin:orders':
            orders = _order_query().filter(SalesBotOrder.status.in_(['pending_payment', 'receipt_sent'])).order_by(SalesBotOrder.id.desc()).limit(10).all()
            if not orders:
                await q.edit_message_text('سفارش در انتظار وجود ندارد.', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
                return
            lines = []
            rows = []
            for o in orders:
                p = (_plan_query().filter_by(id=o.plan_id).first() if o.plan_id else None)
                lines.append(f'#{o.id} | TG:{o.telegram_id} | {p.name if p else "-"} | {_protocol_text(p.protocols if p else "")} | {_fmt_money(o.amount, o.currency)} | {o.status}')
                rows.append([InlineKeyboardButton(f'✅ تأیید #{o.id}', callback_data=f'approve:{o.id}'), InlineKeyboardButton(f'❌ رد #{o.id}', callback_data=f'reject:{o.id}')])
            rows.append(back_button('admin'))
            await q.edit_message_text('\n'.join(lines), reply_markup=InlineKeyboardMarkup(rows))
            return
        if data == 'admin:stats':
            total = _order_query().count()
            approved = _order_query().filter_by(status='approved').count()
            pending = _order_query().filter(SalesBotOrder.status.in_(['pending_payment', 'receipt_sent'])).count()
            xray_plans = _plan_query().filter(SalesBotPlan.protocols.like('%xray%')).count()
            await q.edit_message_text(f'آمار فروش:\nکل سفارش‌ها: {total}\nتأیید شده: {approved}\nدر انتظار: {pending}\nپلن‌های Xray/V2Ray: {xray_plans}', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
            return
        if data.startswith('approve:') or data.startswith('reject:'):
            oid = int(data.split(':', 1)[1])
            o = _order_query().filter_by(id=oid).first()
            if not o:
                await q.edit_message_text('سفارش پیدا نشد')
                return
            if data.startswith('reject:'):
                o.status = 'rejected'
                o.rejected_at = datetime.utcnow()
                o.admin_note = f'rejected by {user.id}'
                db.session.commit()
                await q.edit_message_text(f'سفارش #{o.id} رد شد.')
                try:
                    await context.bot.send_message(chat_id=int(o.telegram_id), text=f'سفارش #{o.id} رد شد. برای پیگیری با پشتیبانی تماس بگیرید.')
                except Exception:
                    pass
                return
            try:
                if o.order_type == 'wallet':
                    new_bal = _wallet_add(o.telegram_id, o.amount)
                    o.status = 'approved'; o.approved_at = datetime.utcnow(); o.admin_note = f'wallet approved by {user.id}'
                    db.session.commit()
                    await q.edit_message_text(f'کیف پول سفارش #{o.id} شارژ شد. موجودی جدید: {_fmt_money(new_bal, o.currency)}')
                    try: await context.bot.send_message(chat_id=int(o.telegram_id), text=f'کیف پول شما شارژ شد ✅\nموجودی: {_fmt_money(new_bal, o.currency)}')
                    except Exception: pass
                    return
                if o.order_type == 'renew':
                    u, pwd = _renew_vpn_user_for_order(o)
                    text = f'تمدید سفارش #{o.id} تأیید شد ✅\nسرویس: {u.username}\nلینک سابسکریپشن:\n{_subscription_url(u)}'
                else:
                    u, pwd = _create_vpn_user_for_order(o)
                    text = f'سفارش #{o.id} تأیید شد ✅\nسرویس شما ساخته شد.\nنام کاربری: {u.username}\nرمز سرویس‌ها: {pwd}\nلینک سابسکریپشن:\n{_subscription_url(u)}'
                await q.edit_message_text(f'سفارش #{o.id} تأیید شد.')
                await context.bot.send_message(chat_id=int(o.telegram_id), text=text)
                if 'xray' in _protocol_list(u.protocol_permissions or u.protocols):
                    await _send_xray_config(context, int(o.telegram_id), u)
            except Exception as e:
                log.exception('approve failed')
                await q.edit_message_text(f'خطا در تأیید سفارش: {e}')
            return


async def receipt_handler(update, context):
    with flask_app.app_context():
        user = update.effective_user
        _ensure_customer(user)
        state = _get_json(f'sales_bot_state_{user.id}', {}) if _is_admin(user.id) else {}
        text = (update.message.text or '').strip() if update.message.text else ''
        if state:
            step = state.get('step')
            if step == 'plan_name':
                state = {'step': 'plan_days', 'name': text}
                _set_json(f'sales_bot_state_{user.id}', state)
                await update.message.reply_text('مدت پلن را به روز ارسال کنید. 0 یعنی نامحدود:')
                return
            if step == 'plan_days':
                state['days'] = int(text)
                state['step'] = 'plan_traffic'
                _set_json(f'sales_bot_state_{user.id}', state)
                await update.message.reply_text('حجم پلن را به گیگ ارسال کنید. 0 یعنی نامحدود:')
                return
            if step == 'plan_traffic':
                state['traffic_gb'] = int(text)
                state['step'] = 'plan_price'
                _set_json(f'sales_bot_state_{user.id}', state)
                await update.message.reply_text('قیمت پلن را ارسال کنید:')
                return
            if step == 'plan_price':
                state['price'] = float(text)
                state['step'] = 'plan_currency'
                _set_json(f'sales_bot_state_{user.id}', state)
                await update.message.reply_text('واحد پول را ارسال کنید، مثل IRT:')
                return
            if step == 'plan_currency':
                state['currency'] = text or _setting('sales_bot_currency', 'IRT')
                state['step'] = 'plan_connection_limit'
                _set_json(f'sales_bot_state_{user.id}', state)
                await update.message.reply_text('محدودیت IP/دستگاه پلن را ارسال کنید. 0 یعنی نامحدود، Enter/1 یعنی یک IP:')
                return
            if step == 'plan_connection_limit':
                state['connection_limit'] = max(0, int(text or 1))
                state['step'] = 'plan_protocol_preset'
                _set_json(f'sales_bot_state_{user.id}', state)
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton('⚡ فقط Xray/V2Ray', callback_data='admin:planproto:xray')],
                    [InlineKeyboardButton('🌐 همه پروتکل‌ها', callback_data='admin:planproto:all')],
                    [InlineKeyboardButton('🧩 کلاسیک بدون Xray', callback_data='admin:planproto:classic')],
                    [InlineKeyboardButton('✏️ انتخاب دستی', callback_data='admin:planproto:custom')],
                ])
                await update.message.reply_text('نوع کانفیگ قابل فروش در این پلن را انتخاب کنید:', reply_markup=kb)
                return
            if step == 'plan_protocols_custom':
                protocols = ','.join(_protocol_list(text) or ['xray'])
                p = SalesBotPlan(name=state['name'], days=int(state['days']), traffic_gb=int(state['traffic_gb']), price=float(state['price']), currency=state.get('currency') or _setting('sales_bot_currency', 'IRT'), protocols=protocols, connection_limit=int(state.get('connection_limit', 1)), created_by_telegram_id=str(user.id), active=True)
                db.session.add(p)
                db.session.commit()
                set_setting(f'sales_bot_state_{user.id}', '')
                await update.message.reply_text(f'پلن ساخته شد ✅\nID {p.id}\n{_fmt_plan(p)}', reply_markup=main_keyboard(True))
                return
            if step == 'trial_days':
                state = {'step': 'trial_traffic', 'days': int(text)}
                _set_json(f'sales_bot_state_{user.id}', state)
                await update.message.reply_text('حجم تست را به GB ارسال کنید:')
                return
            if step == 'trial_traffic':
                set_setting('sales_bot_trial_days', str(state.get('days', 1)))
                set_setting('sales_bot_trial_traffic_gb', str(int(text)))
                set_setting(f'sales_bot_state_{user.id}', '')
                await update.message.reply_text('تنظیم تست ذخیره شد.', reply_markup=main_keyboard(True))
                return
            if step == 'payment_text':
                set_setting('sales_bot_payment_text', text)
                set_setting(f'sales_bot_state_{user.id}', '')
                await update.message.reply_text('متن پرداخت ذخیره شد.', reply_markup=main_keyboard(True))
                return
            if step == 'wallet_amount':
                amount = _safe_float_text(text)
                if amount <= 0:
                    await update.message.reply_text('مبلغ معتبر نیست. دوباره ارسال کنید:')
                    return
                o = SalesBotOrder(telegram_id=str(user.id), customer_id=c.id, owner_id=_owner_value(), order_type='wallet', status='pending_payment', amount=amount, currency=_setting('sales_bot_currency','IRT'))
                db.session.add(o); db.session.commit()
                set_setting(f'sales_bot_pending_order_{user.id}', str(o.id))
                set_setting(f'sales_bot_state_{user.id}', '')
                await update.message.reply_text(f'درخواست شارژ کیف پول #{o.id} ثبت شد.\nمبلغ: {_fmt_money(amount,o.currency)}\n{_setting("sales_bot_payment_text", "رسید پرداخت را ارسال کنید.")}')
                return
            if step == 'free_config' and _is_admin(user.id):
                parts = text.split()
                if len(parts) < 2:
                    await update.message.reply_text('فرمت درست: TelegramID PlanID Count')
                    return
                tg, pid = parts[0], int(parts[1]); count = int(parts[2]) if len(parts) > 2 else 1
                plan = _plan_query().filter_by(id=pid).first()
                if not plan:
                    await update.message.reply_text('پلن پیدا نشد.')
                    return
                made=[]
                cust = _customer_query().filter_by(telegram_id=str(tg)).first() or SalesBotCustomer(telegram_id=str(tg), owner_id=_owner_value())
                db.session.add(cust); db.session.commit()
                for _ in range(max(1,min(count,20))):
                    o = SalesBotOrder(telegram_id=str(tg), customer_id=cust.id, plan_id=plan.id, owner_id=_owner_value(), order_type='free', status='pending_payment', amount=0, currency=plan.currency, admin_note=f'free by {user.id}')
                    db.session.add(o); db.session.commit()
                    u,pwd = _create_vpn_user_for_order(o)
                    made.append(u.username)
                set_setting(f'sales_bot_state_{user.id}', '')
                await update.message.reply_text('کانفیگ رایگان ساخته شد:\n'+'\n'.join(made), reply_markup=main_keyboard(True))
                return
        row = AppSetting.query.filter_by(key=_bot_key(f'sales_bot_pending_order_{user.id}')).first()
        if not row or not row.value:
            return
        o = _order_query().filter_by(id=int(row.value)).first()
        if not o or o.status not in ('pending_payment', 'receipt_sent'):
            return
        file_id = ''
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document:
            file_id = update.message.document.file_id
        else:
            o.receipt_note = (o.receipt_note or '') + '\n' + (update.message.text or '')
        if file_id:
            o.receipt_file_id = file_id
        o.status = 'receipt_sent'
        db.session.commit()
        plan = (_plan_query().filter_by(id=o.plan_id).first() if o.plan_id else None)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton('✅ تأیید پرداخت', callback_data=f'approve:{o.id}'), InlineKeyboardButton('❌ رد پرداخت', callback_data=f'reject:{o.id}')]])
        await update.message.reply_text('رسید شما ثبت شد. پس از بررسی مدیر، نتیجه اعلام می‌شود.')
        await _notify_admins(context, f'رسید جدید برای سفارش #{o.id}\nTelegram ID: {o.telegram_id}\nپلن: {plan.name if plan else "-"}\nنوع کانفیگ: {_protocol_text(plan.protocols if plan else "")}\nمبلغ: {_fmt_money(o.amount, o.currency)}', kb)


def main():
    with flask_app.app_context():
        token = _setting('sales_bot_token', '') or _setting('telegram_bot_token', '')
        enabled = _setting('sales_bot_enabled', '0') == '1'
    if not token:
        log.warning('Sales bot token is empty.')
        return
    if not enabled:
        log.warning('Sales bot is disabled.')
        return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.TEXT, receipt_handler))
    log.info('IronPanel Sales Bot started with Xray/V2Ray sales sync')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

# v17 sales-bot synchronization helpers
# The web panel stores plan.protocols as one of:
#   xray-only, all-protocols, classic-no-xray, custom
# When a paid order is approved, the existing order approval flow creates/renews
# the VPN user and sends the subscription URL. v17 adds separate Xray/V2Ray
# download buttons in the subscription page, so the bot can safely use the same
# subscription token and does not need to send all raw configs in chat.
def v17_protocol_package_buttons():
    return [
        ('⚡ Xray / V2Ray', 'xray'),
        ('🛡 همه پروتکل‌ها', 'all'),
        ('🔐 کلاسیک بدون Xray', 'classic'),
        ('⚙️ انتخاب دستی', 'custom'),
    ]

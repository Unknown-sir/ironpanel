import io
import logging
import secrets
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from app import create_app
from app.core.extensions import db
from app.core.models import AppSetting, SalesBotCustomer, SalesBotOrder, SalesBotPlan, VpnUser
from app.services.provisioning import get_setting, set_setting, sync_user, user_usage_summary, user_access_status, get_public_host, active_protocols
from app.services.xray import xray_profile_text, xray_profile_meta, write_user_xray_profile, xray_runtime_status, XRAY_PROFILE_TYPES, xray_settings

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('ironpanel-sales-bot')
flask_app = create_app()

PROTOCOL_LABELS = {
    'openvpn': 'OpenVPN',
    'wireguard': 'WireGuard',
    'ocserv': 'Cisco AnyConnect/Ocserv',
    'l2tp': 'L2TP/IPsec',
    'xray': 'Xray / V2Ray',
}
XRAY_ALIASES = ('xray', 'v2ray', 'vless', 'vmess', 'trojan', 'shadowsocks')


def _setting(key, default=''):
    val = get_setting(key, default)
    return val if val not in (None, '') else default


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
    c = SalesBotCustomer.query.filter_by(telegram_id=tg_id).first()
    if not c:
        c = SalesBotCustomer(telegram_id=tg_id, username=tg_user.username or '', first_name=tg_user.first_name or '', language_code=tg_user.language_code or 'fa')
        db.session.add(c)
    else:
        c.username = tg_user.username or c.username
        c.first_name = tg_user.first_name or c.first_name
        c.updated_at = datetime.utcnow()
    db.session.commit()
    return c


def _subscription_url(u):
    host = get_public_host().rstrip('/')
    if not host.startswith(('http://', 'https://')):
        host = 'http://' + host
    return f'{host}/s/{u.subscription_token}'


def _active_default_protocols():
    protos = active_protocols() or ['openvpn', 'wireguard', 'ocserv', 'l2tp', 'xray']
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


def _create_vpn_user_for_order(order):
    plan = SalesBotPlan.query.get(order.plan_id)
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
    plan = SalesBotPlan.query.get(order.plan_id)
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
    u = VpnUser(username=username, l2tp_password=password, cisco_password=password, data_limit_mb=max(0, traffic) * 1024, connection_limit=1, protocols=protocols, protocol_permissions=protocols, expires_at=datetime.utcnow() + timedelta(days=max(1, days)), enabled=True)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    _sync_after_user_change(u)
    c.trial_used = True
    db.session.add(SalesBotOrder(telegram_id=str(tg_user.id), customer_id=c.id, vpn_user_id=u.id, order_type='trial', status='approved', amount=0, currency=_setting('sales_bot_currency', 'IRT'), approved_at=datetime.utcnow(), admin_note='trial auto-created'))
    db.session.commit()
    return u, password


def main_keyboard(is_admin=False):
    rows = [
        [InlineKeyboardButton('🛒 خرید سرویس VPN', callback_data='buy'), InlineKeyboardButton('⚡ خرید کانفیگ Xray/V2Ray', callback_data='buy_xray')],
        [InlineKeyboardButton('🎁 تست رایگان', callback_data='trial'), InlineKeyboardButton('📊 سرویس‌های من', callback_data='my_services')],
        [InlineKeyboardButton('📥 دریافت کانفیگ‌ها', callback_data='configs'), InlineKeyboardButton('♻️ تمدید سرویس', callback_data='renew')],
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
    await update.message.reply_text('به ربات فروش IronPanel خوش آمدید. تمام عملیات با دکمه انجام می‌شود؛ فقط برای نام پلن، قیمت، حجم یا ارسال رسید نیاز به تایپ دارید.', reply_markup=main_keyboard(admin))


async def show_admin(q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('➕ ساخت پلن', callback_data='admin:create_plan'), InlineKeyboardButton('📋 مدیریت پلن‌ها', callback_data='admin:plans')],
        [InlineKeyboardButton('⏳ سفارش‌ها', callback_data='admin:orders'), InlineKeyboardButton('🎁 تنظیم تست', callback_data='admin:trial')],
        [InlineKeyboardButton('⚡ وضعیت Xray/V2Ray', callback_data='admin:xray_status'), InlineKeyboardButton('💳 متن پرداخت دستی', callback_data='admin:payment')],
        [InlineKeyboardButton('📊 آمار', callback_data='admin:stats')],
        [InlineKeyboardButton('⬅️ بازگشت', callback_data='home')],
    ])
    await q.edit_message_text('مدیریت فروش IronPanel:', reply_markup=kb)


async def _show_plans(q, xray_only=False):
    plans = SalesBotPlan.query.filter_by(active=True).order_by(SalesBotPlan.sort_order, SalesBotPlan.id).all()
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
            await q.edit_message_text('منوی اصلی:', reply_markup=main_keyboard(is_admin))
            return
        if data == 'buy':
            await _show_plans(q, xray_only=False)
            return
        if data == 'buy_xray':
            await _show_plans(q, xray_only=True)
            return
        if data.startswith('buy:'):
            p = SalesBotPlan.query.get(int(data.split(':', 1)[1]))
            if not p or not p.active:
                await q.edit_message_text('این پلن فعال نیست.')
                return
            o = SalesBotOrder(telegram_id=str(user.id), customer_id=c.id, plan_id=p.id, amount=p.price, currency=p.currency, order_type='new', status='pending_payment')
            db.session.add(o)
            db.session.commit()
            set_setting(f'sales_bot_pending_order_{user.id}', str(o.id))
            await q.edit_message_text(f'سفارش #{o.id}\n\n{_fmt_plan(p)}\n\n{_setting("sales_bot_payment_text", "لطفاً رسید پرداخت را ارسال کنید.")}\n\nپس از پرداخت، تصویر یا فایل رسید را همین‌جا ارسال کنید.')
            return
        if data == 'trial':
            result, extra = _create_trial(user)
            if not result:
                await q.edit_message_text(extra, reply_markup=InlineKeyboardMarkup([back_button('home')]))
                return
            await q.edit_message_text(f'تست رایگان ساخته شد ✅\nنام کاربری: {result.username}\nرمز سرویس‌ها: {extra}\nلینک سابسکریپشن:\n{_subscription_url(result)}\n\nبرای دریافت فایل Xray/V2Ray از دکمه «دریافت کانفیگ‌ها» استفاده کنید.', reply_markup=InlineKeyboardMarkup([back_button('home')]))
            return
        if data in ('my_services', 'configs', 'renew'):
            orders = SalesBotOrder.query.filter_by(telegram_id=str(user.id), status='approved').filter(SalesBotOrder.vpn_user_id.isnot(None)).order_by(SalesBotOrder.id.desc()).all()
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
            await q.edit_message_text(f'🔗 لینک Subscription برای {u.username}:\n{_subscription_url(u)}', reply_markup=InlineKeyboardMarkup([back_button('configs')]))
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
            plans = SalesBotPlan.query.filter_by(active=True).order_by(SalesBotPlan.sort_order, SalesBotPlan.id).all()
            kb = [[InlineKeyboardButton(f'{p.name} - {_fmt_money(p.price, p.currency)}', callback_data=f'renewplan:{uid}:{p.id}')] for p in plans]
            kb.append(back_button('renew'))
            await q.edit_message_text('پلن تمدید را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(kb))
            return
        if data.startswith('renewplan:'):
            _, uid, pid = data.split(':')
            p = SalesBotPlan.query.get(int(pid))
            u = VpnUser.query.get(int(uid))
            if not p or not u:
                await q.edit_message_text('پلن یا کاربر پیدا نشد')
                return
            o = SalesBotOrder(telegram_id=str(user.id), customer_id=c.id, plan_id=p.id, vpn_user_id=u.id, order_type='renew', status='pending_payment', amount=p.price, currency=p.currency)
            db.session.add(o)
            db.session.commit()
            set_setting(f'sales_bot_pending_order_{user.id}', str(o.id))
            await q.edit_message_text(f'سفارش تمدید #{o.id}\nسرویس: {u.username}\n{_fmt_plan(p)}\n\n{_setting("sales_bot_payment_text", "رسید پرداخت را ارسال کنید.")}')
            return
        if data == 'support':
            await q.edit_message_text(f'پشتیبانی: {_setting("sales_bot_support_url", "https://t.me/unknown_eng")}', reply_markup=InlineKeyboardMarkup([back_button('home')]))
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
            p = SalesBotPlan(name=state['name'], days=int(state['days']), traffic_gb=int(state['traffic_gb']), price=float(state['price']), currency=state.get('currency') or _setting('sales_bot_currency', 'IRT'), protocols=protocols, created_by_telegram_id=str(user.id), active=True)
            db.session.add(p)
            db.session.commit()
            set_setting(f'sales_bot_state_{user.id}', '')
            await q.edit_message_text(f'پلن ساخته شد ✅\nID {p.id}\n{_fmt_plan(p)}', reply_markup=main_keyboard(True))
            return
        if data == 'admin:plans':
            plans = SalesBotPlan.query.order_by(SalesBotPlan.sort_order, SalesBotPlan.id).all()
            rows = []
            txt = 'پلن‌ها:' if plans else 'پلنی ثبت نشده است.'
            for p in plans:
                rows.append([InlineKeyboardButton(f'{"✅" if p.active else "❌"} {p.name} | {_protocol_text(p.protocols)}', callback_data=f'admin:plan:{p.id}')])
            rows.append(back_button('admin'))
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(rows))
            return
        if data.startswith('admin:plan:'):
            p = SalesBotPlan.query.get(int(data.split(':')[2]))
            if not p:
                await q.edit_message_text('پلن پیدا نشد.')
                return
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('فعال/غیرفعال', callback_data=f'admin:toggleplan:{p.id}'), InlineKeyboardButton('حذف', callback_data=f'admin:deleteplan:{p.id}')], [InlineKeyboardButton('⬅️ پلن‌ها', callback_data='admin:plans')]])
            await q.edit_message_text(f'ID {p.id}\n{_fmt_plan(p)}\nوضعیت: {"فعال" if p.active else "غیرفعال"}', reply_markup=kb)
            return
        if data.startswith('admin:toggleplan:'):
            p = SalesBotPlan.query.get(int(data.split(':')[2]))
            p.active = not p.active
            db.session.commit()
            await q.edit_message_text('وضعیت پلن تغییر کرد.', reply_markup=InlineKeyboardMarkup([back_button('admin:plans')]))
            return
        if data.startswith('admin:deleteplan:'):
            p = SalesBotPlan.query.get(int(data.split(':')[2]))
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
        if data == 'admin:orders':
            orders = SalesBotOrder.query.filter(SalesBotOrder.status.in_(['pending_payment', 'receipt_sent'])).order_by(SalesBotOrder.id.desc()).limit(10).all()
            if not orders:
                await q.edit_message_text('سفارش در انتظار وجود ندارد.', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
                return
            lines = []
            rows = []
            for o in orders:
                p = SalesBotPlan.query.get(o.plan_id) if o.plan_id else None
                lines.append(f'#{o.id} | TG:{o.telegram_id} | {p.name if p else "-"} | {_protocol_text(p.protocols if p else "")} | {_fmt_money(o.amount, o.currency)} | {o.status}')
                rows.append([InlineKeyboardButton(f'✅ تأیید #{o.id}', callback_data=f'approve:{o.id}'), InlineKeyboardButton(f'❌ رد #{o.id}', callback_data=f'reject:{o.id}')])
            rows.append(back_button('admin'))
            await q.edit_message_text('\n'.join(lines), reply_markup=InlineKeyboardMarkup(rows))
            return
        if data == 'admin:stats':
            total = SalesBotOrder.query.count()
            approved = SalesBotOrder.query.filter_by(status='approved').count()
            pending = SalesBotOrder.query.filter(SalesBotOrder.status.in_(['pending_payment', 'receipt_sent'])).count()
            xray_plans = SalesBotPlan.query.filter(SalesBotPlan.protocols.like('%xray%')).count()
            await q.edit_message_text(f'آمار فروش:\nکل سفارش‌ها: {total}\nتأیید شده: {approved}\nدر انتظار: {pending}\nپلن‌های Xray/V2Ray: {xray_plans}', reply_markup=InlineKeyboardMarkup([back_button('admin')]))
            return
        if data.startswith('approve:') or data.startswith('reject:'):
            oid = int(data.split(':', 1)[1])
            o = SalesBotOrder.query.get(oid)
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
                p = SalesBotPlan(name=state['name'], days=int(state['days']), traffic_gb=int(state['traffic_gb']), price=float(state['price']), currency=state.get('currency') or _setting('sales_bot_currency', 'IRT'), protocols=protocols, created_by_telegram_id=str(user.id), active=True)
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
        row = AppSetting.query.filter_by(key=f'sales_bot_pending_order_{user.id}').first()
        if not row or not row.value:
            return
        o = SalesBotOrder.query.get(int(row.value))
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
        plan = SalesBotPlan.query.get(o.plan_id) if o.plan_id else None
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

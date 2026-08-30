"""v2.0.0: Dargahno payment gateway pages (main admin) and reseller volume/bot flows."""
import json
import math

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import (
    Admin,
    GatewayPayment,
    SalesBotOrder,
    SalesBotPlan,
)
from ..services import dargahno
from ..services.provisioning import get_public_host, log, set_reseller_enabled
from . import web_bp
from .bots import _sales_bot_restart, _set_sales_bot_setting, _get_sales_bot_settings
from .common import _panel_base_url, _reseller_stats

_GATEWAY_PAGE = 'gateway.html'
_STORAGE_PAGE = 'reseller_storage.html'
_BOT_PAGE = 'reseller_bot.html'
_SUCCESS_PAGE = 'payment_success.html'
_FAILED_PAGE = 'payment_failed.html'


def _gateway_public_base():
    host = get_public_host() or ''
    if str(host).startswith(('http://', 'https://')):
        return str(host).rstrip('/')
    return _panel_base_url()


def _credit_gateway_payment(payment):
    """Apply a verified payment: add the purchased GB to the reseller's quota and
    re-enable the panel in case it was auto-disabled after volume exhaustion."""
    payment.status = 'success'
    reseller = Admin.query.get(payment.reseller_id) if payment.reseller_id else None
    if reseller:
        quota = int(getattr(reseller, 'traffic_quota_gb', 0) or 0)
        if quota > 0:
            reseller.traffic_quota_gb = quota + payment.gb_amount
            try:
                set_reseller_enabled(reseller, True, source='dargahno')
            except Exception:
                pass
            log(reseller.username, 'dargahno_payment', str(payment.factor_number),
                f'credited +{payment.gb_amount}GB (quota {quota} -> {reseller.traffic_quota_gb})')
    db.session.commit()


@web_bp.route('/gateway', methods=['GET', 'POST'])
@login_required
def gateway_panel():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    settings = dargahno.gateway_settings()
    if request.method == 'POST':
        action = request.form.get('action', 'settings')
        if action == 'settings':
            errors = dargahno.save_gateway_settings(request.form or {})
            if errors:
                for e in errors:
                    flash(e)
            else:
                flash('تنظیمات درگاه پرداخت ذخیره شد.')
                log(current_user.username, 'dargahno_settings', 'gateway', 'saved')
            return redirect(url_for('web.gateway_panel'))
        if action == 'test':
            result = dargahno.test_connection()
            if result.get('ok'):
                flash(f"اتصال درگاه موفق بود. Merchant ID فعال: {result.get('merchant_id') or '-'}")
                log(current_user.username, 'dargahno_test', 'gateway', 'ok')
            else:
                flash(result.get('message') or 'تست اتصال ناموفق بود.')
                log(current_user.username, 'dargahno_test', 'gateway', 'fail')
            return redirect(url_for('web.gateway_panel'))
    history = dargahno.payment_history(limit=50)
    return render_template(
        _GATEWAY_PAGE,
        settings=settings,
        gateway_configured=dargahno.gateway_configured(),
        price_per_gb=dargahno.price_per_gb(),
        min_purchase=dargahno.min_purchase(),
        history=history,
    )


@web_bp.route('/reseller/storage', methods=['GET', 'POST'])
@login_required
def reseller_storage():
    if current_user.role != 'sub_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        return _reseller_storage_buy()
    stats = _reseller_stats(current_user)
    recent = dargahno.payment_history(reseller_id=current_user.id)
    return render_template(
        _STORAGE_PAGE,
        stats=stats,
        recent=recent,
        gateway_ready=dargahno.gateway_configured(),
        price_per_gb=dargahno.price_per_gb(),
        min_purchase=dargahno.min_purchase(),
    )


def _reseller_storage_buy():
    if not dargahno.gateway_configured():
        flash('درگاه پرداخت هنوز در پنل اصلی فعال نشده است.')
        return redirect(url_for('web.reseller_storage'))
    try:
        gb = int(float(request.form.get('gb_amount') or 0))
    except Exception:
        gb = 0
    if gb <= 0:
        flash('مقدار حجم باید یک عدد بزرگ‌تر از صفر باشد.')
        return redirect(url_for('web.reseller_storage'))
    reseller = Admin.query.get(current_user.id)
    quota = int(getattr(reseller, 'traffic_quota_gb', 0) or 0)
    if quota == 0:
        flash('سقف حجم پنل شما نامحدود است و نیازی به خرید حجم ندارد.')
        return redirect(url_for('web.reseller_storage'))
    price = dargahno.price_for_gb(gb)
    minimum = dargahno.min_purchase()
    if minimum and price < minimum:
        flash(f'حداقل مبلغ قابل پرداخت {minimum:,} ریال است. برای رسیدن به آن حداقل {math.ceil(minimum / dargahno.price_per_gb())} گیگ درخواست بده.')
        return redirect(url_for('web.reseller_storage'))
    factor = dargahno.next_factor_number()
    payment = GatewayPayment(
        provider='dargahno',
        reseller_id=current_user.id,
        gb_amount=gb,
        amount=float(price),
        currency='IRT',
        factor_number=factor,
        status='pending',
    )
    db.session.add(payment)
    db.session.commit()
    callback = f'{_gateway_public_base()}/payment/dargahno/callback/{factor}'
    result = dargahno.register_transaction(
        factor_number=factor,
        price=price,
        callback_url=callback,
        description=f'IronPanel volume top-up {gb}GB',
    )
    if not result.get('ok'):
        payment.status = 'failed'
        payment.error = (result.get('message') or '')[:400]
        db.session.commit()
        log(current_user.username, 'dargahno_register', str(factor), payment.error)
        flash(payment.error or 'ثبت تراکنش در درگاه ناموفق بود. مبلغی از حساب شما کسر نمی شود.')
        return redirect(url_for('web.reseller_storage'))
    payment.authority = result.get('authority', '')
    if result.get('data'):
        payment.raw_response = json.dumps(result['data'], ensure_ascii=False, default=str)[:2000]
    db.session.commit()
    log(current_user.username, 'dargahno_charge', str(factor), f'{gb}GB -> {price} Rial')
    return redirect(result.get('pay_url', '/reseller/storage'))


@web_bp.route('/payment/dargahno/callback/<int:factor_number>', methods=['GET'])
def dargahno_callback(factor_number):
    payment = GatewayPayment.query.filter_by(factor_number=factor_number).first()
    if not payment:
        return render_template(_FAILED_PAGE, title='فاکتور پیدا نشد',
                               message='فاکتور مورد نظر در سیستم ثبت نشده یا قابل شناسایی نیست.',
                               reference=factor_number, pending=False)
    if payment.status == 'success':
        return render_template(_SUCCESS_PAGE, pay=payment,
                               reseller_username=_reseller_username(payment))
    check = dargahno.check_transaction(payment.authority, expected_price=int(payment.amount or 0))
    if check.get('raw'):
        payment.raw_response = check['raw'][:3000]
    if not check.get('ok'):
        payment.error = (check.get('message') or '')[:400]
        db.session.commit()
        return render_template(_FAILED_PAGE, pay=payment, reference=payment.factor_number,
                               amount=int(payment.amount or 0), pending=True,
                               title='وضعیت پرداخت هنوز قطعی نیست',
                               message=check.get('message') or 'تراکنش با خطای موقت مواجه شد؛ در صورت کسر مبلغ با پشتیبانی تماس بگیرید.',
                               support_id=dargahno.support_id(),
                               reseller_username=_reseller_username(payment))
    if check.get('success'):
        if payment.status != 'success':
            _credit_gateway_payment(payment)
        return render_template(_SUCCESS_PAGE, pay=payment,
                               reseller_username=_reseller_username(payment))
    payment.status = 'failed'
    payment.error = 'پرداخت توسط کاربر تأیید نشد یا از سمت درگاه لغو شد.'
    db.session.commit()
    return render_template(_FAILED_PAGE, pay=payment, reference=payment.factor_number,
                           amount=int(payment.amount or 0), pending=False,
                           message='پرداخت توسط شما تأیید یا تکمیل نشد؛ در نتیجه حجم خریداری‌شده به پنل اضافه نشد.',
                           support_id=dargahno.support_id(),
                           reseller_username=_reseller_username(payment))


def _reseller_username(payment):
    if not payment or not payment.reseller_id:
        return None
    a = Admin.query.get(payment.reseller_id)
    return a.username if a else None


# ---------------- Reseller sales bot connection ----------------
@web_bp.route('/reseller/bot', methods=['GET', 'POST'])
@login_required
def reseller_bot():
    if current_user.role != 'sub_admin':
        return redirect(url_for('web.dashboard'))
    owner_id = current_user.id
    if request.method == 'POST':
        _set_sales_bot_setting('sales_bot_enabled', '1' if request.form.get('sales_bot_enabled') else '0', owner_id)
        _set_sales_bot_setting('sales_bot_token', (request.form.get('sales_bot_token') or '').strip(), owner_id)
        db.session.commit()
        _sales_bot_restart(owner_id)
        log(current_user.username, 'reseller_bot_connect', 'owner', str(owner_id))
        flash('تنظیمات ربات فروش ذخیره شد و سرویس ربات sync شد.')
        return redirect(url_for('web.reseller_bot'))
    settings = _get_sales_bot_settings(owner_id)
    stats = _reseller_stats(current_user)
    try:
        plans_count = SalesBotPlan.query.filter_by(owner_id=owner_id).count()
    except Exception:
        plans_count = SalesBotPlan.query.count()
    try:
        orders_count = SalesBotOrder.query.filter_by(owner_id=owner_id).count()
    except Exception:
        orders_count = SalesBotOrder.query.count()
    return render_template(_BOT_PAGE, settings=settings, stats=stats,
                           plans=range(plans_count), orders=orders_count,
                           support_id=dargahno.support_id())
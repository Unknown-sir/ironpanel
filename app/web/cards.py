"""v2.0.3/v2.0.4: manual card-to-card volume recharge (admin settings + approval,
reseller charge flow) and reseller external sales-bot API credentials. No payment
gateway and no built-in sales bot for resellers — bots connect through one of the
four API families (v1, v2, MirzaBot, 3x-ui)."""
import math
import os
import secrets
from pathlib import Path

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..core.extensions import db
from ..core.models import (
    Admin,
    ApiToken,
    ChargeRequest,
)
from ..services import cards
from ..services.provisioning import log, reconcile_reseller_access
from . import web_bp
from .common import _reseller_stats

_ADMIN_PAGE = 'cards.html'
_CHARGE_PAGE = 'reseller_storage.html'
_BOT_PAGE = 'reseller_bot.html'

_ALLOWED_RECEIPT_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def _receipt_dir() -> Path:
    base = current_app.config.get('CONFIG_ROOT') or os.environ.get('IRONPANEL_CONFIG_ROOT', '/etc/ironpanel')
    folder = Path(base) / 'receipts'
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return folder


def _credit_charge(charge):
    """Approve a charge: add the requested GB to the reseller quota and let the
    reseller access reconcile (auto-restores children disabled by quota)."""
    charge.status = 'approved'
    reseller = Admin.query.get(charge.reseller_id) if charge.reseller_id else None
    if reseller:
        quota = int(getattr(reseller, 'traffic_quota_gb', 0) or 0)
        if quota > 0:
            reseller.traffic_quota_gb = quota + charge.gb_amount
            try:
                reconcile_reseller_access(reseller, source='admin')
            except Exception:
                pass
            log(reseller.username, 'charge_approved', str(charge.factor_number),
                f'credited +{charge.gb_amount}GB (quota {quota} -> {reseller.traffic_quota_gb})')
    db.session.commit()


@web_bp.route('/cards', methods=['GET', 'POST'])
@login_required
def cards_panel():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'settings')
        if action == 'settings':
            errors = cards.save_card_settings(request.form or {})
            for e in errors:
                flash(e)
            if not errors:
                flash('تنظیمات شارژ کارت به کارت ذخیره شد.')
                log(current_user.username, 'card_settings', 'cards', 'saved')
            return redirect(url_for('web.cards_panel'))
        if action == 'approve':
            charge_id = request.form.get('charge_id', type=int)
            charge = ChargeRequest.query.get(charge_id or 0)
            if charge and charge.status == 'pending':
                _credit_charge(charge)
                reseller = Admin.query.get(charge.reseller_id) if charge.reseller_id else None
                flash(f"شارژ {charge.gb_amount:g}GB برای نماینده «{reseller.username if reseller else '-'}» تأیید و به حجم اضافه شد.")
                log(current_user.username, 'card_approve', str(charge.factor_number), f'+{charge.gb_amount}GB')
            else:
                flash('درخواست شارژ یافت نشد یا قبلاً تأیید/رد شده است.')
            return redirect(url_for('web.cards_panel'))
        if action == 'reject':
            charge_id = request.form.get('charge_id', type=int)
            charge = ChargeRequest.query.get(charge_id or 0)
            if charge and charge.status == 'pending':
                charge.status = 'rejected'
                charge.note = ((request.form.get('note') or '').strip() or 'رد شده توسط مدیر')[:400]
                db.session.commit()
                flash('درخواست شارژ رد شد و حجمی اضافه نشد.')
                log(current_user.username, 'card_reject', str(charge.factor_number), charge.note)
            else:
                flash('درخواست شارژ یافت نشد یا قبلاً تأیید/رد شده است.')
            return redirect(url_for('web.cards_panel'))
    settings = cards.card_settings()
    history = [c for c in cards.charge_history(limit=50) if c.status == 'pending']
    return render_template(
        _ADMIN_PAGE,
        settings=settings,
        card_active=cards.card_active(),
        price_per_gb=cards.price_per_gb(),
        min_purchase=cards.min_purchase(),
        history=history,
        pending_count=cards.pending_count(),
    )


@web_bp.route('/gateway')
@login_required
def gateway_legacy():
    return redirect(url_for('web.cards_panel'))


@web_bp.route('/payment/receipt/<int:charge_id>')
@login_required
def charge_receipt(charge_id):
    charge = ChargeRequest.query.get(charge_id)
    if not charge or not charge.receipt_file:
        abort(404)
    owner = Admin.query.get(charge.reseller_id) if charge.reseller_id else None
    if current_user.role != 'main_admin' and not (owner and current_user.id == owner.id):
        abort(403)
    return send_from_directory(_receipt_dir(), charge.receipt_file)


# ---------------- Reseller charge (recharge) flow ----------------
@web_bp.route('/reseller/storage', methods=['GET', 'POST'])
@login_required
def reseller_storage():
    if current_user.role != 'sub_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        return _reseller_charge_submit()
    stats = _reseller_stats(current_user)
    recent = cards.charge_history(reseller_id=current_user.id)
    return render_template(
        _CHARGE_PAGE,
        stats=stats,
        recent=recent,
        card_active=cards.card_active(),
        instructions=cards.payment_instructions(),
        price_per_gb=cards.price_per_gb(),
        min_purchase=cards.min_purchase(),
        volume_gated=(not bool(getattr(current_user, 'enabled', True))
                      and str(getattr(current_user, 'disabled_reason', '') or '') == 'traffic_quota'),
    )


def _reseller_charge_submit():
    if current_user.role != 'sub_admin':
        return redirect(url_for('web.dashboard'))
    if not cards.card_active():
        flash('شارژ کارت به کارت هنوز در پنل اصلی فعال نشده است.')
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
    price = cards.price_for_gb(gb)
    minimum = cards.min_purchase()
    if minimum and price < minimum:
        flash(f'حداقل مبلغ قابل پرداخت {minimum:,} ریال است. برای رسیدن به آن حداقل {math.ceil(minimum / cards.price_per_gb())} گیگ درخواست بده.')
        return redirect(url_for('web.reseller_storage'))
    receipt = request.files.get('receipt')
    if not receipt or not receipt.filename:
        flash('تصویر رسید واریز را بارگذاری کن تا درخواست ثبت شود.')
        return redirect(url_for('web.reseller_storage'))
    filename = secure_filename(receipt.filename or '')
    ext = Path(filename or '').suffix.lower()
    if ext not in _ALLOWED_RECEIPT_EXT:
        flash('فرمت تصویر رسید معتبر نیست (jpg, jpeg, png, webp یا gif).')
        return redirect(url_for('web.reseller_storage'))
    receipt.stream.seek(0, 2)
    size = receipt.stream.tell()
    receipt.stream.seek(0)
    if size > _MAX_RECEIPT_BYTES:
        flash('حجم تصویر رسید نباید بیشتر از ۸ مگابایت باشد.')
        return redirect(url_for('web.reseller_storage'))
    factor = cards.next_factor_number()
    charge = ChargeRequest(
        reseller_id=current_user.id,
        gb_amount=gb,
        amount=float(price),
        currency='IRT',
        factor_number=factor,
        status='pending',
    )
    db.session.add(charge)
    db.session.commit()
    stored_name = f'cr{charge.id}_{charge.factor_number}{ext}'
    try:
        receipt.save(str(_receipt_dir() / stored_name))
        charge.receipt_file = stored_name
    except Exception as exc:
        charge.status = 'rejected'
        charge.note = 'بارگذاری رسید ناموفق بود'
        log(current_user.username, 'charge_receipt_error', str(factor), str(exc)[:300])
    db.session.commit()
    log(current_user.username, 'charge_request', str(factor), f'{gb}GB -> {price} Rial')
    flash(f"درخواست شارژ {gb}GB با مبلغ تقریبی {price:,} ریال ثبت شد؛ پس از بررسی رسید، مدیر اصلی آن را تأیید می‌کند.")
    return redirect(url_for('web.reseller_storage'))


# ---------------- Reseller external sales-bot API credentials ----------------
# The panel's built-in sales bot is NOT used for resellers. Instead every reseller
# owns four API credentials (v1 / v2 / MirzaBot / 3x-ui-style) that an external
# bot connects to for creating users, reading them, sending the subscription or
# deleting users. Credentials never expire but can be rotated (regenerated).

_API_TYPE_INFO = {
    'v1': {'label_fa': 'نسخه ۱ (کلاسیک)', 'endpoint_suffix': '/api/v1',
           'usage': 'X-API-KEY', 'note_fa': 'برای اسکریپت\u200cها و ربات\u200cهای قدیمی'},
    'v2': {'label_fa': 'نسخه ۲ (توکن)', 'endpoint_suffix': '/api/v2',
           'usage': 'Authorization: Bearer', 'note_fa': 'برای ربات\u200cهایی که با توکن کار می\u200cکنند'},
    'mirzabot': {'label_fa': 'میرزا بات', 'endpoint_suffix': '/api/mirzabot/v1',
                 'usage': 'X-API-Key', 'note_fa': 'برای ربات میرزا بات'},
    'xui': {'label_fa': '3x-ui (نسخه جدید)', 'endpoint_suffix': '/api/xui',
            'usage': 'X-API-KEY  یا  POST /api/xui/login', 'note_fa': 'سازگار با API پنل 3x-ui', 'is_new': True},
}


def _reseller_token_row(reseller, api_type):
    return ApiToken.query.filter_by(owner_id=reseller.id, api_type=api_type).first()


def _reseller_credential(reseller, api_type, rotate=False):
    """Return the credential secret for an owner, creating/rotating as needed."""
    if api_type == 'v1':
        key = str(getattr(reseller, 'api_key', '') or '').strip()
        if rotate or not key:
            reseller.api_key = secrets.token_urlsafe(48)
            db.session.commit()
        return reseller.api_key
    tok = _reseller_token_row(reseller, api_type)
    if rotate or not tok:
        if not tok:
            tok = ApiToken(name=f'{api_type}-{reseller.username}', owner_id=reseller.id,
                           api_type=api_type, scopes='users:read,users:write', enabled=True)
            db.session.add(tok)
        tok.token = secrets.token_urlsafe(48)
        db.session.commit()
    return tok.token


def _reseller_api_creds(reseller):
    creds = {}
    for api_type, info in _API_TYPE_INFO.items():
        key = _reseller_credential(reseller, api_type, rotate=False)
        tok = _reseller_token_row(reseller, api_type) if api_type != 'v1' else None
        creds[api_type] = {
            'key': key,
            'label_fa': info['label_fa'],
            'endpoint': f"{request.url_root.rstrip('/')}{info['endpoint_suffix']}",
            'usage': info['usage'],
            'note_fa': info['note_fa'],
            'is_new': bool(info.get('is_new')),
            'enabled': bool(tok.enabled) if tok else True,
        }
    return creds


@web_bp.route('/reseller/bot', methods=['GET', 'POST'])
@login_required
def reseller_bot():
    if current_user.role != 'sub_admin':
        return redirect(url_for('web.dashboard'))
    reseller = Admin.query.get(current_user.id)
    stats = _reseller_stats(current_user)
    rotated = ''
    if request.method == 'POST':
        api_type = request.form.get('api_type') or ''
        if api_type in _API_TYPE_INFO:
            _reseller_credential(reseller, api_type, rotate=True)
            log(current_user.username, 'reseller_api_rotate', api_type, 'rotated')
            rotated = api_type
        elif request.form.get('action') == 'enable-toggle':
            api_type = request.form.get('api_type2') or ''
            tok = _reseller_token_row(reseller, api_type) if api_type else None
            if tok:
                tok.enabled = not tok.enabled
                db.session.commit()
                rotated = api_type
    support = cards.card_settings().get('card_support') or ''
    creds = _reseller_api_creds(reseller)
    return render_template(_BOT_PAGE, stats=stats, creds=creds, rotated=rotated,
                           support_id=support,
                           volume_gated=(not bool(getattr(current_user, 'enabled', True))
                                         and str(getattr(current_user, 'disabled_reason', '') or '') == 'traffic_quota'))
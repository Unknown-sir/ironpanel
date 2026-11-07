# v2.0.3: manual card-to-card (کارت به کارت) volume recharge for resellers.
# There is no payment gateway here. The main admin stores the card number,
# account holder and a payment instructions text; a reseller enters the GB they
# want, sees the estimated amount (GB x price-per-GB), transfers the money, and
# uploads the receipt as a ChargeRequest. The main admin approves it manually
# and the purchased volume is added to the reseller's quota.
from ..core.extensions import db
from ..core.models import Admin, ChargeRequest
from .provisioning import get_setting, set_setting

CARD_SETTING_KEYS = [
    'card_charge_enabled',
    'card_price_per_gb',
    'card_min_purchase',
    'card_number',
    'card_holder',
    'card_payment_text',
    'card_support',
]

DEFAULT_CARD_VALUES = {
    'card_charge_enabled': '0',
    'card_price_per_gb': '20000',
    'card_min_purchase': '50000',
    'card_number': '',
    'card_holder': '',
    'card_payment_text': 'کارت به کارت به شماره کارت اعلام‌شده واریز کنید و پس از پرداخت، تصویر رسید را در فرم «درخواست شارژ» بارگذاری کنید.',
    'card_support': '',
}


def _ensure_database_schema() -> None:
    try:
        db.create_all()
    except Exception:
        pass


def card_settings() -> dict:
    _ensure_database_schema()
    out = {}
    for key in CARD_SETTING_KEYS:
        out[key] = get_setting(key, DEFAULT_CARD_VALUES.get(key, ''))
    return out


def card_active() -> bool:
    """Card recharge is on and a target card number is configured."""
    s = card_settings()
    return bool(s.get('card_charge_enabled') == '1' and (s.get('card_number') or '').strip())


def price_per_gb() -> int:
    try:
        return max(0, int(float(card_settings().get('card_price_per_gb') or 0)))
    except Exception:
        return 0


def min_purchase() -> int:
    try:
        return max(0, int(float(card_settings().get('card_min_purchase') or 0)))
    except Exception:
        return 0


def price_for_gb(gb: float) -> int:
    """Estimated price in Rial for a requested GB amount."""
    return int(round(max(0.0, float(gb or 0)) * price_per_gb()))


def payment_instructions() -> dict:
    s = card_settings()
    return {
        'card_number': (s.get('card_number') or '').strip(),
        'card_holder': (s.get('card_holder') or '').strip(),
        'payment_text': (s.get('card_payment_text') or '').strip(),
        'support': (s.get('card_support') or '').strip(),
    }


def save_card_settings(form: dict) -> list:
    """Persist card recharge settings from a form. Returns a list of error messages."""
    errors = []
    number = (form.get('card_number') or '').strip()
    holder = (form.get('card_holder') or '').strip()
    enabled = True if form.get('card_charge_enabled') else False
    try:
        price = int(float(form.get('card_price_per_gb') or 0))
        if price <= 0:
            errors.append('قیمت هر گیگ باید بزرگ‌تر از صفر باشد.')
    except Exception:
        errors.append('قیمت هر گیگ معتبر نیست.')
        price = 0
    try:
        minimum = int(float(form.get('card_min_purchase') or 0))
        if minimum < 0:
            errors.append('حداقل مبلغ خرید معتبر نیست.')
            minimum = 0
    except Exception:
        errors.append('حداقل مبلغ خرید معتبر نیست.')
        minimum = 0
    if enabled and not number:
        errors.append('شماره کارت برای دریافت وجه (کارت به کارت) الزامی است.')
    if errors:
        return errors
    set_setting('card_charge_enabled', '1' if enabled else '0')
    set_setting('card_price_per_gb', str(price))
    set_setting('card_min_purchase', str(minimum))
    set_setting('card_number', number)
    set_setting('card_holder', holder)
    set_setting('card_payment_text', ((form.get('card_payment_text') or '').strip() or DEFAULT_CARD_VALUES['card_payment_text']))
    set_setting('card_support', (form.get('card_support') or '').strip())
    db.session.commit()
    return []


def next_factor_number() -> int:
    _ensure_database_schema()
    top = ChargeRequest.query.with_entities(ChargeRequest.factor_number).order_by(ChargeRequest.factor_number.desc()).first()
    base = (top[0] if top else 0)
    return int(base or 1000) + 1


def charge_history(reseller_id=None, limit=50):
    """Recent charge requests, newest first. reseller_id=None returns everyone."""
    _ensure_database_schema()
    q = ChargeRequest.query
    if reseller_id is not None:
        q = q.filter_by(reseller_id=reseller_id)
    q = q.order_by(ChargeRequest.id.desc())
    if limit > 0:
        q = q.limit(limit)
    return q.all()


def pending_count() -> int:
    _ensure_database_schema()
    return int(ChargeRequest.query.filter_by(status='pending').count() or 0)
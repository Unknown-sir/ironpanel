# v2.0.0: Dargahno (درگاه نو) online payment gateway integration.
# Lets the main admin configure a gateway and lets resellers (sub_admin) buy
# extra traffic volume by paying through the gateway. Success/failure callbacks
# are verified server-side with /api/v2/transaction/check before any volume is
# credited (never trust the callback status parameter alone).
import json
import time
import requests

from ..core.extensions import db
from ..core.models import Admin, AppSetting, GatewayPayment
from .provisioning import get_setting, set_setting

API_BASE = 'https://dargahno.net'
PAY_BASE = 'https://pay.dargahno.net'

SETTING_KEYS = [
    'dargahno_enabled',
    'dargahno_username',
    'dargahno_password',
    'dargahno_merchant_id',
    'dargahno_price_per_gb',
    'dargahno_min_purchase',
    'dargahno_support_id',
]

DEFAULT_VALUES = {
    'dargahno_enabled': '0',
    'dargahno_username': '',
    'dargahno_password': '',
    'dargahno_merchant_id': '',
    'dargahno_price_per_gb': '20000',
    'dargahno_min_purchase': '50000',
    'dargahno_support_id': '',
}

TOKEN_KEY = 'dargahno_access_token'
REFRESH_KEY = 'dargahno_refresh_token'
EXPIRE_KEY = 'dargahno_token_expire_ts'


def _ensure_database_schema() -> None:
    try:
        db.create_all()
    except Exception:
        pass


def gateway_settings() -> dict:
    _ensure_database_schema()
    out = {}
    for key in SETTING_KEYS:
        out[key] = get_setting(key, DEFAULT_VALUES.get(key, ''))
    out['dargahno_password'] = get_setting('dargahno_password', '')
    return out


def gateway_configured() -> bool:
    s = gateway_settings()
    return bool(s.get('dargahno_enabled') == '1'
                and s.get('dargahno_merchant_id')
                and s.get('dargahno_username')
                and s.get('dargahno_password'))


def price_per_gb() -> int:
    try:
        return max(0, int(float(gateway_settings().get('dargahno_price_per_gb') or 0)))
    except Exception:
        return 0


def min_purchase() -> int:
    try:
        return max(0, int(float(gateway_settings().get('dargahno_min_purchase') or 0)))
    except Exception:
        return 0


def support_id():
    return gateway_settings().get('dargahno_support_id', '') or ''


def price_for_gb(gb: float) -> int:
    """Return the gateway price in Rial for a given GB amount."""
    return int(round(max(0.0, float(gb or 0)) * price_per_gb()))


def next_factor_number() -> int:
    _ensure_database_schema()
    top = GatewayPayment.query.with_entities(GatewayPayment.factor_number).order_by(GatewayPayment.factor_number.desc()).first()
    base = (top[0] if top else 0)
    return int(base or 1000) + 1


def pay_url_for_authority(authority: str, forwarder_link: str = '') -> str:
    if forwarder_link:
        return forwarder_link
    return f'{PAY_BASE}/?authority={authority}'


def save_gateway_settings(form: dict) -> list:
    """Persist gateway settings from a form/request.form. Returns list of error messages."""
    errors = []
    s = gateway_settings()
    password = (form.get('dargahno_password') or '').strip()
    if not password:
        password = s.get('dargahno_password', '')
    merchant = (form.get('dargahno_merchant_id') or '').strip()
    username = (form.get('dargahno_username') or '').strip()
    if not merchant:
        errors.append('شناسه درگاه (Merchant ID) الزامی است.')
    if not username:
        errors.append('نام کاربری درگاه الزامی است.')
    if not password:
        errors.append('رمز عبور درگاه الزامی است.')
    try:
        price = int(float(form.get('dargahno_price_per_gb') or 0))
        if price <= 0:
            errors.append('قیمت هر گیگ باید بزرگ‌تر از صفر باشد.')
    except Exception:
        errors.append('قیمت هر گیگ معتبر نیست.')
        price = 0
    try:
        minimum = int(float(form.get('dargahno_min_purchase') or 0))
        if minimum < 0:
            errors.append('حداقل مبلغ خرید معتبر نیست.')
            minimum = 0
    except Exception:
        errors.append('حداقل مبلغ خرید معتبر نیست.')
        minimum = 0
    if errors:
        return errors
    set_setting('dargahno_enabled', '1' if form.get('dargahno_enabled') else '0')
    set_setting('dargahno_username', username)
    if password:
        set_setting('dargahno_password', password)
    set_setting('dargahno_merchant_id', merchant)
    set_setting('dargahno_price_per_gb', str(price))
    set_setting('dargahno_min_purchase', str(minimum))
    set_setting('dargahno_support_id', (form.get('dargahno_support_id') or '').strip())
    # Credentials/token may have changed; reset the cached token.
    clear_cached_token()
    db.session.commit()
    return []


def clear_cached_token() -> None:
    set_setting(TOKEN_KEY, '')
    set_setting(REFRESH_KEY, '')
    set_setting(EXPIRE_KEY, '0')


def _login() -> tuple:
    """Authenticate with Dargahno and cache the token pair.

    Returns (token_dict, error_message). token_dict contains access_token,
    refresh_token and expire_time seconds when successful.
    """
    s = gateway_settings()
    username = s.get('dargahno_username', '')
    password = s.get('dargahno_password', '')
    if not username or not password:
        return None, 'نام کاربری یا رمز درگاه نهایی نشده است.'
    # v3 form login (OAuth2 password flow) documented in the OpenAPI spec.
    payload = {'grant_type': 'password', 'username': username, 'password': password, 'scope': ''}
    try:
        resp = requests.post(
            f'{API_BASE}/api/v3/auth/login',
            data=payload,
            headers={'Accept': 'application/json'},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, f'ارتباط با درگاه برقرار نشد: {exc}'
    try:
        data = resp.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return None, 'پاسخ درگاه قابل خواندن نیست.'
    access = data.get('access_token')
    if not access:
        detail = data.get('detail') or data.get('message') or data.get('error') or ''
        if isinstance(detail, (list, dict)):
            detail = json.dumps(detail, ensure_ascii=False)
        return None, f'ورود به درگاه ناموفق بود (HTTP {resp.status_code}). {detail}'.strip()
    expire = 0
    try:
        expire = max(0, int(float(data.get('expire_time') or 0)))
    except Exception:
        expire = 0
    refresh = data.get('refresh_token') or ''
    user_info = data.get('user_info') or {}
    if isinstance(user_info, dict) and user_info.get('merchent_id'):
        current = get_setting('dargahno_merchant_id', '')
        if current != str(user_info['merchent_id']):
            set_setting('dargahno_merchant_id', str(user_info['merchent_id']))
            db.session.commit()
    set_setting(TOKEN_KEY, access)
    if refresh:
        set_setting(REFRESH_KEY, refresh)
    set_setting(EXPIRE_KEY, str(time.time() + expire))
    db.session.commit()
    return {'access_token': access, 'refresh_token': refresh, 'expire_time': expire, 'user_info': user_info}, None


def _access_token() -> str:
    token = get_setting(TOKEN_KEY, '')
    if not token:
        return ''
    try:
        expire_ts = float(get_setting(EXPIRE_KEY, '0') or 0)
    except Exception:
        expire_ts = 0
    if expire_ts and time.time() < expire_ts:
        return token
    _, err = _login()
    if err:
        return ''
    return get_setting(TOKEN_KEY, '') or ''


def _auth_headers() -> dict:
    return {'Accept': 'application/json', 'Authorization': f'Bearer {_access_token()}'}


def test_connection() -> dict:
    """Login against the live gateway and report the authenticated merchant."""
    token, err = _login()
    if not token:
        return {'ok': False, 'message': err or 'اتصال به درگاه ناموفق بود.'}
    merchant = get_setting('dargahno_merchant_id', '')
    return {'ok': True, 'message': 'ورود به درگاه موفق بود.', 'merchant_id': merchant}


def register_transaction(*, factor_number: int, price: int, callback_url: str = '', description: str = '') -> dict:
    """Register a new transaction on Dargahno and return the payment URL.

    Returns {'ok': True, 'authority': ..., 'pay_url': ...} or an error dict.
    Price is in Rial (integer).
    """
    merchant = get_setting('dargahno_merchant_id', '')
    if not merchant:
        return {'ok': False, 'message': 'شناسه درگاه (Merchant ID) تنظیم نشده است.'}
    if merchant == '0':
        return {'ok': False, 'message': 'شناسه درگاه (Merchant ID) معتبر نیست.'}
    body = {
        'merchent_id': merchant,  # field spelling comes straight from Dargahno's API
        'factor_number': int(factor_number),
        'price': int(price),
        'callback_url': callback_url or '',
        'category': 'Forwarder',
    }
    if description:
        body['description'] = description[:500]
    token = _access_token()
    if not token:
        _, err = _login()
        if err:
            return {'ok': False, 'message': err}
        token = _access_token()
        if not token:
            return {'ok': False, 'message': 'دریافت توکن درگاه ناموفق بود.'}
    try:
        resp = requests.post(
            f'{API_BASE}/api/v2/transaction/register',
            json=body,
            headers=_auth_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        return {'ok': False, 'message': f'ارتباط با درگاه برقرار نشد: {exc}'}
    try:
        data = resp.json()
    except Exception:
        data = {}
    if not isinstance(data, dict) or resp.status_code >= 400:
        detail = data.get('detail') or data.get('message') or data.get('error') or ''
        if isinstance(detail, (list, dict)):
            detail = json.dumps(detail, ensure_ascii=False)
        if resp.status_code == 401:
            clear_cached_token()
        return {'ok': False, 'message': f'ثبت تراکنش ناموفق بود (HTTP {resp.status_code}). {str(detail)[:300]}'.strip()}
    authority = data.get('authority')
    if not authority:
        return {'ok': False, 'message': 'در پاسخ درگاه، کد Authority وجود ندارد.'}
    forwarder = data.get('forwarder_link') or ''
    zarin = data.get('zarin_link') or ''
    return {
        'ok': True,
        'authority': authority,
        'forwarder_link': forwarder,
        'pay_url': pay_url_for_authority(authority, forwarder or zarin),
        'data': data,
    }


def check_transaction(authority: str, expected_price: int = None) -> dict:
    """Verify a transaction server-side. The shared schema is undefined in the
    OpenAPI spec, so the result parser is deliberately tolerant.

    Returns {'ok': True, 'success': True, 'data': ...} when the transaction is
    confirmed paid. On errors or an unpaid result ok stays True and success is False.
    """
    if not authority:
        return {'ok': False, 'success': False, 'message': 'کد Authority ندارد.'}
    token = _access_token()
    if not token:
        _, err = _login()
        if err:
            return {'ok': False, 'success': False, 'message': err}
        token = _access_token()
        if not token:
            return {'ok': False, 'success': False, 'message': 'دریافت توکن درگاه ناموفق بود.'}
    body = {'authority': authority}
    if expected_price is not None:
        body['new_price'] = str(int(expected_price))
    try:
        resp = requests.post(
            f'{API_BASE}/api/v2/transaction/check',
            json=body,
            headers=_auth_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        return {'ok': False, 'success': False, 'message': f'ارتباط با درگاه برقرار نشد: {exc}'}
    try:
        data = resp.json()
    except Exception:
        data = {}
    raw = json.dumps({"status_code": resp.status_code, "body": data}, ensure_ascii=False, default=str)
    if not isinstance(data, dict):
        return {'ok': False, 'success': False, 'message': f'پاسخ درگاه نامعتبر است (HTTP {resp.status_code}).', 'raw': raw}
    if resp.status_code == 401:
        clear_cached_token()
    # Success heuristics across the possible Dargahno response shapes.
    paidish = {1, '1', True, 'true', 'True', 'TRUE', 'paid', 'PAID', 'Paid', 'success', 'SUCCESS', 'successful', 'Success'}
    success = None
    for field in ('success', 'paid', 'status', 'payment_status'):
        if data.get(field) is not None:
            success = data.get(field) in paidish
            break
    if success is None:
        nested = data.get('data') or data.get('result') or data.get('result_data') or data.get('transaction')
        if isinstance(nested, dict):
            for field in ('success', 'paid', 'status', 'payment_status'):
                if nested.get(field) is not None:
                    success = nested.get(field) in paidish
                    break
    if success is None and data.get('authority'):
        # The presence of transaction data alone is not proof of payment.
        success = False
    if success is None:
        return {'ok': False, 'success': False, 'message': f'نمی‌توان وضعیت تراکنش را از پاسخ درگاه تشخیص داد (HTTP {resp.status_code}).', 'raw': raw}
    if resp.status_code >= 400:
        return {'ok': False, 'success': False, 'message': f'تأیید تراکنش ناموفق بود (HTTP {resp.status_code}).', 'raw': raw}
    return {'ok': True, 'success': bool(success), 'data': data, 'raw': raw}


def payment_history(reseller_id=None, limit=50) -> list:
    """Recent gateway payments, newest first. reseller_id=None returns everyone."""
    _ensure_database_schema()
    q = GatewayPayment.query
    if reseller_id is not None:
        q = q.filter_by(reseller_id=reseller_id)
    q = q.order_by(GatewayPayment.id.desc())
    if limit > 0:
        q = q.limit(limit)
    return q.all()
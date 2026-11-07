"""Admin Telegram automation helpers for IronPanel."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Iterable

from ..core.extensions import db
from ..core.models import AppSetting, VpnUser, OnlineSession
from .provisioning import get_setting, set_setting, user_usage_summary, telegram_notify, service_status, backup_now

DEFAULTS = {
    'admin_bot_enabled': '0',
    'admin_bot_daily_report': '1',
    'admin_bot_usage_warning_percent': '85',
    'admin_bot_expiry_warning_days': '3',
    # v19.10.10: after the admin bot is activated, server backup delivery is
    # enabled by default and runs every 24 hours. Existing installations can
    # still turn it off from Admin Bot settings.
    'admin_bot_backup_enabled': '1',
    'admin_bot_backup_send_file': '1',
    'admin_bot_backup_interval_hours': '24',
    'admin_bot_last_backup_sent_at': '',
    'admin_bot_login_alerts': '1',
    'admin_bot_admin_ids': '',
    'admin_bot_welcome_text': 'به ربات مدیریتی IronPanel خوش آمدید ✅\nاز دکمه‌های زیر برای مدیریت سریع پنل استفاده کنید.',
}


def _truthy(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


_TG_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_telegram_id(value) -> str:
    """Normalize Telegram IDs saved by admins.

    Admins often paste IDs with Persian/Arabic digits, spaces, semicolons or
    invisible unicode marks. Without normalization the bot may reject a valid
    admin and send the confusing «⛔ دسترسی مجاز نیست.» message.
    """
    raw = str(value or '').translate(_TG_DIGITS)
    raw = raw.replace('\u200c', '').replace('\u200f', '').replace('\u202a', '').replace('\u202c', '')
    sign = '-' if raw.strip().startswith('-') else ''
    digits = ''.join(ch for ch in raw if ch.isdigit())
    return sign + digits if digits else ''


def parse_telegram_ids(raw) -> set[str]:
    out: set[str] = set()
    text = str(raw or '').translate(_TG_DIGITS)
    for part in text.replace('\n', ',').replace(';', ',').replace('،', ',').replace('|', ',').split(','):
        norm = normalize_telegram_id(part)
        if norm:
            out.add(norm)
    return out


def _setting_exists(key: str) -> bool:
    try:
        return AppSetting.query.filter_by(key=key).first() is not None
    except Exception:
        return False


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _parse_utc_iso(value: str | None) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1]
        return datetime.fromisoformat(text)
    except Exception:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.strptime(str(value).strip().rstrip('Z'), fmt)
            except Exception:
                continue
    return None


def ensure_admin_bot_runtime_defaults() -> None:
    """Create missing admin-bot automation settings without overriding custom values.

    Older installs stored backup defaults as disabled. For new installs or keys
    that do not exist yet, v19.10.10 enables daily backup file delivery by
    default so activating the admin bot is enough.
    """
    for key, value in DEFAULTS.items():
        if not _setting_exists(key):
            set_setting(key, value)


def admin_bot_admin_ids() -> set[str]:
    """Return chat ids allowed to use the admin bot buttons.

    Falls back to the main Telegram chat id and sales-bot admin ids so existing
    installations keep working without another configuration step. v19.9.28
    parses all candidate fields instead of only the first non-empty one.
    """
    raw_values = [
        get_setting('admin_bot_admin_ids', ''),
        get_setting('telegram_chat_id', ''),
        get_setting('sales_bot_admin_ids', ''),
    ]
    out: set[str] = set()
    for raw in raw_values:
        out |= parse_telegram_ids(raw)
    return out


def admin_bot_settings() -> Dict[str, Any]:
    ensure_admin_bot_runtime_defaults()
    data = {k: get_setting(k, v) for k, v in DEFAULTS.items()}
    data['enabled'] = _truthy(data.get('admin_bot_enabled'))
    data['daily_report'] = _truthy(data.get('admin_bot_daily_report'))
    data['backup_enabled'] = _truthy(data.get('admin_bot_backup_enabled'))
    data['backup_send_file'] = _truthy(data.get('admin_bot_backup_send_file'))
    data['login_alerts'] = _truthy(data.get('admin_bot_login_alerts'))
    try:
        data['usage_warning_percent_int'] = int(data.get('admin_bot_usage_warning_percent') or 85)
    except Exception:
        data['usage_warning_percent_int'] = 85
    try:
        data['expiry_warning_days_int'] = int(data.get('admin_bot_expiry_warning_days') or 3)
    except Exception:
        data['expiry_warning_days_int'] = 3
    try:
        data['backup_interval_hours_int'] = max(1, int(data.get('admin_bot_backup_interval_hours') or 24))
    except Exception:
        data['backup_interval_hours_int'] = 24
    last_dt = _parse_utc_iso(data.get('admin_bot_last_backup_sent_at'))
    data['last_backup_sent_at_dt'] = last_dt
    data['last_backup_sent_at_human'] = '-' if not last_dt else last_dt.strftime('%Y-%m-%d %H:%M UTC')
    if last_dt:
        next_dt = last_dt + timedelta(hours=data['backup_interval_hours_int'])
        data['next_backup_at_human'] = next_dt.strftime('%Y-%m-%d %H:%M UTC')
    else:
        data['next_backup_at_human'] = 'بعد از فعال شدن ربات / اولین اجرای زمان‌بند'
    token = get_setting('telegram_bot_token', '') or get_setting('sales_bot_token', '')
    data['telegram_configured'] = bool(token and admin_bot_admin_ids())
    data['admin_ids'] = ','.join(sorted(admin_bot_admin_ids()))
    return data


def save_admin_bot_settings(form):
    ensure_admin_bot_runtime_defaults()
    boolean_keys = {
        'admin_bot_enabled', 'admin_bot_daily_report', 'admin_bot_backup_enabled',
        'admin_bot_backup_send_file', 'admin_bot_login_alerts'
    }
    was_enabled = _truthy(get_setting('admin_bot_enabled', '0'))
    will_enable = bool(form.get('admin_bot_enabled'))

    for key in DEFAULTS:
        # Important: there are two admin-bot forms on the page. A checkbox that
        # is absent from the submitted form must not reset unrelated options to
        # 0. This used to disable daily backup when the admin only edited IDs.
        if key in boolean_keys:
            if key in form:
                set_setting(key, '1' if form.get(key) else '0')
            elif not _setting_exists(key):
                set_setting(key, DEFAULTS[key])
        else:
            if key in form:
                set_setting(key, form.get(key, DEFAULTS[key]))
            elif not _setting_exists(key):
                set_setting(key, DEFAULTS[key])

    # When the admin bot is activated for the first time, make automatic backup
    # delivery active by default. The admin can disable it later from the same
    # page, but activation should not require another hidden configuration step.
    if will_enable and not was_enabled:
        set_setting('admin_bot_backup_enabled', '1')
        set_setting('admin_bot_backup_send_file', '1')
        if not get_setting('admin_bot_backup_interval_hours', '').strip():
            set_setting('admin_bot_backup_interval_hours', '24')
        # Empty last-run makes the scheduler treat the first run as due.
        set_setting('admin_bot_last_backup_sent_at', '')

    return admin_bot_settings()

def online_users_snapshot(limit: int = 30):
    from .v10 import refresh_online_sessions
    sessions = refresh_online_sessions()
    return sessions[:limit]


def online_users_text(limit: int = 30) -> str:
    sessions = online_users_snapshot(limit)
    if not sessions:
        return '👥 کاربر آنلاینی پیدا نشد. اگر Cisco/Ocserv وصل است، Doctor را اجرا کن تا hook آنلاین نصب شود.'
    lines = [f'👥 کاربران آنلاین: {len(sessions)}']
    for s in sessions:
        seen = s.last_seen.strftime('%H:%M:%S') if s.last_seen else '-'
        ip = s.remote_ip or '-'
        lines.append(f'• {s.username} | {s.protocol} | {ip} | {seen}')
    return '\n'.join(lines)


def users_summary_text(limit: int = 25) -> str:
    users = VpnUser.query.order_by(VpnUser.id.desc()).limit(limit).all()
    if not users:
        return 'کاربری ثبت نشده است.'
    lines = [f'👤 آخرین {len(users)} کاربر']
    for u in users:
        us = user_usage_summary(u)
        status = '✅' if u.enabled and not u.expired else '⛔'
        exp = 'نامحدود' if not u.expires_at else u.expires_at.strftime('%Y-%m-%d')
        lines.append(f'{status} #{u.id} {u.username} | {us.get("used_human", "0")} / {us.get("total_human", "∞")} | {exp}')
    return '\n'.join(lines)


def user_detail_text(user_id: int) -> str:
    u = VpnUser.query.get(user_id)
    if not u:
        return 'کاربر پیدا نشد.'
    us = user_usage_summary(u)
    sessions = OnlineSession.query.filter_by(user_id=u.id, active=True).order_by(OnlineSession.last_seen.desc()).all()
    lines = [
        f'👤 اطلاعات کاربر #{u.id}',
        f'نام کاربری: {u.username}',
        f'وضعیت: {"فعال" if u.enabled and not u.expired else "غیرفعال/منقضی"}',
        f'پروتکل‌ها: {u.protocol_permissions or u.protocols}',
        f'مصرف: {us.get("used_human", "0")} / {us.get("total_human", "نامحدود")}',
        f'انقضا: {"نامحدود" if not u.expires_at else u.expires_at.strftime("%Y-%m-%d %H:%M")}',
        f'نشست آنلاین: {len(sessions)}',
    ]
    for s in sessions[:10]:
        lines.append(f'  • {s.protocol} | {s.remote_ip or "-"} | {s.last_seen.strftime("%H:%M:%S") if s.last_seen else "-"}')
    return '\n'.join(lines)



def _mask_login_password(value: str | None) -> str:
    value = str(value or '')
    if not value:
        return '(empty)'
    return '•' * min(len(value), 12) + f' (len={len(value)})'


def _send_admin_bot_message(message: str) -> bool:
    token = get_setting('telegram_bot_token', '') or get_setting('sales_bot_token', '')
    chat_ids = sorted(admin_bot_admin_ids())
    if not token or not chat_ids:
        return telegram_notify(message)
    ok = False
    try:
        import requests
        for chat_id in chat_ids:
            try:
                r = requests.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id': chat_id, 'text': message, 'disable_web_page_preview': True},
                    timeout=5,
                )
                ok = ok or bool(getattr(r, 'ok', False))
            except Exception:
                continue
    except Exception:
        return telegram_notify(message)
    return ok


def send_login_alert(username: str, password: str | None, success: bool, reason: str, ip: str, user_agent: str, portal: str = 'admin') -> bool:
    """Send a safe login-attempt notification to the admin Telegram bot.

    Raw attempted passwords are intentionally not sent to Telegram. Sending raw
    passwords would turn the panel into a credential-leak channel. The message
    includes a masked value and length so admins can still audit attempts.
    """
    if str(get_setting('admin_bot_login_alerts', '1')).lower() in {'0', 'false', 'off', 'no'}:
        return False
    status = '✅ ورود موفق' if success else '⛔ تلاش ناموفق برای ورود'
    uname = (username or '').strip() or '(empty)'
    masked = _mask_login_password(password)
    ua = (user_agent or '-')[:180]
    text = (
        f'{status}\n'
        f'پنل: {portal}\n'
        f'نام کاربری تست‌شده: {uname}\n'
        f'رمز تست‌شده: {masked}\n'
        f'IP: {ip or "-"}\n'
        f'Reason: {reason or "-"}\n'
        f'User-Agent: {ua}\n'
        f'زمان: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}'
    )
    return _send_admin_bot_message(text)

def admin_bot_report_text() -> str:
    users = VpnUser.query.order_by(VpnUser.username).all()
    total = len(users)
    active = len([u for u in users if u.enabled and not u.expired])
    over = 0
    expiring = 0
    warning_lines = []
    settings = admin_bot_settings()
    percent_threshold = settings['usage_warning_percent_int']
    expiry_days = settings['expiry_warning_days_int']
    now = datetime.utcnow()
    for u in users:
        us = user_usage_summary(u)
        if us.get('total_bytes'):
            percent = int((us.get('used_bytes') or 0) * 100 / max(1, us.get('total_bytes') or 1))
            if percent >= percent_threshold:
                over += 1
                warning_lines.append(f'- {u.username}: {percent}% حجم مصرف شده')
        if u.expires_at and now <= u.expires_at <= now + timedelta(days=expiry_days):
            expiring += 1
    svc = service_status()
    bad = [name for name, state in svc.items() if state != 'active']
    online_count = OnlineSession.query.filter_by(active=True).count()
    text = [
        '📊 IronPanel Admin Report',
        f'Users: {active}/{total} active',
        f'Online sessions: {online_count}',
        f'Usage warnings: {over}',
        f'Expiring soon: {expiring}',
        f'Services not active: {len(bad)}',
    ]
    if bad:
        text.append('Services: ' + ', '.join(bad[:12]))
    if warning_lines:
        text.append('\n'.join(warning_lines[:20]))
    return '\n'.join(text)


def create_admin_backup() -> Path:
    return backup_now()


def _backup_due(settings: Dict[str, Any] | None = None) -> bool:
    settings = settings or admin_bot_settings()
    if not settings.get('enabled') or not settings.get('backup_enabled'):
        return False
    last_dt = _parse_utc_iso(get_setting('admin_bot_last_backup_sent_at', ''))
    if not last_dt:
        return True
    try:
        interval_hours = max(1, int(get_setting('admin_bot_backup_interval_hours', '24') or 24))
    except Exception:
        interval_hours = 24
    return datetime.utcnow() >= last_dt + timedelta(hours=interval_hours)


def send_admin_backup_file(path: Path, caption: str | None = None) -> bool:
    """Send a backup file to all allowed admin-bot chats."""
    token = (get_setting('telegram_bot_token', '') or get_setting('sales_bot_token', '') or '').strip()
    chat_ids = sorted(admin_bot_admin_ids())
    if not token or not chat_ids or not path or not Path(path).exists():
        return False
    ok = False
    try:
        import requests
        for chat_id in chat_ids:
            try:
                with open(path, 'rb') as f:
                    r = requests.post(
                        f'https://api.telegram.org/bot{token}/sendDocument',
                        data={'chat_id': chat_id, 'caption': caption or f'🗄 IronPanel automatic backup: {Path(path).name}'},
                        files={'document': (Path(path).name, f, 'application/zip')},
                        timeout=180,
                    )
                ok = ok or bool(getattr(r, 'ok', False))
            except Exception:
                continue
    except Exception:
        ok = False
    return ok


def run_scheduled_admin_bot_tasks(force_backup: bool = False) -> Dict[str, Any]:
    """Run scheduled admin bot report/backup tasks.

    The systemd timer calls this script once on boot and then every 24 hours.
    The function also protects against duplicate backup sends by storing the
    last successful send timestamp in AppSetting.
    """
    result: Dict[str, Any] = {'report_sent': False, 'backup_created': None, 'backup_sent': False, 'backup_due': False}
    s = admin_bot_settings()
    if not s.get('enabled'):
        return result

    if s.get('daily_report'):
        result['report_sent'] = bool(send_test_admin_report())

    due = force_backup or _backup_due(s)
    result['backup_due'] = bool(due)
    if s.get('backup_enabled') and due:
        path = create_admin_backup()
        result['backup_created'] = str(path)
        if s.get('backup_send_file'):
            result['backup_sent'] = bool(send_admin_backup_file(path, caption=f'🗄 IronPanel automatic 24h backup\n{Path(path).name}'))
            if not result['backup_sent']:
                _send_admin_bot_message(f'⚠️ بکاپ ساخته شد اما ارسال فایل ناموفق بود.\nمسیر فایل: {path}')
        else:
            result['backup_sent'] = bool(_send_admin_bot_message(f'🗄 بکاپ ۲۴ ساعته ساخته شد.\nمسیر فایل: {path}'))
        # Store last-run after creating the backup to prevent duplicate heavy
        # backup jobs on timer retries/restarts. Sending errors are reported.
        set_setting('admin_bot_last_backup_sent_at', _utcnow_iso())
    return result


def send_test_admin_report() -> bool:
    return telegram_notify(admin_bot_report_text())

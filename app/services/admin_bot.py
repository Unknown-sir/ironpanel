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
    'admin_bot_backup_enabled': '0',
    'admin_bot_backup_send_file': '0',
    'admin_bot_login_alerts': '1',
    'admin_bot_admin_ids': '',
}


def _truthy(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def admin_bot_admin_ids() -> set[str]:
    """Return chat ids allowed to use the admin bot buttons.

    Falls back to the main Telegram chat id and sales-bot admin ids so existing
    installations keep working without another configuration step.
    """
    raw = get_setting('admin_bot_admin_ids', '') or get_setting('telegram_chat_id', '') or get_setting('sales_bot_admin_ids', '') or ''
    out = set()
    for part in str(raw).replace('\n', ',').replace(';', ',').split(','):
        part = part.strip()
        if part:
            out.add(part)
    return out


def admin_bot_settings() -> Dict[str, Any]:
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
    token = get_setting('telegram_bot_token', '') or get_setting('sales_bot_token', '')
    data['telegram_configured'] = bool(token and admin_bot_admin_ids())
    data['admin_ids'] = ','.join(sorted(admin_bot_admin_ids()))
    return data


def save_admin_bot_settings(form):
    for key in DEFAULTS:
        if key in ('admin_bot_enabled', 'admin_bot_daily_report', 'admin_bot_backup_enabled', 'admin_bot_backup_send_file', 'admin_bot_login_alerts'):
            set_setting(key, '1' if form.get(key) else '0')
        else:
            set_setting(key, form.get(key, DEFAULTS[key]))
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


def send_test_admin_report() -> bool:
    return telegram_notify(admin_bot_report_text())

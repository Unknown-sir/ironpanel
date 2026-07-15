"""Admin Telegram automation helpers."""
from __future__ import annotations

from typing import Dict, Any
from ..core.extensions import db
from ..core.models import AppSetting, VpnUser
from .provisioning import get_setting, set_setting, user_usage_summary, telegram_notify, service_status

DEFAULTS = {
    'admin_bot_enabled': '0',
    'admin_bot_daily_report': '1',
    'admin_bot_usage_warning_percent': '85',
    'admin_bot_expiry_warning_days': '3',
    'admin_bot_backup_enabled': '0',
    'admin_bot_login_alerts': '1',
}


def admin_bot_settings() -> Dict[str, Any]:
    data = {k: get_setting(k, v) for k, v in DEFAULTS.items()}
    data['enabled'] = data.get('admin_bot_enabled') == '1'
    data['daily_report'] = data.get('admin_bot_daily_report') == '1'
    data['backup_enabled'] = data.get('admin_bot_backup_enabled') == '1'
    data['login_alerts'] = data.get('admin_bot_login_alerts') == '1'
    try:
        data['usage_warning_percent_int'] = int(data.get('admin_bot_usage_warning_percent') or 85)
    except Exception:
        data['usage_warning_percent_int'] = 85
    try:
        data['expiry_warning_days_int'] = int(data.get('admin_bot_expiry_warning_days') or 3)
    except Exception:
        data['expiry_warning_days_int'] = 3
    data['telegram_configured'] = bool(get_setting('telegram_bot_token','') and get_setting('telegram_chat_id',''))
    return data


def save_admin_bot_settings(form):
    for key in DEFAULTS:
        if key in ('admin_bot_enabled', 'admin_bot_daily_report', 'admin_bot_backup_enabled', 'admin_bot_login_alerts'):
            set_setting(key, '1' if form.get(key) else '0')
        else:
            set_setting(key, form.get(key, DEFAULTS[key]))
    return admin_bot_settings()


def admin_bot_report_text() -> str:
    users = VpnUser.query.order_by(VpnUser.username).all()
    total = len(users)
    active = len([u for u in users if u.enabled and not u.expired])
    over = 0
    warning_lines = []
    settings = admin_bot_settings()
    percent_threshold = settings['usage_warning_percent_int']
    for u in users:
        us = user_usage_summary(u)
        if us.get('total_bytes'):
            percent = int((us.get('used_bytes') or 0) * 100 / max(1, us.get('total_bytes') or 1))
            if percent >= percent_threshold:
                over += 1
                warning_lines.append(f'- {u.username}: {percent}% حجم مصرف شده')
    svc = service_status()
    bad = [name for name, state in svc.items() if state != 'active']
    text = [
        '📊 IronPanel Admin Report',
        f'Users: {active}/{total} active',
        f'Usage warnings: {over}',
        f'Services not active: {len(bad)}',
    ]
    if bad:
        text.append('Services: ' + ', '.join(bad[:12]))
    if warning_lines:
        text.append('\n'.join(warning_lines[:20]))
    return '\n'.join(text)


def send_test_admin_report() -> bool:
    return telegram_notify(admin_bot_report_text())

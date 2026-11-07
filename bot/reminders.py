from datetime import datetime
import requests
from app import create_app
from app.core.extensions import db
from app.core.models import AppSetting, SalesBotOrder, VpnUser
from app.services.provisioning import get_setting, set_setting, user_usage_summary

app = create_app()


def _send(token, chat_id, text):
    if not token:
        return False
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text},
            timeout=8,
        )
        return bool(resp.ok)
    except Exception:
        return False


def _token_for_owner(owner_id: int) -> str:
    oid = int(owner_id or 0)
    if oid > 0:
        enabled = get_setting(f'sales_bot_enabled_owner_{oid}', '0') == '1'
        tok = get_setting(f'sales_bot_token_owner_{oid}', '')
        return tok if enabled else ''
    if get_setting('sales_bot_enabled', '0') != '1':
        return ''
    return get_setting('sales_bot_token', '') or get_setting('telegram_bot_token', '')


def main():
    with app.app_context():
        now = datetime.utcnow()
        sent = 0
        orders = SalesBotOrder.query.filter_by(status='approved').filter(SalesBotOrder.vpn_user_id.isnot(None)).all()
        for o in orders:
            u = db.session.get(VpnUser, o.vpn_user_id)
            if not u:
                continue
            owner_id = int(getattr(o, 'owner_id', 0) or getattr(u, 'owner_id', 0) or 0)
            token = _token_for_owner(owner_id)
            if not token:
                continue
            if u.expires_at:
                days = (u.expires_at - now).days
                if days in (7, 3, 1, 0):
                    key = f'sales_reminder_exp_{o.telegram_id}_{u.id}_{days}_{now.date()}'
                    if not AppSetting.query.filter_by(key=key).first():
                        if _send(token, o.telegram_id, f'⏳ سرویس {u.username} تا {max(days,0)} روز دیگر منقضی می‌شود. برای تمدید از گزینه تمدید سرویس استفاده کنید.'):
                            set_setting(key, '1')
                            sent += 1
            usage = user_usage_summary(u)
            try:
                total = int(usage.get('total_bytes') or 0)
                used = int(usage.get('used_bytes') or 0)
                percent = (used / total * 100.0) if total > 0 else 0
            except Exception:
                percent = 0
            if percent >= 80:
                bucket = '95' if percent >= 95 else '80'
                key = f'sales_reminder_usage_{o.telegram_id}_{u.id}_{bucket}_{now.date()}'
                if not AppSetting.query.filter_by(key=key).first():
                    if _send(token, o.telegram_id, f'📦 مصرف سرویس {u.username} به حدود {int(percent)}٪ رسیده است. برای خرید حجم یا تمدید از ربات استفاده کنید.'):
                        set_setting(key, '1')
                        sent += 1
        print(f'sent reminders: {sent}')


if __name__ == '__main__':
    main()

from datetime import datetime
import requests
from app import create_app
from app.core.extensions import db
from app.core.models import AppSetting, SalesBotOrder, VpnUser
from app.services.provisioning import get_setting, set_setting, user_usage_summary

app = create_app()


def _send(token, chat_id, text):
    try:
        requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat_id, 'text': text}, timeout=8)
        return True
    except Exception:
        return False


def main():
    with app.app_context():
        token = get_setting('sales_bot_token','') or get_setting('telegram_bot_token','')
        if not token or get_setting('sales_bot_enabled','0') != '1':
            print('sales bot disabled or token empty')
            return
        now = datetime.utcnow()
        sent = 0
        orders = SalesBotOrder.query.filter_by(status='approved').filter(SalesBotOrder.vpn_user_id.isnot(None)).all()
        for o in orders:
            u = VpnUser.query.get(o.vpn_user_id)
            if not u:
                continue
            if u.expires_at:
                days = (u.expires_at - now).days
                if days in (7,3,1,0):
                    key=f'sales_reminder_exp_{o.telegram_id}_{u.id}_{days}_{now.date()}'
                    if not AppSetting.query.filter_by(key=key).first():
                        if _send(token, o.telegram_id, f'⏳ سرویس {u.username} تا {max(days,0)} روز دیگر منقضی می‌شود. برای تمدید از گزینه تمدید سرویس استفاده کنید.'):
                            set_setting(key, '1'); sent += 1
            usage=user_usage_summary(u)
            try:
                total = int(usage.get('total_bytes') or 0)
                used = int(usage.get('used_bytes') or 0)
                percent = (used / total * 100.0) if total > 0 else 0
            except Exception:
                percent = 0
            if percent >= 80:
                bucket='95' if percent >= 95 else '80'
                key=f'sales_reminder_usage_{o.telegram_id}_{u.id}_{bucket}_{now.date()}'
                if not AppSetting.query.filter_by(key=key).first():
                    if _send(token, o.telegram_id, f'📦 مصرف سرویس {u.username} به حدود {int(percent)}٪ رسیده است. برای خرید حجم یا تمدید از ربات استفاده کنید.'):
                        set_setting(key, '1'); sent += 1
        print(f'sent reminders: {sent}')

if __name__ == '__main__':
    main()

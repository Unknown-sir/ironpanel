#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
from app import create_app
from app.services.admin_bot import admin_bot_settings, send_test_admin_report, create_admin_backup, admin_bot_admin_ids
from app.services.provisioning import get_setting, telegram_notify

app = create_app()
with app.app_context():
    s = admin_bot_settings()
    if s.get('enabled') and s.get('daily_report'):
        send_test_admin_report()
    if s.get('enabled') and s.get('backup_enabled'):
        path = create_admin_backup()
        token = (get_setting('telegram_bot_token','') or get_setting('sales_bot_token','') or '').strip()
        if s.get('backup_send_file') and token:
            for chat_id in admin_bot_admin_ids():
                try:
                    subprocess.run([
                        'curl','-sS','--max-time','90','-X','POST',
                        '-F',f'chat_id={chat_id}',
                        '-F',f'document=@{path}',
                        '-F',f'caption=IronPanel daily backup: {path.name}',
                        f'https://api.telegram.org/bot{token}/sendDocument'
                    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
        else:
            telegram_notify(f'🗄 بکاپ روزانه ساخته شد: {path}')

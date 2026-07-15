#!/usr/bin/env python3
from app import create_app
from app.services.admin_bot import admin_bot_settings, send_test_admin_report
app = create_app()
with app.app_context():
    s = admin_bot_settings()
    if s.get('enabled'):
        send_test_admin_report()

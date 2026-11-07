#!/usr/bin/env python3
"""Scheduled Telegram admin report and 24-hour backup delivery."""
import json
from app import create_app
from app.services.admin_bot import run_scheduled_admin_bot_tasks

app = create_app()
with app.app_context():
    result = run_scheduled_admin_bot_tasks()
    print(json.dumps(result, ensure_ascii=False))

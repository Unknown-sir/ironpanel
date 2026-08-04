import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

class Config:
    SECRET_KEY = os.environ.get('IRONPANEL_SECRET_KEY', 'change-me-dev-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "ironpanel.db"}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite is used by default. Give migrations/background sync enough time to
    # wait for short-lived writer locks instead of immediately failing with
    # sqlite3.OperationalError: database is locked.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {'connect_args': {'timeout': int(os.environ.get('IRONPANEL_SQLITE_TIMEOUT', '60')), 'check_same_thread': False}}
        if SQLALCHEMY_DATABASE_URI.startswith('sqlite') else {}
    )
    API_KEY = os.environ.get('IRONPANEL_API_KEY', 'change-me-api-key')
    PUBLIC_HOST = os.environ.get('IRONPANEL_PUBLIC_HOST', '127.0.0.1')
    PANEL_PORT = int(os.environ.get('IRONPANEL_PORT', '8080'))
    CONFIG_ROOT = Path(os.environ.get('IRONPANEL_CONFIG_ROOT', '/etc/ironpanel'))

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_env_fallback(env_path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    try:
        if env_path.is_file():
            for raw in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return vals


def _resolve_secret(env_key: str, fallback_map: dict[str, str], persisted_file: Path) -> str:
    val = (os.environ.get(env_key) or fallback_map.get(env_key) or '').strip()
    if val and val not in ('change-me-dev-key', 'change-me-api-key'):
        return val
    try:
        if persisted_file.is_file():
            saved = persisted_file.read_text(encoding='utf-8', errors='ignore').strip()
            if saved:
                return saved
        persisted_file.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_hex(32)
        persisted_file.write_text(generated + '\n', encoding='utf-8')
        os.chmod(persisted_file, 0o600)
        return generated
    except Exception:
        return secrets.token_hex(32)


_CONFIG_ROOT = Path(os.environ.get('IRONPANEL_CONFIG_ROOT', '/etc/ironpanel'))
_ENV_MAP = _load_env_fallback(_CONFIG_ROOT / 'ironpanel.env')


class Config:
    CONFIG_ROOT = _CONFIG_ROOT
    SECRET_KEY = _resolve_secret('IRONPANEL_SECRET_KEY', _ENV_MAP, _CONFIG_ROOT / '.secret_key')
    # Manual CLI/repair commands do not inherit systemd EnvironmentFile. Never
    # fall back to /opt/ironpanel/ironpanel.db because SQLAlchemy may silently
    # create an empty database there and then fail with missing-table errors.
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or _ENV_MAP.get('DATABASE_URL')
        or f'sqlite:///{CONFIG_ROOT / "ironpanel.db"}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite is used by default. Give migrations/background sync enough time to
    # wait for short-lived writer locks instead of immediately failing with
    # sqlite3.OperationalError: database is locked.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {'connect_args': {'timeout': int(os.environ.get('IRONPANEL_SQLITE_TIMEOUT', '60')), 'check_same_thread': False}}
        if SQLALCHEMY_DATABASE_URI.startswith('sqlite') else {}
    )
    API_KEY = _resolve_secret('IRONPANEL_API_KEY', _ENV_MAP, _CONFIG_ROOT / '.api_key')
    PUBLIC_HOST = os.environ.get('IRONPANEL_PUBLIC_HOST') or _ENV_MAP.get('IRONPANEL_PUBLIC_HOST') or '127.0.0.1'
    PANEL_PORT = int(os.environ.get('IRONPANEL_PORT') or _ENV_MAP.get('IRONPANEL_PORT') or '8080')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = (os.environ.get('IRONPANEL_COOKIE_SECURE', '0') == '1')

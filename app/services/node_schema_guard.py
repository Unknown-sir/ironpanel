"""Runtime schema guard for the Nodes page.

SQLite does not ALTER existing tables when SQLAlchemy models gain new columns.
If an admin opens /nodes before running upgrade-db successfully, SQLAlchemy's
SELECT against the Node model can fail with "no such column" and the panel
returns HTTP 500.  This lightweight guard adds the optional node columns used by
recent Node Auto Installer / Direct Location releases before the page queries
Node records.
"""
from __future__ import annotations
import re
import time
from typing import Dict
from flask import current_app
from sqlalchemy import text
from ..core.extensions import db

NODE_COLUMN_SQL: Dict[str, str] = {
    'location': "ALTER TABLE node ADD COLUMN location VARCHAR(120) DEFAULT ''",
    'server_name': "ALTER TABLE node ADD COLUMN server_name VARCHAR(160) DEFAULT ''",
    'config_domain': "ALTER TABLE node ADD COLUMN config_domain VARCHAR(255) DEFAULT ''",
    'version': "ALTER TABLE node ADD COLUMN version VARCHAR(40) DEFAULT ''",
    'agent_version': "ALTER TABLE node ADD COLUMN agent_version VARCHAR(40) DEFAULT ''",
    'public_ip': "ALTER TABLE node ADD COLUMN public_ip VARCHAR(80) DEFAULT ''",
    'cpu_percent': "ALTER TABLE node ADD COLUMN cpu_percent FLOAT DEFAULT 0",
    'ram_percent': "ALTER TABLE node ADD COLUMN ram_percent FLOAT DEFAULT 0",
    'disk_percent': "ALTER TABLE node ADD COLUMN disk_percent FLOAT DEFAULT 0",
    'traffic_rx_bytes': "ALTER TABLE node ADD COLUMN traffic_rx_bytes BIGINT DEFAULT 0",
    'traffic_tx_bytes': "ALTER TABLE node ADD COLUMN traffic_tx_bytes BIGINT DEFAULT 0",
    'last_seen': "ALTER TABLE node ADD COLUMN last_seen DATETIME",
    'last_error': "ALTER TABLE node ADD COLUMN last_error TEXT DEFAULT ''",
    'ping_ms': "ALTER TABLE node ADD COLUMN ping_ms FLOAT DEFAULT 0",
    'online_users': "ALTER TABLE node ADD COLUMN online_users INTEGER DEFAULT 0",
    'protocol_health_json': "ALTER TABLE node ADD COLUMN protocol_health_json TEXT DEFAULT ''",
    'gateway_enabled': "ALTER TABLE node ADD COLUMN gateway_enabled BOOLEAN DEFAULT 1",
    'weight': "ALTER TABLE node ADD COLUMN weight INTEGER DEFAULT 100",
    'max_users': "ALTER TABLE node ADD COLUMN max_users INTEGER DEFAULT 0",
    'sync_status': "ALTER TABLE node ADD COLUMN sync_status VARCHAR(40) DEFAULT 'idle'",
    'last_sync_at': "ALTER TABLE node ADD COLUMN last_sync_at DATETIME",
    'ssh_host': "ALTER TABLE node ADD COLUMN ssh_host VARCHAR(255) DEFAULT ''",
    'ssh_port': "ALTER TABLE node ADD COLUMN ssh_port INTEGER DEFAULT 22",
    'ssh_username': "ALTER TABLE node ADD COLUMN ssh_username VARCHAR(120) DEFAULT 'root'",
    'ssh_auth_method': "ALTER TABLE node ADD COLUMN ssh_auth_method VARCHAR(20) DEFAULT 'password'",
    'ssh_password_enc': "ALTER TABLE node ADD COLUMN ssh_password_enc TEXT DEFAULT ''",
    'ssh_key_enc': "ALTER TABLE node ADD COLUMN ssh_key_enc TEXT DEFAULT ''",
    'ssh_key_passphrase_enc': "ALTER TABLE node ADD COLUMN ssh_key_passphrase_enc TEXT DEFAULT ''",
    'ssh_sudo_password_enc': "ALTER TABLE node ADD COLUMN ssh_sudo_password_enc TEXT DEFAULT ''",
    'ssh_credentials_saved': "ALTER TABLE node ADD COLUMN ssh_credentials_saved BOOLEAN DEFAULT 0",
    'auto_install_status': "ALTER TABLE node ADD COLUMN auto_install_status VARCHAR(40) DEFAULT 'idle'",
    'last_auto_install_at': "ALTER TABLE node ADD COLUMN last_auto_install_at DATETIME",
    'last_install_log': "ALTER TABLE node ADD COLUMN last_install_log TEXT DEFAULT ''",
    'delivery_mode': "ALTER TABLE node ADD COLUMN delivery_mode VARCHAR(20) DEFAULT 'relay'",
    'subscription_enabled': "ALTER TABLE node ADD COLUMN subscription_enabled BOOLEAN DEFAULT 0",
    'subscription_host': "ALTER TABLE node ADD COLUMN subscription_host VARCHAR(255) DEFAULT ''",
    'subscription_label': "ALTER TABLE node ADD COLUMN subscription_label VARCHAR(160) DEFAULT ''",
    'subscription_flag': "ALTER TABLE node ADD COLUMN subscription_flag VARCHAR(16) DEFAULT ''",
    'subscription_ports_json': "ALTER TABLE node ADD COLUMN subscription_ports_json TEXT DEFAULT '{}'",
    'last_usage_sync_at': "ALTER TABLE node ADD COLUMN last_usage_sync_at DATETIME",
}


def _is_sqlite() -> bool:
    try:
        return (db.engine.url.drivername or '').startswith('sqlite')
    except Exception:
        return False


def _table_exists(conn, table: str) -> bool:
    if not re.match(r'^[A-Za-z0-9_]+$', table or ''):
        return False
    rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchall()
    return bool(rows)


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.exec_driver_sql(f'PRAGMA table_info({table})').fetchall()}


def ensure_node_page_schema(retries: int = 6) -> int:
    """Ensure optional columns used by /nodes exist on SQLite.

    Returns the number of added columns. Non-SQLite databases are left to their
    normal migration system.
    """
    if not _is_sqlite():
        return 0
    added = 0
    last_exc = None
    for attempt in range(max(1, retries)):
        try:
            with db.engine.connect() as conn:
                conn.exec_driver_sql('PRAGMA busy_timeout=15000')
                if not _table_exists(conn, 'node'):
                    return 0
                existing = _columns(conn, 'node')
            missing = [(name, sql) for name, sql in NODE_COLUMN_SQL.items() if name not in existing]
            for name, sql in missing:
                # SQLite takes a write lock per ALTER; run each column separately
                # so a single already-existing column never rolls back all others.
                try:
                    with db.engine.begin() as conn:
                        conn.exec_driver_sql('PRAGMA busy_timeout=15000')
                        current = _columns(conn, 'node')
                        if name in current:
                            continue
                        conn.exec_driver_sql(sql)
                        added += 1
                except Exception as exc:
                    if 'duplicate column' in str(exc).lower():
                        continue
                    raise
            if added:
                current_app.logger.info('Node schema guard added %s missing node columns', added)
            return added
        except Exception as exc:
            last_exc = exc
            if 'locked' not in str(exc).lower() or attempt >= retries - 1:
                raise
            try:
                db.session.rollback()
            except Exception:
                pass
            time.sleep(min(0.35 * (attempt + 1), 2.0))
    if last_exc:
        raise last_exc
    return added


def node_schema_error_summary(exc: Exception) -> str:
    msg = str(exc or '').strip().replace('\n', ' ')
    if not msg:
        return 'unknown error'
    if 'no such column' in msg.lower():
        return 'ستون‌های جدید Node هنوز روی دیتابیس ساخته نشده‌اند. اسکریپت upgrade_db_safe یا Schema Guard باید اجرا شود.'
    if 'database is locked' in msg.lower():
        return 'دیتابیس SQLite قفل است. سرویس‌های پنل/بات را موقتاً stop کن و upgrade_db_safe را اجرا کن.'
    return msg[:300]

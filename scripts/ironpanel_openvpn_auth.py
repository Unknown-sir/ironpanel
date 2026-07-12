#!/usr/bin/env python3
"""IronPanel OpenVPN certificate gate.

This script is called by OpenVPN client-connect. It intentionally avoids
`source`-ing /etc/ironpanel/ironpanel.env because admin-entered values can
contain spaces or non-ASCII text. A broken env file must never turn into a
false AUTH_FAILED for valid certificate users.
"""
import datetime as _dt
import os
import re
import sqlite3
import sys
from pathlib import Path

LOG_PATH = Path('/var/log/openvpn/ironpanel-auth.log')


def log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        now = _dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        with LOG_PATH.open('a', encoding='utf-8') as f:
            f.write(f'[{now}] {message}\n')
    except Exception:
        pass


def parse_env_file(path='/etc/ironpanel/ironpanel.env'):
    vals = {}
    p = Path(path)
    if not p.exists():
        return vals
    for raw in p.read_text(errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        vals[key] = value
    return vals


def db_path() -> str:
    vals = parse_env_file()
    url = os.environ.get('DATABASE_URL') or vals.get('DATABASE_URL') or 'sqlite:////etc/ironpanel/ironpanel.db'
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', '', 1)
    return '/etc/ironpanel/ironpanel.db'


def safe_cn(username: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', username or 'user')[:64] or 'user'

def openvpn_cn(user_id, username: str) -> str:
    try:
        uid = int(user_id or 0)
    except Exception:
        uid = 0
    base = safe_cn(username)
    return f'ip{uid}-{base}'[:64] if uid else base


def table_columns(cur, table: str):
    try:
        cur.execute(f'PRAGMA table_info({table})')
        return {row[1] for row in cur.fetchall()}
    except Exception:
        return set()


def get_value(row, columns, name, default=None):
    if name not in columns:
        return default
    return row[columns.index(name)]


def parse_dt(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return _dt.datetime.strptime(text.replace('Z', ''), fmt)
        except Exception:
            pass
    try:
        return _dt.datetime.fromisoformat(text.replace('Z', '').replace('T', ' '))
    except Exception:
        return None


def find_user(cur, identity: str):
    cols = list(table_columns(cur, 'vpn_user'))
    if not cols:
        return None, cols
    # Stable order for row indexing.
    wanted = ['id', 'username', 'enabled', 'expires_at', 'data_limit_mb', 'used_upload_mb', 'used_download_mb', 'used_upload_bytes', 'used_download_bytes', 'protocols', 'protocol_permissions']
    selected = [c for c in wanted if c in cols]
    cur.execute(f"SELECT {','.join(selected)} FROM vpn_user")
    rows = cur.fetchall()
    selected_cols = selected
    ident = identity or ''
    for row in rows:
        username = str(get_value(row, selected_cols, 'username', '') or '')
        user_id = get_value(row, selected_cols, 'id', 0)
        if username == ident or safe_cn(username) == ident or openvpn_cn(user_id, username) == ident:
            return row, selected_cols
    return None, selected_cols


def ensure_online_schema(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS online_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username VARCHAR(80) NOT NULL,
        protocol VARCHAR(40) DEFAULT 'unknown',
        remote_ip VARCHAR(80) DEFAULT '',
        country VARCHAR(80) DEFAULT 'Unknown',
        device_id VARCHAR(128) DEFAULT '',
        node_id INTEGER,
        connected_at DATETIME,
        last_seen DATETIME,
        active BOOLEAN DEFAULT 1
    )''')


def country(ip: str) -> str:
    if not ip:
        return 'Unknown'
    private_prefixes = ('10.', '192.168.', '127.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.')
    return 'Private' if ip.startswith(private_prefixes) else 'Unknown'


def record_connect(cur, user_id, username, remote_ip, device_id):
    ensure_online_schema(cur)
    now = _dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute('''SELECT id FROM online_session
                   WHERE username=? AND protocol='openvpn' AND active=1
                     AND COALESCE(remote_ip,'')=? AND COALESCE(device_id,'')=?
                   ORDER BY id DESC LIMIT 1''', (username, remote_ip, device_id))
    row = cur.fetchone()
    if row:
        cur.execute('''UPDATE online_session SET user_id=?, last_seen=?, country=?, remote_ip=?, device_id=?, active=1 WHERE id=?''',
                    (user_id, now, country(remote_ip), remote_ip, device_id, row[0]))
    else:
        cur.execute('''INSERT INTO online_session(user_id,username,protocol,remote_ip,country,device_id,connected_at,last_seen,active)
                       VALUES(?,?,?,?,?,?,?,?,1)''',
                    (user_id, username, 'openvpn', remote_ip, country(remote_ip), device_id, now, now))


def main():
    identity = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('common_name') or os.environ.get('username') or ''
    remote_ip = (sys.argv[2] if len(sys.argv) > 2 else os.environ.get('trusted_ip') or os.environ.get('untrusted_ip') or '').split(':')[0].strip('[]')
    device_id = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('ifconfig_pool_remote_ip') or os.environ.get('trusted_port') or ''
    if not identity:
        log('deny: missing common_name')
        return 1
    db = db_path()
    if not Path(db).exists():
        log(f'deny {identity}: db not found: {db}')
        return 1
    try:
        con = sqlite3.connect(db, timeout=10)
        cur = con.cursor()
        row, cols = find_user(cur, identity)
        if not row:
            log(f'deny {identity}: user not found; check certificate CN vs IronPanel username')
            return 1
        user_id = int(get_value(row, cols, 'id', 0) or 0)
        username = str(get_value(row, cols, 'username', identity) or identity)
        enabled = int(get_value(row, cols, 'enabled', 1) if get_value(row, cols, 'enabled', 1) is not None else 1)
        if enabled != 1:
            log(f'deny {identity}/{username}: disabled')
            return 1
        protocols = str(get_value(row, cols, 'protocol_permissions', '') or get_value(row, cols, 'protocols', '') or 'openvpn')
        if protocols and 'openvpn' not in [p.strip() for p in protocols.split(',') if p.strip()]:
            log(f'deny {identity}/{username}: openvpn not allowed')
            return 1
        expires = parse_dt(get_value(row, cols, 'expires_at', None))
        if expires and expires < _dt.datetime.utcnow():
            log(f'deny {identity}/{username}: expired {expires}')
            return 1
        limit_mb = int(get_value(row, cols, 'data_limit_mb', 0) or 0)
        up_bytes = int(get_value(row, cols, 'used_upload_bytes', 0) or 0)
        down_bytes = int(get_value(row, cols, 'used_download_bytes', 0) or 0)
        if up_bytes == 0:
            up_bytes = int(get_value(row, cols, 'used_upload_mb', 0) or 0) * 1024 * 1024
        if down_bytes == 0:
            down_bytes = int(get_value(row, cols, 'used_download_mb', 0) or 0) * 1024 * 1024
        if limit_mb > 0 and (up_bytes + down_bytes) >= limit_mb * 1024 * 1024:
            log(f'deny {identity}/{username}: traffic limit reached')
            return 1
        try:
            record_connect(cur, user_id, username, remote_ip, device_id)
            con.commit()
        except Exception as rec_exc:
            # Never reject an otherwise valid certificate only because online-session accounting failed.
            # Common cause: OpenVPN still running an old config with user/group privilege drop.
            log(f'allow {identity}/{username}: session record failed but access is valid: {rec_exc!r}')
        finally:
            try:
                con.close()
            except Exception:
                pass
        log(f'allow {identity}/{username}: {remote_ip} {device_id}')
        return 0
    except Exception as exc:
        # Fail closed only for explicit policy checks above; unexpected DB/schema errors should be visible.
        # To avoid breaking all OpenVPN users during a panel migration, allow when the certificate itself is valid
        # and log the issue for Health Check / Repair.
        log(f'allow {identity}: auth script internal error, certificate accepted by OpenVPN CA: {exc!r}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())

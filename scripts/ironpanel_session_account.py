#!/usr/bin/env python3
"""Record VPN online/offline sessions from daemon hooks.

Usage:
  ironpanel_session_account.py connect openvpn USER REMOTE_IP DEVICE_ID
  ironpanel_session_account.py disconnect openvpn USER REMOTE_IP DEVICE_ID

It uses SQLite directly so it can be safely called from OpenVPN/pppd hooks
without importing the full Flask app.
"""
import os, sqlite3, sys, datetime, re


def db_path():
    env = '/etc/ironpanel/ironpanel.env'
    vals = {}
    if os.path.exists(env):
        for line in open(env, errors='ignore'):
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.strip().split('=', 1)
                vals[k] = v.strip().strip('"')
    url = os.environ.get('DATABASE_URL') or vals.get('DATABASE_URL') or 'sqlite:////etc/ironpanel/ironpanel.db'
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', '', 1)
    return '/etc/ironpanel/ironpanel.db'


def safe_cn(username):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', username or 'user')[:64] or 'user'


def ensure_schema(cur):
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
    cur.execute('''CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor VARCHAR(120) NOT NULL,
        action VARCHAR(80) NOT NULL,
        target VARCHAR(120),
        details TEXT,
        created_at DATETIME
    )''')


def find_user(cur, identity):
    ident = identity or ''
    cur.execute('SELECT id, username, COALESCE(enabled,1), COALESCE(expires_at,\'\') FROM vpn_user WHERE username=? LIMIT 1', (ident,))
    row = cur.fetchone()
    if row:
        return row
    safe = safe_cn(ident)
    cur.execute('SELECT id, username, COALESCE(enabled,1), COALESCE(expires_at,\'\') FROM vpn_user')
    for row in cur.fetchall():
        if safe_cn(row[1]) == safe:
            return row
    return None


def country(ip):
    if not ip or ip.startswith(('10.', '192.168.', '127.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.')):
        return 'Private'
    return 'Unknown'


def main():
    if len(sys.argv) < 4:
        return 0
    action = sys.argv[1].lower()
    protocol = sys.argv[2].lower()
    identity = sys.argv[3]
    remote_ip = (sys.argv[4] if len(sys.argv) > 4 else '').split(':')[0].strip('[]')
    device_id = sys.argv[5] if len(sys.argv) > 5 else ''
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    db = db_path()
    if not os.path.exists(db):
        return 0
    con = sqlite3.connect(db, timeout=10)
    cur = con.cursor()
    ensure_schema(cur)
    user = find_user(cur, identity)
    username = user[1] if user else identity
    user_id = user[0] if user else None
    if action == 'connect' or action == 'seen':
        # Reuse an active row for the same user/protocol/device/remote, otherwise create one.
        cur.execute('''SELECT id FROM online_session
                       WHERE username=? AND protocol=? AND active=1
                         AND COALESCE(remote_ip,'')=? AND COALESCE(device_id,'')=?
                       ORDER BY id DESC LIMIT 1''', (username, protocol, remote_ip, device_id))
        row = cur.fetchone()
        if row:
            cur.execute('''UPDATE online_session SET user_id=?, last_seen=?, country=?, remote_ip=?, device_id=?, active=1 WHERE id=?''',
                        (user_id, now, country(remote_ip), remote_ip, device_id, row[0]))
        else:
            cur.execute('''INSERT INTO online_session(user_id,username,protocol,remote_ip,country,device_id,connected_at,last_seen,active)
                           VALUES(?,?,?,?,?,?,?,?,1)''',
                        (user_id, username, protocol, remote_ip, country(remote_ip), device_id, now, now))
    elif action == 'disconnect':
        cur.execute('''UPDATE online_session SET active=0,last_seen=?
                       WHERE username=? AND protocol=? AND active=1
                         AND (?='' OR COALESCE(remote_ip,'')=? OR COALESCE(device_id,'')=?)''',
                    (now, username, protocol, remote_ip, remote_ip, device_id))
    con.commit(); con.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

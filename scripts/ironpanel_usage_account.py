#!/usr/bin/env python3
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

def ensure_columns(cur):
    cols = {r[1] for r in cur.execute('PRAGMA table_info(vpn_user)').fetchall()}
    if 'used_upload_bytes' not in cols:
        cur.execute('ALTER TABLE vpn_user ADD COLUMN used_upload_bytes BIGINT DEFAULT 0')
    if 'used_download_bytes' not in cols:
        cur.execute('ALTER TABLE vpn_user ADD COLUMN used_download_bytes BIGINT DEFAULT 0')

def upsert_setting(cur, key, value):
    cur.execute('SELECT id FROM app_setting WHERE key=?', (key,))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE app_setting SET value=? WHERE key=?', (str(value), key))
    else:
        cur.execute('INSERT INTO app_setting(key,value,updated_at) VALUES(?,?,?)', (key, str(value), datetime.datetime.utcnow().isoformat()))

def get_setting(cur, key, default=''):
    try:
        cur.execute('SELECT value FROM app_setting WHERE key=?', (key,))
        row = cur.fetchone()
        return row[0] if row and row[0] not in (None, '') else default
    except Exception:
        return default

def traffic_multiplier_factor(cur):
    enabled = str(get_setting(cur, 'traffic_multiplier_enabled', '0')).lower() in ('1', 'true', 'yes', 'on')
    if not enabled:
        return 1.0
    try:
        factor = float(str(get_setting(cur, 'traffic_multiplier_value', '1')).replace(',', '.'))
    except Exception:
        factor = 1.0
    if factor <= 0:
        factor = 1.0
    return max(0.01, min(100.0, factor))

def effective_usage_bytes(cur, raw_bytes):
    return int(max(0, int(raw_bytes or 0)) * traffic_multiplier_factor(cur) + 0.999999)

def main():
    if len(sys.argv) < 5:
        return 0
    source, identity, rx_s, tx_s = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    try:
        rx, tx = int(rx_s or 0), int(tx_s or 0)
    except Exception:
        return 0
    con = sqlite3.connect(db_path(), timeout=10)
    cur = con.cursor()
    ensure_columns(cur)
    cur.execute('SELECT id, username, COALESCE(used_upload_bytes, COALESCE(used_upload_mb,0)*1048576,0), COALESCE(used_download_bytes, COALESCE(used_download_mb,0)*1048576,0), COALESCE(data_limit_mb,0), COALESCE(enabled,1) FROM vpn_user')
    user = None
    for row in cur.fetchall():
        if row[1] == identity or safe_cn(row[1]) == identity:
            user = row
            break
    if not user:
        con.close(); return 0
    uid, username, up0, down0, limit_mb, enabled = user
    key = f'usage_last_{source}_{uid}'
    cur.execute('SELECT value FROM app_setting WHERE key=?', (key,))
    old = (cur.fetchone() or ['0:0'])[0]
    try:
        old_rx, old_tx = [int(x or 0) for x in str(old).split(':', 1)]
    except Exception:
        old_rx, old_tx = 0, 0
    d_rx = rx - old_rx if rx >= old_rx else rx
    d_tx = tx - old_tx if tx >= old_tx else tx
    new_up = int(up0 or 0) + max(0, d_rx)
    new_down = int(down0 or 0) + max(0, d_tx)
    cur.execute('UPDATE vpn_user SET used_upload_bytes=?, used_download_bytes=?, used_upload_mb=?, used_download_mb=? WHERE id=?', (new_up, new_down, new_up//1048576, new_down//1048576, uid))
    upsert_setting(cur, key, f'{rx}:{tx}')
    day = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    cur.execute('SELECT id FROM daily_usage WHERE user_id=? AND day=?', (uid, day))
    du = cur.fetchone()
    if du:
        cur.execute('UPDATE daily_usage SET upload_mb=COALESCE(upload_mb,0)+?, download_mb=COALESCE(download_mb,0)+? WHERE id=?', (max(0,d_rx)//1048576, max(0,d_tx)//1048576, du[0]))
    else:
        cur.execute('INSERT INTO daily_usage(user_id,day,upload_mb,download_mb) VALUES(?,?,?,?)', (uid, day, max(0,d_rx)//1048576, max(0,d_tx)//1048576))
    raw_total = new_up + new_down
    charged_total = effective_usage_bytes(cur, raw_total)
    if int(limit_mb or 0) > 0 and charged_total >= int(limit_mb) * 1048576 and int(enabled or 0) == 1:
        cur.execute('UPDATE vpn_user SET enabled=0 WHERE id=?', (uid,))
        details = f'traffic_limit; raw={raw_total}; charged={charged_total}; multiplier={traffic_multiplier_factor(cur):g}'
        cur.execute('INSERT INTO activity_log(actor,action,target,details,created_at) VALUES(?,?,?,?,?)', ('system','auto_disable_user',username,details,datetime.datetime.utcnow().isoformat()))
    con.commit(); con.close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

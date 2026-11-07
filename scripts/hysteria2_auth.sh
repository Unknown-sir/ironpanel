#!/usr/bin/env bash
set -euo pipefail
# Hysteria2 command auth receives: addr auth tx
ADDR="${1:-}"
PASS="${2:-}"
TX="${3:-0}"
if [[ -z "$PASS" ]]; then read -r PASS || true; fi
export PASS ADDR TX
python3 - <<'PY'
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

password = (os.environ.get('PASS') or '').strip()
if not password:
    raise SystemExit(1)

def parse_dt(value):
    if not value:
        return None
    text = str(value).strip().replace('Z', '')
    try:
        return dt.datetime.fromisoformat(text.replace('T', ' '))
    except Exception:
        return None

def active(row):
    if not bool(row.get('enabled', True)):
        return False
    expires = parse_dt(row.get('expires_at'))
    if expires and expires < dt.datetime.utcnow():
        return False
    try:
        limit = int(row.get('data_limit_mb') or 0) * 1024 * 1024
        used = int(row.get('quota_used_bytes') or 0) or (int(row.get('used_upload_bytes') or 0) + int(row.get('used_download_bytes') or 0))
    except Exception:
        limit = used = 0
    return not (limit > 0 and used >= limit)

# Remote nodes use compact master-synchronized metadata. No Flask application or
# full IronPanel database is required on the node.
root = Path('/etc/ironpanel-node/users')
if root.is_dir():
    for path in root.glob('*.hysteria2.json'):
        try:
            row = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if active(row) and str(row.get('hysteria2_password') or '') == password:
            print(str(row.get('username') or 'ironpanel-user'))
            raise SystemExit(0)
    raise SystemExit(1)

# Main-server/local fallback for installations that invoke this script directly.
def env_db_path():
    env = Path('/etc/ironpanel/ironpanel.env')
    vals = {}
    if env.exists():
        for raw in env.read_text(errors='ignore').splitlines():
            if '=' not in raw or raw.lstrip().startswith('#'):
                continue
            k, v = raw.split('=', 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    url = os.environ.get('DATABASE_URL') or vals.get('DATABASE_URL') or 'sqlite:////etc/ironpanel/ironpanel.db'
    return url.replace('sqlite:///', '', 1) if url.startswith('sqlite:///') else '/etc/ironpanel/ironpanel.db'

db = Path(env_db_path())
if not db.exists():
    raise SystemExit(1)
con = sqlite3.connect(str(db), timeout=8)
con.row_factory = sqlite3.Row
cur = con.cursor()
try:
    cur.execute("SELECT value FROM app_setting WHERE key='hysteria2_obfs_password'")
    setting = cur.fetchone()
    obfs = str(setting[0] if setting else '')
except Exception:
    obfs = ''
try:
    rows = cur.execute('SELECT * FROM vpn_user').fetchall()
except Exception:
    rows = []
for dbrow in rows:
    row = dict(dbrow)
    protocols = str(row.get('protocol_permissions') or row.get('protocols') or '')
    if protocols and 'hysteria2' not in [x.strip() for x in protocols.split(',') if x.strip()]:
        continue
    expected = hashlib.sha256(f"{row.get('subscription_token') or ''}:{row.get('username') or ''}:{obfs}".encode()).hexdigest()[:32]
    if expected == password and active(row):
        print(str(row.get('username') or 'ironpanel-user'))
        con.close()
        raise SystemExit(0)
con.close()
raise SystemExit(1)
PY

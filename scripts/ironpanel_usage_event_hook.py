#!/usr/bin/env python3
"""Non-blocking runtime traffic event hook for Ocserv and PPP.

The hook never opens the panel database. It only writes small atomic JSON files,
so authentication/session teardown cannot fail when the panel is busy. The main
collector or node agent consumes the files and applies idempotent counters.
"""
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

EVENT_DIR = Path('/var/lib/ironpanel/usage-events')
PPP_STATE_DIR = Path('/run/ironpanel-ppp')


def _num(name, default=0):
    try:
        return max(0, int(str(os.environ.get(name, default) or default).strip()))
    except Exception:
        return 0


def _safe(value, fallback='session'):
    text = re.sub(r'[^A-Za-z0-9_.:-]+', '_', str(value or '')).strip('_.:-')
    return (text[:120] or fallback)


def _atomic_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _write_event(protocol, username, source, rx, tx, extra=None):
    if not username:
        return
    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(EVENT_DIR, 0o700)
    except Exception:
        pass
    payload = {
        'version': 1,
        'protocol': _safe(protocol, 'unknown').lower(),
        'username': str(username).strip(),
        'source': _safe(source, protocol),
        'rx': max(0, int(rx or 0)),
        'tx': max(0, int(tx or 0)),
        'created_at': int(time.time()),
    }
    if isinstance(extra, dict):
        payload.update(extra)
    name = f"{int(time.time()*1000)}-{os.getpid()}-{secrets.token_hex(4)}.json"
    _atomic_json(EVENT_DIR / name, payload)


def _ppp_context():
    iface = _safe(os.environ.get('IFNAME') or (sys.argv[2] if len(sys.argv) > 2 else '') or 'ppp')
    ipparam = str(os.environ.get('IPPARAM') or '').lower()
    protocol = 'pptp' if 'pptp' in ipparam else 'l2tp'
    username = (os.environ.get('PEERNAME') or os.environ.get('PPP_PEER') or '').strip()
    source = f'ppp_{protocol}_{iface}'
    return iface, protocol, username, source


def ppp_up():
    iface, protocol, username, source = _ppp_context()
    if not username:
        return
    source = f'ppp_{protocol}_{iface}_{int(time.time())}_{secrets.token_hex(3)}'
    payload = {
        'version': 1, 'protocol': protocol, 'username': username,
        'source': source, 'interface': iface, 'created_at': int(time.time()),
    }
    _atomic_json(PPP_STATE_DIR / f'{iface}.json', payload)


def ppp_down():
    iface, protocol, username, source = _ppp_context()
    state_path = PPP_STATE_DIR / f'{iface}.json'
    try:
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding='utf-8'))
            username = username or str(state.get('username') or '')
            protocol = str(state.get('protocol') or protocol)
            source = str(state.get('source') or source)
    except Exception:
        pass
    # pppd exposes bytes received from the peer and bytes sent to the peer.
    rx = _num('BYTES_RCVD', _num('BYTES_RECEIVED', 0))
    tx = _num('BYTES_SENT', 0)
    _write_event(protocol, username, source, rx, tx, {'interface': iface, 'event': 'disconnect'})
    try:
        state_path.unlink(missing_ok=True)
    except Exception:
        pass


def ocserv_disconnect():
    if str(os.environ.get('REASON') or '').lower() not in ('disconnect', 'user-disconnect', 'server-disconnect'):
        return
    username = (os.environ.get('USERNAME') or os.environ.get('USER') or '').strip()
    session = (os.environ.get('ID') or os.environ.get('SESSION_ID') or
               os.environ.get('DEVICE') or os.environ.get('IP_REMOTE') or username)
    source = f'ocserv_{_safe(session, username or "session")}'
    _write_event('ocserv', username, source, _num('STATS_BYTES_IN'), _num('STATS_BYTES_OUT'),
                 {'event': 'disconnect', 'session_id': str(session or '')})


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else '').strip().lower()
    try:
        if mode == 'ppp-up':
            ppp_up()
        elif mode == 'ppp-down':
            ppp_down()
        elif mode in ('ocserv', 'ocserv-disconnect'):
            ocserv_disconnect()
    except Exception:
        # Session hooks must never break VPN authentication or teardown.
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

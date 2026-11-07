"""GeoIP / GeoSite manager for Xray routing files."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any

from flask import current_app

from ..core.extensions import db
from ..core.models import AppSetting

GEO_DIR = Path('/usr/local/share/xray')
GEO_SOURCES = {
    'loyalsoldier': {
        'title': 'Loyalsoldier v2ray-rules-dat',
        'geoip': 'https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat',
        'geosite': 'https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat',
    },
    'v2fly': {
        'title': 'V2Fly official community files',
        'geoip': 'https://github.com/v2fly/geoip/releases/latest/download/geoip.dat',
        'geosite': 'https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat',
    },
}


def run_cmd(cmd):
    try:
        return subprocess.run(cmd, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, '', str(exc))


def _setting(key: str, default: str = '') -> str:
    row = AppSetting.query.filter_by(key=key).first()
    return row.value if row and row.value not in (None, '') else default


def _set(key: str, value: str):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        row = AppSetting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)
    db.session.commit()
    return row


def _file_info(name: str) -> Dict[str, Any]:
    p = GEO_DIR / name
    if not p.exists():
        return {'exists': False, 'path': str(p), 'size': 0, 'size_human': 'ندارد', 'mtime': ''}
    size = p.stat().st_size
    return {
        'exists': True,
        'path': str(p),
        'size': size,
        'size_human': f'{size/1024/1024:.2f} MB',
        'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.stat().st_mtime)),
    }


def geofile_status() -> Dict[str, Any]:
    return {
        'dir': str(GEO_DIR),
        'source': _setting('geofile_source', 'loyalsoldier'),
        'sources': GEO_SOURCES,
        'geoip': _file_info('geoip.dat'),
        'geosite': _file_info('geosite.dat'),
        'last_update': _setting('geofile_last_update', ''),
        'last_error': _setting('geofile_last_error', ''),
    }


def _download(url: str, target: Path) -> tuple[bool, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + '.tmp')
    tmp.unlink(missing_ok=True)
    quoted_url = url.replace("'", "'\\''")
    quoted_tmp = str(tmp).replace("'", "'\\''")
    cmd = ['bash', '-lc', f"curl -L --fail --connect-timeout 15 --max-time 120 -o '{quoted_tmp}' '{quoted_url}' || wget -O '{quoted_tmp}' '{quoted_url}'"]
    p = run_cmd(cmd)
    out = ((p.stdout or '') + '\n' + (p.stderr or '')).strip()
    if p.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 1024:
        tmp.unlink(missing_ok=True)
        return False, out[-2000:] or 'download failed'
    shutil.move(str(tmp), str(target))
    try:
        target.chmod(0o644)
    except Exception:
        pass
    return True, f'{target.name} updated ({target.stat().st_size} bytes)'


def update_geofiles(source: str = 'loyalsoldier') -> Dict[str, Any]:
    source = source if source in GEO_SOURCES else 'loyalsoldier'
    urls = GEO_SOURCES[source]
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    logs = []
    ok1, msg1 = _download(urls['geoip'], GEO_DIR / 'geoip.dat')
    logs.append(msg1)
    ok2, msg2 = _download(urls['geosite'], GEO_DIR / 'geosite.dat')
    logs.append(msg2)
    _set('geofile_source', source)
    if ok1 and ok2:
        _set('geofile_last_update', time.strftime('%Y-%m-%d %H:%M:%S'))
        _set('geofile_last_error', '')
        run_cmd(['bash', '-lc', 'systemctl restart xray >/dev/null 2>&1 || true'])
        return {'ok': True, 'message': 'GeoIP/GeoSite آپدیت شد و Xray ری‌استارت شد.', 'log': '\n'.join(logs)}
    _set('geofile_last_error', '\n'.join(logs)[-3000:])
    return {'ok': False, 'message': 'آپدیت GeoFile کامل نشد.', 'log': '\n'.join(logs)}

from __future__ import annotations
from io import BytesIO
from datetime import datetime
import qrcode
import socket

COUNTRY_HINTS = {
    '10.': 'Private', '172.16.': 'Private', '192.168.': 'Private', '127.': 'Localhost'
}

def geoip_country(ip: str) -> str:
    if not ip:
        return 'Unknown'
    for prefix, country in COUNTRY_HINTS.items():
        if ip.startswith(prefix):
            return country
    # Offline best-effort placeholder. Production installs may replace this with MaxMind/GeoLite2.
    return 'Internet'

def make_qr_png(data: str) -> bytes:
    img = qrcode.make(data or '')
    bio = BytesIO()
    img.save(bio, format='PNG')
    return bio.getvalue()

def hostname_ok(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False

def openapi_spec(base_url: str = '') -> dict:
    return {
        'openapi': '3.0.3',
        'info': {'title': 'IronPanel API', 'version': '11.0.0'},
        'servers': [{'url': base_url or '/api/v2'}],
        'paths': {
            '/users': {'get': {'summary': 'List VPN users'}, 'post': {'summary': 'Create VPN user'}},
            '/users/{id}': {'get': {'summary': 'Read VPN user'}, 'patch': {'summary': 'Edit VPN user'}, 'delete': {'summary': 'Delete VPN user'}},
            '/users/{id}/reset-traffic': {'post': {'summary': 'Reset traffic'}},
            '/metrics': {'get': {'summary': 'Realtime server metrics'}},
            '/health': {'get': {'summary': 'VPN core health'}},
        },
        'components': {'securitySchemes': {'ApiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-KEY'}}},
    }

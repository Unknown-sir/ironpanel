"""Shared helpers, background refreshers and app-wide hooks for the web UI.

This module keeps the cross-cutting pieces that every domain module needs:
usage/session background collectors, reseller capacity helpers, protocol
permission helpers and the blueprint-wide before/after/context hooks.
"""
import re
import secrets
import threading
import time
from datetime import datetime, timedelta

from flask import current_app, flash, redirect, request, url_for
from flask_login import current_user, logout_user

from ..core.extensions import db
from ..core.models import Admin, DnsProfile, OnlineSession, VpnUser
from ..services.provisioning import (
    active_protocols,
    collect_usage_from_runtime,
    get_port,
    get_public_host,
    get_setting,
    normalize_user_protocols,
    set_setting,
)
from ..services.license import (
    allowed_protocols_for_license,
    check_license,
    current_license_features,
    current_license_type,
    feature_allowed,
    feature_label,
    filter_protocols_for_license,
    is_free_edition,
    paid_license_active,
)
from ..services.i18n import (
    LANGUAGES,
    THEMES,
    current_language,
    current_theme,
    language_dir,
    localize_hardcoded_text,
    t,
    ui,
)
from ..services.node_auto_installer import node_auto_installer_allowed, node_has_saved_ssh_credentials
from ..services.v10 import refresh_online_sessions

from . import web_bp


_USAGE_COLLECT_LAST_TS = 0.0
_USAGE_COLLECT_LOCK = threading.Lock()


def _collect_usage_background(throttle_seconds=45):
    """Start traffic accounting in the background for read-only web pages.

    User creation/deletion used to feel slow because the next page load ran full
    runtime accounting synchronously. A systemd timer already accounts traffic;
    this helper only refreshes opportunistically and never blocks the request.
    """
    global _USAGE_COLLECT_LAST_TS
    now = time.time()
    with _USAGE_COLLECT_LOCK:
        if now - _USAGE_COLLECT_LAST_TS < throttle_seconds:
            return False
        _USAGE_COLLECT_LAST_TS = now
    try:
        app = current_app._get_current_object()
    except Exception:
        return False

    def _worker():
        try:
            with app.app_context():
                collect_usage_from_runtime()
        except Exception:
            pass

    threading.Thread(target=_worker, name='ironpanel-usage-collect', daemon=True).start()
    return True


def _collect_usage_for_view(throttle_seconds=8):
    """Refresh accounting before traffic-sensitive pages are rendered.

    The previous background-only refresh returned stale ORM values in the same
    request. This bounded synchronous path is protected by both a thread lock
    and the collector process lock, then expires ORM state before rendering.
    """
    global _USAGE_COLLECT_LAST_TS
    now = time.time()
    if now - _USAGE_COLLECT_LAST_TS < max(0, throttle_seconds):
        return False
    if not _USAGE_COLLECT_LOCK.acquire(blocking=False):
        return False
    try:
        now = time.time()
        if now - _USAGE_COLLECT_LAST_TS < max(0, throttle_seconds):
            return False
        collect_usage_from_runtime()
        _USAGE_COLLECT_LAST_TS = time.time()
        try:
            db.session.expire_all()
        except Exception:
            pass
        return True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False
    finally:
        _USAGE_COLLECT_LOCK.release()


_SESSIONS_REFRESH_LAST_TS = 0.0
_SESSIONS_REFRESH_LOCK = threading.Lock()

def _refresh_sessions_background(throttle_seconds=30):
    """Refresh online sessions in the background so dashboard loads fast."""
    global _SESSIONS_REFRESH_LAST_TS
    now = time.time()
    with _SESSIONS_REFRESH_LOCK:
        if now - _SESSIONS_REFRESH_LAST_TS < throttle_seconds:
            return False
        _SESSIONS_REFRESH_LAST_TS = now
    try:
        app = current_app._get_current_object()
    except Exception:
        return False
    def _worker():
        try:
            with app.app_context():
                refresh_online_sessions()
        except Exception:
            pass
    threading.Thread(target=_worker, name='ironpanel-online-refresh', daemon=True).start()
    return True

def _online_sessions_snapshot(limit=200):
    try:
        stale_before = datetime.utcnow() - timedelta(minutes=12)
        OnlineSession.query.filter(OnlineSession.last_seen < stale_before, OnlineSession.active == True).update({'active': False})
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Return both: unique user count and full session list for details
    users_with_sessions = db.session.query(OnlineSession.user_id).filter_by(active=True).distinct().count()
    sessions = OnlineSession.query.filter_by(active=True).order_by(OnlineSession.last_seen.desc()).limit(limit).all()
    return users_with_sessions, sessions


# Reseller panel helpers ------------------------------------------------------

RESERVED_RESELLER_PATHS = {
    'dashboard','users','user','static','login','logout','api','api-v2','subscription','sub','settings',
    'resellers','reseller','r','admin-bot','sales-bot','upgrade','updates','health','monitoring','sessions'
}

def _normalize_reseller_path(raw, username='', exclude_id=None):
    base = (raw or username or '').strip().strip('/')
    base = re.sub(r'[^a-zA-Z0-9_-]+', '-', base).strip('-_').lower()
    if not base:
        base = f"reseller-{secrets.token_hex(3)}"
    if base in RESERVED_RESELLER_PATHS:
        base = f"r-{base}"
    candidate = base
    i = 2
    while Admin.query.filter(Admin.role == 'sub_admin', Admin.panel_path == candidate, Admin.id != (exclude_id or 0)).first():
        candidate = f"{base}-{i}"
        i += 1
    return candidate

def _panel_base_url():
    root = (request.url_root or '').rstrip('/')
    if root:
        return root
    host = get_public_host() or 'SERVER_IP'
    if str(host).startswith(('http://', 'https://')):
        return str(host).rstrip('/')
    return f"http://{host}:{get_port('panel')}"

def reseller_panel_url(reseller):
    slug = getattr(reseller, 'panel_path', '') or _normalize_reseller_path('', getattr(reseller, 'username', 'reseller'), getattr(reseller, 'id', None))
    return f"{_panel_base_url()}/r/{slug}"

def _reseller_stats(reseller):
    users = VpnUser.query.filter_by(owner_id=reseller.id).all()
    allocated_mb = sum(int(u.data_limit_mb or 0) for u in users)
    live_used_mb = sum(int(u.used_total_mb or 0) for u in users)
    ledger_bytes = int(getattr(reseller, 'reseller_used_bytes', 0) or 0)
    ledger_gb = round(ledger_bytes / (1024 * 1024 * 1024), 2)
    quota_gb = int(reseller.traffic_quota_gb or 0)
    return dict(
        user_count=len(users),
        user_limit=int(reseller.user_limit or 0),
        traffic_quota_gb=quota_gb,
        allocated_gb=round(allocated_mb / 1024, 2),
        used_gb=ledger_gb,
        live_used_gb=round(live_used_mb / 1024, 2),
        reseller_used_bytes=ledger_bytes,
        remaining_users=None if not reseller.user_limit else max(int(reseller.user_limit or 0) - len(users), 0),
        remaining_gb=None if not quota_gb else max(round(float(quota_gb) - ledger_gb, 2), 0),
    )

def _check_reseller_capacity(new_data_limit_mb=0, user_delta=1):
    if not current_user.is_authenticated or current_user.role != 'sub_admin':
        return True, ''
    if not bool(getattr(current_user, 'enabled', True)):
        return False, 'پنل نماینده شما توسط مدیر متوقف شده است.'
    stats = _reseller_stats(current_user)
    if stats['user_limit'] and stats['user_count'] + int(user_delta or 0) > stats['user_limit']:
        return False, f"سقف تعداد کاربر نماینده تکمیل شده است ({stats['user_count']}/{stats['user_limit']})."
    quota_gb = stats['traffic_quota_gb']
    if quota_gb and stats['used_gb'] >= quota_gb:
        return False, f"سقف حجم مصرفی نماینده تکمیل شده است. مصرف ثبت‌شده: {stats['used_gb']}GB از {quota_gb}GB"
    return True, ''

def _normalize_reseller_protocols(values=None, *, allow_default=False):
    from ..services.provisioning import normalize_user_protocols as _normalize
    selected = filter_protocols_for_license(_normalize(values or [], allow_default=allow_default))
    active = filter_protocols_for_license(normalize_user_protocols(active_protocols() or [], allow_default=True))
    active_set = set(active)
    return [p for p in selected if p in active_set]


def available_protocols_for_current_user():
    """Return protocols the authenticated actor may assign. Main admin sees all licensed protocols."""
    available = _normalize_reseller_protocols(active_protocols() or [], allow_default=True)
    try:
        if current_user.is_authenticated and current_user.role == 'sub_admin':
            allowed = set(_normalize_reseller_protocols(current_user.allowed_protocol_list(), allow_default=True))
            return [p for p in available if p in allowed]
    except Exception:
        pass
    return available


def _allowed_form_protocols(values=None, *, allow_default=False):
    from ..services.provisioning import normalize_user_protocols as _normalize
    requested = filter_protocols_for_license(_normalize(values or [], allow_default=allow_default))
    actor_allowed = available_protocols_for_current_user()
    allowed_set = set(actor_allowed)
    if allow_default and not values:
        return actor_allowed
    return [p for p in requested if p in allowed_set]


def _node_selection_from_form(default_mode='auto'):
    if current_user.role == 'main_admin' and feature_allowed('nodes'):
        return request.form.get('node_mode', default_mode) or default_mode, int(request.form.get('preferred_node_id') or 0) or None
    return 'local', None


def _parse_unlimited_days(value, default_days=30):
    days = int(value or default_days)
    if days <= 0:
        return None
    return datetime.utcnow() + timedelta(days=days)


# Famous DNS presets (DNS manager + settings page) ----------------------------

WIREGUARD_DNS_PRESETS = [
    {'name': 'Cloudflare', 'value': '1.1.1.1, 1.0.0.1', 'note': 'Fast global DNS'},
    {'name': 'Google', 'value': '8.8.8.8, 8.8.4.4', 'note': 'Google Public DNS'},
    {'name': 'Quad9', 'value': '9.9.9.9, 149.112.112.112', 'note': 'Security filtered DNS'},
    {'name': 'OpenDNS', 'value': '208.67.222.222, 208.67.220.220', 'note': 'Cisco OpenDNS'},
    {'name': 'AdGuard', 'value': '94.140.14.14, 94.140.15.15', 'note': 'Ad blocking DNS'},
    {'name': 'DNS.SB', 'value': '185.222.222.222, 45.11.45.11', 'note': 'Privacy-focused DNS'},
    {'name': 'Shecan', 'value': '178.22.122.100, 185.51.200.2', 'note': 'Popular Iran DNS'},
    {'name': 'Electro', 'value': '78.157.42.100, 78.157.42.101', 'note': 'Popular Iran DNS'},
    {'name': 'Begzar', 'value': '185.55.226.26, 185.55.225.25', 'note': 'Popular Iran DNS'},
]


def _ensure_famous_dns_profiles_web():
    changed = False
    has_default = bool(DnsProfile.query.filter_by(is_default=True).first())
    for item in WIREGUARD_DNS_PRESETS:
        parts = [x.strip() for x in item['value'].split(',') if x.strip()]
        primary = parts[0]
        secondary = parts[1] if len(parts) > 1 else ''
        profile = DnsProfile.query.filter_by(name=item['name']).first()
        preferred_default = item['name'] == 'Cloudflare'
        should_default = bool(preferred_default and not has_default)
        if not profile:
            db.session.add(DnsProfile(name=item['name'], primary_dns=primary, secondary_dns=secondary, is_default=should_default))
            changed = True
            if should_default:
                has_default = True
        else:
            if profile.primary_dns != primary or profile.secondary_dns != secondary:
                profile.primary_dns = primary
                profile.secondary_dns = secondary
                changed = True
            if preferred_default and not has_default:
                profile.is_default = True
                has_default = True
                changed = True
    if changed:
        db.session.commit()
    return changed


# Blueprint-wide hooks --------------------------------------------------------

@web_bp.app_context_processor
def inject_globals():
    return dict(
        panel_host=get_public_host,
        active_protocols=active_protocols,
        feature_allowed=feature_allowed,
        license_type=current_license_type,
        license_features=current_license_features,
        paid_license_active=paid_license_active,
        is_free_edition=is_free_edition,
        ui_mode=lambda: get_setting('ui_mode', 'simple'),
        is_simple_ui=lambda: get_setting('ui_mode', 'simple') != 'advanced',
        t=t,
        ui=ui,
        current_language=current_language,
        current_theme=current_theme,
        language_dir=language_dir,
        available_languages=LANGUAGES,
        available_themes=THEMES,
        allowed_protocols_for_license=allowed_protocols_for_license,
        available_protocols=available_protocols_for_current_user,
        node_auto_installer_allowed=node_auto_installer_allowed,
        node_has_saved_ssh_credentials=node_has_saved_ssh_credentials,
        admin_label_by_id=lambda admin_id: ((Admin.query.get(admin_id).username if Admin.query.get(admin_id) else '') if admin_id else ''),
    )


@web_bp.after_app_request
def localize_legacy_persian_ui(response):
    # v19.10.0: remove legacy Persian hard-coded UI text from non-Persian pages.
    try:
        lang = current_language()
        ctype = response.headers.get('Content-Type', '')
        if not lang.startswith('fa') and 'text/html' in ctype and not response.direct_passthrough:
            body = response.get_data(as_text=True)
            fixed = localize_hardcoded_text(body, lang)
            if fixed != body:
                response.set_data(fixed)
                response.headers['Content-Length'] = str(len(response.get_data()))
    except Exception:
        pass
    return response


@web_bp.before_app_request
def enforce_license_features():
    # IronPanel is always operational. Without a paid key it runs as the free
    # Beginner edition; this hook only protects modules unavailable in that tier.
    if (request.path or '').startswith('/static/'):
        return None
    try:
        check_license(force=False)
    except Exception:
        # A licensing outage must never prevent Beginner from loading.
        pass
    if not current_user.is_authenticated:
        return None
    path = request.path or ''
    feature_paths = {
        'nodes': ['/nodes', '/cluster', '/v17/nodes'],
        'network': ['/firewall', '/dns', '/domains'],
        'billing': ['/billing', '/plans', '/wallet', '/invoices'],
        'sales_bot': ['/sales-bot'],
    }
    if current_user.is_authenticated and current_user.role == 'sub_admin' and not bool(getattr(current_user, 'enabled', True)):
        if path not in ('/logout',) and not path.startswith('/static/'):
            logout_user()
            flash('پنل نماینده شما توسط مدیر متوقف شده است.')
            return redirect(url_for('web.login'))
    for feature, prefixes in feature_paths.items():
        if any(path.startswith(prefix) for prefix in prefixes) and not feature_allowed(feature):
            flash(f'این بخش در نسخه فعلی فعال نیست: {feature_label(feature)}. از بخش آپگرید لایسنس مناسب را وارد کنید.')
            return redirect(url_for('web.upgrade'))
    return None

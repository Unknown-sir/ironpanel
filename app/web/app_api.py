"""IronAPP compatibility API (panel v2.2.1+).

Public, token-authenticated JSON endpoints consumed by the open-source
IronAPP Android client (https://github.com/Unknown-sir/IronAPP):

  GET /s/<token>/app.json  -> full user snapshot (quota, expiry, protocols,
                             configs, xray links, subscription URLs)
  GET /s/<token>/status    -> lightweight polling snapshot for quota/expiry

Design notes:
  * The subscription token in the URL *is* the credential (same trust model
    as the existing /s/<token> pages and /s/<token>/raw|clash|singbox feeds).
  * Unlike the raw feeds (which return HTTP 403 when the account is expired
    or out of traffic), ``app.json``/``status`` always answer HTTP 200 for a
    known token and report ``access_ok: false`` + a human reason instead.
    The app MUST refuse to (re)connect while ``access_ok`` is false, and the
    panel keeps enforcing the same gate server-side on every download, QR
    and VPN auth hook, so a modified client cannot bypass quota/expiry.
  * ``expires_at: null`` and ``*_mb: 0`` keep the panel-wide convention and
    mean "unlimited".
"""

from datetime import datetime, timezone

from flask import jsonify, request

from ..core.models import VpnUser
from ..services.provisioning import (
    active_protocols,
    get_subscription_base_url,
    user_access_status,
    user_config_payload,
    user_usage_summary,
)
from . import web_bp

APP_API_MIN_APP_VERSION = "1.0.0"
PANEL_VERSION_FALLBACK = "2.2.1"

# Short English mirrors of the Persian access reasons so the app can render
# either locale without parsing Persian text.
_REASON_EN = {
    "فعال": "active",
    "کاربر غیرفعال است": "disabled",
    "کاربر به صورت دستی غیرفعال است": "disabled by admin",
    "اعتبار کاربر منقضی شده است": "expired",
    "حجم کاربر تمام شده است": "traffic limit reached",
    "کاربر به علت IP Limit غیرفعال شده است": "disabled (IP limit)",
}


def _panel_version():
    try:
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        text = (root / "VERSION").read_text(encoding="utf-8").strip()
        return text or PANEL_VERSION_FALLBACK
    except Exception:
        return PANEL_VERSION_FALLBACK


def _iso(value):
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)
    except Exception:
        return None


def _reason_en(fa_reason):
    if not fa_reason:
        return "unknown"
    if fa_reason in _REASON_EN:
        return _REASON_EN[fa_reason]
    if fa_reason.startswith("غیرفعال به علت اتمام حجم نماینده"):
        return "suspended (reseller traffic quota)"
    if fa_reason.startswith("غیرفعال به علت محدودیت تعداد اکانت نماینده"):
        return "suspended (reseller user limit)"
    if fa_reason.startswith("غیرفعال به علت توقف پنل نماینده"):
        return "suspended (reseller panel stopped)"
    return fa_reason


def _allowed_protocols(user):
    try:
        allowed = user.allowed_protocol_list() or user.protocol_list() or []
    except Exception:
        allowed = []
    try:
        active = set(active_protocols())
    except Exception:
        active = set()
    # Preserve the user's configured order, keep only protocols the panel
    # currently serves.
    return [p for p in allowed if p in active]


def _xray_links(user):
    try:
        from ..services.xray import xray_links

        links = [x for x in (xray_links(user) or []) if str(x).strip()]
        if links:
            return links
    except Exception:
        pass
    try:
        from ..services.xray import xray_link

        single = (xray_link(user) or "").strip()
        if single:
            return [single]
    except Exception:
        pass
    return []


def _subscription_urls(user):
    base = (get_subscription_base_url() or "").rstrip("/")
    page = f"{base}/s/{user.subscription_token}"
    return {
        "page": page,
        "raw": f"{page}/raw",
        "clash": f"{page}/clash",
        "singbox": f"{page}/singbox",
        "hiddify": f"{page}/hiddify",
        "app_json": f"{page}/app.json",
        "status": f"{page}/status",
    }


def _usage_json(user):
    summary = user_usage_summary(user) or {}
    # datetimes are not JSON serialisable; expose ISO strings.
    summary = dict(summary)
    summary["expires_at"] = _iso(summary.get("expires_at") or getattr(user, "expires_at", None))
    return summary


def _snapshot(user, include_configs=True):
    ok, reason = user_access_status(user)
    protocols = _allowed_protocols(user)
    usage = _usage_json(user)
    configs = {}
    links = []
    if ok and include_configs:
        try:
            payload = user_config_payload(user) or {}
            # Never leak the internal disabled marker to the app.
            payload.pop("ACCOUNT_STATUS.txt", None)
            configs = {str(k): str(v or "") for k, v in payload.items()}
        except Exception:
            configs = {}
        links = _xray_links(user)
    return {
        "username": user.username,
        "enabled": bool(getattr(user, "enabled", True)),
        "access_ok": bool(ok),
        "connectable": bool(ok and protocols),
        "access_reason": reason,
        "access_reason_en": _reason_en(reason),
        "protocols": protocols,
        "expires_at": _iso(getattr(user, "expires_at", None)),
        "unlimited_time": getattr(user, "expires_at", None) is None,
        "remaining_days": usage.get("remaining_days"),
        "remaining_seconds": usage.get("remaining_seconds"),
        "usage": usage,
        "subscription": _subscription_urls(user),
        "configs": configs,
        "xray_links": links,
    }


def _audit(user):
    try:
        from ..services.v17 import _audit_subscription

        _audit_subscription(user, "ironapp", request=request)
    except Exception:
        pass


@web_bp.route("/s/<token>/app.json")
def subscription_app_json(token):
    """Full IronAPP snapshot for one subscription token."""
    user = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    _audit(user)
    body = {
        "success": True,
        "app": "ironapp",
        "min_app_version": APP_API_MIN_APP_VERSION,
        "panel_version": _panel_version(),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "user": _snapshot(user, include_configs=True),
    }
    response = jsonify(body)
    response.headers["Cache-Control"] = "no-store"
    return response


@web_bp.route("/s/<token>/status")
def subscription_status(token):
    """Lightweight polling endpoint (quota/expiry gate) for IronAPP."""
    user = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    ok, reason = user_access_status(user)
    usage = _usage_json(user)
    body = {
        "success": True,
        "app": "ironapp",
        "panel_version": _panel_version(),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "username": user.username,
        "access_ok": bool(ok),
        "connectable": bool(ok and _allowed_protocols(user)),
        "access_reason": reason,
        "access_reason_en": _reason_en(reason),
        "protocols": _allowed_protocols(user),
        "expires_at": _iso(getattr(user, "expires_at", None)),
        "remaining_days": usage.get("remaining_days"),
        "remaining_seconds": usage.get("remaining_seconds"),
        "used_bytes": usage.get("used_bytes"),
        "remaining_bytes": usage.get("remaining_bytes"),
        "total_bytes": usage.get("total_bytes"),
        "unlimited_traffic": usage.get("unlimited_traffic"),
        "unlimited_time": getattr(user, "expires_at", None) is None,
    }
    response = jsonify(body)
    response.headers["Cache-Control"] = "no-store"
    return response

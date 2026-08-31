"""Shared helpers for reseller-scoped external-bot APIs (v1/v2/mirzabot/xui).

ApiToken rows may carry an owner_id (a sub_admin) plus an api_type so every
reseller owns its own credentials for each API family. Tokens without an owner
(main-admin tokens) keep unrestricted access. Any create/edit triggered through
an owner-scoped token is blocked while the reseller is volume-gated or at its
user cap, matching the panel/bot behaviour.
"""
from ..core.models import Admin, ApiToken, VpnUser
from ..services.provisioning import reseller_limit_reason


def resolve_api_token(raw=None, allowed_types=None):
    """Resolve a raw secret to an ApiToken and its owner Admin.

    Returns (token_or_None, owner_or_None). owner is None for global
    (main-admin) tokens and for missing/invalid ones; the caller distinguishes
    failures by checking the token object.
    """
    raw = (raw or '').strip()
    if not raw:
        return None, None
    q = ApiToken.query.filter_by(token=raw, enabled=True)
    if allowed_types:
        q = q.filter(ApiToken.api_type.in_(allowed_types))
    tok = q.first()
    if not tok:
        return None, None
    owner = None
    if tok.owner_id:
        owner = Admin.query.filter_by(id=tok.owner_id, role='sub_admin').first()
        if not owner:
            return None, None
    return tok, owner


def volume_gate_reason(owner):
    """Non-empty reason when an owner reseller cannot create/edit, else ''."""
    if not owner or owner.role != 'sub_admin':
        return ''
    if not getattr(owner, 'enabled', True):
        return str(getattr(owner, 'disabled_reason', '') or 'disabled')
    return reseller_limit_reason(owner)


def capacity_reason(owner):
    """Non-empty when the reseller is at its user cap, else ''."""
    if not owner or owner.role != 'sub_admin':
        return ''
    limit = max(0, int(getattr(owner, 'user_limit', 0) or 0))
    if limit and VpnUser.query.filter_by(owner_id=owner.id).count() >= limit:
        return 'user_limit'
    return ''


def create_block_reason(owner):
    """Reason blocking user creation by a reseller, or '' when allowed."""
    return volume_gate_reason(owner) or capacity_reason(owner)


def owner_user_query(owner):
    if owner and owner.role == 'sub_admin':
        return VpnUser.query.filter_by(owner_id=owner.id)
    return VpnUser.query


def can_manage_user(owner, user):
    if not owner or owner.role != 'sub_admin':
        return True
    return getattr(user, 'owner_id', None) == owner.id


def owner_protocols(owner, protocols):
    """Restrict a requested protocol list to the reseller's allowed set."""
    if not owner or owner.role != 'sub_admin':
        return protocols
    allowed = owner.allowed_protocol_list()
    if not allowed:
        return protocols
    return [p for p in protocols if p in allowed]
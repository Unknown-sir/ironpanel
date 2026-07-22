from __future__ import annotations

import ipaddress
from typing import Iterable, Tuple

from ..core.extensions import db
from ..core.models import FirewallRule
from .provisioning import run_cmd

BAN_CHAIN = 'IRONPANEL-BAN'


def _shell(cmd: str, timeout: int = 20) -> None:
    run_cmd(['bash', '-lc', cmd], timeout=timeout)


def normalize_ip_target(value: str) -> Tuple[str, str]:
    """Validate and normalize an IPv4/IPv6 address or CIDR for full blocking."""
    raw = (value or '').strip()
    if not raw:
        raise ValueError('IP یا CIDR خالی است.')
    try:
        net = ipaddress.ip_network(raw, strict=False)
    except Exception:
        raise ValueError('فرمت IP یا CIDR معتبر نیست.')
    if net.prefixlen == 0:
        raise ValueError('برای جلوگیری از قفل‌شدن کامل سرور، بن کردن کل اینترنت مجاز نیست.')
    if net.is_loopback:
        raise ValueError('بن کردن loopback مجاز نیست.')
    return str(net), ('ipv6' if net.version == 6 else 'ipv4')


def ip_matches_target(ip_value: str, target: str) -> bool:
    try:
        return ipaddress.ip_address((ip_value or '').split(',')[0].strip()) in ipaddress.ip_network(target, strict=False)
    except Exception:
        return False


def _bin_for_family(family: str) -> str:
    return 'ip6tables' if family == 'ipv6' else 'iptables'


def _save_firewall() -> None:
    """Persist rules best-effort when iptables-persistent/netfilter-persistent exists."""
    _shell('mkdir -p /etc/iptables >/dev/null 2>&1 || true; iptables-save > /etc/iptables/rules.v4 2>/dev/null || true; ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true; netfilter-persistent save >/dev/null 2>&1 || true', 30)


def _ensure_ban_chain(family: str) -> None:
    tool = _bin_for_family(family)
    # Create/flush a dedicated chain. The jump is kept at the top of INPUT, FORWARD and OUTPUT.
    _shell(f'{tool} -N {BAN_CHAIN} 2>/dev/null || true; {tool} -F {BAN_CHAIN} 2>/dev/null || true')
    for chain in ('INPUT', 'FORWARD', 'OUTPUT'):
        _shell(f'{tool} -C {chain} -j {BAN_CHAIN} 2>/dev/null || {tool} -I {chain} 1 -j {BAN_CHAIN} 2>/dev/null || true')


def _ban_targets() -> Iterable[Tuple[str, str]]:
    for r in FirewallRule.query.filter_by(enabled=True).all():
        if (r.action or '').lower() == 'ban':
            try:
                target, family = normalize_ip_target(r.source)
                yield target, family
            except Exception:
                continue


def apply_ip_bans() -> None:
    """Rebuild dedicated ban chains from DB without touching unrelated firewall rules."""
    for family in ('ipv4', 'ipv6'):
        _ensure_ban_chain(family)
    for target, family in _ban_targets():
        tool = _bin_for_family(family)
        safe_target = target.replace("'", '')
        _shell(f"{tool} -A {BAN_CHAIN} -s '{safe_target}' -j DROP 2>/dev/null || true")
        _shell(f"{tool} -A {BAN_CHAIN} -d '{safe_target}' -j DROP 2>/dev/null || true")
    _save_firewall()


def _apply_port_rule(r: FirewallRule) -> None:
    proto = 'udp' if (r.protocol or '').lower() == 'udp' else 'tcp'
    action = (r.action or 'allow').lower()
    source = (r.source or 'any').strip()
    if r.port is None or int(r.port or 0) <= 0:
        return
    if action not in ('allow', 'deny'):
        return
    verb = 'allow' if action == 'allow' else 'deny'
    if source and source.lower() not in ('any', 'all', '*'):
        # Validate source, but keep best-effort behavior so older values do not break the firewall page.
        try:
            source, _ = normalize_ip_target(source)
            _shell(f"ufw {verb} from '{source}' to any port {int(r.port)} proto {proto} >/dev/null 2>&1 || true")
        except Exception:
            _shell(f'ufw {verb} {int(r.port)}/{proto} >/dev/null 2>&1 || true')
    else:
        _shell(f'ufw {verb} {int(r.port)}/{proto} >/dev/null 2>&1 || true')


def apply_firewall_rules() -> None:
    """Apply normal port rules and rebuild full IP ban chains."""
    for r in FirewallRule.query.filter_by(enabled=True).all():
        if (r.action or '').lower() in ('allow', 'deny'):
            _apply_port_rule(r)
    apply_ip_bans()


def create_ip_ban(ip_or_cidr: str, name: str = '', note: str = '') -> FirewallRule:
    target, family = normalize_ip_target(ip_or_cidr)
    label = (name or '').strip() or f'Ban {target}'
    existing = FirewallRule.query.filter(
        FirewallRule.action == 'ban',
        FirewallRule.source == target,
    ).first()
    if existing:
        existing.enabled = True
        existing.name = label
        existing.protocol = family
        db.session.commit()
        apply_ip_bans()
        return existing
    r = FirewallRule(name=label, port=0, protocol=family, action='ban', source=target, enabled=True)
    db.session.add(r)
    db.session.commit()
    apply_ip_bans()
    return r


def firewall_summary() -> dict:
    bans = FirewallRule.query.filter(FirewallRule.action == 'ban').order_by(FirewallRule.id.desc()).all()
    normal = FirewallRule.query.filter(FirewallRule.action != 'ban').order_by(FirewallRule.id.desc()).all()
    return {'bans': bans, 'rules': normal, 'ban_chain': BAN_CHAIN}

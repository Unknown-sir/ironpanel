from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from flask import current_app

from ..core.extensions import db
from ..core.models import BackupRecord
from .provisioning import (
    active_protocols,
    apply_runtime_configs,
    get_port,
    get_setting,
    run_cmd,
    service_error_detail,
    sync_all_users,
)

CRITICAL_SERVICES = [
    {"id": "ironpanel", "label": "IronPanel Web", "unit": "ironpanel.service", "category": "core"},
    {"id": "usage", "label": "Usage Sync Timer", "unit": "ironpanel-usage-sync.timer", "category": "core"},
    {"id": "speed_limits", "label": "Speed Limits", "unit": "ironpanel-speed-limits.service", "category": "core"},
    {"id": "openvpn", "label": "OpenVPN", "unit": "openvpn-server@server.service", "category": "protocol", "proto": "openvpn", "repair": "repair_openvpn.sh"},
    {"id": "wireguard", "label": "WireGuard", "unit": "wg-quick@wg0.service", "category": "protocol", "proto": "wireguard", "repair": "repair_wireguard.sh"},
    {"id": "ocserv", "label": "Cisco / Ocserv", "unit": "ocserv.service", "category": "protocol", "proto": "ocserv", "repair": "repair_ocserv.sh"},
    {"id": "xray", "label": "Xray Core", "unit": "xray.service", "category": "protocol", "proto": "xray", "repair": "repair_xray.sh"},
    {"id": "hysteria2", "label": "Hysteria2", "unit": "hysteria-server.service", "category": "protocol", "proto": "hysteria2", "repair": "repair_hysteria2.sh"},
    {"id": "pptp", "label": "PPTP", "unit": "pptpd.service", "category": "protocol", "proto": "pptp", "repair": "repair_pptp.sh"},
    {"id": "l2tp", "label": "L2TP / xl2tpd", "unit": "xl2tpd.service", "category": "protocol", "proto": "l2tp"},
    {"id": "ssh", "label": "SSH Protocol", "unit": "ssh.service", "fallback_unit": "sshd.service", "category": "protocol", "proto": "ssh", "repair": "repair_ssh.sh"},
    {"id": "telegram_proxy", "label": "Telegram Proxy", "unit": "ironpanel-tgproxy.service", "category": "protocol", "proto": "telegram_proxy", "repair": "repair_telegram_proxy.sh --sync"},
    {"id": "node_agent", "label": "Node Agent", "unit": "ironpanel-node.service", "category": "node"},
    {"id": "node_gateway", "label": "Node Gateway Rules", "unit": "ironpanel-node-gateway.service", "category": "node"},
    {"id": "license_heartbeat", "label": "License Heartbeat", "unit": "ironpanel-license-heartbeat.timer", "category": "license"},
]

PORT_CHECKS = [
    {"id": "panel_port", "label": "Panel Port", "setting": "port_panel", "default": 8080, "proto": None, "transport": "tcp"},
    {"id": "openvpn_udp", "label": "OpenVPN UDP", "setting": "port_openvpn_udp", "default": 1194, "proto": "openvpn", "transport": "udp"},
    {"id": "openvpn_tcp", "label": "OpenVPN TCP", "setting": "port_openvpn_tcp", "default": 1195, "proto": "openvpn", "transport": "tcp"},
    {"id": "wireguard", "label": "WireGuard UDP", "setting": "port_wireguard_udp", "default": 51820, "proto": "wireguard", "transport": "udp"},
    {"id": "ocserv_tcp", "label": "Ocserv TCP", "setting": "port_ocserv_tcp", "default": 8445, "proto": "ocserv", "transport": "tcp"},
    {"id": "xray", "label": "Xray TCP", "setting": "port_xray_tcp", "default": 443, "proto": "xray", "transport": "tcp"},
    {"id": "pptp", "label": "PPTP TCP", "setting": "port_pptp_tcp", "default": 1723, "proto": "pptp", "transport": "tcp"},
    {"id": "hysteria2", "label": "Hysteria2 UDP", "setting": "port_hysteria2_udp", "default": 4433, "proto": "hysteria2", "transport": "udp"},
    {"id": "telegram_proxy", "label": "Telegram Proxy TCP", "setting": "port_telegram_proxy_base", "default": 6969, "proto": "telegram_proxy", "transport": "tcp"},
    {"id": "ssh", "label": "SSH Protocol TCP", "setting": "port_ssh_tcp", "default": 422, "proto": "ssh", "transport": "tcp"},
]

IMPORTANT_PATHS = [
    {"id": "env", "label": "Environment file", "path": "/etc/ironpanel/ironpanel.env", "category": "files"},
    {"id": "db", "label": "SQLite database", "path": "/etc/ironpanel/ironpanel.db", "category": "files"},
    {"id": "app", "label": "Application directory", "path": "/opt/ironpanel", "category": "files"},
    {"id": "venv", "label": "Python venv", "path": "/opt/ironpanel/.venv/bin/python", "category": "files"},
    {"id": "profiles", "label": "Generated profiles", "path": "/etc/ironpanel/profiles", "category": "files"},
    {"id": "tgproxy", "label": "Telegram Proxy runtime", "path": "/opt/ironpanel-telegram-proxy/ironpanel", "category": "files"},
]

BACKUP_EXCLUDES = (
    "/opt/ironpanel/.venv",
    "/opt/ironpanel/.git",
    "/opt/ironpanel/__pycache__",
    "/etc/ironpanel/backups",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _backup_dir() -> Path:
    root = current_app.config.get("CONFIG_ROOT") or Path("/etc/ironpanel")
    root = Path(root)
    out = root / "backups"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _unit_active(unit: str) -> tuple[bool, str]:
    state = (run_cmd(["bash", "-lc", f"systemctl is-active {unit} 2>/dev/null || true"], timeout=8).stdout or "").strip() or "unknown"
    return state == "active", state


def _unit_exists(unit: str) -> bool:
    r = run_cmd(["bash", "-lc", f"systemctl list-unit-files {unit} >/dev/null 2>&1 || systemctl status {unit} >/dev/null 2>&1"], timeout=8)
    return r.returncode == 0


def _port_open(port: int, transport: str) -> tuple[bool, str]:
    if not port:
        return False, "port is empty"
    if transport == "udp":
        cmd = f"ss -lun '( sport = :{port} )' 2>/dev/null | tail -n +2 | head -1"
    else:
        cmd = f"ss -ltn '( sport = :{port} )' 2>/dev/null | tail -n +2 | head -1"
    out = (run_cmd(["bash", "-lc", cmd], timeout=8).stdout or "").strip()
    return bool(out), out or "not listening"


def _status_row(id: str, label: str, category: str, ok: bool, status: str, detail: str = "", repair: str = "", severity: str = "warning") -> Dict:
    return {
        "id": id,
        "label": label,
        "category": category,
        "ok": bool(ok),
        "status": status,
        "detail": detail,
        "repair": repair,
        "severity": "ok" if ok else severity,
    }


def doctor_status() -> Dict:
    protocols = set(active_protocols() or [])
    rows: List[Dict] = []

    for item in IMPORTANT_PATHS:
        p = Path(item["path"])
        ok = p.exists()
        detail = str(p)
        if ok and p.is_file():
            try:
                detail += f" · {p.stat().st_size} bytes"
            except Exception:
                pass
        rows.append(_status_row(item["id"], item["label"], item["category"], ok, "exists" if ok else "missing", detail, "all" if not ok else ""))

    for svc in CRITICAL_SERVICES:
        proto = svc.get("proto")
        if proto and proto not in protocols:
            rows.append(_status_row(svc["id"], svc["label"], svc["category"], True, "disabled", "Protocol is disabled in Active Protocols"))
            continue
        unit = svc["unit"]
        if not _unit_exists(unit) and svc.get("fallback_unit"):
            unit = svc["fallback_unit"]
        exists = _unit_exists(unit)
        if not exists:
            rows.append(_status_row(svc["id"], svc["label"], svc["category"], False, "missing", f"Unit not found: {svc['unit']}", svc.get("repair", "all"), "danger"))
            continue
        ok, state = _unit_active(unit)
        detail = f"unit={unit}, state={state}"
        rows.append(_status_row(svc["id"], svc["label"], svc["category"], ok, state, detail, svc.get("repair", "restart:" + unit) if not ok else ""))

    for chk in PORT_CHECKS:
        proto = chk.get("proto")
        if proto and proto not in protocols:
            continue
        try:
            port = int(get_setting(chk["setting"], str(chk["default"])) or chk["default"])
        except Exception:
            port = int(chk["default"])
        ok, detail = _port_open(port, chk["transport"])
        rows.append(_status_row(chk["id"], chk["label"], "ports", ok, "listening" if ok else "closed", f"{chk['transport'].upper()}:{port} · {detail}", "all" if not ok else "", "warning"))

    ssl_domain = get_setting("ssl_domain", "") or get_setting("public_host", "") or get_setting("subscription_domain", "")
    cert_file = get_setting("ssl_cert_file", "") or get_setting("IRONPANEL_SSL_CERT", "")
    cert_ok = bool(cert_file and Path(str(cert_file)).exists())
    rows.append(_status_row("ssl", "Panel SSL Certificate", "ssl", cert_ok or not ssl_domain, "ok" if cert_ok else ("not configured" if not ssl_domain else "missing"), f"domain={ssl_domain or '-'} cert={cert_file or '-'}", "ssl" if ssl_domain and not cert_ok else ""))

    db_ok = run_cmd(["bash", "-lc", "test -f /etc/ironpanel/ironpanel.db && sqlite3 /etc/ironpanel/ironpanel.db 'pragma integrity_check;' 2>/dev/null | head -1 || true"], timeout=30).stdout.strip()
    rows.append(_status_row("db_integrity", "Database Integrity", "database", db_ok == "ok", db_ok or "not checked", "sqlite pragma integrity_check", "db" if db_ok != "ok" else "", "danger"))

    ok_count = sum(1 for r in rows if r.get("ok"))
    bad_count = len(rows) - ok_count
    return {"checked_at": _now(), "ok": bad_count == 0, "ok_count": ok_count, "bad_count": bad_count, "rows": rows}


def doctor_repair(target: str = "all") -> tuple[bool, str]:
    target = (target or "all").strip()
    app_dir = Path("/opt/ironpanel")
    script_dir = app_dir / "scripts"
    cmds = []
    if target == "all":
        cmds.extend([
            "systemctl daemon-reload || true",
            f"bash {script_dir}/repair_db.sh || true",
            f"bash {script_dir}/install_vpn_core.sh || true",
            f"bash {script_dir}/repair_certbot.sh || true",
            f"bash {script_dir}/repair_openvpn.sh || true",
            f"bash {script_dir}/repair_wireguard.sh || true",
            f"bash {script_dir}/repair_ocserv.sh || true",
            f"bash {script_dir}/repair_xray.sh || true",
            f"bash {script_dir}/repair_hysteria2.sh || true",
            f"bash {script_dir}/repair_pptp.sh || true",
            f"bash {script_dir}/repair_telegram_proxy.sh --sync || true",
            f"bash {script_dir}/repair_ssh.sh --sync || true",
            f"bash {script_dir}/apply_speed_limits.sh --apply || true",
            f"bash {script_dir}/apply_node_gateway.sh --apply || true",
            "systemctl restart ironpanel-usage-sync.timer >/dev/null 2>&1 || true",
        ])
    elif target == "db":
        cmds.append(f"bash {script_dir}/repair_db.sh || true")
    elif target == "ssl":
        cmds.append(f"bash {script_dir}/repair_certbot.sh || true")
    elif target.startswith("restart:"):
        unit = target.split(":", 1)[1]
        cmds.append(f"systemctl restart {unit} || true")
    else:
        cmds.append(f"bash {script_dir}/{target} || true")
    cmd = "\n".join(cmds) + "\n"
    p = run_cmd(["bash", "-lc", cmd], timeout=1800)
    try:
        apply_runtime_configs()
        sync_all_users(restart=True)
    except Exception as exc:
        out = (p.stdout or "") + (p.stderr or "") + f"\nRuntime sync warning: {exc}"
        return False, out[-12000:]
    return p.returncode == 0, ((p.stdout or "") + (p.stderr or ""))[-12000:]


def backup_catalog() -> List[Dict]:
    rows = []
    for p in sorted(_backup_dir().glob("*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
        manifest = {}
        try:
            with tarfile.open(p, "r:gz") as tar:
                member = tar.extractfile("manifest.json")
                if member:
                    manifest = json.loads(member.read().decode("utf-8", "ignore"))
        except Exception:
            manifest = {}
        rows.append({
            "name": p.name,
            "size": p.stat().st_size,
            "created_at": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "kind": manifest.get("kind", "legacy"),
            "version": manifest.get("version", ""),
            "note": manifest.get("note", ""),
            "path": str(p),
        })
    return rows


def _tar_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    name = tarinfo.name
    if name.startswith("/") or ".." in Path(name).parts:
        return None
    for ex in BACKUP_EXCLUDES:
        if name.startswith(ex.lstrip("/")):
            return None
    return tarinfo


def create_safe_backup(note: str = "manual", include_source: bool = True) -> Path:
    out_dir = _backup_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"ironpanel-safe-backup-{stamp}.tar.gz"
    manifest = {
        "kind": "ironpanel-safe-backup",
        "version": Path("/opt/ironpanel/VERSION").read_text().strip() if Path("/opt/ironpanel/VERSION").exists() else "unknown",
        "created_at": _now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "note": note,
        "includes": ["/etc/ironpanel", "/etc/systemd/system/ironpanel*", "/opt/ironpanel source"] if include_source else ["/etc/ironpanel", "/etc/systemd/system/ironpanel*"],
    }
    with tempfile.TemporaryDirectory() as td:
        m = Path(td) / "manifest.json"
        m.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        with tarfile.open(out, "w:gz") as tar:
            tar.add(m, arcname="manifest.json")
            etc = Path("/etc/ironpanel")
            if etc.exists():
                tar.add(etc, arcname="etc/ironpanel", filter=_tar_filter)
            sysd = Path("/etc/systemd/system")
            if sysd.exists():
                for item in sysd.glob("ironpanel*"):
                    tar.add(item, arcname=f"etc/systemd/system/{item.name}", filter=_tar_filter)
            if include_source and Path("/opt/ironpanel").exists():
                tar.add(Path("/opt/ironpanel"), arcname="opt/ironpanel", filter=_tar_filter)
    try:
        rec = BackupRecord(filename=out.name, size_bytes=out.stat().st_size)
        db.session.add(rec); db.session.commit()
    except Exception:
        db.session.rollback()
    return out


def _validate_archive(path: Path) -> None:
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if member.name.startswith("/") or ".." in parts:
                raise ValueError(f"Unsafe path in backup: {member.name}")


def restore_safe_backup(path: Path, restore_source: bool = False) -> tuple[bool, str]:
    path = Path(path)
    _validate_archive(path)
    pre = create_safe_backup(note=f"pre-restore backup before {path.name}", include_source=True)
    log_lines = [f"Pre-restore backup created: {pre.name}"]
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(td_path)
        etc_src = td_path / "etc" / "ironpanel"
        if etc_src.exists():
            run_cmd(["bash", "-lc", "mkdir -p /etc/ironpanel"], timeout=20)
            run_cmd(["bash", "-lc", f"rsync -a --delete --exclude backups {etc_src}/ /etc/ironpanel/"], timeout=600)
            log_lines.append("/etc/ironpanel restored")
        sysd_src = td_path / "etc" / "systemd" / "system"
        if sysd_src.exists():
            run_cmd(["bash", "-lc", f"cp -a {sysd_src}/ironpanel* /etc/systemd/system/ 2>/dev/null || true"], timeout=120)
            log_lines.append("systemd units restored")
        opt_src = td_path / "opt" / "ironpanel"
        if restore_source and opt_src.exists():
            run_cmd(["bash", "-lc", "mkdir -p /opt/ironpanel"], timeout=20)
            run_cmd(["bash", "-lc", f"rsync -a --delete --exclude .venv --exclude __pycache__ {opt_src}/ /opt/ironpanel/"], timeout=900)
            log_lines.append("/opt/ironpanel source restored")
    run_cmd(["systemctl", "daemon-reload"], timeout=60)
    try:
        apply_runtime_configs()
        sync_all_users(restart=True)
        log_lines.append("runtime configs synced")
    except Exception as exc:
        log_lines.append(f"runtime sync warning: {exc}")
    run_cmd(["bash", "-lc", "systemctl restart ironpanel-usage-sync.timer >/dev/null 2>&1 || true"], timeout=60)
    return True, "\n".join(log_lines)


def safe_updater_terminal_command() -> str:
    return "sudo bash /opt/ironpanel/scripts/safe_update.sh"

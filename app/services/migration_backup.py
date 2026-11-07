from __future__ import annotations

import hashlib
import json
import os
import posixpath
import shutil
import socket
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

from flask import current_app

from ..core.extensions import db
from ..core.models import Admin, AppSetting, BackupRecord, DomainRecord, Node, VpnUser

BACKUP_FORMAT_VERSION = 2
BACKUP_KIND = "ironpanel-migration-backup"

# Runtime/identity state that must survive a server migration so existing client
# profiles keep the same certificates, shared secrets, UUID inputs and server keys.
MIGRATION_STATE_PATHS = (
    "/etc/openvpn",
    "/etc/wireguard",
    "/etc/ocserv",
    "/etc/xl2tpd",
    "/etc/ppp",
    "/etc/ipsec.conf",
    "/etc/ipsec.secrets",
    "/etc/ipsec.d",
    "/etc/strongswan.conf",
    "/etc/strongswan.d",
    "/etc/pptpd.conf",
    "/etc/xray",
    "/usr/local/etc/xray",
    "/etc/hysteria",
    "/etc/hysteria2",
    "/etc/letsencrypt",
    "/etc/ssh/sshd_config.d/ironpanel.conf",
    "/etc/sysctl.d/99-ironpanel-l2tp.conf",
    "/etc/systemd/system/ironpanel.service.d",
    "/etc/systemd/system/ironpanel-tgproxy.service",
    "/etc/systemd/system/ironpanel-outbound-openvpn.service",
    "/opt/ironpanel-telegram-proxy/ironpanel/config.json",
    "/var/lib/ironpanel",
)

CRITICAL_IDENTITY_FILES = (
    "/etc/ironpanel/ironpanel.env",
    "/etc/ironpanel/node_credential.key",
    "/etc/ironpanel/wg_server_private.key",
    "/etc/ironpanel/ipsec.psk",
    "/etc/openvpn/server/ca.crt",
    "/etc/openvpn/server/tls-crypt.key",
    "/etc/openvpn/easy-rsa/pki/private/ca.key",
    "/etc/wireguard/server_private.key",
    "/etc/ocserv/certs/server-key.pem",
    "/etc/hysteria/server.key",
    "/etc/ipsec.d/private/ironpanel-ikev2-server.key",
)

RUNTIME_SERVICES = (
    "openvpn-server@server.service",
    "wg-quick@wg0.service",
    "ocserv.service",
    "xray.service",
    "hysteria-server.service",
    "xl2tpd.service",
    "pptpd.service",
    "strongswan-starter.service",
    "strongswan.service",
    "ironpanel-tgproxy.service",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _config_root() -> Path:
    return Path(current_app.config.get("CONFIG_ROOT") or "/etc/ironpanel")


def _backup_dir() -> Path:
    out = _config_root() / "backups"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _version() -> str:
    p = Path("/opt/ironpanel/VERSION")
    try:
        return p.read_text(encoding="utf-8").strip() if p.exists() else "unknown"
    except Exception:
        return "unknown"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _database_path() -> Path:
    uri = str(current_app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    prefix = "sqlite:///"
    if uri.startswith(prefix):
        raw = uri[len(prefix):]
        if raw:
            return Path("/" + raw.lstrip("/")) if uri.startswith("sqlite:////") else Path(raw)
    return _config_root() / "ironpanel.db"


def _sqlite_snapshot(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"IronPanel database not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    # SQLite backup API creates one transactionally consistent snapshot even when
    # the live DB is in WAL mode and background usage writes are happening.
    with sqlite3.connect(str(src), timeout=60) as source, sqlite3.connect(str(dst), timeout=60) as target:
        source.backup(target, pages=256, sleep=0.05)
        row = target.execute("PRAGMA integrity_check").fetchone()
        if not row or str(row[0]).lower() != "ok":
            raise RuntimeError(f"Backup database integrity_check failed: {row}")


def _validate_sqlite_snapshot(path: Path) -> Dict[str, int]:
    if not path.exists() or path.stat().st_size < 1024:
        raise ValueError("Backup database is missing or empty")
    with sqlite3.connect(str(path), timeout=30) as conn:
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise ValueError(f"Backup database integrity_check failed: {check}")
        tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"vpn_user", "admin", "app_setting"}
        missing = sorted(required - tables)
        if missing:
            raise ValueError("Backup database misses required tables: " + ", ".join(missing))
        def count(table: str) -> int:
            if table not in tables:
                return 0
            return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        return {
            "users": count("vpn_user"),
            "admins": count("admin"),
            "settings": count("app_setting"),
            "domains": count("domain_record"),
            "nodes": count("node"),
        }


def _identity_fingerprints(paths: Iterable[str] = CRITICAL_IDENTITY_FILES) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for raw in paths:
        p = Path(raw)
        try:
            if p.is_file() and not p.is_symlink():
                result[raw] = _sha256(p)
        except Exception:
            continue
    return result


def _manifest_counts() -> Dict[str, int]:
    def safe_count(model) -> int:
        try:
            return int(model.query.count())
        except Exception:
            return 0
    try:
        reseller_count = int(Admin.query.filter_by(role="sub_admin").count())
    except Exception:
        reseller_count = 0
    return {
        "users": safe_count(VpnUser),
        "admins": safe_count(Admin),
        "resellers": reseller_count,
        "settings": safe_count(AppSetting),
        "domains": safe_count(DomainRecord),
        "nodes": safe_count(Node),
    }


def _tar_filter(info: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    parts = Path(info.name).parts
    if info.name.startswith("/") or ".." in parts:
        return None
    # Never recursively include the backup directory itself or volatile SQLite
    # WAL/SHM files; the database is stored as a consistent sqlite backup below.
    if info.name.startswith("etc/ironpanel/backups"):
        return None
    if info.name.endswith(("ironpanel.db-wal", "ironpanel.db-shm")):
        return None
    if info.name.startswith(("opt/ironpanel/.venv", "opt/ironpanel/.git")):
        return None
    if "__pycache__" in parts or info.name.endswith((".pyc", ".pyo")):
        return None
    return info


def _add_if_exists(tar: tarfile.TarFile, source: str | Path, arcname: Optional[str] = None) -> bool:
    p = Path(source)
    if not p.exists() and not p.is_symlink():
        return False
    tar.add(p, arcname=arcname or str(p).lstrip("/"), recursive=True, filter=_tar_filter)
    return True


def create_migration_backup(note: str = "manual", include_source: bool = False) -> Path:
    out_dir = _backup_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"ironpanel-migration-backup-{stamp}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="ironpanel-backup-") as td:
        td_path = Path(td)
        db_snapshot = td_path / "ironpanel.db"
        _sqlite_snapshot(_database_path(), db_snapshot)
        db_counts = _validate_sqlite_snapshot(db_snapshot)

        included = ["/etc/ironpanel (transactional DB snapshot + settings/profiles/keys)"]
        for raw in MIGRATION_STATE_PATHS:
            p = Path(raw)
            if p.exists() or p.is_symlink():
                included.append(raw)
        included.append("/etc/systemd/system/ironpanel*")
        if include_source and Path("/opt/ironpanel").exists():
            included.append("/opt/ironpanel source (without .venv/.git/cache)")

        manifest = {
            "kind": BACKUP_KIND,
            "format_version": BACKUP_FORMAT_VERSION,
            "migration_capable": True,
            "version": _version(),
            "created_at": _now(),
            "hostname": socket.gethostname(),
            "platform": os.uname().sysname + " " + os.uname().release,
            "note": note,
            "include_source": bool(include_source),
            "includes": included,
            "counts": _manifest_counts(),
            "db_counts": db_counts,
            "db_sha256": _sha256(db_snapshot),
            "identity_fingerprints": _identity_fingerprints(),
            "restore_contract": "Preserve DB tokens/keys and protocol identity; rebuild runtime on target without rotating client credentials.",
        }
        manifest_path = td_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with tarfile.open(out, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            tar.add(manifest_path, arcname="manifest.json")

            # /etc/ironpanel except live DB, backup dir and WAL/SHM.
            etc_root = _config_root()
            if etc_root.exists():
                for child in sorted(etc_root.iterdir(), key=lambda x: x.name):
                    if child.name in {"backups", "ironpanel.db", "ironpanel.db-wal", "ironpanel.db-shm"}:
                        continue
                    _add_if_exists(tar, child, f"etc/ironpanel/{child.name}")
            tar.add(db_snapshot, arcname="etc/ironpanel/ironpanel.db")

            for raw in MIGRATION_STATE_PATHS:
                _add_if_exists(tar, raw)

            systemd = Path("/etc/systemd/system")
            if systemd.exists():
                for item in sorted(systemd.glob("ironpanel*"), key=lambda x: x.name):
                    _add_if_exists(tar, item, f"etc/systemd/system/{item.name}")

            if include_source and Path("/opt/ironpanel").exists():
                tar.add(Path("/opt/ironpanel"), arcname="opt/ironpanel", filter=_tar_filter)

    # This archive contains private protocol/server identities. Never leave it
    # world-readable even if the host has a permissive umask.
    try:
        os.chmod(out, 0o600)
    except Exception:
        pass

    try:
        db.session.add(BackupRecord(filename=out.name, size_bytes=out.stat().st_size))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return out


def read_backup_manifest(path: Path) -> Dict:
    try:
        with tarfile.open(path, "r:gz") as tar:
            f = tar.extractfile("manifest.json")
            return json.loads(f.read().decode("utf-8", "replace")) if f else {}
    except Exception:
        return {}


def validate_backup_archive(path: Path) -> Dict:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    total = 0
    count = 0
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            count += 1
            total += max(0, int(member.size or 0))
            parts = Path(member.name).parts
            if member.name.startswith("/") or ".." in parts:
                raise ValueError(f"Unsafe path in backup: {member.name}")
            if member.ischr() or member.isblk() or member.isfifo():
                raise ValueError(f"Unsupported special file in backup: {member.name}")
            if member.issym() or member.islnk():
                link = str(member.linkname or "")
                if link.startswith("/"):
                    raise ValueError(f"Unsafe absolute link in backup: {member.name} -> {link}")
                # LetsEncrypt intentionally uses links such as ../../archive/... .
                # Allow those only when normalization still stays inside the
                # archive root; reject links that actually escape it.
                normalized = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), link))
                if normalized == ".." or normalized.startswith("../"):
                    raise ValueError(f"Unsafe link in backup: {member.name} -> {link}")
        if count > 150000:
            raise ValueError("Backup contains too many archive members")
        if total > 25 * 1024 * 1024 * 1024:
            raise ValueError("Backup expands beyond the 25 GiB safety limit")
    return read_backup_manifest(path)


def _extract_safely(path: Path, destination: Path) -> None:
    with tarfile.open(path, "r:gz") as tar:
        try:
            tar.extractall(destination, filter="data")
        except TypeError:  # Python < 3.12 fallback after explicit validation.
            tar.extractall(destination)


def _run(args, timeout=120):
    from .provisioning import run_cmd
    return run_cmd(args, timeout=timeout)


def _rsync_tree(src: Path, dst: Path, delete: bool = True, extra_excludes: Iterable[str] = ()) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    args = ["rsync", "-aH", "--numeric-ids"]
    if delete:
        args.append("--delete")
    for ex in extra_excludes:
        args.extend(["--exclude", ex])
    args.extend([str(src).rstrip("/") + "/", str(dst).rstrip("/") + "/"])
    result = _run(args, timeout=1200)
    if result.returncode != 0:
        raise RuntimeError(f"rsync failed for {dst}: {(result.stderr or result.stdout)[-1200:]}")


def _restore_one(staged_root: Path, absolute: str) -> bool:
    rel = absolute.lstrip("/")
    src = staged_root / rel
    if not src.exists() and not src.is_symlink():
        return False
    dst = Path(absolute)
    if src.is_dir() and not src.is_symlink():
        _rsync_tree(src, dst, delete=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() or dst.is_symlink():
            if dst.is_dir() and not dst.is_symlink():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        shutil.copy2(src, dst, follow_symlinks=False)
    return True


def _restore_database(snapshot: Path) -> Dict[str, int]:
    counts = _validate_sqlite_snapshot(snapshot)
    live = _database_path()
    live.parent.mkdir(parents=True, exist_ok=True)
    # Release SQLAlchemy file handles before overwriting SQLite through its backup API.
    db.session.remove()
    try:
        db.engine.dispose()
    except Exception:
        pass
    with sqlite3.connect(str(snapshot), timeout=60) as source, sqlite3.connect(str(live), timeout=60) as target:
        source.backup(target, pages=256, sleep=0.05)
        target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        check = target.execute("PRAGMA integrity_check").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError(f"Restored DB integrity check failed: {check}")
    try:
        os.chmod(live, 0o600)
    except Exception:
        pass
    db.session.remove()
    try:
        db.engine.dispose()
    except Exception:
        pass
    return counts


def _stop_runtime_best_effort() -> None:
    for svc in RUNTIME_SERVICES:
        _run(["systemctl", "stop", svc], timeout=45)


def _restart_runtime_best_effort() -> None:
    for svc in RUNTIME_SERVICES:
        _run(["systemctl", "restart", svc], timeout=60)


def _restore_systemd(staged_root: Path) -> int:
    src = staged_root / "etc/systemd/system"
    if not src.exists():
        return 0
    restored = 0
    dst = Path("/etc/systemd/system")
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.glob("ironpanel*"):
        target = dst / item.name
        if item.is_dir() and not item.is_symlink():
            _rsync_tree(item, target, delete=True)
        else:
            if target.exists() or target.is_symlink():
                target.unlink(missing_ok=True)
            shutil.copy2(item, target, follow_symlinks=False)
        restored += 1
    return restored


def _reload_restored_environment_for_current_process() -> None:
    """Refresh the few Flask config values needed before regenerating profiles.

    The web restore runs inside a process that was started with the destination
    server's pre-restore EnvironmentFile. Without this refresh, a legacy setup
    that stores PUBLIC_HOST only in ironpanel.env could regenerate profiles using
    the destination's temporary install host before systemd restarts IronPanel.
    """
    env_path = _config_root() / "ironpanel.env"
    if not env_path.is_file():
        return
    values: Dict[str, str] = {}
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            values[key.strip()] = value
    except Exception:
        return
    mapping = {
        "IRONPANEL_PUBLIC_HOST": "PUBLIC_HOST",
        "IRONPANEL_API_KEY": "API_KEY",
        "IRONPANEL_SECRET_KEY": "SECRET_KEY",
    }
    for env_key, cfg_key in mapping.items():
        if values.get(env_key):
            current_app.config[cfg_key] = values[env_key]
    if values.get("IRONPANEL_PORT"):
        try:
            current_app.config["PANEL_PORT"] = int(values["IRONPANEL_PORT"])
        except Exception:
            pass


def _post_restore_runtime(log_lines: list[str]) -> None:
    # The target should already have the current IronPanel installed. Upgrade the
    # restored DB with CURRENT code, then rebuild runtime files from restored data.
    upgrade = _run([
        "bash", "-lc",
        "set -a; [ -f /etc/ironpanel/ironpanel.env ] && source /etc/ironpanel/ironpanel.env; set +a; "
        "cd /opt/ironpanel && .venv/bin/flask --app run.py upgrade-db",
    ], timeout=600)
    if upgrade.returncode != 0:
        raise RuntimeError("Database upgrade after restore failed: " + ((upgrade.stderr or upgrade.stdout)[-3000:]))
    log_lines.append("database schema upgraded/verified")

    db.session.remove()
    try:
        db.engine.dispose()
    except Exception:
        pass

    _reload_restored_environment_for_current_process()
    log_lines.append("restored public host/API environment loaded for runtime regeneration")

    from .provisioning import apply_runtime_configs, sync_all_users
    apply_runtime_configs()
    sync_all_users(restart=True)
    log_lines.append("all users/protocol runtime regenerated with restored identities")

    try:
        from .firewall_manager import apply_firewall_rules
        apply_firewall_rules()
        log_lines.append("firewall rules restored from database")
    except Exception as exc:
        log_lines.append(f"firewall reapply warning: {exc}")
    try:
        from .speed_limit import apply_speed_limits_runtime
        apply_speed_limits_runtime()
        log_lines.append("speed limits reapplied")
    except Exception as exc:
        log_lines.append(f"speed-limit reapply warning: {exc}")
    try:
        from .node_gateway import apply_node_gateway_runtime
        apply_node_gateway_runtime()
        log_lines.append("node gateway rules reapplied")
    except Exception as exc:
        log_lines.append(f"node-gateway reapply warning: {exc}")

    _run(["systemctl", "daemon-reload"], timeout=60)
    _run(["bash", "-lc", "systemctl restart ironpanel-usage-sync.timer ironpanel-license-heartbeat.timer >/dev/null 2>&1 || true"], timeout=60)
    # Environment/API/SECRET_KEY are loaded by gunicorn at process start. Schedule
    # a restart after this HTTP request can finish, so encrypted node credentials
    # and panel API keys use the restored environment on the next request.
    _run(["bash", "-lc", "systemd-run --on-active=4s /bin/systemctl restart ironpanel.service >/dev/null 2>&1 || true"], timeout=20)
    log_lines.append("IronPanel service restart scheduled to load restored environment")


def restore_migration_backup(path: Path, restore_source: bool = False) -> tuple[bool, str]:
    path = Path(path)
    manifest = validate_backup_archive(path)

    # Always create a complete rollback point using the new format before touching
    # a live server. Source is intentionally excluded to keep the safety snapshot small.
    pre = create_migration_backup(note=f"pre-restore rollback before {path.name}", include_source=False)
    log_lines = [f"Pre-restore migration backup: {pre.name}"]

    with tempfile.TemporaryDirectory(prefix="ironpanel-restore-") as td:
        staged = Path(td)
        _extract_safely(path, staged)

        db_snapshot = staged / "etc/ironpanel/ironpanel.db"
        if not db_snapshot.exists():
            # Legacy v9 backup compatibility stored ironpanel.db at archive root.
            # Use it in-place; do NOT fabricate an otherwise-empty etc/ironpanel
            # tree, because a --delete restore of that tree could remove current
            # environment/secrets that the legacy archive never contained.
            legacy_db = staged / "ironpanel.db"
            if legacy_db.exists():
                db_snapshot = legacy_db
        restored_counts = _validate_sqlite_snapshot(db_snapshot)
        log_lines.append("backup database validated: " + json.dumps(restored_counts, ensure_ascii=False))

        expected_db_sha = str(manifest.get("db_sha256") or "")
        if expected_db_sha and _sha256(db_snapshot) != expected_db_sha:
            raise ValueError("Backup database checksum does not match manifest")

        is_migration = bool(manifest.get("migration_capable")) and int(manifest.get("format_version") or 0) >= 2
        if not is_migration:
            log_lines.append("WARNING: legacy backup detected; protocol identity files may not exist in this archive")

        _stop_runtime_best_effort()
        try:
            # Restore config-root files first, except the DB and backup directory.
            etc_src = staged / "etc/ironpanel"
            if etc_src.exists():
                etc_dst = _config_root()
                _rsync_tree(etc_src, etc_dst, delete=True, extra_excludes=("backups", "ironpanel.db", "ironpanel.db-wal", "ironpanel.db-shm"))
                log_lines.append("/etc/ironpanel settings/profiles/secrets restored")

            _restore_database(db_snapshot)
            log_lines.append("transactional SQLite database restored")

            identity_restored = []
            for raw in MIGRATION_STATE_PATHS:
                if _restore_one(staged, raw):
                    identity_restored.append(raw)
            log_lines.append(f"protocol identity/runtime paths restored: {len(identity_restored)}")

            opt_src = staged / "opt/ironpanel"
            if restore_source and opt_src.exists():
                _rsync_tree(opt_src, Path("/opt/ironpanel"), delete=True, extra_excludes=(".venv", ".git", "__pycache__"))
                log_lines.append("/opt/ironpanel source restored (explicitly requested)")
                units = _restore_systemd(staged)
                if units:
                    log_lines.append(f"matching IronPanel systemd units restored: {units}")
            else:
                # On a migration the destination is installed first with the same
                # or a newer IronPanel. Keep its current service definitions; the
                # restored EnvironmentFile/settings drive them. This avoids
                # downgrading a newer target's unit hardening/timers.
                log_lines.append("target IronPanel systemd units kept (recommended migration mode)")

            # Verify identity files after copy when the backup manifest provided hashes.
            expected_fp = manifest.get("identity_fingerprints") or {}
            mismatches = []
            for raw, digest in expected_fp.items():
                p = Path(raw)
                if p.is_file() and not p.is_symlink():
                    if _sha256(p) != digest:
                        mismatches.append(raw)
                else:
                    mismatches.append(raw)
            if mismatches:
                raise RuntimeError("Restored identity checksum mismatch: " + ", ".join(mismatches[:12]))
            if expected_fp:
                log_lines.append(f"identity checksum verification passed: {len(expected_fp)} files")

            _post_restore_runtime(log_lines)
        except Exception:
            _restart_runtime_best_effort()
            raise

    return True, "\n".join(log_lines)

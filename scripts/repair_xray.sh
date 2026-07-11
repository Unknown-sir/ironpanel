#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
# Manual execution must use the same DATABASE_URL and runtime settings as systemd.
# Without this, Flask falls back to /opt/ironpanel/app/ironpanel.db and repair can
# fail with: sqlite3.OperationalError: no such table: app_setting
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ETC_DIR/ironpanel.env"
  set +a
fi
mkdir -p /usr/local/etc/xray /var/log/xray
if ! command -v xray >/dev/null 2>&1 && [[ ! -x /usr/local/bin/xray ]]; then
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray-install.sh || true
  if [[ -s /tmp/xray-install.sh ]]; then bash /tmp/xray-install.sh install || true; fi
fi

ensure_xray_runtime_permissions() {
  # v16.3: use a clean IronPanel-managed unit instead of the upstream unit/drop-ins.
  # The upstream installer may leave User=nobody and our old v16.1 drop-in had
  # DynamicUser= with an empty value, which systemd rejects as "Failed to parse
  # boolean value". When that drop-in is ignored, Xray keeps running as nobody
  # and cannot open /var/log/xray/access.log.
  install -d -m 755 -o root -g root /usr/local/etc/xray 2>/dev/null || mkdir -p /usr/local/etc/xray
  install -d -m 755 -o root -g root /var/log/xray 2>/dev/null || mkdir -p /var/log/xray
  touch /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  chown root:root /var/log/xray /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  chmod 755 /var/log/xray 2>/dev/null || true
  chmod 644 /var/log/xray/access.log /var/log/xray/error.log 2>/dev/null || true
  if [[ -f /usr/local/etc/xray/config.json ]]; then
    chown root:root /usr/local/etc/xray/config.json 2>/dev/null || true
    chmod 644 /usr/local/etc/xray/config.json 2>/dev/null || true
  fi
  if [[ -x /usr/local/bin/xray || -x /usr/bin/xray || -n "$(command -v xray 2>/dev/null || true)" ]]; then
    XRAY_BIN="$(command -v xray 2>/dev/null || true)"
    [[ -n "$XRAY_BIN" ]] || XRAY_BIN=/usr/local/bin/xray
    # Remove broken/old drop-ins, including:
    # - 10-donot_touch_single_conf.conf from the official installer
    # - 20-ironpanel-runtime.conf from v16.1/v16.2 with DynamicUser=
    if [[ -d /etc/systemd/system/xray.service.d ]]; then
      BACKUP_DIR="/etc/systemd/system/xray.service.d.ironpanel-backup-$(date +%Y%m%d%H%M%S)"
      mkdir -p "$BACKUP_DIR" 2>/dev/null || true
      cp -a /etc/systemd/system/xray.service.d/. "$BACKUP_DIR"/ 2>/dev/null || true
      rm -rf /etc/systemd/system/xray.service.d
    fi
    cat > /etc/systemd/system/xray.service <<EOF_SERVICE
[Unit]
Description=Xray Service - IronPanel Managed
Documentation=https://github.com/XTLS/Xray-core
After=network.target nss-lookup.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
ExecStartPre=/bin/sh -c 'mkdir -p /var/log/xray /usr/local/etc/xray; touch /var/log/xray/access.log /var/log/xray/error.log; chmod 755 /var/log/xray; chmod 644 /var/log/xray/access.log /var/log/xray/error.log'
ExecStart=$XRAY_BIN run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF_SERVICE
  fi
}


ensure_xray_runtime_permissions
systemctl daemon-reload || true
PY="$APP_DIR/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3
FLASK="$APP_DIR/.venv/bin/flask"
[[ -x "$FLASK" ]] || FLASK=flask
cd "$APP_DIR"
# Create/upgrade tables before importing Xray settings. This makes repair_xray.sh
# safe when it is run manually after a partial install or after adding v16.x.
set +e
"$FLASK" --app run.py upgrade-db >/tmp/ironpanel-xray-upgrade-db.log 2>&1
UPGRADE_RC=$?
set -e
if [[ $UPGRADE_RC -ne 0 ]]; then
  echo "Warning: database upgrade command failed; continuing with Xray self-repair. Details:"
  tail -n 60 /tmp/ironpanel-xray-upgrade-db.log || true
fi
set +e
"$PY" - <<'PYCODE'
from app import create_app
from app.core.extensions import db
from app.core.models import VpnUser
from app.services.provisioning import user_access_status, generate_profiles
from app.services.xray import ensure_reality_keys, write_xray_config, prepare_xray_runtime, test_xray_config_file
app=create_app()
with app.app_context():
    db.create_all()
    prepare_xray_runtime()
    ensure_reality_keys(commit=True, force=True)
    users=[u for u in VpnUser.query.all() if user_access_status(u)[0] and 'xray' in (u.allowed_protocol_list() or u.protocol_list())]
    ok,out=write_xray_config(users, restart=False)
    for u in VpnUser.query.all():
        generate_profiles(u)
    test_ok,test_out=test_xray_config_file()
    print(out)
    print(test_out[-800:] if not test_ok else 'Xray config validation passed')
    raise SystemExit(0 if ok else 1)
PYCODE
RC=$?
set -e
ensure_xray_runtime_permissions
systemctl daemon-reload || true
systemctl enable xray >/dev/null 2>&1 || true
systemctl restart xray >/dev/null 2>&1 || true
if ! systemctl is-active --quiet xray; then
  echo "Xray did not become active. Last logs:"
  journalctl -u xray -n 80 --no-pager || true
  exit 1
fi
exit $RC

#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${IRONPANEL_APP_DIR:-/opt/ironpanel}
ETC_DIR=${IRONPANEL_ETC_DIR:-/etc/ironpanel}
LOG=${IRONPANEL_SAFE_UPDATE_LOG:-/var/log/ironpanel-safe-update.log}
STATE=${IRONPANEL_SAFE_UPDATE_STATE:-/var/run/ironpanel-safe-update.json}
UPDATE_BACKUP=${IRONPANEL_UPDATE_BACKUP:-0}
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"
exec > >(tee -a "$LOG") 2>&1

progress(){
  local pct="$1"; shift
  local msg="$*"
  printf '{"progress":%s,"message":"%s","updated_at":"%s"}\n' "$pct" "$(printf '%s' "$msg" | sed 's/"/\\"/g')" "$(date -Is)" > "$STATE"
  echo "IRONPANEL_PROGRESS ${pct}% - ${msg}"
}

fail(){ progress 99 "Safe update failed: $*"; echo "ERROR: $*"; exit 1; }
[[ $EUID -eq 0 ]] || fail "Run as root"

progress 5 "Pre-checks"
command -v curl >/dev/null 2>&1 || apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y curl ca-certificates git rsync tar sqlite3 >/dev/null 2>&1 || true
[[ -d "$APP_DIR" ]] || fail "Missing $APP_DIR"
[[ -f "$ETC_DIR/ironpanel.env" ]] || echo "warning: env file missing"

if [[ "$UPDATE_BACKUP" == "1" ]]; then
  progress 15 "Creating optional full backup"
  mkdir -p /var/backups/ironpanel
  if [[ -x "$APP_DIR/.venv/bin/flask" ]]; then
    cd "$APP_DIR"
    "$APP_DIR/.venv/bin/flask" --app run.py safe-backup || true
  else
    STAMP=$(date +%Y%m%d-%H%M%S)
    tar -C /etc -czf "/var/backups/ironpanel/ironpanel-etc-safe-$STAMP.tar.gz" ironpanel 2>/dev/null || true
  fi
else
  progress 15 "Automatic backup skipped for faster update"
fi

progress 30 "Downloading and installing update"
IRONPANEL_UPDATE_BACKUP=0 bash "$APP_DIR/scripts/update_from_github.sh"

progress 82 "Database migration and service reconciliation"
cd "$APP_DIR"
if [[ -x "$APP_DIR/.venv/bin/flask" ]]; then
  if [[ -x "$APP_DIR/scripts/upgrade_db_safe.sh" ]]; then bash "$APP_DIR/scripts/upgrade_db_safe.sh" || true; else "$APP_DIR/.venv/bin/flask" --app run.py upgrade-db || true; fi
fi
systemctl daemon-reload || true

progress 90 "Post-update lightweight reconciliation"
if [[ "${IRONPANEL_SAFE_UPDATE_DEEP_REPAIR:-0}" == "1" && -x "$APP_DIR/scripts/ironpanel_doctor.sh" ]]; then
  bash "$APP_DIR/scripts/ironpanel_doctor.sh" --repair || true
fi
if [[ -x "$APP_DIR/scripts/apply_speed_limits.sh" ]]; then timeout 60 bash "$APP_DIR/scripts/apply_speed_limits.sh" --apply || true; fi
if [[ -x "$APP_DIR/scripts/apply_node_gateway.sh" ]]; then timeout 60 bash "$APP_DIR/scripts/apply_node_gateway.sh" --apply || true; fi

progress 97 "Restarting services"
for unit in ironpanel-usage-sync.timer ironpanel-license-heartbeat.timer ironpanel-job-worker.timer ironpanel-backup-v17.timer; do
  systemctl enable --now "$unit" >/dev/null 2>&1 || true
done
systemctl restart ironpanel >/dev/null 2>&1 || true
systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true
systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true

VERSION=$(cat "$APP_DIR/VERSION" 2>/dev/null || echo unknown)
progress 100 "Update completed. Installed version: $VERSION"
echo "IRONPANEL_UPDATE_COMPLETE"
echo "Safe update completed successfully. Installed version: $VERSION"

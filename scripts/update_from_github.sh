#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash /opt/ironpanel/scripts/update_from_github.sh"
  exit 1
fi

REPO_URL="${IRONPANEL_GITHUB_REPO:-https://github.com/Unknown-sir/ironpanel.git}"
BRANCH="${IRONPANEL_GITHUB_BRANCH:-main}"
APP_DIR="${IRONPANEL_APP_DIR:-/opt/ironpanel}"
ETC_DIR="${IRONPANEL_ETC_DIR:-/etc/ironpanel}"
WORK="/tmp/ironpanel-github-update"
BACKUP_DIR="/var/backups/ironpanel"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="/var/log/ironpanel-github-upgrade.log"

mkdir -p "$(dirname "$LOG")" "$WORK" "$BACKUP_DIR"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

echo "[$(date -Is)] IronPanel GitHub updater started"
echo "IRONPANEL_PROGRESS 1% - updater started"
echo "Mode: fast source + database + systemd sync; protocol repairs are manual from Health & Repair"
echo "Repo: $REPO_URL"
echo "Branch: $BRANCH"
echo "App: $APP_DIR"

apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y git rsync curl ca-certificates >/dev/null 2>&1 || true

if [[ -d "$APP_DIR" ]]; then
  echo "IRONPANEL_PROGRESS 10% - creating source backup"
  tar -C "$(dirname "$APP_DIR")" -czf "$BACKUP_DIR/ironpanel-src-$STAMP.tar.gz" "$(basename "$APP_DIR")" \
    --exclude='ironpanel/.venv' --exclude='ironpanel/__pycache__' --exclude='ironpanel/*.pyc' >/dev/null 2>&1 || true
fi
if [[ -d "$ETC_DIR" ]]; then
  echo "IRONPANEL_PROGRESS 15% - creating config backup"
  tar -C "$(dirname "$ETC_DIR")" -czf "$BACKUP_DIR/ironpanel-etc-$STAMP.tar.gz" "$(basename "$ETC_DIR")" >/dev/null 2>&1 || true
fi

echo "IRONPANEL_PROGRESS 30% - fetching latest source"
if [[ -d "$APP_DIR/.git" ]]; then
  cd "$APP_DIR"
  git remote set-url origin "$REPO_URL" || true
  git fetch --depth 1 origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
  chmod +x "$APP_DIR/upgrade.sh" "$APP_DIR/scripts/"*.sh 2>/dev/null || true
  echo "IRONPANEL_PROGRESS 55% - running fast upgrade"
  IRONPANEL_SKIP_CORE_REPAIR=1 IRONPANEL_DEFER_RESTART=1 IRONPANEL_FULL_SERVICE_SYNC=0 timeout 900 bash "$APP_DIR/upgrade.sh" --github-fast
else
  rm -rf "$WORK/ironpanel"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$WORK/ironpanel"
  if [[ ! -f "$WORK/ironpanel/upgrade.sh" ]]; then
    echo "ERROR: upgrade.sh not found in repository. Aborting."
    exit 2
  fi
  mkdir -p "$APP_DIR"
  rsync -a --delete \
    --exclude='.venv' --exclude='instance' --exclude='__pycache__' --exclude='*.pyc' \
    "$WORK/ironpanel/" "$APP_DIR/"
  chmod +x "$APP_DIR/upgrade.sh" "$APP_DIR/scripts/"*.sh 2>/dev/null || true
  cd "$APP_DIR"
  echo "IRONPANEL_PROGRESS 55% - running fast upgrade"
  IRONPANEL_SKIP_CORE_REPAIR=1 IRONPANEL_DEFER_RESTART=1 IRONPANEL_FULL_SERVICE_SYNC=0 timeout 900 bash "$APP_DIR/upgrade.sh" --github-fast
fi

echo "IRONPANEL_PROGRESS 85% - post-upgrade service reconciliation"
systemctl daemon-reload || true
for unit in ironpanel ironpanel-sales-bot ironpanel-admin-bot ironpanel-usage-sync.timer ironpanel-license-heartbeat.timer ironpanel-job-worker.timer ironpanel-sales-reminders.timer ironpanel-admin-report.timer ironpanel-backup-v17.timer ironpanel-safe-backup.timer; do
  systemctl enable --now "$unit" >/dev/null 2>&1 || true
done
for unit in ironpanel-legacy-bot ironpanel-simple-install ironpanel-old-updater; do
  systemctl disable --now "$unit" >/dev/null 2>&1 || true
done
# Protocol core repairs are intentionally not run here; they can hang on package conflicts.
# Use Health & Repair for manual repair of a specific protocol.
timeout 60 bash "$APP_DIR/scripts/apply_speed_limits.sh" --install-service >/dev/null 2>&1 || true
timeout 60 bash "$APP_DIR/scripts/apply_node_gateway.sh" --apply >/dev/null 2>&1 || true
systemctl restart ironpanel >/dev/null 2>&1 || true

if [[ -f "$APP_DIR/VERSION" ]]; then
  echo "Installed version: $(cat "$APP_DIR/VERSION")"
fi
echo "IRONPANEL_PROGRESS 100% - update completed after real upgrade exit"
echo "IRONPANEL_UPDATE_COMPLETE_REAL"
echo "[$(date -Is)] IronPanel GitHub updater finished"

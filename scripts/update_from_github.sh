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
exec > >(tee -a "$LOG") 2>&1

echo "[$(date -Is)] IronPanel GitHub updater started"
echo "IRONPANEL_PROGRESS 1% - updater started"
echo "Mode: full source + dependency + database + systemd + VPN service sync"
echo "Repo: $REPO_URL"
echo "Branch: $BRANCH"
echo "App: $APP_DIR"

apt-get update >/dev/null 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y git rsync curl ca-certificates >/dev/null 2>&1 || true

if [[ -d "$APP_DIR" ]]; then
  echo "IRONPANEL_PROGRESS 10% - creating source backup"
echo "Creating source backup..."
  tar -C "$(dirname "$APP_DIR")" -czf "$BACKUP_DIR/ironpanel-src-$STAMP.tar.gz" "$(basename "$APP_DIR")" \
    --exclude='ironpanel/.venv' --exclude='ironpanel/__pycache__' --exclude='ironpanel/*.pyc' >/dev/null 2>&1 || true
fi
if [[ -d "$ETC_DIR" ]]; then
  echo "Creating config/database backup..."
  tar -C "$(dirname "$ETC_DIR")" -czf "$BACKUP_DIR/ironpanel-etc-$STAMP.tar.gz" "$(basename "$ETC_DIR")" >/dev/null 2>&1 || true
fi

if [[ -d "$APP_DIR/.git" ]]; then
  echo "IRONPANEL_PROGRESS 35% - updating existing checkout"
echo "Existing Git checkout detected; updating in-place."
  cd "$APP_DIR"
  git remote set-url origin "$REPO_URL" || true
  git fetch --depth 1 origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
  chmod +x "$APP_DIR/upgrade.sh" "$APP_DIR/scripts/"*.sh 2>/dev/null || true
  IRONPANEL_FULL_SERVICE_SYNC=1 bash "$APP_DIR/upgrade.sh" --github-full-sync
else
  echo "IRONPANEL_PROGRESS 35% - cloning fresh source"
echo "Non-Git install detected; cloning fresh release to temporary directory."
  rm -rf "$WORK/ironpanel"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$WORK/ironpanel"
  if [[ ! -f "$WORK/ironpanel/upgrade.sh" ]]; then
    echo "ERROR: upgrade.sh not found in repository. Aborting."
    exit 2
  fi
  chmod +x "$WORK/ironpanel/upgrade.sh" "$WORK/ironpanel/scripts/"*.sh 2>/dev/null || true
  cd "$WORK/ironpanel"
  IRONPANEL_FULL_SERVICE_SYNC=1 bash upgrade.sh --github-full-sync
fi

echo "IRONPANEL_PROGRESS 85% - post-upgrade service reconciliation"
echo "Running post-upgrade service reconciliation..."
systemctl daemon-reload || true
for unit in ironpanel ironpanel-sales-bot ironpanel-admin-bot ironpanel-usage-sync.timer ironpanel-job-worker.timer ironpanel-sales-reminders.timer ironpanel-admin-report.timer ironpanel-backup-v17.timer; do
  systemctl enable --now "$unit" >/dev/null 2>&1 || true
done
for unit in ironpanel-legacy-bot ironpanel-simple-install ironpanel-old-updater; do
  systemctl disable --now "$unit" >/dev/null 2>&1 || true
done
if [[ -x "$APP_DIR/scripts/repair_telegram_proxy.sh" ]]; then bash "$APP_DIR/scripts/repair_telegram_proxy.sh" --sync >/dev/null 2>&1 || true; fi
if [[ -x "$APP_DIR/scripts/repair_ssh.sh" ]]; then bash "$APP_DIR/scripts/repair_ssh.sh" --sync >/dev/null 2>&1 || true; fi
if [[ -x "$APP_DIR/scripts/ironpanel_doctor.sh" ]]; then bash "$APP_DIR/scripts/ironpanel_doctor.sh" --repair >/dev/null 2>&1 || true; fi

if [[ -f "$APP_DIR/VERSION" ]]; then
  echo "Installed version: $(cat "$APP_DIR/VERSION")"
fi
echo "IRONPANEL_PROGRESS 100% - update completed"
echo "IRONPANEL_UPDATE_COMPLETE" # safe-update marker for UI
echo "[$(date -Is)] IronPanel GitHub updater finished"

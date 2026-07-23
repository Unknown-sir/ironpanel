#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${IRONPANEL_APP_DIR:-/opt/ironpanel}
ETC_DIR=${IRONPANEL_ETC_DIR:-/etc/ironpanel}
LOG=${IRONPANEL_UPGRADE_DB_LOG:-/var/log/ironpanel-upgrade-db.log}
mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

restart_after=0
stop_unit(){ systemctl stop "$1" >/dev/null 2>&1 || true; }
start_unit(){ systemctl start "$1" >/dev/null 2>&1 || true; }
enable_now(){ systemctl enable --now "$1" >/dev/null 2>&1 || true; }

echo "[$(date -Is)] IronPanel safe DB upgrade started"
if [[ ! -x "$APP_DIR/.venv/bin/flask" ]]; then
  echo "ERROR: Flask binary not found: $APP_DIR/.venv/bin/flask"
  exit 2
fi

# Stop background DB writers first. Keep this list broad: missing units are ignored.
for unit in \
  ironpanel-usage-sync.timer ironpanel-usage-sync.service \
  ironpanel-job-worker.timer ironpanel-job-worker.service \
  ironpanel-license-heartbeat.timer ironpanel-license-heartbeat.service \
  ironpanel-sales-bot.service ironpanel-admin-bot.service \
  ironpanel-sales-reminders.timer ironpanel-sales-reminders.service \
  ironpanel-admin-report.timer ironpanel-admin-report.service \
  ironpanel-backup-v17.timer ironpanel-backup-v17.service \
  ironpanel-safe-backup.timer ironpanel-safe-backup.service; do
  stop_unit "$unit"
done

# When called manually or by upgrade.sh, stop the web process too unless disabled.
if [[ "${IRONPANEL_DB_UPGRADE_KEEP_PANEL:-0}" != "1" ]]; then
  if systemctl is-active --quiet ironpanel; then restart_after=1; fi
  stop_unit ironpanel
  # Give gunicorn/Flask workers time to release SQLite handles.
  sleep 2
fi

cd "$APP_DIR"
if [[ -f "$ETC_DIR/ironpanel.env" ]]; then set -a; . "$ETC_DIR/ironpanel.env"; set +a; fi
export IRONPANEL_SQLITE_TIMEOUT=${IRONPANEL_SQLITE_TIMEOUT:-90}

attempts=${IRONPANEL_DB_UPGRADE_ATTEMPTS:-12}
for i in $(seq 1 "$attempts"); do
  echo "[$(date -Is)] Running flask upgrade-db attempt $i/$attempts"
  if "$APP_DIR/.venv/bin/flask" --app run.py upgrade-db; then
    echo "[$(date -Is)] IronPanel DB upgrade completed"
    ok=1
    break
  fi
  rc=$?
  echo "[$(date -Is)] upgrade-db failed with rc=$rc"
  if [[ $i -lt $attempts ]]; then
    sleep $(( i < 8 ? i : 8 ))
  fi
done

if [[ "${ok:-0}" != "1" ]]; then
  echo "ERROR: upgrade-db failed after $attempts attempts. Current DB users:"
  command -v fuser >/dev/null 2>&1 && fuser -v "${DATABASE_URL#sqlite:///}" || true
  exit 1
fi

systemctl daemon-reload || true
for unit in ironpanel-usage-sync.timer ironpanel-license-heartbeat.timer ironpanel-job-worker.timer ironpanel-backup-v17.timer; do
  enable_now "$unit"
done
if [[ $restart_after == 1 || "${IRONPANEL_DB_UPGRADE_RESTART_PANEL:-0}" == "1" ]]; then
  start_unit ironpanel
fi
start_unit ironpanel-admin-bot
start_unit ironpanel-sales-bot

echo "[$(date -Is)] IronPanel safe DB upgrade finished"

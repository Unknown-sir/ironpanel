#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR=${IRONPANEL_APP_DIR:-/opt/ironpanel}
ETC_DIR=${IRONPANEL_ETC_DIR:-/etc/ironpanel}
ENV_FILE=${IRONPANEL_ENV_FILE:-$ETC_DIR/ironpanel.env}
REPAIR=0
[[ "${1:-}" == "--repair" ]] && REPAIR=1

# Manual commands do not inherit EnvironmentFile= from systemd. Load the same
# runtime environment as ironpanel.service before importing the Flask app.
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi
export IRONPANEL_CONFIG_ROOT=${IRONPANEL_CONFIG_ROOT:-$ETC_DIR}
export DATABASE_URL=${DATABASE_URL:-sqlite:///$ETC_DIR/ironpanel.db}

validate_sqlite_target(){
  [[ "$DATABASE_URL" == sqlite:///* ]] || return 0
  local db_path="${DATABASE_URL#sqlite:///}"
  echo "IronPanel database: $db_path"
  if [[ ! -s "$db_path" ]]; then
    echo "ERROR: configured IronPanel database is missing or empty: $db_path" >&2
    echo "Refusing repair against an unrelated/empty database. Check $ENV_FILE" >&2
    return 31
  fi
  if command -v sqlite3 >/dev/null 2>&1; then
    local missing=()
    local table count
    for table in app_setting vpn_user; do
      count=$(sqlite3 "$db_path" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='$table';" 2>/dev/null || echo 0)
      [[ "$count" == "1" ]] || missing+=("$table")
    done
    if (( ${#missing[@]} )); then
      echo "ERROR: $db_path is not an initialized IronPanel database." >&2
      echo "Missing tables: ${missing[*]}" >&2
      echo "Locate/restore the original database before running init-db or repair." >&2
      return 32
    fi
  fi
}

if [[ -x "$APP_DIR/.venv/bin/flask" && -f "$APP_DIR/run.py" ]]; then
  validate_sqlite_target
  cd "$APP_DIR"
  if [[ "$REPAIR" == "1" ]]; then
    "$APP_DIR/.venv/bin/flask" --app run.py doctor --repair
  else
    "$APP_DIR/.venv/bin/flask" --app run.py doctor
  fi
  exit $?
fi

echo "IronPanel Doctor fallback"
echo "========================="
echo "App: $APP_DIR"
echo "Config: $ETC_DIR"
echo "Database URL: $DATABASE_URL"
[[ -d "$APP_DIR" ]] && echo "OK app directory" || echo "FAIL missing app directory"
[[ -f "$ENV_FILE" ]] && echo "OK env file" || echo "FAIL missing env file"
[[ -f "$ETC_DIR/ironpanel.db" ]] && echo "OK database" || echo "WARN database missing"
for svc in ironpanel ironpanel-usage-sync.timer openvpn-server@server wg-quick@wg0 ocserv xray hysteria-server ironpanel-tgproxy ssh sshd; do
  state=$(systemctl is-active "$svc" 2>/dev/null || true)
  [[ -n "$state" ]] && echo "$svc: $state"
done
if [[ "$REPAIR" == "1" ]]; then
  systemctl daemon-reload || true
  systemctl restart ironpanel || true
  echo "Fallback repair finished"
fi

#!/usr/bin/env bash
set -Eeuo pipefail

# IronPanel installer v18.6.3
# One installer only: interactive, simple questions, safe defaults on Enter.
# Can also bootstrap directly from GitHub when run via curl/wget.
# Full logs: /var/log/ironpanel-install.log

LOG_FILE=${IRONPANEL_INSTALL_LOG:-/var/log/ironpanel-install.log}
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
touch "$LOG_FILE" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1

on_error(){
  local line="$1" code="$2"
  echo ""
  echo "[ERROR] Installation failed. line: $line | exit code: $code"
  echo "[ERROR] Full log: $LOG_FILE"
  echo "[HINT] After fixing the issue, rerun: sudo bash install.sh"
  echo "[HINT] Health repair: sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair"
}
trap 'on_error $LINENO $?' ERR

if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash install.sh"; exit 1; fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR=${IRONPANEL_APP_DIR:-/opt/ironpanel}
ETC_DIR=${IRONPANEL_ETC_DIR:-/etc/ironpanel}
ENV_FILE="$ETC_DIR/ironpanel.env"

# Direct GitHub bootstrap: if this standalone install.sh was fetched with curl
# and the project files are not beside it, download the repository archive first.
bootstrap_from_github(){
  local repo branch tmp zip src repo_name
  repo=${IRONPANEL_GITHUB_REPO:-Unknown-sir/ironpanel}
  branch=${IRONPANEL_GITHUB_BRANCH:-main}
  repo_name="${repo##*/}"
  tmp=$(mktemp -d /tmp/ironpanel-src.XXXXXX)
  zip="$tmp/source.zip"
  echo "[IronPanel] Downloading source from GitHub: $repo@$branch"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y >/dev/null 2>&1 || true
  apt-get install -y curl unzip ca-certificates >/dev/null 2>&1 || true
  curl -fsSL "https://github.com/$repo/archive/refs/heads/$branch.zip" -o "$zip"
  unzip -q "$zip" -d "$tmp"
  src="$tmp/${repo_name}-${branch}"
  if [[ ! -f "$src/install.sh" ]]; then
    src=$(find "$tmp" -maxdepth 3 -type f -name install.sh -printf '%h\n' | head -n1 || true)
  fi
  if [[ -z "$src" || ! -f "$src/install.sh" ]]; then
    echo "[ERROR] install.sh was not found in the GitHub source." >&2
    exit 1
  fi
  exec bash "$src/install.sh" "$@"
}
if [[ ! -f "$SCRIPT_DIR/requirements.txt" || ! -d "$SCRIPT_DIR/app" ]]; then
  bootstrap_from_github "$@"
fi

INSTALL_VPN_CORE=1
AUTO_SSL=${IRONPANEL_AUTO_SSL:-n}
AUTO_RESTART=1
CUSTOM_PORTS=${IRONPANEL_CUSTOM_PORTS:-n}
INSTALL_CORE_ANSWER=${IRONPANEL_INSTALL_VPN_CORE:-y}

ADMIN_USER=${IRONPANEL_ADMIN_USER:-admin}
ADMIN_PASS=${IRONPANEL_ADMIN_PASS:-}
PANEL_PORT=${IRONPANEL_PORT:-8080}
PUBLIC_HOST=${IRONPANEL_PUBLIC_HOST:-}
TUNNEL_HOST=${IRONPANEL_TUNNEL_HOST:-}
SSL_DOMAIN=${IRONPANEL_SSL_DOMAIN:-}
SSL_EMAIL=${IRONPANEL_SSL_EMAIL:-}
LICENSE_SERVER=${IRONPANEL_LICENSE_SERVER:-http://license.skyshield.space:8002}
LICENSE_KEY=${IRONPANEL_LICENSE_KEY:-}
OPENVPN_PROTO=${IRONPANEL_OPENVPN_PROTO:-udp}
OPENVPN_UDP=${IRONPANEL_OPENVPN_UDP:-1194}
OPENVPN_TCP=${IRONPANEL_OPENVPN_TCP:-1195}
OCSERV_PORT=${IRONPANEL_OCSERV_PORT:-8445}
WIREGUARD_PORT=${IRONPANEL_WIREGUARD_PORT:-51820}
XRAY_PORT=${IRONPANEL_XRAY_PORT:-443}
XRAY_API_PORT=${IRONPANEL_XRAY_API_PORT:-10085}
PPTP_PORT=${IRONPANEL_PPTP_PORT:-1723}
HYSTERIA2_PORT=${IRONPANEL_HYSTERIA2_PORT:-4433}
HYSTERIA2_UP=${IRONPANEL_HYSTERIA2_UP:-100 mbps}
HYSTERIA2_DOWN=${IRONPANEL_HYSTERIA2_DOWN:-300 mbps}
TELEGRAM_PROXY_BASE=${IRONPANEL_TELEGRAM_PROXY_BASE:-6969}
WIREGUARD_MTU=${IRONPANEL_WIREGUARD_MTU:-1280}
WIREGUARD_KEEPALIVE=${IRONPANEL_WIREGUARD_KEEPALIVE:-25}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-vpn-core) INSTALL_CORE_ANSWER=n; shift;;
    --skip-ssl) AUTO_SSL=n; shift;;
    --auto-ssl) AUTO_SSL=y; shift;;
    --domain|--host) PUBLIC_HOST="${2:-}"; SSL_DOMAIN="${2:-}"; shift 2;;
    --ssl-domain) SSL_DOMAIN="${2:-}"; shift 2;;
    --email) SSL_EMAIL="${2:-}"; shift 2;;
    --admin-user) ADMIN_USER="${2:-admin}"; shift 2;;
    --admin-pass) ADMIN_PASS="${2:-}"; shift 2;;
    --port|--panel-port) PANEL_PORT="${2:-8080}"; shift 2;;
    --tunnel-host) TUNNEL_HOST="${2:-}"; shift 2;;
    --openvpn-proto) OPENVPN_PROTO="${2:-udp}"; shift 2;;
    --xray-port) XRAY_PORT="${2:-443}"; shift 2;;
    --hysteria2-port) HYSTERIA2_PORT="${2:-4433}"; shift 2;;
    --telegram-proxy-base) TELEGRAM_PROXY_BASE="${2:-6969}"; shift 2;;
    --repo) IRONPANEL_GITHUB_REPO="${2:-Unknown-sir/ironpanel}"; shift 2;;
    --branch) IRONPANEL_GITHUB_BRANCH="${2:-main}"; shift 2;;
    --help|-h)
      cat <<HELP
IronPanel installer
Usage:
  sudo bash install.sh
  sudo bash install.sh --domain panel.example.com --email admin@example.com --auto-ssl
  bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)

This is the only installer. It asks simple questions and uses safe defaults when you press Enter.
Options are optional shortcuts for automation, not a second install mode.
HELP
      exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

exec 9>/tmp/ironpanel-install.lock
if ! flock -n 9; then echo "Another IronPanel installation is already running. Try again in a few minutes."; exit 1; fi

info(){ echo -e "\n[IronPanel] $*"; }
warn(){ echo -e "[WARN] $*"; }
is_yes(){ [[ "$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')" =~ ^(y|yes|1|true|on|بله|آره)$ ]]; }
retry(){
  local tries=${IRONPANEL_RETRY:-3}; local delay=5; local n=1
  until "$@"; do
    if (( n >= tries )); then return 1; fi
    warn "Command failed; retrying ($n/$tries): $*"
    sleep "$delay"; n=$((n+1)); delay=$((delay+5))
  done
}
wait_for_apt(){
  local i
  for i in {1..60}; do
    if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && ! fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  warn "apt/dpkg is still locked; continuing and logging any failure."
}
apt_install(){
  wait_for_apt
  export DEBIAN_FRONTEND=noninteractive
  echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections || true
  echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections || true
  retry apt-get update -y
  retry apt-get install -y "$@"
}
valid_port(){ [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 65535 )); }
ask(){
  local var="$1" prompt="$2" def="$3" secret="${4:-0}" val=""
  # Bash does not support defaults inside indirect expansion like ${!var:-}.
  # Keep compatibility with older Ubuntu/Debian bash builds by reading the
  # current value only when the variable is already set.
  if [[ -n "${!var+x}" ]]; then
    val="${!var}"
  fi
  if [[ "$secret" == "1" ]]; then
    read -rsp "$prompt [$def]: " val; echo
  else
    read -rp "$prompt [$def]: " val
  fi
  val=${val:-$def}; printf -v "$var" '%s' "$val"
}
detect_public_host(){
  local host=""
  host=$(curl -fsS4 --max-time 6 https://api.ipify.org 2>/dev/null || true)
  [[ -n "$host" ]] || host=$(hostname -I 2>/dev/null | awk '{print $1}')
  [[ -n "$host" ]] || host="127.0.0.1"
  printf '%s' "$host"
}
install_certbot_safe() {
  info "Preparing a healthy Certbot for Auto SSL"
  apt_install snapd ca-certificates python3-venv python3-pip || true
  systemctl enable --now snapd.socket >/dev/null 2>&1 || true
  systemctl start snapd.service >/dev/null 2>&1 || true
  if command -v snap >/dev/null 2>&1; then
    snap install core >/dev/null 2>&1 || snap refresh core >/dev/null 2>&1 || true
    snap install --classic certbot >/dev/null 2>&1 || true
    ln -sf /snap/bin/certbot /usr/local/bin/certbot >/dev/null 2>&1 || true
  fi
  if ! /snap/bin/certbot --version >/dev/null 2>&1 && ! /usr/local/bin/certbot --version >/dev/null 2>&1; then
    apt_install certbot python3-openssl python3-cryptography || true
  fi
  if [[ -x "$APP_DIR/scripts/repair_certbot.sh" ]]; then bash "$APP_DIR/scripts/repair_certbot.sh" >/dev/null 2>&1 || true; fi
}
backup_existing(){
  local stamp backup_root
  stamp=$(date +%Y%m%d-%H%M%S)
  backup_root=/var/backups/ironpanel
  mkdir -p "$backup_root"
  if [[ -d "$APP_DIR" && "$SCRIPT_DIR" != "$APP_DIR" ]]; then
    tar -czf "$backup_root/app-$stamp.tar.gz" -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")" >/dev/null 2>&1 || true
  fi
  if [[ -d "$ETC_DIR" ]]; then
    tar -czf "$backup_root/etc-$stamp.tar.gz" -C "$(dirname "$ETC_DIR")" "$(basename "$ETC_DIR")" >/dev/null 2>&1 || true
  fi
}
write_env_file(){
  local secret api_key
  secret=${IRONPANEL_SECRET_KEY:-$(openssl rand -hex 32)}
  api_key=${IRONPANEL_API_KEY:-$(openssl rand -hex 32)}
  cat > "$ENV_FILE" <<ENV
IRONPANEL_SECRET_KEY=$secret
IRONPANEL_API_KEY=$api_key
IRONPANEL_PUBLIC_HOST=$PUBLIC_HOST
IRONPANEL_TUNNEL_HOST=$TUNNEL_HOST
IRONPANEL_PORT=$PANEL_PORT
IRONPANEL_CONFIG_ROOT=$ETC_DIR
IRONPANEL_WIREGUARD_MTU=$WIREGUARD_MTU
IRONPANEL_WIREGUARD_KEEPALIVE=$WIREGUARD_KEEPALIVE
DATABASE_URL=sqlite:///$ETC_DIR/ironpanel.db
ENV
  chmod 600 "$ENV_FILE"
}
write_services(){
  cat > /etc/systemd/system/ironpanel.service <<SERVICE
[Unit]
Description=Ironpanel VPN Management Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=/bin/bash -lc 'CERT="\${IRONPANEL_SSL_CERT:-}"; KEY="\${IRONPANEL_SSL_KEY:-}"; SSL_ARGS=""; if [ -n "\$CERT" ] && [ -n "\$KEY" ] && [ -f "\$CERT" ] && [ -f "\$KEY" ]; then SSL_ARGS="--certfile \$CERT --keyfile \$KEY"; fi; exec $APP_DIR/.venv/bin/gunicorn -k gthread -w 2 -b 0.0.0.0:\${IRONPANEL_PORT} \$SSL_ARGS run:app'
Restart=always
RestartSec=3
User=root
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SERVICE

  cat > /etc/systemd/system/ironpanel-usage-sync.service <<SERVICE
[Unit]
Description=Ironpanel VPN Traffic Usage Sync
After=network-online.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/flask --app run.py sync-usage
User=root
SERVICE

  cat > /etc/systemd/system/ironpanel-usage-sync.timer <<TIMER
[Unit]
Description=Run Ironpanel VPN Traffic Usage Sync every minute

[Timer]
OnBootSec=60s
OnUnitActiveSec=60s
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
TIMER

  cat > /etc/systemd/system/ironpanel-sales-bot.service <<SERVICE
[Unit]
Description=IronPanel Telegram Sales Bot
After=network-online.target ironpanel.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SERVICE

  cat > /etc/systemd/system/ironpanel-admin-bot.service <<SERVICE
[Unit]
Description=IronPanel Telegram Admin Bot
After=network-online.target ironpanel.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/python -m bot.admin
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SERVICE

  cat > /etc/systemd/system/ironpanel-sales-reminders.service <<SERVICE
[Unit]
Description=IronPanel Sales Bot Expiry and Traffic Reminders
After=network-online.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/python -m bot.reminders
User=root
SERVICE

  cat > /etc/systemd/system/ironpanel-sales-reminders.timer <<TIMER
[Unit]
Description=Run IronPanel Sales Bot reminders daily

[Timer]
OnBootSec=180s
OnCalendar=*-*-* 10:00:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER

  cat > /etc/systemd/system/ironpanel-job-worker.service <<SERVICE
[Unit]
Description=IronPanel Local Job Worker
After=network-online.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/flask --app run.py process-jobs
User=root
SERVICE

  cat > /etc/systemd/system/ironpanel-job-worker.timer <<TIMER
[Unit]
Description=Run IronPanel local job worker every minute

[Timer]
OnBootSec=90s
OnUnitActiveSec=60s
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
TIMER

  cat > /etc/systemd/system/ironpanel-admin-report.service <<SERVICE
[Unit]
Description=IronPanel Telegram Admin Daily Report
After=network-online.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/scripts/admin_telegram_report.py
User=root
SERVICE

  cat > /etc/systemd/system/ironpanel-admin-report.timer <<TIMER
[Unit]
Description=Run IronPanel Telegram admin report daily

[Timer]
OnBootSec=240s
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER

  cat > /etc/systemd/system/ironpanel-backup-v17.service <<SERVICE
[Unit]
Description=IronPanel Full Backup
After=network-online.target ironpanel.service

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/flask --app run.py backup-v17
User=root
SERVICE

  cat > /etc/systemd/system/ironpanel-backup-v17.timer <<TIMER
[Unit]
Description=Run IronPanel full backup daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER
}

info "Starting IronPanel installation"
. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  warn "Ubuntu 22.04/24.04 or Debian is recommended. Continuing anyway."
fi
ARCH=$(uname -m)
case "$ARCH" in x86_64|amd64|aarch64|arm64) ;; *) warn "Architecture $ARCH is not fully tested.";; esac

if [[ -n "$SSL_DOMAIN" && -z "$PUBLIC_HOST" ]]; then PUBLIC_HOST="$SSL_DOMAIN"; fi
[[ -n "$PUBLIC_HOST" ]] || PUBLIC_HOST=$(detect_public_host)
[[ -n "$TUNNEL_HOST" ]] || TUNNEL_HOST=""
[[ -n "$ADMIN_PASS" ]] || ADMIN_PASS=$(openssl rand -base64 18 | tr -d '\n')

cat <<INTRO

IronPanel one-step installer
Press Enter on any question to use the recommended safe default.

INTRO
ask ADMIN_USER "Admin username" "$ADMIN_USER"
ask ADMIN_PASS "Admin password" "$ADMIN_PASS" 1
ask PANEL_PORT "Panel port" "$PANEL_PORT"
ask PUBLIC_HOST "Public domain or IP for panel and configs" "$PUBLIC_HOST"
ask TUNNEL_HOST "Separate config domain/IP; leave empty to use the public host" "$TUNNEL_HOST"
ask INSTALL_CORE_ANSWER "Install/repair VPN cores? y/n" "$INSTALL_CORE_ANSWER"
ask AUTO_SSL "Issue Auto SSL now? y/n" "$AUTO_SSL"
if is_yes "$AUTO_SSL"; then
  [[ -n "$SSL_DOMAIN" ]] || SSL_DOMAIN="$PUBLIC_HOST"
  ask SSL_DOMAIN "SSL domain" "$SSL_DOMAIN"
  ask SSL_EMAIL "Let's Encrypt email" "${SSL_EMAIL:-admin@$SSL_DOMAIN}"
fi
ask CUSTOM_PORTS "Change advanced ports? y/n" "$CUSTOM_PORTS"
if is_yes "$CUSTOM_PORTS"; then
  ask OPENVPN_PROTO "OpenVPN transport tcp/udp" "$OPENVPN_PROTO"
  ask OPENVPN_UDP "OpenVPN UDP port" "$OPENVPN_UDP"
  ask OPENVPN_TCP "OpenVPN TCP port" "$OPENVPN_TCP"
  ask OCSERV_PORT "Cisco/Ocserv TCP/UDP port" "$OCSERV_PORT"
  ask WIREGUARD_PORT "WireGuard UDP port" "$WIREGUARD_PORT"
  ask WIREGUARD_MTU "WireGuard MTU" "$WIREGUARD_MTU"
  ask WIREGUARD_KEEPALIVE "WireGuard PersistentKeepalive" "$WIREGUARD_KEEPALIVE"
  ask XRAY_PORT "Xray TCP port" "$XRAY_PORT"
  ask XRAY_API_PORT "Xray local API port" "$XRAY_API_PORT"
  ask PPTP_PORT "PPTP TCP port" "$PPTP_PORT"
  ask HYSTERIA2_PORT "Hysteria2 UDP port" "$HYSTERIA2_PORT"
  ask TELEGRAM_PROXY_BASE "Telegram MTProto proxy base TCP port" "$TELEGRAM_PROXY_BASE"
  ask HYSTERIA2_UP "Hysteria2 upload hint" "$HYSTERIA2_UP"
  ask HYSTERIA2_DOWN "Hysteria2 download hint" "$HYSTERIA2_DOWN"
fi
is_yes "$INSTALL_CORE_ANSWER" && INSTALL_VPN_CORE=1 || INSTALL_VPN_CORE=0
OPENVPN_PROTO=$(echo "$OPENVPN_PROTO" | tr '[:upper:]' '[:lower:]'); [[ "$OPENVPN_PROTO" == "tcp" ]] || OPENVPN_PROTO=udp
for p in "$PANEL_PORT" "$OPENVPN_UDP" "$OPENVPN_TCP" "$OCSERV_PORT" "$WIREGUARD_PORT" "$XRAY_PORT" "$XRAY_API_PORT" "$PPTP_PORT" "$HYSTERIA2_PORT"; do valid_port "$p" || { echo "Invalid port: $p"; exit 1; }; done
[[ "$WIREGUARD_MTU" =~ ^[0-9]+$ ]] || { echo "Invalid WireGuard MTU: $WIREGUARD_MTU"; exit 1; }

mkdir -p "$APP_DIR" "$ETC_DIR" "$ETC_DIR/profiles"
backup_existing

info "Installing base dependencies"
apt_install python3 python3-venv python3-pip nginx snapd openssl curl rsync sqlite3 qrencode iptables-persistent ca-certificates lsof net-tools iproute2 ufw unzip

info "Copying project files"
if [[ "$SCRIPT_DIR" != "$APP_DIR" ]]; then
  rsync -a --delete --exclude '.venv' --exclude '__pycache__' "$SCRIPT_DIR/" "$APP_DIR/"
fi
chmod +x "$APP_DIR/scripts/"*.sh "$APP_DIR/scripts/"*.py "$APP_DIR/install"*.sh 2>/dev/null || true

install_certbot_safe

info "Creating Python environment"
python3 -m venv "$APP_DIR/.venv"
retry "$APP_DIR/.venv/bin/pip" install --upgrade pip wheel setuptools
retry "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

write_env_file
write_services

info "Initializing database and defaults"
set -a; . "$ENV_FILE"; set +a
cd "$APP_DIR"
"$APP_DIR/.venv/bin/flask" --app run.py init-db --admin-user "$ADMIN_USER" --admin-pass "$ADMIN_PASS"
"$APP_DIR/.venv/bin/python" - <<PYSET
import os
from app import create_app
from app.core.extensions import db
from app.core.models import AppSetting
app=create_app()
settings={
 "public_host": os.environ.get("IRONPANEL_PUBLIC_HOST",""),
 "tunnel_host": os.environ.get("IRONPANEL_TUNNEL_HOST",""),
 "subscription_domain": os.environ.get("IRONPANEL_SUBSCRIPTION_DOMAIN",""),
 "active_protocols": "openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy",
 "openvpn_transport": "$OPENVPN_PROTO",
 "port_panel": os.environ.get("IRONPANEL_PORT","8080"),
 "port_openvpn_udp": "$OPENVPN_UDP",
 "port_openvpn_tcp": "$OPENVPN_TCP",
 "port_ocserv_tcp": "$OCSERV_PORT",
 "port_ocserv_udp": "$OCSERV_PORT",
 "port_wireguard_udp": "$WIREGUARD_PORT",
 "port_xray_tcp": "$XRAY_PORT",
 "port_xray_api": "$XRAY_API_PORT",
 "port_pptp_tcp": "$PPTP_PORT",
 "port_hysteria2_udp": "$HYSTERIA2_PORT",
 "port_telegram_proxy_base": "$TELEGRAM_PROXY_BASE",
 "telegram_proxy_enabled": "1",
 "telegram_proxy_secret_salt": "",
 "telegram_proxy_repo": "https://github.com/Unknown-sir/JSMTProxy.git",
 "hysteria2_tls_cert_file": "/etc/hysteria/server.crt",
 "hysteria2_tls_key_file": "/etc/hysteria/server.key",
 "hysteria2_up_mbps": "$HYSTERIA2_UP",
 "hysteria2_down_mbps": "$HYSTERIA2_DOWN",
 "xray_port": "$XRAY_PORT",
 "xray_api_port": "$XRAY_API_PORT",
 "license_server_url": "$LICENSE_SERVER",
 "license_key": "$LICENSE_KEY",
 "ocserv_transport": "tcp_udp",
 "wireguard_transport": "udp",
 "wireguard_mtu": "$WIREGUARD_MTU",
 "wireguard_persistent_keepalive": "$WIREGUARD_KEEPALIVE",
 "language": "en",
 "theme_mode": "dark",
 "l2tp_transport": "udp",
 "ui_mode": "simple",
 "first_run_checklist": "1",
}
with app.app_context():
    for k,v in settings.items():
        row=AppSetting.query.filter_by(key=k).first()
        if not row:
            db.session.add(AppSetting(key=k,value=str(v)))
        elif k not in ("license_key",):
            row.value=str(v)
    db.session.commit()
PYSET

if [[ "$INSTALL_VPN_CORE" == "1" ]]; then
  info "Installing/repairing VPN cores. If a service is unsupported on this OS, the panel still installs and Health Check shows the repair path."
  if ! env ETC_DIR="$ETC_DIR" PUBLIC_HOST="$PUBLIC_HOST" WIREGUARD_MTU="$WIREGUARD_MTU" IRONPANEL_WIREGUARD_MTU="$WIREGUARD_MTU" OPENVPN_PROTO="$OPENVPN_PROTO" OPENVPN_UDP="$OPENVPN_UDP" OPENVPN_TCP="$OPENVPN_TCP" OCSERV_PORT="$OCSERV_PORT" OCSERV_TCP="$OCSERV_PORT" OCSERV_UDP="$OCSERV_PORT" WIREGUARD_PORT="$WIREGUARD_PORT" XRAY_PORT="$XRAY_PORT" XRAY_API_PORT="$XRAY_API_PORT" PPTP_PORT="$PPTP_PORT" HYSTERIA2_PORT="$HYSTERIA2_PORT" HYSTERIA2_UP="$HYSTERIA2_UP" HYSTERIA2_DOWN="$HYSTERIA2_DOWN" TELEGRAM_PROXY_BASE="$TELEGRAM_PROXY_BASE" bash "$APP_DIR/scripts/install_vpn_core.sh"; then
    warn "Some VPN cores did not install completely. The panel will still start; use Health Check / Repair or: sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair"
  fi
fi

bash "$APP_DIR/scripts/repair_xray.sh" >/dev/null 2>&1 || true
bash "$APP_DIR/scripts/repair_hysteria2.sh" >/dev/null 2>&1 || true
bash "$APP_DIR/scripts/repair_telegram_proxy.sh" --install-only >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable --now ironpanel >/dev/null 2>&1 || true
systemctl enable --now ironpanel-usage-sync.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl enable --now ironpanel-job-worker.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-admin-bot >/dev/null 2>&1 || true
systemctl enable --now ironpanel-admin-report.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-reminders.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-backup-v17.timer >/dev/null 2>&1 || true
if [[ "$AUTO_RESTART" == "1" ]]; then systemctl restart ironpanel; fi
systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl restart ironpanel-admin-bot >/dev/null 2>&1 || true

if [[ -n "$SSL_DOMAIN" && -n "$SSL_EMAIL" ]] && is_yes "$AUTO_SSL"; then
  info "Trying initial SSL issuance for $SSL_DOMAIN"
  "$APP_DIR/.venv/bin/python" - <<PYSSL || true
from app import create_app
from app.services.ssl_manager import issue_and_apply_ssl
app=create_app()
with app.app_context():
    print(issue_and_apply_ssl('$SSL_DOMAIN', '$SSL_EMAIL').get('message',''))
PYSSL
fi

URL_HOST="$PUBLIC_HOST"
cat <<INFO

✅ IronPanel installed/updated successfully.

Panel URL: http://$URL_HOST:$PANEL_PORT
Admin username: $ADMIN_USER
Admin password: $ADMIN_PASS
UI mode: Simple by default; change it from the panel header/settings.
Version: $(cat "$APP_DIR/VERSION" 2>/dev/null || echo unknown)
Install path: $APP_DIR
Config path: $ETC_DIR
Install log: $LOG_FILE

Useful commands:
  sudo systemctl status ironpanel --no-pager
  sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh
  sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair
  sudo bash /opt/ironpanel/upgrade.sh --restart-only

INFO

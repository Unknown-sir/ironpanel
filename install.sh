#!/usr/bin/env bash
set -Eeuo pipefail

# IronPanel installer v18.5.2
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
  echo "[ERROR] نصب کامل نشد. خط: $line | کد خروجی: $code"
  echo "[ERROR] لاگ کامل: $LOG_FILE"
  echo "[HINT] بعد از رفع مشکل، همین دستور نصب را دوباره اجرا کن: sudo bash install.sh"
  echo "[HINT] یا برای بررسی سلامت: sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair"
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
  echo "[IronPanel] دریافت سورس از GitHub: $repo@$branch"
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
    echo "[ERROR] install.sh داخل سورس GitHub پیدا نشد." >&2
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
if ! flock -n 9; then echo "یک نصب دیگر در حال اجراست. چند دقیقه بعد دوباره تلاش کن."; exit 1; fi

info(){ echo -e "\n[IronPanel] $*"; }
warn(){ echo -e "[WARN] $*"; }
is_yes(){ [[ "$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')" =~ ^(y|yes|1|true|on|بله|آره)$ ]]; }
retry(){
  local tries=${IRONPANEL_RETRY:-3}; local delay=5; local n=1
  until "$@"; do
    if (( n >= tries )); then return 1; fi
    warn "دستور ناموفق بود؛ تلاش دوباره ($n/$tries): $*"
    sleep "$delay"; n=$((n+1)); delay=$((delay+5))
  done
}
wait_for_apt(){
  local i
  for i in {1..60}; do
    if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && ! fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  warn "apt/dpkg هنوز قفل است؛ ادامه می‌دهم و اگر خطا بدهد در لاگ ثبت می‌شود."
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
  local var="$1" prompt="$2" def="$3" secret="${4:-0}" val="${!var:-}"
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
  info "آماده‌سازی Certbot سالم برای Auto SSL"
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

info "شروع نصب IronPanel"
. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  warn "Ubuntu 22.04/24.04 یا Debian پیشنهاد می‌شود. نصب را ادامه می‌دهم."
fi
ARCH=$(uname -m)
case "$ARCH" in x86_64|amd64|aarch64|arm64) ;; *) warn "معماری $ARCH تست کامل نشده است.";; esac

if [[ -n "$SSL_DOMAIN" && -z "$PUBLIC_HOST" ]]; then PUBLIC_HOST="$SSL_DOMAIN"; fi
[[ -n "$PUBLIC_HOST" ]] || PUBLIC_HOST=$(detect_public_host)
[[ -n "$TUNNEL_HOST" ]] || TUNNEL_HOST=""
[[ -n "$ADMIN_PASS" ]] || ADMIN_PASS=$(openssl rand -base64 18 | tr -d '\n')

cat <<INTRO

IronPanel نصب یک‌مرحله‌ای
برای هر گزینه اگر مطمئن نیستی Enter بزن تا مقدار پیشنهادی استفاده شود.

INTRO
ask ADMIN_USER "نام کاربری مدیر" "$ADMIN_USER"
ask ADMIN_PASS "رمز مدیر" "$ADMIN_PASS" 1
ask PANEL_PORT "پورت پنل" "$PANEL_PORT"
ask PUBLIC_HOST "دامنه یا IP عمومی برای پنل و کانفیگ‌ها" "$PUBLIC_HOST"
ask TUNNEL_HOST "دامنه/IP جدا برای کانفیگ‌ها؛ خالی یعنی همان مورد بالا" "$TUNNEL_HOST"
ask INSTALL_CORE_ANSWER "هسته‌های VPN هم نصب/ترمیم شوند؟ y/n" "$INSTALL_CORE_ANSWER"
ask AUTO_SSL "SSL خودکار الان گرفته شود؟ y/n" "$AUTO_SSL"
if is_yes "$AUTO_SSL"; then
  [[ -n "$SSL_DOMAIN" ]] || SSL_DOMAIN="$PUBLIC_HOST"
  ask SSL_DOMAIN "دامنه SSL" "$SSL_DOMAIN"
  ask SSL_EMAIL "ایمیل Let's Encrypt" "${SSL_EMAIL:-admin@$SSL_DOMAIN}"
fi
ask CUSTOM_PORTS "پورت‌های پیشرفته را تغییر می‌دهی؟ y/n" "$CUSTOM_PORTS"
if is_yes "$CUSTOM_PORTS"; then
  ask OPENVPN_PROTO "OpenVPN transport tcp/udp" "$OPENVPN_PROTO"
  ask OPENVPN_UDP "OpenVPN UDP port" "$OPENVPN_UDP"
  ask OPENVPN_TCP "OpenVPN TCP port" "$OPENVPN_TCP"
  ask OCSERV_PORT "Cisco/Ocserv TCP/UDP port" "$OCSERV_PORT"
  ask WIREGUARD_PORT "WireGuard UDP port" "$WIREGUARD_PORT"
  ask XRAY_PORT "Xray TCP port" "$XRAY_PORT"
  ask XRAY_API_PORT "Xray local API port" "$XRAY_API_PORT"
  ask PPTP_PORT "PPTP TCP port" "$PPTP_PORT"
  ask HYSTERIA2_PORT "Hysteria2 UDP port" "$HYSTERIA2_PORT"
  ask HYSTERIA2_UP "Hysteria2 upload hint" "$HYSTERIA2_UP"
  ask HYSTERIA2_DOWN "Hysteria2 download hint" "$HYSTERIA2_DOWN"
fi
is_yes "$INSTALL_CORE_ANSWER" && INSTALL_VPN_CORE=1 || INSTALL_VPN_CORE=0
OPENVPN_PROTO=$(echo "$OPENVPN_PROTO" | tr '[:upper:]' '[:lower:]'); [[ "$OPENVPN_PROTO" == "tcp" ]] || OPENVPN_PROTO=udp
for p in "$PANEL_PORT" "$OPENVPN_UDP" "$OPENVPN_TCP" "$OCSERV_PORT" "$WIREGUARD_PORT" "$XRAY_PORT" "$XRAY_API_PORT" "$PPTP_PORT" "$HYSTERIA2_PORT"; do valid_port "$p" || { echo "پورت نامعتبر: $p"; exit 1; }; done

mkdir -p "$APP_DIR" "$ETC_DIR" "$ETC_DIR/profiles"
backup_existing

info "نصب وابستگی‌های پایه"
apt_install python3 python3-venv python3-pip nginx snapd openssl curl rsync sqlite3 qrencode iptables-persistent ca-certificates lsof net-tools iproute2 ufw unzip

info "کپی فایل‌های پروژه"
if [[ "$SCRIPT_DIR" != "$APP_DIR" ]]; then
  rsync -a --delete --exclude '.venv' --exclude '__pycache__' "$SCRIPT_DIR/" "$APP_DIR/"
fi
chmod +x "$APP_DIR/scripts/"*.sh "$APP_DIR/scripts/"*.py "$APP_DIR/install"*.sh 2>/dev/null || true

install_certbot_safe

info "ساخت محیط Python"
python3 -m venv "$APP_DIR/.venv"
retry "$APP_DIR/.venv/bin/pip" install --upgrade pip wheel setuptools
retry "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

write_env_file
write_services

info "راه‌اندازی دیتابیس و تنظیمات اولیه"
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
  info "نصب/ترمیم هسته‌های VPN. اگر یکی از سرویس‌ها روی این OS نصب نشود، پنل همچنان نصب می‌شود و Health Check مسیر ترمیم را نشان می‌دهد."
  if ! env ETC_DIR="$ETC_DIR" PUBLIC_HOST="$PUBLIC_HOST" OPENVPN_PROTO="$OPENVPN_PROTO" OPENVPN_UDP="$OPENVPN_UDP" OPENVPN_TCP="$OPENVPN_TCP" OCSERV_PORT="$OCSERV_PORT" OCSERV_TCP="$OCSERV_PORT" OCSERV_UDP="$OCSERV_PORT" WIREGUARD_PORT="$WIREGUARD_PORT" XRAY_PORT="$XRAY_PORT" XRAY_API_PORT="$XRAY_API_PORT" PPTP_PORT="$PPTP_PORT" HYSTERIA2_PORT="$HYSTERIA2_PORT" HYSTERIA2_UP="$HYSTERIA2_UP" HYSTERIA2_DOWN="$HYSTERIA2_DOWN" bash "$APP_DIR/scripts/install_vpn_core.sh"; then
    warn "نصب بعضی هسته‌های VPN کامل نشد. پنل بالا می‌آید؛ از Health Check / Repair یا دستور زیر استفاده کن: sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair"
  fi
fi

bash "$APP_DIR/scripts/repair_xray.sh" >/dev/null 2>&1 || true
bash "$APP_DIR/scripts/repair_hysteria2.sh" >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable --now ironpanel >/dev/null 2>&1 || true
systemctl enable --now ironpanel-usage-sync.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-bot >/dev/null 2>&1 || true
systemctl enable --now ironpanel-sales-reminders.timer >/dev/null 2>&1 || true
systemctl enable --now ironpanel-backup-v17.timer >/dev/null 2>&1 || true
if [[ "$AUTO_RESTART" == "1" ]]; then systemctl restart ironpanel; fi
systemctl restart ironpanel-sales-bot >/dev/null 2>&1 || true

if [[ -n "$SSL_DOMAIN" && -n "$SSL_EMAIL" ]] && is_yes "$AUTO_SSL"; then
  info "تلاش برای دریافت SSL اولیه برای $SSL_DOMAIN"
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

✅ IronPanel نصب/به‌روزرسانی شد.

آدرس پنل: http://$URL_HOST:$PANEL_PORT
نام کاربری مدیر: $ADMIN_USER
رمز مدیر: $ADMIN_PASS
حالت رابط کاربری: ساده، قابل تغییر از بالای پنل
نسخه: $(cat "$APP_DIR/VERSION" 2>/dev/null || echo unknown)
مسیر نصب: $APP_DIR
تنظیمات: $ETC_DIR
لاگ نصب: $LOG_FILE

دستورات مفید:
  sudo systemctl status ironpanel --no-pager
  sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh
  sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair
  sudo bash /opt/ironpanel/upgrade.sh --restart-only

INFO

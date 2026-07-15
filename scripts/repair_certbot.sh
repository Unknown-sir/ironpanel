#!/usr/bin/env bash
set -u
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash scripts/repair_certbot.sh"; exit 1; fi
LOG=/tmp/ironpanel-repair-certbot.log
: > "$LOG"
echo "[IronPanel] Repairing certbot..." | tee -a "$LOG"

check_certbot() {
  local bin="$1"
  [[ -x "$bin" || "$bin" == "certbot" ]] || return 1
  "$bin" --version >>"$LOG" 2>&1 || return 1
  return 0
}

apt-get update >>"$LOG" 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y snapd ca-certificates python3-venv python3-pip >>"$LOG" 2>&1 || true
systemctl enable --now snapd.socket >>"$LOG" 2>&1 || true
systemctl start snapd.service >>"$LOG" 2>&1 || true

if command -v snap >/dev/null 2>&1; then
  snap install core >>"$LOG" 2>&1 || snap refresh core >>"$LOG" 2>&1 || true
  snap install --classic certbot >>"$LOG" 2>&1 || true
  ln -sf /snap/bin/certbot /usr/local/bin/certbot >>"$LOG" 2>&1 || true
fi

if check_certbot /snap/bin/certbot || check_certbot /usr/local/bin/certbot; then
  echo "[IronPanel] Certbot OK: snap/isolated path" | tee -a "$LOG"
  exit 0
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y --reinstall certbot python3-acme python3-josepy python3-openssl python3-cryptography >>"$LOG" 2>&1 || \
DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-openssl python3-cryptography >>"$LOG" 2>&1 || true
if check_certbot /usr/bin/certbot || check_certbot certbot; then
  echo "[IronPanel] Certbot OK: apt path" | tee -a "$LOG"
  exit 0
fi

python3 -m venv /opt/ironpanel-certbot-venv >>"$LOG" 2>&1 || true
/opt/ironpanel-certbot-venv/bin/pip install --upgrade pip wheel >>"$LOG" 2>&1 || true
/opt/ironpanel-certbot-venv/bin/pip install 'certbot>=2,<4' >>"$LOG" 2>&1 || true
ln -sf /opt/ironpanel-certbot-venv/bin/certbot /usr/local/bin/certbot >>"$LOG" 2>&1 || true

if check_certbot /opt/ironpanel-certbot-venv/bin/certbot || check_certbot /usr/local/bin/certbot; then
  echo "[IronPanel] Certbot OK: venv path" | tee -a "$LOG"
  exit 0
fi

echo "[IronPanel] Certbot repair failed. See $LOG" | tee -a "$LOG"
exit 1

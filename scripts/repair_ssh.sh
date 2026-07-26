#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
SSH_PORT=${IRONPANEL_SSH_PORT:-${SSH_PORT:-422}}
SSHD_CONF_DIR=/etc/ssh/sshd_config.d
SSHD_CONF=$SSHD_CONF_DIR/99-ironpanel-ssh.conf
SSH_GROUP=${IRONPANEL_SSH_GROUP:-ironpanel-ssh}
LOG_PREFIX='[IronPanel SSH]'

log(){ echo "$LOG_PREFIX $*"; }
valid_port(){ [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 65535 )); }
if ! valid_port "$SSH_PORT"; then SSH_PORT=422; fi

install_packages(){
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server passwd sudo iproute2 || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y openssh-server passwd shadow-utils iproute || true
  fi
}

sshd_unit(){
  if systemctl list-unit-files ssh.service >/dev/null 2>&1; then echo ssh; return; fi
  if systemctl list-unit-files sshd.service >/dev/null 2>&1; then echo sshd; return; fi
  if systemctl status ssh >/dev/null 2>&1; then echo ssh; return; fi
  echo sshd
}

configure_sshd(){
  mkdir -p "$SSHD_CONF_DIR" "$ETC_DIR"
  mapfile -t existing_ports < <(grep -RhsE '^[[:space:]]*Port[[:space:]]+[0-9]+' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | awk '{print $2}' | sort -n | uniq || true)
  if [[ ${#existing_ports[@]} -eq 0 ]]; then existing_ports=(22); fi
  {
    echo '# Managed by IronPanel. Adds the VPN-style SSH user port while preserving admin SSH ports.'
    for p in "${existing_ports[@]}" "$SSH_PORT"; do valid_port "$p" && echo "Port $p"; done | awk '!seen[$0]++'
    cat <<EOF
PasswordAuthentication yes
KbdInteractiveAuthentication yes
UsePAM yes
AllowTcpForwarding yes
PermitTunnel yes
X11Forwarding no
ClientAliveInterval 60
ClientAliveCountMax 2

Match Group $SSH_GROUP
  PasswordAuthentication yes
  KbdInteractiveAuthentication yes
  AllowTcpForwarding yes
  PermitTunnel yes
  X11Forwarding no
  PermitTTY no
  GatewayPorts no
  ForceCommand /bin/false
EOF
  } > "$SSHD_CONF"
  groupadd -r "$SSH_GROUP" 2>/dev/null || true
  sshd -t || { log 'sshd config validation failed'; sshd -t; exit 1; }
  local unit; unit=$(sshd_unit)
  systemctl enable "$unit" >/dev/null 2>&1 || true
  systemctl restart "$unit" || systemctl restart ssh || systemctl restart sshd || true
  ufw allow "$SSH_PORT/tcp" >/dev/null 2>&1 || true
  iptables -C INPUT -p tcp --dport "$SSH_PORT" -m comment --comment ironpanel-ssh -j ACCEPT 2>/dev/null || iptables -I INPUT -p tcp --dport "$SSH_PORT" -m comment --comment ironpanel-ssh -j ACCEPT || true
}

sync_users_from_app(){
  if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
    (cd "$APP_DIR" && "$APP_DIR/.venv/bin/python" - <<'PYAPP'
from run import app
from app.services.provisioning import sync_all_users
with app.app_context():
    sync_all_users(restart=False)
PYAPP
) || true
  fi
}

case "${1:---install}" in
  --status|--diagnose)
    echo "SSH port: $SSH_PORT"
    echo "Group: $SSH_GROUP"
    echo "Config: $SSHD_CONF"
    systemctl status ssh --no-pager 2>/dev/null || systemctl status sshd --no-pager 2>/dev/null || true
    ss -ltnp 2>/dev/null | grep -E ":${SSH_PORT}\\b" || true
    exit 0
    ;;
  --sync)
    install_packages
    configure_sshd
    sync_users_from_app
    ;;
  --install|*)
    install_packages
    configure_sshd
    ;;
esac
log "Done. SSH user port is $SSH_PORT/tcp"

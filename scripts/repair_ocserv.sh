#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo '[IronPanel] repair_ocserv.sh must run as root' >&2
  exit 2
fi

if [[ -f /etc/ironpanel/ironpanel.env ]]; then
  set -a
  # shellcheck disable=SC1091
  . /etc/ironpanel/ironpanel.env
  set +a
fi

exec 9>/run/ironpanel-repair-ocserv.lock
flock -w 60 9 || { echo '[IronPanel] another ocserv repair is already running' >&2; exit 3; }

PORT=${OCSERV_PORT:-${OCSERV_TCP:-8445}}
UDP_PORT=${OCSERV_UDP:-$PORT}
TRANSPORT=$(printf '%s' "${OCSERV_TRANSPORT:-tcp_udp}" | tr '[:upper:]' '[:lower:]')
PUBLIC_HOST=${IRONPANEL_PUBLIC_HOST:-${PUBLIC_HOST:-$(hostname -f 2>/dev/null || hostname)}}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
PASSWD_FILE=/etc/ocserv/ocpasswd
# Never honor legacy per-user/profile auth paths. Cisco/AnyConnect will fail
# with cookie/auth errors if ocserv reads any path other than this canonical file.
OC_NET=${OCSERV_IPV4_NETWORK:-10.44.0.0}
OC_MASK=${OCSERV_IPV4_NETMASK:-255.255.255.0}
OC_CIDR=${OCSERV_IPV4_CIDR:-10.44.0.0/24}
LOG=/var/log/ironpanel-ocserv-repair.log

log(){ printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }
valid_port(){ [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 65535 )); }

valid_port "$PORT" || { log "ERROR: invalid TCP port: $PORT"; exit 4; }
if [[ "$TRANSPORT" != "tcp" ]]; then
  valid_port "$UDP_PORT" || { log "ERROR: invalid UDP port: $UDP_PORT"; exit 4; }
fi

if ! command -v ocserv >/dev/null 2>&1 || ! command -v ocpasswd >/dev/null 2>&1; then
  log 'Ocserv binaries are missing; installing the ocserv package'
  apt-get update >>"$LOG" 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y ocserv >>"$LOG" 2>&1 || true
fi
command -v ocserv >/dev/null 2>&1 || { log 'ERROR: ocserv binary is missing'; exit 8; }
command -v ocpasswd >/dev/null 2>&1 || { log 'ERROR: ocpasswd binary is missing'; exit 9; }

mkdir -p /etc/ocserv/certs "$ETC_DIR" "$(dirname "$PASSWD_FILE")" /var/run /var/log
install -m 600 /dev/null "$PASSWD_FILE.tmp-create"
if [[ ! -e "$PASSWD_FILE" ]]; then
  mv -f "$PASSWD_FILE.tmp-create" "$PASSWD_FILE"
else
  rm -f "$PASSWD_FILE.tmp-create"
fi
chmod 600 "$PASSWD_FILE" || true
chown root:root "$PASSWD_FILE" 2>/dev/null || true

# Keep legacy panel path compatible, but ocserv itself reads the canonical /etc/ocserv/ocpasswd.
if [[ "$PASSWD_FILE" == "/etc/ocserv/ocpasswd" ]]; then
  if [[ ! -e "$ETC_DIR/ocpasswd" ]]; then
    ln -s "$PASSWD_FILE" "$ETC_DIR/ocpasswd" 2>/dev/null || cp -f "$PASSWD_FILE" "$ETC_DIR/ocpasswd" 2>/dev/null || true
  fi
fi
# Never truncate ocpasswd during repair. User synchronization owns this file.
# Prefer a valid panel/Let's Encrypt certificate and fall back to a stable self-signed certificate.
CERT=/etc/ocserv/certs/server-cert.pem
KEY=/etc/ocserv/certs/server-key.pem
cert_pair_valid(){
  [[ -s "$1" && -s "$2" ]] || return 1
  openssl x509 -in "$1" -noout >/dev/null 2>&1 || return 1
  openssl pkey -in "$2" -noout >/dev/null 2>&1 || return 1
  local cert_pub key_pub
  cert_pub=$(openssl x509 -in "$1" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
  key_pub=$(openssl pkey -in "$2" -pubout -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
  [[ -n "$cert_pub" && "$cert_pub" == "$key_pub" ]]
}

find_managed_cert(){
  local candidate key_candidate clean_host
  clean_host=${PUBLIC_HOST#http://}; clean_host=${clean_host#https://}; clean_host=${clean_host%%/*}; clean_host=${clean_host%%:*}
  for candidate in \
    "${IRONPANEL_SSL_CERT:-}" \
    "${SSL_CERT_FILE:-}" \
    "/etc/letsencrypt/live/$clean_host/fullchain.pem"; do
    [[ -n "$candidate" ]] || continue
    case "$candidate" in
      */fullchain.pem) key_candidate="${candidate%/fullchain.pem}/privkey.pem" ;;
      *) key_candidate="${IRONPANEL_SSL_KEY:-${SSL_KEY_FILE:-}}" ;;
    esac
    if [[ -n "$key_candidate" ]] && cert_pair_valid "$candidate" "$key_candidate"; then
      printf '%s\n%s\n' "$candidate" "$key_candidate"
      return 0
    fi
  done
  while IFS= read -r candidate; do
    key_candidate="${candidate%/fullchain.pem}/privkey.pem"
    if cert_pair_valid "$candidate" "$key_candidate"; then
      printf '%s\n%s\n' "$candidate" "$key_candidate"
      return 0
    fi
  done < <(find /etc/ironpanel/ssl -maxdepth 3 -type f -name fullchain.pem 2>/dev/null | sort -r)
  return 1
}

mapfile -t managed_pair < <(find_managed_cert || true)
if (( ${#managed_pair[@]} >= 2 )); then
  install -m 644 "${managed_pair[0]}" "$CERT"
  install -m 600 "${managed_pair[1]}" "$KEY"
  log "Using managed TLS certificate: ${managed_pair[0]}"
elif ! cert_pair_valid "$CERT" "$KEY"; then
  clean_cn=${PUBLIC_HOST#http://}; clean_cn=${clean_cn#https://}; clean_cn=${clean_cn%%/*}; clean_cn=${clean_cn%%:*}
  [[ -n "$clean_cn" ]] || clean_cn=IronPanel-Ocserv
  openssl req -x509 -nodes -newkey rsa:3072 \
    -keyout "$KEY" -out "$CERT" -days 3650 \
    -subj "/CN=${clean_cn}" >/dev/null 2>&1
  chmod 600 "$KEY"; chmod 644 "$CERT"
  log 'Generated a stable self-signed ocserv certificate'
fi

UDP_LINE="udp-port = ${UDP_PORT}"
[[ "$TRANSPORT" == "tcp" ]] && UDP_LINE='udp-port = 0'
# v19.9.20: Do not attach session hooks to ocserv. A failing hook makes
# AnyConnect pass password auth and then fail CSTP/cookie authentication.
HOOK_LINES=''

cat > /etc/ocserv/ocserv.conf.tmp <<OC
# Managed by IronPanel 19.9.20
isolate-workers = false
socket-file = /var/run/ocserv-socket
occtl-socket-file = /var/run/occtl.socket
device = vpns
tcp-port = ${PORT}
${UDP_LINE}
auth = "plain[passwd=${PASSWD_FILE}]"
server-cert = ${CERT}
server-key = ${KEY}
try-mtu-discovery = true
ipv4-network = ${OC_NET}
ipv4-netmask = ${OC_MASK}
dns = 1.1.1.1
dns = 8.8.8.8
route = default
tunnel-all-dns = true
cisco-client-compat = true
max-clients = 512
max-same-clients = 3
auth-timeout = 240
cookie-timeout = 86400
dpd = 90
mobile-dpd = 1800
${HOOK_LINES}
OC
chmod 600 /etc/ocserv/ocserv.conf.tmp

if ! ocserv -t -c /etc/ocserv/ocserv.conf.tmp >>"$LOG" 2>&1; then
  log 'ERROR: ocserv config validation failed; existing config was preserved'
  rm -f /etc/ocserv/ocserv.conf.tmp
  exit 5
fi
mv -f /etc/ocserv/ocserv.conf.tmp /etc/ocserv/ocserv.conf
sed -i -e '/^connect-script[[:space:]]*=.*ocserv_session_hook\.sh/d' -e '/^disconnect-script[[:space:]]*=.*ocserv_session_hook\.sh/d' /etc/ocserv/ocserv.conf 2>/dev/null || true
chmod 600 /etc/ocserv/ocserv.conf

sysctl -w net.ipv4.ip_forward=1 >/dev/null || true
cat > /etc/sysctl.d/99-ironpanel-ocserv.conf <<SYSCTL
net.ipv4.ip_forward=1
SYSCTL

EXT_IF=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')
open_rule(){
  local table=$1; shift
  if [[ "$table" == filter ]]; then
    iptables -C "$@" 2>/dev/null || iptables -I "$@" || true
  else
    iptables -t "$table" -C "$@" 2>/dev/null || iptables -t "$table" -A "$@" || true
  fi
}
open_rule filter INPUT -p tcp --dport "$PORT" -m comment --comment ironpanel-ocserv -j ACCEPT
if [[ "$TRANSPORT" != "tcp" ]]; then
  open_rule filter INPUT -p udp --dport "$UDP_PORT" -m comment --comment ironpanel-ocserv -j ACCEPT
fi
open_rule filter FORWARD -s "$OC_CIDR" -m comment --comment ironpanel-ocserv -j ACCEPT
open_rule filter FORWARD -d "$OC_CIDR" -m conntrack --ctstate ESTABLISHED,RELATED -m comment --comment ironpanel-ocserv -j ACCEPT
if [[ -n "${EXT_IF:-}" ]]; then
  open_rule nat POSTROUTING -s "$OC_CIDR" -o "$EXT_IF" -m comment --comment ironpanel-ocserv -j MASQUERADE
fi
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi active; then
  ufw allow "$PORT/tcp" >/dev/null 2>&1 || true
  [[ "$TRANSPORT" == "tcp" ]] || ufw allow "$UDP_PORT/udp" >/dev/null 2>&1 || true
fi
mkdir -p /etc/iptables
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true

systemctl daemon-reload
systemctl stop ocserv >/dev/null 2>&1 || true
rm -f /var/run/ocserv-socket /var/run/occtl.socket /run/ocserv-socket /run/occtl.socket 2>/dev/null || true
systemctl enable ocserv >/dev/null 2>&1 || true
systemctl restart ocserv
sleep 1
if ! systemctl is-active --quiet ocserv; then
  journalctl -u ocserv -n 80 --no-pager >>"$LOG" 2>&1 || true
  log 'ERROR: ocserv did not become active'
  exit 6
fi
if ! ss -lnt 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$PORT$"; then
  log "ERROR: ocserv is active but TCP port $PORT is not listening"
  exit 7
fi

user_count=$(grep -c '^[^#[:space:]][^:]*:' "$PASSWD_FILE" 2>/dev/null || true)
log "Ocserv healthy: tcp/$PORT, udp/${UDP_PORT}, subnet=$OC_CIDR, users=$user_count"
if [[ "$user_count" -eq 0 ]]; then
  log 'WARNING: ocpasswd has no users; run panel user sync after creating users'
fi

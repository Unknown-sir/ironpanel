#!/usr/bin/env bash
set -euo pipefail
PROTOCOLS="${1:-${IRONPANEL_NODE_PROTOCOLS:-openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2,telegram_proxy,ssh}}"
LOG=/var/log/ironpanel-node-core-install.log
mkdir -p /var/log /etc/ironpanel-node /opt/ironpanel-node/scripts
log(){ echo "[IronPanel Node Cores] $*" | tee -a "$LOG"; }
has_proto(){ [[ ",${PROTOCOLS}," == *",$1,"* ]]; }
export DEBIAN_FRONTEND=noninteractive
log "Installing selected protocol cores: $PROTOCOLS"
apt-get update -y >>"$LOG" 2>&1 || true
BASE_PKGS=(curl ca-certificates iproute2 iptables openssl net-tools cron)
PKGS=("${BASE_PKGS[@]}")
has_proto ssh && PKGS+=(openssh-server)
has_proto openvpn && PKGS+=(openvpn easy-rsa)
has_proto wireguard && PKGS+=(wireguard wireguard-tools)
has_proto ocserv && PKGS+=(ocserv)
if has_proto l2tp; then PKGS+=(strongswan strongswan-starter libcharon-extra-plugins xl2tpd ppp); fi
has_proto pptp && PKGS+=(pptpd ppp)
has_proto telegram_proxy && PKGS+=(nodejs git)
# hysteria2/xray may be installed by upstream release scripts below.
for pkg in "${PKGS[@]}"; do
  apt-get install -y "$pkg" >>"$LOG" 2>&1 || log "WARN: package $pkg could not be installed; continuing"
done
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
cat > /etc/sysctl.d/99-ironpanel-node.conf <<'SYSCTL'
net.ipv4.ip_forward=1
SYSCTL
WAN_IF=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')
open_port(){ local port="$1" proto="$2"; [[ -z "$port" || -z "$proto" ]] && return 0; iptables -C INPUT -p "$proto" --dport "$port" -j ACCEPT >/dev/null 2>&1 || iptables -A INPUT -p "$proto" --dport "$port" -j ACCEPT >/dev/null 2>&1 || true; }
ensure_nat(){ local subnet="$1"; [[ -z "${WAN_IF:-}" ]] && return 0; iptables -t nat -C POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || iptables -t nat -A POSTROUTING -s "$subnet" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || true; }
# Standard IronPanel protocol ports. The main panel may override configs later via node jobs.
has_proto openvpn && { open_port 1194 udp; open_port 1195 tcp; ensure_nat 10.8.0.0/24; }
has_proto wireguard && { open_port 51820 udp; ensure_nat 10.66.66.0/24; }
has_proto ocserv && { open_port 443 tcp; open_port 443 udp; open_port 8445 tcp; open_port 8445 udp; ensure_nat 10.10.10.0/24; }
if has_proto l2tp; then open_port 500 udp; open_port 4500 udp; open_port 1701 udp; ensure_nat 10.20.20.0/24; systemctl enable --now xl2tpd >/dev/null 2>&1 || true; systemctl enable --now strongswan-starter >/dev/null 2>&1 || systemctl enable --now strongswan >/dev/null 2>&1 || true; fi
has_proto pptp && { open_port 1723 tcp; ensure_nat 10.70.70.0/24; systemctl enable --now pptpd >/dev/null 2>&1 || true; }
has_proto xray && { open_port 443 tcp; if ! command -v xray >/dev/null 2>&1 && [[ ! -x /usr/local/bin/xray ]]; then curl -fsSL --connect-timeout 8 --max-time 60 https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray-install.sh >>"$LOG" 2>&1 || true; [[ -s /tmp/xray-install.sh ]] && bash /tmp/xray-install.sh install >>"$LOG" 2>&1 || true; fi; }
has_proto hysteria2 && { open_port 443 udp; open_port 4433 udp; if ! command -v hysteria >/dev/null 2>&1 && ! command -v hysteria2 >/dev/null 2>&1; then bash -c 'curl -fsSL https://get.hy2.sh/ | bash' >>"$LOG" 2>&1 || true; fi; }
has_proto telegram_proxy && { open_port 6969 tcp; command -v node >/dev/null 2>&1 || command -v nodejs >/dev/null 2>&1 || log "WARN: nodejs binary not found after package install"; }
has_proto ssh && { open_port 22 tcp; open_port 422 tcp; systemctl enable --now ssh >/dev/null 2>&1 || systemctl enable --now sshd >/dev/null 2>&1 || true; }
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
systemctl daemon-reload >/dev/null 2>&1 || true
log "Protocol core installation finished"

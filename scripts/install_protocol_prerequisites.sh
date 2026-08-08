#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
LOG=${LOG:-/var/log/ironpanel-protocol-prerequisites.log}
MODE=${1:---install-all}
mkdir -p "$(dirname "$LOG")" "$ETC_DIR"
touch "$LOG"
exec 9>/run/ironpanel-protocol-prerequisites.lock
flock -w 60 9 || { echo '[IronPanel] another protocol prerequisite task is running' >&2; exit 75; }

log(){ printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }
fail(){ log "ERROR: $*"; return 1; }
need_root(){ [[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'Run as root.' >&2; exit 2; }; }
need_root

if [[ -f "$ETC_DIR/ironpanel.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ETC_DIR/ironpanel.env"
  set +a
fi

export DEBIAN_FRONTEND=noninteractive
APT_UPDATED=0
PKG_MANAGER_REPAIRED=0
repair_package_manager(){
  (( PKG_MANAGER_REPAIRED == 1 )) && return 0
  command -v dpkg >/dev/null 2>&1 || { PKG_MANAGER_REPAIRED=1; return 0; }
  if dpkg --audit 2>/dev/null | grep -q .; then
    log 'Repairing interrupted dpkg state before protocol installation'
  fi
  dpkg --configure -a >>"$LOG" 2>&1 || true
  if command -v apt-get >/dev/null 2>&1; then
    apt-get -f install -y >>"$LOG" 2>&1 || true
  fi
  # A second configure pass catches packages unpacked by apt -f.
  dpkg --configure -a >>"$LOG" 2>&1 || true
  if dpkg --audit 2>/dev/null | grep -q .; then
    log 'WARN: dpkg still reports incomplete packages; package installs may fail'
  fi
  PKG_MANAGER_REPAIRED=1
}
apt_refresh(){
  (( APT_UPDATED == 1 )) && return 0
  command -v apt-get >/dev/null 2>&1 || return 1
  repair_package_manager
  log 'Refreshing APT package metadata'
  apt-get update -y >>"$LOG" 2>&1 || return 1
  APT_UPDATED=1
}

enable_ubuntu_universe(){
  [[ -r /etc/os-release ]] || return 0
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == ubuntu ]] || return 0
  apt_refresh || true
  if ! command -v add-apt-repository >/dev/null 2>&1; then
    apt-get install -y software-properties-common >>"$LOG" 2>&1 || true
  fi
  if command -v add-apt-repository >/dev/null 2>&1; then
    add-apt-repository -y universe >>"$LOG" 2>&1 || true
    APT_UPDATED=0
    apt_refresh || true
  fi
}

pkg_available(){ apt-cache show "$1" >/dev/null 2>&1; }
install_pkg(){
  local pkg="$1"
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' && return 0
  apt_refresh || return 1
  if ! pkg_available "$pkg"; then
    log "WARN: package is not available in enabled repositories: $pkg"
    return 1
  fi
  log "Installing package: $pkg"
  apt-get install -y "$pkg" >>"$LOG" 2>&1
}
install_packages(){
  local failed=() p
  for p in "$@"; do install_pkg "$p" || failed+=("$p"); done
  if (( ${#failed[@]} )); then
    log "WARN: packages not installed: ${failed[*]}"
    return 1
  fi
}

install_pptpd_from_debian_source(){
  command -v pptpd >/dev/null 2>&1 && return 0
  log 'PPTP server package is unavailable; attempting a local Debian source build'
  install_packages build-essential dpkg-dev debhelper-compat libwrap0-dev ppp-dev pkg-config wget xz-utils || true
  command -v dpkg-buildpackage >/dev/null 2>&1 || return 1
  local root=/usr/local/src/ironpanel-pptpd-build
  rm -rf "$root"; mkdir -p "$root"; cd "$root"
  local base=https://deb.debian.org/debian/pool/main/p/pptpd
  curl -fL --retry 2 --connect-timeout 10 --max-time 120 "$base/pptpd_1.4.0-12.dsc" -o pptpd_1.4.0-12.dsc >>"$LOG" 2>&1 || return 1
  curl -fL --retry 2 --connect-timeout 10 --max-time 120 "$base/pptpd_1.4.0.orig.tar.gz" -o pptpd_1.4.0.orig.tar.gz >>"$LOG" 2>&1 || return 1
  curl -fL --retry 2 --connect-timeout 10 --max-time 120 "$base/pptpd_1.4.0-12.debian.tar.xz" -o pptpd_1.4.0-12.debian.tar.xz >>"$LOG" 2>&1 || return 1
  dpkg-source -x pptpd_1.4.0-12.dsc >>"$LOG" 2>&1 || return 1
  cd pptpd-1.4.0
  dpkg-buildpackage -b -uc -us >>"$LOG" 2>&1 || return 1
  cd ..
  local debs=()
  while IFS= read -r -d '' f; do debs+=("$f"); done < <(find . -maxdepth 1 -type f \( -name 'pptpd_*_*.deb' -o -name 'bcrelay_*_*.deb' \) -print0)
  (( ${#debs[@]} )) || return 1
  apt-get install -y "${debs[@]}" >>"$LOG" 2>&1 || dpkg -i "${debs[@]}" >>"$LOG" 2>&1 || return 1
  command -v pptpd >/dev/null 2>&1
}


ensure_kernel_prerequisites(){
  local module
  for module in tun wireguard ppp_generic ppp_async ppp_mppe pppol2tp xfrm_user af_key nf_conntrack_pptp nf_nat_pptp; do
    modprobe "$module" >>"$LOG" 2>&1 || log "WARN: kernel module is unavailable or built-in: $module"
  done
  if [[ ! -c /dev/net/tun ]]; then
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200 >>"$LOG" 2>&1 || true
    chmod 600 /dev/net/tun 2>/dev/null || true
  fi
  [[ -c /dev/net/tun ]] || log 'WARN: /dev/net/tun is unavailable; TUN-based protocols cannot start in this environment'
}
install_all_packages(){
  enable_ubuntu_universe
  install_packages \
    ca-certificates curl openssl gnupg git jq unzip xz-utils tar rsync sqlite3 \
    iproute2 iptables iptables-persistent nftables net-tools lsof procps socat kmod \
    cron util-linux coreutils findutils grep sed gawk || true
  install_packages openvpn easy-rsa || true
  install_packages wireguard-tools wireguard || install_packages wireguard-tools || true
  install_packages ocserv gnutls-bin || true
  install_packages strongswan strongswan-starter libcharon-extra-plugins libstrongswan-extra-plugins xl2tpd ppp || true
  install_packages openssh-server passwd sudo || true
  # Ubuntu/NodeSource nodejs packages may conflict with the separate npm package.
  # IronPanel Telegram Proxy only requires the Node runtime, so install nodejs alone.
  install_packages nodejs || true
  if ! install_packages pptpd ppp; then
    install_pptpd_from_debian_source || log 'WARN: PPTP server could not be installed on this OS'
  fi
  ensure_kernel_prerequisites
}

cert_valid(){ [[ -s "$1" ]] && openssl x509 -in "$1" -noout >/dev/null 2>&1; }
key_valid(){ [[ -s "$1" ]] && openssl pkey -in "$1" -noout >/dev/null 2>&1; }
cert_key_match(){
  cert_valid "$1" && key_valid "$2" || return 1
  local a b
  a=$(openssl x509 -in "$1" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
  b=$(openssl pkey -in "$2" -pubout -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
  [[ -n "$a" && "$a" == "$b" ]]
}
server_chain_valid(){
  cert_valid "$1" && cert_valid "$2" || return 1
  openssl verify -CAfile "$1" "$2" >/dev/null 2>&1
}
dh_valid(){ [[ -s "$1" ]] && openssl dhparam -in "$1" -check -noout >/dev/null 2>&1; }
tls_crypt_valid(){
  [[ -s "$1" ]] || return 1
  grep -q '^-----BEGIN OpenVPN Static key V1-----$' "$1" && grep -q '^-----END OpenVPN Static key V1-----$' "$1"
}

backup_openvpn_files(){
  local stamp dir f
  stamp=$(date +%Y%m%d-%H%M%S)
  dir="/var/backups/ironpanel/protocol-prerequisites/$stamp/openvpn"
  mkdir -p "$dir"
  for f in /etc/openvpn/server /etc/openvpn/easy-rsa /etc/openvpn/easy-rsa-new; do [[ -e "$f" ]] && cp -a "$f" "$dir/" 2>/dev/null || true; done
  log "OpenVPN files backed up to $dir"
}

find_easyrsa(){
  if command -v easyrsa >/dev/null 2>&1; then command -v easyrsa; return 0; fi
  for f in /usr/share/easy-rsa/easyrsa /usr/share/easy-rsa/3/easyrsa; do [[ -x "$f" ]] && { echo "$f"; return 0; }; done
  return 1
}

prepare_easyrsa_dir(){
  local dir=/etc/openvpn/easy-rsa src
  mkdir -p "$dir"
  if [[ ! -x "$dir/easyrsa" ]]; then
    src=$(find_easyrsa) || return 1
    cp -a "$(dirname "$src")/." "$dir/"
    chmod +x "$dir/easyrsa"
  fi
  echo "$dir"
}

restore_openvpn_from_existing_pki(){
  local pki
  for pki in /etc/openvpn/easy-rsa/pki /etc/openvpn/pki /etc/ironpanel/openvpn-pki; do
    [[ -d "$pki" ]] || continue
    if cert_valid "$pki/ca.crt" && cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" && server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt" && dh_valid "$pki/dh.pem"; then
      install -m 644 "$pki/ca.crt" /etc/openvpn/server/ca.crt
      install -m 644 "$pki/issued/server.crt" /etc/openvpn/server/server.crt
      install -m 600 "$pki/private/server.key" /etc/openvpn/server/server.key
      install -m 644 "$pki/dh.pem" /etc/openvpn/server/dh.pem
      [[ -s "$pki/crl.pem" ]] && install -m 644 "$pki/crl.pem" /etc/openvpn/server/crl.pem || true
      log "Restored OpenVPN PKI from $pki"
      return 0
    fi
  done
  return 1
}

build_or_repair_openvpn_pki(){
  install_packages openvpn easy-rsa openssl || return 1
  mkdir -p /etc/openvpn/server /var/log/openvpn
  local er pki candidate selected=''
  er=$(prepare_easyrsa_dir) || return 1
  pki="$er/pki"

  # Canonical rule: IronPanel has exactly one issuing PKI, /etc/openvpn/easy-rsa/pki.
  # Prefer the issuing PKI whose CA matches the *currently active server CA*.
  # This is important on upgraded systems where an old /etc/openvpn/easy-rsa
  # may still exist beside a repaired/new PKI. Picking the first valid PKI would
  # otherwise recreate the exact split-CA failure where server and client certs
  # are issued by different authorities.
  ca_same(){
    cert_valid "$1" && cert_valid "$2" || return 1
    cmp -s "$1" "$2" && return 0
    local a b
    a=$(openssl x509 -in "$1" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
    b=$(openssl x509 -in "$2" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
    [[ -n "$a" && "$a" == "$b" ]]
  }
  candidates=("$pki" /etc/openvpn/easy-rsa-new/pki /etc/openvpn/pki /etc/ironpanel/openvpn-pki)
  if cert_valid /etc/openvpn/server/ca.crt && cert_valid /etc/openvpn/server/server.crt \
     && server_chain_valid /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt; then
    for candidate in "${candidates[@]}"; do
      [[ -d "$candidate" ]] || continue
      if cert_valid "$candidate/ca.crt" && key_valid "$candidate/private/ca.key" \
         && cert_key_match "$candidate/ca.crt" "$candidate/private/ca.key" \
         && ca_same /etc/openvpn/server/ca.crt "$candidate/ca.crt"; then
        selected="$candidate"
        log "Selected OpenVPN issuing PKI matching active server CA: $candidate"
        break
      fi
    done
  fi
  if [[ -z "$selected" ]]; then
    for candidate in "${candidates[@]}"; do
      [[ -d "$candidate" ]] || continue
      if cert_valid "$candidate/ca.crt" && key_valid "$candidate/private/ca.key" && cert_key_match "$candidate/ca.crt" "$candidate/private/ca.key"; then
        selected="$candidate"
        break
      fi
    done
  fi

  if [[ -n "$selected" && "$selected" != "$pki" ]]; then
    backup_openvpn_files
    rm -rf "$pki"
    mkdir -p "$pki"
    cp -a "$selected/." "$pki/"
    log "Adopted OpenVPN issuing PKI from $selected into canonical $pki"
  fi

  if ! cert_valid "$pki/ca.crt" || ! key_valid "$pki/private/ca.key" || ! cert_key_match "$pki/ca.crt" "$pki/private/ca.key"; then
    backup_openvpn_files
    cd "$er"
    rm -rf "$pki"
    EASYRSA_BATCH=1 ./easyrsa init-pki >>"$LOG" 2>&1
    EASYRSA_BATCH=1 EASYRSA_REQ_CN=IronPanel-CA ./easyrsa build-ca nopass >>"$LOG" 2>&1
    log 'Created a new canonical OpenVPN CA because no issuing CA/private-key pair was recoverable'
  fi

  cd "$er"
  if ! cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" || ! server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt"; then
    rm -f "$pki/issued/server.crt" "$pki/private/server.key" "$pki/reqs/server.req"
    EASYRSA_BATCH=1 EASYRSA_REQ_CN=server ./easyrsa build-server-full server nopass >>"$LOG" 2>&1
  fi
  if ! dh_valid "$pki/dh.pem"; then
    rm -f "$pki/dh.pem"
    EASYRSA_BATCH=1 ./easyrsa gen-dh >>"$LOG" 2>&1
  fi
  EASYRSA_BATCH=1 ./easyrsa gen-crl >>"$LOG" 2>&1 || true

  cert_valid "$pki/ca.crt" || return 1
  cert_key_match "$pki/ca.crt" "$pki/private/ca.key" || return 1
  cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" || return 1
  server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt" || return 1
  dh_valid "$pki/dh.pem" || return 1

  # Always synchronize daemon files FROM the canonical issuing PKI.
  install -m 644 "$pki/ca.crt" /etc/openvpn/server/ca.crt
  install -m 644 "$pki/issued/server.crt" /etc/openvpn/server/server.crt
  install -m 600 "$pki/private/server.key" /etc/openvpn/server/server.key
  install -m 644 "$pki/dh.pem" /etc/openvpn/server/dh.pem
  [[ -s "$pki/crl.pem" ]] && install -m 644 "$pki/crl.pem" /etc/openvpn/server/crl.pem || true

  if ! tls_crypt_valid /etc/openvpn/server/tls-crypt.key; then
    rm -f /etc/openvpn/server/tls-crypt.key
    openvpn --genkey tls-crypt /etc/openvpn/server/tls-crypt.key >>"$LOG" 2>&1 \
      || openvpn --genkey secret /etc/openvpn/server/tls-crypt.key >>"$LOG" 2>&1
  fi
  if [[ -s /etc/openvpn/server/crl.pem ]] && ! openssl crl -in /etc/openvpn/server/crl.pem -noout >/dev/null 2>&1; then
    rm -f /etc/openvpn/server/crl.pem
  fi

  chown root:root /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt /etc/openvpn/server/server.key /etc/openvpn/server/dh.pem /etc/openvpn/server/tls-crypt.key
  chmod 644 /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt /etc/openvpn/server/dh.pem
  [[ -s /etc/openvpn/server/crl.pem ]] && { chown root:root /etc/openvpn/server/crl.pem; chmod 644 /etc/openvpn/server/crl.pem; } || true
  chmod 600 /etc/openvpn/server/server.key /etc/openvpn/server/tls-crypt.key

  # Final invariant checks: server and client issuer path are the same CA.
  cmp -s "$pki/ca.crt" /etc/openvpn/server/ca.crt || { log 'ERROR: OpenVPN canonical CA and server CA differ'; return 1; }
  server_chain_valid /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt || return 1
  tls_crypt_valid /etc/openvpn/server/tls-crypt.key || return 1
  log 'OpenVPN canonical PKI verified and synchronized'
}

ensure_xray_binary(){
  if command -v xray >/dev/null 2>&1 || [[ -x /usr/local/bin/xray ]]; then return 0; fi
  install_packages curl ca-certificates unzip || true
  log 'Installing Xray using the official XTLS installer'
  curl -fsSL --connect-timeout 10 --max-time 120 https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/ironpanel-xray-install.sh >>"$LOG" 2>&1 || return 1
  bash /tmp/ironpanel-xray-install.sh install >>"$LOG" 2>&1 || return 1
  command -v xray >/dev/null 2>&1 || [[ -x /usr/local/bin/xray ]]
}

ensure_hysteria_binary(){
  if command -v hysteria >/dev/null 2>&1 || command -v hysteria2 >/dev/null 2>&1 || [[ -x /usr/local/bin/hysteria ]]; then return 0; fi
  install_packages curl ca-certificates || true
  log 'Installing Hysteria2 using the official installer'
  timeout 240 bash -c 'curl -fsSL --connect-timeout 10 --max-time 120 https://get.hy2.sh/ | bash' >>"$LOG" 2>&1 || true
  if command -v hysteria >/dev/null 2>&1 || command -v hysteria2 >/dev/null 2>&1 || [[ -x /usr/local/bin/hysteria ]]; then return 0; fi
  local arch
  case "$(uname -m)" in x86_64|amd64) arch=amd64;; aarch64|arm64) arch=arm64;; *) return 1;; esac
  curl -fL --retry 2 --connect-timeout 10 --max-time 180 "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-$arch" -o /usr/local/bin/hysteria >>"$LOG" 2>&1 || return 1
  chmod 755 /usr/local/bin/hysteria
}

ensure_runtime_binaries(){
  ensure_xray_binary || log 'WARN: Xray binary installation failed'
  ensure_hysteria_binary || log 'WARN: Hysteria2 binary installation failed'
  if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then ln -sf "$(command -v nodejs)" /usr/local/bin/node; fi
}

case "$MODE" in
  --install-all)
    install_all_packages
    build_or_repair_openvpn_pki
    ensure_runtime_binaries
    ;;
  --packages) install_all_packages ;;
  --ensure-openvpn) build_or_repair_openvpn_pki ;;
  --runtime-binaries) ensure_runtime_binaries ;;
  *) echo "Usage: $0 [--install-all|--packages|--ensure-openvpn|--runtime-binaries]" >&2; exit 2 ;;
esac

log "Protocol prerequisites completed: $MODE"

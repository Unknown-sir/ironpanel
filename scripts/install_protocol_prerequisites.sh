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
# Fast parse check only. `openssl dhparam -check` performs expensive mathematical
# validation and used to make normal updates appear frozen even for a healthy PKI.
dh_valid(){ [[ -s "$1" ]] && timeout 10 openssl dhparam -in "$1" -noout >/dev/null 2>&1; }
crl_valid(){ [[ -s "$1" ]] && timeout 10 openssl crl -in "$1" -noout >/dev/null 2>&1; }
tls_crypt_valid(){
  [[ -s "$1" ]] || return 1
  grep -q '^-----BEGIN OpenVPN Static key V1-----$' "$1" && grep -q '^-----END OpenVPN Static key V1-----$' "$1"
}

backup_openvpn_files(){
  # Normal install/update must never copy an entire historical Easy-RSA tree:
  # panels with thousands of issued certs used to look frozen immediately after
  # "Selected OpenVPN issuing PKI...". Keep a small recovery snapshot instead.
  # A full copy is opt-in for operators who explicitly need it.
  local stamp dir f rel
  stamp=$(date +%Y%m%d-%H%M%S)
  dir="/var/backups/ironpanel/protocol-prerequisites/$stamp/openvpn"
  mkdir -p "$dir/server" "$dir/pki"
  log "Saving lightweight OpenVPN recovery snapshot to $dir"
  for f in ca.crt server.crt server.key dh.pem tls-crypt.key crl.pem server.conf; do
    [[ -e "/etc/openvpn/server/$f" ]] && cp -a "/etc/openvpn/server/$f" "$dir/server/$f" 2>/dev/null || true
  done
  for rel in ca.crt private/ca.key issued/server.crt private/server.key dh.pem crl.pem; do
    if [[ -e "/etc/openvpn/easy-rsa/pki/$rel" ]]; then
      mkdir -p "$dir/pki/$(dirname "$rel")"
      cp -a "/etc/openvpn/easy-rsa/pki/$rel" "$dir/pki/$rel" 2>/dev/null || true
    fi
  done
  if [[ "${IRONPANEL_PROTOCOL_FULL_BACKUP:-0}" == "1" ]]; then
    log 'Full OpenVPN protocol backup explicitly requested; this may take time'
    for f in /etc/openvpn/easy-rsa /etc/openvpn/easy-rsa-new; do [[ -e "$f" ]] && cp -a "$f" "$dir/" 2>/dev/null || true; done
  fi
}

archive_canonical_pki_fast(){
  # Rename is metadata-only on the same filesystem and preserves every old
  # client certificate without making update wait for a recursive backup copy.
  local pki="$1" stamp archived
  [[ -e "$pki" ]] || return 0
  stamp=$(date +%Y%m%d-%H%M%S)
  archived="${pki}.pre-repair-${stamp}"
  log "Archiving previous canonical OpenVPN PKI by fast rename: $archived"
  mv "$pki" "$archived"
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


# Easy-RSA can be left with a valid CA/key pair but without the small state
# files/directories required to issue a leaf certificate. This exact partial
# state was observed on fresh Ubuntu 24.04 installs: ca.crt + ca.key + crl.pem
# existed while server.crt/server.key/dh.pem were never created. Preserve the
# existing CA and repair only Easy-RSA bookkeeping instead of creating a second
# CA or letting OpenVPN start with an incomplete runtime directory.
ensure_easyrsa_pki_metadata(){
  local pki="$1"
  mkdir -p "$pki/private" "$pki/issued" "$pki/reqs" "$pki/certs_by_serial" "$pki/revoked" \
    "$pki/revoked/certs_by_serial" "$pki/revoked/private_by_serial" "$pki/revoked/reqs_by_serial"
  [[ -e "$pki/index.txt" ]] || : > "$pki/index.txt"
  [[ -s "$pki/serial" ]] || printf '01\n' > "$pki/serial"
  [[ -s "$pki/crlnumber" ]] || printf '01\n' > "$pki/crlnumber"
  # Allow a replacement server leaf if an interrupted install left a stale
  # index entry. This does not change the CA and is the Easy-RSA supported
  # setting for repeated subject names.
  if [[ ! -s "$pki/index.txt.attr" ]]; then
    printf 'unique_subject = no\n' > "$pki/index.txt.attr"
  elif grep -qE '^[[:space:]]*unique_subject[[:space:]]*=' "$pki/index.txt.attr"; then
    sed -i -E 's/^[[:space:]]*unique_subject[[:space:]]*=.*/unique_subject = no/' "$pki/index.txt.attr"
  else
    printf '\nunique_subject = no\n' >> "$pki/index.txt.attr"
  fi
}

issue_openvpn_server_identity(){
  local er="$1" pki="$2" idx_backup
  if cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" \
     && server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt"; then
    return 0
  fi

  ensure_easyrsa_pki_metadata "$pki"
  rm -f "$pki/issued/server.crt" "$pki/private/server.key" "$pki/reqs/server.req"
  cd "$er"
  if timeout 180 env EASYRSA_BATCH=1 EASYRSA_REQ_CN=server ./easyrsa build-server-full server nopass >>"$LOG" 2>&1; then
    cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" \
      && server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt"
    return $?
  fi

  # One bounded recovery retry for a stale/incomplete Easy-RSA database. Only
  # the old CN=server leaf entry is removed; CA/client records are untouched.
  log 'WARN: first OpenVPN server certificate issuance failed; repairing stale server leaf state and retrying once'
  idx_backup="$pki/index.txt.ironpanel-server-retry-$(date +%Y%m%d-%H%M%S)"
  cp -a "$pki/index.txt" "$idx_backup" 2>/dev/null || true
  if [[ -s "$pki/index.txt" ]]; then
    awk -F'\t' '$NF !~ /\/CN=server$/ {print}' "$pki/index.txt" > "$pki/index.txt.tmp"
    mv "$pki/index.txt.tmp" "$pki/index.txt"
  fi
  rm -f "$pki/issued/server.crt" "$pki/private/server.key" "$pki/reqs/server.req"
  timeout 180 env EASYRSA_BATCH=1 EASYRSA_REQ_CN=server ./easyrsa build-server-full server nopass >>"$LOG" 2>&1 \
    || { log 'ERROR: OpenVPN server certificate generation failed after recovery retry'; return 1; }
  cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" \
    && server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt"
}

validate_openvpn_runtime_files(){
  local f
  for f in /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt \
           /etc/openvpn/server/server.key /etc/openvpn/server/dh.pem \
           /etc/openvpn/server/tls-crypt.key; do
    [[ -s "$f" ]] || { log "ERROR: required OpenVPN runtime file is missing/empty: $f"; return 1; }
  done
  cert_valid /etc/openvpn/server/ca.crt || return 1
  cert_key_match /etc/openvpn/server/server.crt /etc/openvpn/server/server.key || return 1
  server_chain_valid /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt || return 1
  dh_valid /etc/openvpn/server/dh.pem || return 1
  tls_crypt_valid /etc/openvpn/server/tls-crypt.key || return 1
  [[ -s /etc/openvpn/easy-rsa/pki/ca.crt ]] || return 1
  [[ -s /etc/openvpn/easy-rsa/pki/private/ca.key ]] || return 1
  cert_key_match /etc/openvpn/easy-rsa/pki/ca.crt /etc/openvpn/easy-rsa/pki/private/ca.key || return 1
  cmp -s /etc/openvpn/server/ca.crt /etc/openvpn/easy-rsa/pki/ca.crt || return 1
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
  # Health gate for updates/repairs: do not touch APT, regenerate CRLs or validate
  # DH primes when the active server and the canonical issuing PKI are already
  # consistent. This makes a healthy OpenVPN stage complete in milliseconds.
  local canonical=/etc/openvpn/easy-rsa/pki
  if command -v openvpn >/dev/null 2>&1 \
     && [[ -x /etc/openvpn/easy-rsa/easyrsa ]] \
     && cert_valid /etc/openvpn/server/ca.crt \
     && cert_valid /etc/openvpn/server/server.crt \
     && key_valid /etc/openvpn/server/server.key \
     && cert_key_match /etc/openvpn/server/server.crt /etc/openvpn/server/server.key \
     && server_chain_valid /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt \
     && cert_valid "$canonical/ca.crt" \
     && key_valid "$canonical/private/ca.key" \
     && cert_key_match "$canonical/ca.crt" "$canonical/private/ca.key" \
     && cert_key_match "$canonical/issued/server.crt" "$canonical/private/server.key" \
     && server_chain_valid "$canonical/ca.crt" "$canonical/issued/server.crt" \
     && dh_valid "$canonical/dh.pem" \
     && cmp -s /etc/openvpn/server/ca.crt "$canonical/ca.crt" \
     && dh_valid /etc/openvpn/server/dh.pem \
     && tls_crypt_valid /etc/openvpn/server/tls-crypt.key; then
    log 'OpenVPN canonical PKI/files are healthy; skipping PKI rebuild'
    return 0
  fi

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
    archive_canonical_pki_fast "$pki"
    mkdir -p "$pki"
    log "Copying selected issuing PKI into canonical path: $selected -> $pki"
    # Bound the copy as a final safety net. This copy is only required when the
    # active server CA lives in a non-canonical recovery PKI.
    timeout 120 cp -a "$selected/." "$pki/" \
      || { log 'ERROR: timed out while adopting selected OpenVPN PKI'; return 1; }
    log "Adopted OpenVPN issuing PKI from $selected into canonical $pki"
  fi

  if ! cert_valid "$pki/ca.crt" || ! key_valid "$pki/private/ca.key" || ! cert_key_match "$pki/ca.crt" "$pki/private/ca.key"; then
    backup_openvpn_files
    cd "$er"
    archive_canonical_pki_fast "$pki"
    EASYRSA_BATCH=1 ./easyrsa init-pki >>"$LOG" 2>&1
    EASYRSA_BATCH=1 EASYRSA_REQ_CN=IronPanel-CA ./easyrsa build-ca nopass >>"$LOG" 2>&1
    log 'Created a new canonical OpenVPN CA because no issuing CA/private-key pair was recoverable'
  fi

  cd "$er"
  ensure_easyrsa_pki_metadata "$pki"
  # Reuse the already-running server identity when it is valid for this CA.
  # Otherwise issue a new leaf from the SAME canonical CA. The helper repairs
  # the partial Easy-RSA state seen on affected fresh Ubuntu 24.04 installs.
  if ! cert_key_match "$pki/issued/server.crt" "$pki/private/server.key" || ! server_chain_valid "$pki/ca.crt" "$pki/issued/server.crt"; then
    if cert_key_match /etc/openvpn/server/server.crt /etc/openvpn/server/server.key \
       && server_chain_valid "$pki/ca.crt" /etc/openvpn/server/server.crt; then
      mkdir -p "$pki/issued" "$pki/private"
      install -m 644 /etc/openvpn/server/server.crt "$pki/issued/server.crt"
      install -m 600 /etc/openvpn/server/server.key "$pki/private/server.key"
      log 'Reused healthy active OpenVPN server certificate/key in canonical PKI'
    else
      issue_openvpn_server_identity "$er" "$pki" \
        || { log 'ERROR: failed generating a valid OpenVPN server certificate/key from canonical CA'; return 1; }
    fi
  fi
  if ! dh_valid "$pki/dh.pem"; then
    if dh_valid /etc/openvpn/server/dh.pem; then
      install -m 644 /etc/openvpn/server/dh.pem "$pki/dh.pem"
      log 'Reused healthy active OpenVPN DH parameters in canonical PKI'
    else
      rm -f "$pki/dh.pem"
      timeout 300 env EASYRSA_BATCH=1 EASYRSA_KEY_SIZE=2048 ./easyrsa gen-dh >>"$LOG" 2>&1 \
        || { log 'ERROR: timed out or failed generating OpenVPN DH parameters'; return 1; }
    fi
  fi
  # CRL generation is cheap in normal cases, but on large/old PKIs it can still
  # delay an upgrade. Preserve a valid CRL and regenerate only when required.
  if ! crl_valid "$pki/crl.pem"; then
    timeout 60 env EASYRSA_BATCH=1 ./easyrsa gen-crl >>"$LOG" 2>&1 || log 'WARN: OpenVPN CRL generation failed/timed out'
  fi

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
    if openvpn --genkey tls-crypt /etc/openvpn/server/tls-crypt.key >>"$LOG" 2>&1; then
      :
    elif openvpn --genkey secret /etc/openvpn/server/tls-crypt.key >>"$LOG" 2>&1; then
      :
    else
      log 'ERROR: failed generating OpenVPN tls-crypt key'
      return 1
    fi
    log 'Generated a new OpenVPN tls-crypt key because no valid managed key existed'
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
  validate_openvpn_runtime_files || { log 'ERROR: OpenVPN final runtime invariant validation failed'; return 1; }
  log 'OpenVPN canonical PKI verified and synchronized; all mandatory runtime files are present'
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

ensure_wireguard_packages(){
  install_packages wireguard-tools wireguard || install_packages wireguard-tools || true
  ensure_kernel_prerequisites
}

ensure_pptp_packages(){
  install_packages ppp || true
  if ! command -v pptpd >/dev/null 2>&1; then
    install_packages pptpd || install_pptpd_from_debian_source || log 'WARN: PPTP server could not be installed on this OS'
  fi
}

case "$MODE" in
  --install-all)
    install_all_packages
    build_or_repair_openvpn_pki
    ensure_runtime_binaries
    ;;
  --packages) install_all_packages ;;
  --ensure-openvpn) build_or_repair_openvpn_pki ;;
  --wireguard-packages) ensure_wireguard_packages ;;
  --pptp-packages) ensure_pptp_packages ;;
  --ensure-xray) ensure_xray_binary ;;
  --ensure-hysteria) ensure_hysteria_binary ;;
  --runtime-binaries) ensure_runtime_binaries ;;
  *) echo "Usage: $0 [--install-all|--packages|--ensure-openvpn|--wireguard-packages|--pptp-packages|--ensure-xray|--ensure-hysteria|--runtime-binaries]" >&2; exit 2 ;;
esac

log "Protocol prerequisites completed: $MODE"

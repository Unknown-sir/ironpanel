#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR=${APP_DIR:-/opt/ironpanel}
ETC_DIR=${ETC_DIR:-/etc/ironpanel}
STRICT=0
JSON=0
QUIET=0
INSTALLED_ONLY=0
TARGET=''
while (($#)); do
  case "$1" in
    --strict) STRICT=1 ;;
    --json) JSON=1 ;;
    --quiet) QUIET=1 ;;
    --installed-only|--configured) INSTALLED_ONLY=1 ;;
    --protocol) shift; TARGET=${1:-} ;;
    --protocol=*) TARGET=${1#*=} ;;
  esac
  shift || true
done

if [[ -f "$ETC_DIR/ironpanel.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ETC_DIR/ironpanel.env"
  set +a
fi

failures=0
selected=0
rows=()
add(){
  local proto="$1" state="$2" detail="$3"
  [[ -n "$TARGET" && "$proto" != "$TARGET" ]] && return 0
  selected=$((selected+1))
  rows+=("$proto|$state|$detail")
  [[ "$state" == ok || "$state" == warning ]] || failures=$((failures+1))
}
active(){ systemctl is-active --quiet "$1" 2>/dev/null; }
exists_nonempty(){ [[ -s "$1" ]]; }
service_result(){
  local proto="$1" unit="$2" ready="$3"
  if active "$unit"; then add "$proto" ok "$ready; service is active"
  elif (( INSTALLED_ONLY )); then add "$proto" ok "$ready; service inactive (runtime reconciliation will decide whether to start it)"
  else add "$proto" failed "$unit is not active"
  fi
}

# OpenVPN: intentionally avoid `openssl dhparam -check` here. On large DH files
# that deep primality verification can look like an update hang. Parsing the
# generated parameters is sufficient for a fast health gate; OpenVPN validates
# them again when the daemon starts.
ovpn_missing=()
for f in /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt /etc/openvpn/server/server.key /etc/openvpn/server/dh.pem /etc/openvpn/server/tls-crypt.key /etc/openvpn/server/server.conf; do
  exists_nonempty "$f" || ovpn_missing+=("$f")
done
if ! command -v openvpn >/dev/null 2>&1; then
  add openvpn failed 'openvpn binary missing'
elif (( ${#ovpn_missing[@]} )); then
  add openvpn failed "missing files: ${ovpn_missing[*]}"
elif ! openssl x509 -in /etc/openvpn/server/server.crt -noout >/dev/null 2>&1 || ! openssl pkey -in /etc/openvpn/server/server.key -noout >/dev/null 2>&1; then
  add openvpn failed 'server certificate or private key is invalid'
elif ! timeout 10 openssl dhparam -in /etc/openvpn/server/dh.pem -noout >/dev/null 2>&1; then
  add openvpn failed 'DH parameters cannot be parsed'
elif ! openssl verify -CAfile /etc/openvpn/server/ca.crt /etc/openvpn/server/server.crt >/dev/null 2>&1; then
  add openvpn failed 'server certificate is not signed by the configured CA'
elif ! exists_nonempty /etc/openvpn/easy-rsa/pki/ca.crt || ! exists_nonempty /etc/openvpn/easy-rsa/pki/private/ca.key; then
  add openvpn failed 'canonical Easy-RSA issuing CA or private key is missing'
elif ! cmp -s /etc/openvpn/server/ca.crt /etc/openvpn/easy-rsa/pki/ca.crt; then
  add openvpn failed 'server CA and canonical Easy-RSA client issuing CA differ'
elif ! grep -q '^tls-crypt /etc/openvpn/server/tls-crypt.key$' /etc/openvpn/server/server.conf; then
  add openvpn failed 'server.conf does not reference the managed tls-crypt key'
else
  service_result openvpn openvpn-server@server.service 'binary, canonical PKI and config are ready'
fi

# WireGuard
if ! command -v wg >/dev/null 2>&1; then
  add wireguard failed 'wg binary missing'
elif ! exists_nonempty /etc/wireguard/server_private.key || ! exists_nonempty /etc/wireguard/wg0.conf; then
  add wireguard failed 'server_private.key or wg0.conf missing'
elif ! grep -Eq '^PostUp[[:space:]]*=.*FORWARD.*MASQUERADE|^PostUp[[:space:]]*=.*MASQUERADE.*FORWARD' /etc/wireguard/wg0.conf; then
  add wireguard failed 'wg0.conf is missing managed forwarding/NAT rules'
else
  service_result wireguard wg-quick@wg0.service 'binary, keys and forwarding/NAT config are ready'
fi

# Ocserv
if ! command -v ocserv >/dev/null 2>&1; then
  add ocserv failed 'ocserv binary missing'
elif ! exists_nonempty /etc/ocserv/ocserv.conf; then
  add ocserv failed 'ocserv.conf missing'
elif ! grep -Eq '^server-cert[[:space:]]*=' /etc/ocserv/ocserv.conf || ! grep -Eq '^server-key[[:space:]]*=' /etc/ocserv/ocserv.conf; then
  add ocserv failed 'certificate paths are missing from ocserv.conf'
else
  service_result ocserv ocserv.service 'binary and config are ready'
fi

# L2TP/IPsec
ipsec_service=''
active strongswan-starter.service && ipsec_service=strongswan-starter.service
[[ -n "$ipsec_service" ]] || { active strongswan.service && ipsec_service=strongswan.service || true; }
if ! command -v ipsec >/dev/null 2>&1 || ! command -v xl2tpd >/dev/null 2>&1; then
  add l2tp failed 'ipsec or xl2tpd binary missing'
elif ! exists_nonempty /etc/ipsec.conf || ! exists_nonempty /etc/ipsec.secrets || ! exists_nonempty /etc/xl2tpd/xl2tpd.conf || ! exists_nonempty /etc/ppp/options.xl2tpd; then
  add l2tp failed 'one or more L2TP/IPsec configuration files are missing'
elif (( INSTALLED_ONLY )); then
  add l2tp ok 'binaries and L2TP/IPsec configuration are ready'
elif [[ -z "$ipsec_service" ]] || ! active xl2tpd.service; then
  add l2tp failed 'StrongSwan or xl2tpd service is not active'
else
  add l2tp ok "IPsec service=$ipsec_service and xl2tpd are active"
fi

# PPTP
if ! command -v pptpd >/dev/null 2>&1; then
  add pptp failed 'pptpd binary missing (unsupported distributions may require source fallback)'
elif ! exists_nonempty /etc/pptpd.conf || ! exists_nonempty /etc/ppp/pptpd-options; then
  add pptp failed 'pptpd configuration files are missing'
else
  service_result pptp pptpd.service 'binary and config are ready'
fi

# Xray
xray_bin=$(command -v xray 2>/dev/null || true)
[[ -n "$xray_bin" ]] || [[ ! -x /usr/local/bin/xray ]] || xray_bin=/usr/local/bin/xray
if [[ -z "$xray_bin" ]]; then
  add xray failed 'xray binary missing'
elif ! exists_nonempty /usr/local/etc/xray/config.json; then
  add xray failed 'Xray config.json missing'
elif ! timeout 15 "$xray_bin" run -test -config /usr/local/etc/xray/config.json >/tmp/ironpanel-xray-test.log 2>&1; then
  add xray failed "config test failed: $(tail -n 2 /tmp/ironpanel-xray-test.log | tr '\n' ' ')"
else
  service_result xray xray.service 'binary and tested config are ready'
fi

# Hysteria2
hy_bin=$(command -v hysteria 2>/dev/null || command -v hysteria2 2>/dev/null || true)
[[ -n "$hy_bin" ]] || [[ ! -x /usr/local/bin/hysteria ]] || hy_bin=/usr/local/bin/hysteria
if [[ -z "$hy_bin" ]]; then
  add hysteria2 failed 'Hysteria2 binary missing'
elif ! exists_nonempty /etc/hysteria/config.yaml || ! exists_nonempty /etc/hysteria/server.crt || ! exists_nonempty /etc/hysteria/server.key; then
  add hysteria2 failed 'config or TLS certificate/key missing'
else
  service_result hysteria2 hysteria-server.service 'binary, TLS files and config are ready'
fi

# Telegram MTProto Proxy
if ! command -v node >/dev/null 2>&1 && ! command -v nodejs >/dev/null 2>&1; then
  add telegram_proxy failed 'Node.js runtime missing'
elif ! exists_nonempty /etc/systemd/system/ironpanel-tgproxy.service; then
  add telegram_proxy failed 'ironpanel-tgproxy systemd unit missing'
elif active ironpanel-tgproxy.service; then
  add telegram_proxy ok 'Node.js runtime and service are ready'
else
  add telegram_proxy warning 'runtime is installed but service is inactive; it may have no synchronized proxy users yet'
fi

# SSH
ssh_service=''
active ssh.service && ssh_service=ssh.service
[[ -n "$ssh_service" ]] || { active sshd.service && ssh_service=sshd.service || true; }
if ! command -v sshd >/dev/null 2>&1; then
  add ssh failed 'sshd binary missing'
elif ! timeout 10 sshd -t >/tmp/ironpanel-sshd-test.log 2>&1; then
  add ssh failed "sshd config test failed: $(tail -n 2 /tmp/ironpanel-sshd-test.log | tr '\n' ' ')"
elif [[ -n "$ssh_service" ]]; then
  add ssh ok "service=$ssh_service and config are ready"
elif (( INSTALLED_ONLY )); then
  add ssh ok 'sshd config is valid; service is currently inactive'
else
  add ssh failed 'SSH service is not active'
fi

if [[ -n "$TARGET" && $selected -eq 0 ]]; then
  (( QUIET )) || echo "Unknown protocol target: $TARGET" >&2
  exit 2
fi

if (( ! QUIET )); then
  if (( JSON )); then
    python3 - "${rows[@]}" <<'PY'
import json, sys
items=[]
for row in sys.argv[1:]:
    protocol,state,detail=row.split('|',2)
    items.append({'protocol':protocol,'state':state,'detail':detail})
print(json.dumps({'ok':not any(x['state']=='failed' for x in items),'protocols':items},ensure_ascii=False,indent=2))
PY
  else
    printf '%-18s %-9s %s\n' PROTOCOL STATUS DETAIL
    printf '%-18s %-9s %s\n' '------------------' '---------' '------'
    for row in "${rows[@]}"; do IFS='|' read -r p st d <<<"$row"; printf '%-18s %-9s %s\n' "$p" "$st" "$d"; done
  fi
fi

if (( STRICT && failures > 0 )); then exit 30; fi
exit 0

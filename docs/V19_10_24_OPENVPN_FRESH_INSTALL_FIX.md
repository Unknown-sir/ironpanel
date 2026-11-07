# IronPanel v19.10.24 — OpenVPN fresh-install PKI fix

## Observed failure
On an affected fresh Ubuntu 24.04 installation the OpenVPN package and `server.conf` existed, but `/etc/openvpn/server/ca.crt`, `server.crt`, `server.key`, `dh.pem` and `tls-crypt.key` were absent. The Easy-RSA directory still contained a valid `pki/ca.crt`, `pki/private/ca.key` and CRL. Starting `openvpn-server@server` therefore failed repeatedly on the first missing referenced key/file.

## New installer invariant
IronPanel uses `/etc/openvpn/easy-rsa/pki` as the single canonical issuing PKI. Before OpenVPN can start, installation must verify all of the following:

1. canonical CA certificate and CA private key exist and match;
2. Easy-RSA bookkeeping required for certificate issuance exists;
3. `issued/server.crt` and `private/server.key` exist, match, and verify against the canonical CA;
4. canonical `dh.pem` parses successfully;
5. runtime files are synchronized from the canonical PKI;
6. `tls-crypt.key` exists and has a valid OpenVPN static-key envelope;
7. runtime CA equals canonical CA.

If a valid CA exists, it is preserved. A second CA is created only when no valid CA/private-key pair is recoverable. Server leaf issuance has one bounded retry that clears only stale `CN=server` state.

## Start safety
`install_vpn_core.sh` performs a strict OpenVPN preflight and does not start the systemd service unless the PKI/runtime invariant passes. This prevents the previous five-second restart loop on a partially installed server.

## Existing servers
`repair_openvpn.sh` uses the same prerequisite routine, so affected installations can be repaired without reinstalling the panel. Upgrade/smart protocol repair will detect the incomplete OpenVPN core and run the repair for active OpenVPN installations.

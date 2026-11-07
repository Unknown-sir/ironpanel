# IronPanel v19.10.16 — Protocol prerequisites and installation validation

This release fixes incomplete protocol installations where the package or one
configuration file existed but required keys, certificates, binaries, systemd
units, or dependent packages were missing.

## Main changes

- Added `scripts/install_protocol_prerequisites.sh` as the shared prerequisite installer.
- OpenVPN now validates every required PKI artifact independently:
  `ca.crt`, `server.crt`, `server.key`, `dh.pem`, `tls-crypt.key`, and CRL when available.
- Existing Easy-RSA PKI is restored before a new CA is generated.
- Broken OpenVPN files are backed up under `/var/backups/ironpanel/protocol-prerequisites/`.
- Added Ubuntu `universe` enablement for protocol packages that live outside `main`.
- Added package/runtime preparation for WireGuard, Ocserv, StrongSwan, xl2tpd,
  PPP/PPTP, Xray, Hysteria2, Telegram MTProto Proxy, and SSH.
- Added a source-build fallback for `pptpd` on systems where the binary package
  is not available, including Ubuntu 24.04.
- Added `scripts/protocol_health_check.sh` to verify binaries, required files,
  config syntax, systemd services, and protocol-specific TLS/PKI material.
- Installation and full upgrade now run a strict final protocol health check.
- Added `IRONPANEL_ALLOW_PARTIAL_CORES=1` only as an explicit escape hatch for
  administrators who intentionally accept an incomplete protocol set.
- OpenVPN now uses `topology subnet` and does not add `crl-verify` unless a valid
  CRL is available.
- Node core installation also uses the shared prerequisite and OpenVPN PKI repair.

## Repair an already installed server

For complete core reconciliation, run `upgrade.sh` from the extracted full project package. The commands below are the safe targeted repair for prerequisites and the reported OpenVPN PKI failure.

```bash
sudo APP_DIR=/opt/ironpanel ETC_DIR=/etc/ironpanel \
  bash /opt/ironpanel/scripts/install_protocol_prerequisites.sh --install-all
sudo APP_DIR=/opt/ironpanel ETC_DIR=/etc/ironpanel \
  bash /opt/ironpanel/scripts/repair_openvpn.sh
sudo bash /opt/ironpanel/scripts/protocol_health_check.sh
```

Logs:

- `/var/log/ironpanel-protocol-prerequisites.log`
- `/var/log/ironpanel-protocol-health.log`

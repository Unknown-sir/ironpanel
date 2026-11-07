# IronPanel 19.9.20 — Node Hysteria2 Sync Fix

This release fixes the node auto-install/sync flow where protocol files were written and direct ports were normalized, but the final verification failed with `inactive=hysteria2 unhealthy=hysteria2`.

## Fixes

- Creates/repairs a dedicated `hysteria-server.service` on nodes.
- Forces Hysteria2 to listen on the node direct UDP port after config bundle sync.
- Generates a local node TLS certificate if the synced Hysteria2 certificate/key path is missing.
- Ensures `hysteria2_auth.sh` exists and is executable on the node runtime.
- Restarts and verifies Hysteria2 using the actual direct UDP port.
- Health check now retries the dedicated Hysteria2 runtime once before declaring the node unhealthy.
- Hysteria2 service aliases include `hysteria-server`, `hysteria2-server`, `hysteria-server@server`, `hysteria`, and `hysteria2`.

## Why

The node log showed successful package installation and correct normalization:

- `hysteria2:/etc/hysteria/config.yaml:port=4434`
- `post_exit=0`
- `inactive=hysteria2 unhealthy=hysteria2`

That meant the failure was not the direct-port JSON anymore. The Hysteria2 binary existed, but the node did not have a reliable systemd runtime unit after sync.

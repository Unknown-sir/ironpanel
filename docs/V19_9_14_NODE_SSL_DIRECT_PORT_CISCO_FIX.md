# IronPanel v19.9.14 — Node SSL probing, Direct Ports and Cisco Auth Hotfix

This release fixes three regressions reported during real node installation and Cisco/Ocserv login testing.

## Fixes

- Node runtime package download now probes all panel HTTP/HTTPS candidates in two passes:
  1. normal HTTP or TLS-valid HTTPS
  2. explicit TLS fallback for self-signed/IP-mismatch HTTPS only if every strict candidate fails
- The node installer no longer selects `https://IP:PORT` with `curl -k` before trying the HTTP endpoint or SSL domain.
- The selected TLS fallback state is passed into `install_node.sh` and stored in `/etc/ironpanel-node/node.env`.
- Node heartbeat no longer disables certificate verification automatically for every HTTPS IP; it follows the stored TLS mode.
- Node core install now returns the recent `/var/log/ironpanel-node-core-install.log` tail to the panel when a selected core fails.
- Telegram Proxy core installation retries NodeJS with `nodejs npm`, creates a `node` symlink when only `nodejs` exists, and logs the detected runtime version.
- Node health now validates the configured direct port from `IRONPANEL_NODE_DIRECT_PORTS_JSON` instead of accepting a service listening on the main-server port.
- Cisco/Ocserv password rebuild now calls `ocpasswd -c /etc/ocserv/ocpasswd <username>` for every user. Earlier builds used the file path as a positional argument for the second and following users, causing valid Cisco passwords to fail with cookie/auth errors.
- Node-side Cisco auth rebuild uses the same corrected ocpasswd invocation.

## After updating

Run this once on the main server:

```bash
sudo bash /opt/ironpanel/scripts/repair_cisco_auth.sh
```

Then run **Install/Repair automatic** for existing nodes so the node agent and core installer are replaced with v19.9.14.

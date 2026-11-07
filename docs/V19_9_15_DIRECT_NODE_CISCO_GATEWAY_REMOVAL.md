# IronPanel v19.9.15 — Direct Node Runtime + Cisco CSTP Fix

## Cisco / Ocserv
- Removed `connect-script` and `disconnect-script` hook injection from all ocserv repair/config generation paths.
- The broken hook could authenticate the password successfully and then fail CSTP/cookie authentication.
- `repair_cisco_auth.sh` and `repair_ocserv.sh` now strip old hook lines from `/etc/ocserv/ocserv.conf`.

## Direct Location Nodes
- Prefer configured SSL domains/public URLs before request IPs when building node installer candidates.
- Probe HTTP and HTTPS custom panel ports, and use insecure TLS fallback only after strict candidates fail.
- Node bootstrap and node installer now print candidate endpoints for debugging.
- Telegram Proxy node runtime is installed from the current IronPanel package, not GitHub, and is started on the direct port entered for the node.
- Direct port overrides are written into the node environment and applied during core install and config sync.

## Legacy Node Gateway
- Legacy Node Gateway UI links are hidden.
- Auto SSH installation no longer applies legacy Node Gateway DNAT/relay rules.
- Install/upgrade no longer installs the legacy node-gateway service automatically.

# IronPanel 19.9.9 — Node Runtime and Subscription Fixes

## Node execution

- The master worker executes only master actions. Remote Agent actions remain queued until the correct node heartbeat fetches them.
- Node Agent receives only its supported actions. `auto_ssh_install` remains a master-side SSH job.
- Installation validates the node token against the authenticated heartbeat endpoint.
- Selected core binaries are verified after installation.
- Public Xray and Hysteria listeners copied from the main server are normalized away from localhost so the node is externally reachable.
- Initial user metadata, protocol configs, service restarts, and health checks are executed and checked before Auto SSH Installer reports success.
- OpenVPN and Hysteria2 use compact node metadata instead of requiring a full panel database copy. SSH users are created/updated/locked on the node. Telegram Proxy runtime files are included in node config sync.

## Subscription layout

The public subscription page displays:

1. Main server configs at the top.
2. Each direct node as a separate location block.
3. Location flag first, then server name/location/host.
4. Download/copy cards for only that node's configs.

Node files use deterministic names (`node-<id>-<protocol>.<ext>`), are written to the profile directory, and are available through both individual downloads and the complete ZIP bundle.

## Faster update/install

Automatic full backups are skipped by default:

```bash
sudo bash /opt/ironpanel/scripts/safe_update.sh
```

Opt in when a pre-update backup is required:

```bash
sudo IRONPANEL_UPDATE_BACKUP=1 bash /opt/ironpanel/scripts/safe_update.sh
```

For reinstall backup:

```bash
sudo IRONPANEL_INSTALL_BACKUP=1 bash install.sh
```

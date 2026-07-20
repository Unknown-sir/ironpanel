# v19.8.0 - Smart Core Reload + Reliable Update Manager

## Smart Core Reload

User create/edit/delete operations now rebuild required config files but reload only the affected protocol cores.

Examples:

- WireGuard user change: updates wg0 peers using `wg syncconf` when possible.
- Xray user change: rewrites and restarts only Xray.
- Telegram Proxy user change: rewrites shared secrets and restarts only the proxy.
- SSH user change: applies Linux account changes without restarting sshd.
- Quota/traffic reset only updates database/profiles and does not restart cores.

Manual full sync and repair flows can still run a full service reconciliation when explicitly requested.

## Update Manager

The inline updater now clears stale update logs at the beginning of each run, so old completion markers cannot make the UI show 100% before a real upgrade happens. The updater writes explicit progress markers and waits for this-run completion markers before reporting success.

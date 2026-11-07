# v19.9.20 Sales Bot, Node Pre-Clean and License Sync

- Sales bot receipt handling now prioritizes pending payment orders over stale admin states such as free-config creation. This prevents the misleading `TelegramID PlanID Count` error during normal purchases.
- Public buy/renew inline buttons now show only the plan name entered by the admin.
- Admin free-config creation still supports `TelegramID PlanID Count [Name]`; the optional name is used as a prefix only when the prefix option is enabled.
- Node installer now pre-cleans old IronPanel node/panel runtime services before reinstalling with new node data. It stops/disables stale node, gateway and protocol services, removes old node unit files, clears `/opt/ironpanel-node` and `/etc/ironpanel-node`, then creates a fresh runtime.
- License heartbeat/version reporting is synced with IronPanel 19.9.20 so LicensePanel can track the latest installed version and remote-safe actions remain compatible.

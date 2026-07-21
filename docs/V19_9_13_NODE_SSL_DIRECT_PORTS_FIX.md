# IronPanel v19.9.13 - Node SSL Auto-Detect and Direct Port Runtime Fix

- Node Auto Installer now probes both HTTP and HTTPS variants for every known panel host/port before downloading the authenticated runtime package.
- Installer no longer depends on a single `request.url_root`; it also considers node_master_url, public_host, subscription_domain and tunnel_host.
- Node Agent heartbeat fallback also tests both schemes on explicit custom ports.
- Node direct-location ports are exported to core installation and post-sync verification.
- Telegram Proxy node runtime now rewrites `/opt/ironpanel-telegram-proxy/ironpanel/config.json` to the node-specific port instead of keeping the main-server port.
- Firewall opening now includes node-specific direct ports for selected protocols.
- Initial SSH installation receives the direct-port map from the panel and writes it to `/etc/ironpanel-node/node.env`.
- `ensure_protocols` jobs now carry the same direct-port map, so repair/reinstall keeps node services on the node-specific ports.
- Telegram Proxy health validates the configured TCP listener and exposes the actual port in node health details.

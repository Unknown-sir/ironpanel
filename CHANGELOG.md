## v13.5

- Fixed online users detection.
- Online sessions now read OpenVPN status logs, WireGuard handshakes/endpoints, Ocserv `occtl show users`, and L2TP PPP hooks.
- Added OpenVPN connect/disconnect online-session hooks.
- Added PPP ip-up/ip-down hooks for L2TP online-session tracking.
- Added dashboard online user count and improved Sessions page with protocol, IP, device and last-seen time.
- Fixed OpenVPN status-version 2 byte counter parsing for usage accounting.


## v13.3

- Added real traffic accounting sync for OpenVPN and WireGuard.
- Added one-minute systemd timer: `ironpanel-usage-sync.timer`.
- Subscription page now shows traffic capacity, used traffic, remaining traffic, expiration date and remaining days.
- OpenVPN and WireGuard configuration content is hidden on subscription pages; users can only download the files through their subscription token URL.
- Direct public `/profiles/...` downloads are now admin-login protected; public user downloads must use `/s/<token>/download/<file>`.

## v13.2

- Added complete bilingual API documentation for GitHub.
- Added `docs/API_GUIDE.md` with Persian and English API reference.
- Added `docs/openapi.yaml` for API tools and external integrations.
- Added curl, Python and Node.js examples.
- Documented API v1 and API v2 authentication.
- Documented user management, monitoring, sessions, billing, nodes, tickets, logs and Health Check details.

## v13.1

- Redesigned the Ironpanel sidebar menu.
- Added categorized collapsible navigation groups.
- Added active item highlighting for easier navigation.
- Reduced sidebar scrolling by grouping all advanced modules.

## 13.0.0

- Added v12/v13 modules.
- Added Health Check/Repair error detail buttons.
- Added finance, wallet, plans, payments, API additions, 2FA, recovery codes, login history, Telegram console, update manager.

## v13.4.0 - Accurate Usage Accounting & Quota Enforcement

- Fixed traffic usage not showing because sub-MB deltas were rounded down and lost.
- Added exact byte counters: `used_upload_bytes` and `used_download_bytes`.
- Added OpenVPN client-connect quota gate to block expired or over-quota users before connection.
- Added OpenVPN client-disconnect accounting script to capture final session counters.
- Added automatic quota enforcement in the one-minute usage sync timer.
- Over-quota or expired users are disabled, removed from WireGuard/Ocserv/L2TP runtime access, and VPN services are restarted to drop active sessions.
- Subscription page now displays human-readable total, used, remaining, upload and download traffic.
- Reset traffic now clears exact byte counters and runtime accounting baselines.

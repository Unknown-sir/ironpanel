# Changelog

## v15.5
- Fixed OpenVPN `User authentication failed` caused by client-connect scripts running after OpenVPN privilege drop.
- OpenVPN server config is now refreshed to remove legacy username/password auth directives.
- OpenVPN certificate-only profiles remain passwordless.
- Added safer OpenVPN auth logging and repair helper.


## v15.4

- Fixed OpenVPN `User authentication failed` for certificate-only profiles.
- OpenVPN client-connect no longer sources `/etc/ironpanel/ironpanel.env`, preventing Persian/unquoted env values from causing false AUTH_FAILED.
- Added robust OpenVPN certificate CN mapping for Unicode/Persian usernames.
- Added `/var/log/openvpn/ironpanel-auth.log` for OpenVPN auth diagnostics.
- Existing users should download a fresh OpenVPN profile after upgrading.


## v15.1
- Improved dashboard Version & License status layout.
- Fixed Health Check / Repair internal server error caused by incorrect HealthCheckRun database insertion.
- Added safer health diagnostics logging and rollback handling.

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

## v13.6 / v14 Sales Bot
- Added Telegram Sales Bot inside IronPanel for end-user VPN sales.
- Sales bot admins are registered from the panel using Telegram IDs.
- Bot admins can create plans from Telegram with custom name, duration, traffic, price and currency.
- Added manual payment workflow with receipt upload, admin approval/rejection and automatic VPN user creation after approval.
- Added trial service toggle, trial duration and trial traffic settings.
- Free trial is limited to one time per Telegram ID.
- Added Sales Bot web management page with settings, plans, orders and Telegram customers.
- Added systemd service `ironpanel-sales-bot` and daily reminders timer `ironpanel-sales-reminders.timer`.


## v15
- License type feature gating: Beginer, Plus, Pro, Admin, Trial.
- Update Manager checks GitHub and can update from https://github.com/Unknown-sir/ironpanel with one button.
- Sales bot admin workflow now uses inline buttons; text input is only used where necessary.

## v15.2
- Redesigned dashboard License & Version section for a cleaner, card-based layout.
- Hardened Health Check / Repair page against missing units, missing DB migrations and diagnostics failures.
- Added `/health/check-repair` alias and safe service error details page.
- Improved Update/License feature visibility for all license types.

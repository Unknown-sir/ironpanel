## 19.9.11 — Cisco Plain-Auth Path Hotfix

- Fixed the real Cisco/ocserv authentication regression visible as `plain-auth: error authenticating user ...` while `ocserv.service` was active.
- `generate_profiles()` no longer rewrites `/etc/ocserv/ocserv.conf` to a per-user path like `/etc/ironpanel/profiles/<username>/ocpasswd`.
- Cisco/ocserv now always reads the canonical auth database from `/etc/ocserv/ocpasswd`; `/etc/ironpanel/ocpasswd` is only kept as a legacy symlink/mirror.
- Rebuilt Cisco auth hashes directly with SHA-512 crypt format accepted by ocserv plain-auth instead of relying on interactive `ocpasswd` prompts.
- Added `scripts/repair_cisco_auth.sh` to rebuild Cisco users, repair ocserv, restart the service, and print the active auth path/user count.
- Node Agent Cisco auth now uses the same canonical `/etc/ocserv/ocpasswd` path and mirrors the compact legacy hash file for compatibility.

## 19.9.10 — Cisco Authentication + Node Connectivity Full Repair

- Fixed the Cisco/ocserv repair path that truncated `/etc/ironpanel/ocpasswd`, causing every valid username/password to be rejected after repair or update.
- Rebuilt ocserv configuration atomically, validated it before replacement, preserved managed TLS certificates, opened TCP/UDP firewall rules, enabled forwarding/NAT, and verified the real listening port.
- Unified the ocserv address pool and NAT source network on `10.44.0.0/24` across main-server install, node install, runtime config, and outbound routing.
- Fast GitHub updates now run a lightweight critical ocserv/auth repair and queue full node runtime synchronization even when heavy core reinstall is skipped.
- Disabled the large inline web-updater backup by default as well; optional update backup remains available with `IRONPANEL_UPDATE_BACKUP=1`.
- User create/edit/delete and full repair now synchronize credentials and runtime configuration to nodes automatically.
- Node config bundles no longer copy the whole `/etc/ironpanel` directory, preventing database, environment, license, backup, and stale authentication files from being transferred to nodes.
- For backward compatibility with already-installed v19.9.9 Agents, only the compact hashed `ocpasswd` file is explicitly synchronized so existing Cisco nodes recover credentials before a one-time Agent reinstall.
- Node ocserv and PPP authentication databases are rebuilt atomically from compact synchronized user metadata; partial L2TP/PPTP syncs no longer erase the other protocol's credentials.
- Fixed direct-node Xray port handling: the configured subscription port is now applied to the public Xray inbound instead of only changing the client link.
- Added SSH direct-port normalization and stricter node runtime health verification for service state, configuration validity, interfaces, and actual listening ports.
- Installer heartbeat probes no longer lease real node jobs, and node-only jobs remain isolated from the master worker.
- Node installation now downloads an authenticated runtime package from the exact running panel version instead of cloning a fixed GitHub repository, preventing stale Agent/core scripts on new or repaired nodes.
- Added validated-TLS-first/self-signed fallback handling for node package download and heartbeat setup, plus root/sudo-safe installation commands.
- Main-server Cisco health now checks `ocserv -t`, real TCP/UDP listeners, the configured password file, and actual auth-user count instead of reporting systemd Active as healthy.
- Direct OpenVPN node profiles now use the port matching the selected TCP/UDP transport, and node config jobs fail when a service is active but its real runtime/listener is unhealthy.

## 19.9.9 — Verified Node Runtime + Grouped Subscriptions + Fast Updates

- Fixed a critical job-routing bug where the master worker consumed node-agent jobs and marked them successful without executing them on the remote node.
- Restricted master and node workers to their own supported action sets; master-only SSH install jobs are never sent to Node Agent.
- Node installation now requires an authenticated heartbeat, verified core binaries, successful config/user sync, active protocol services, and a running Agent service.
- Fixed copied Xray/Hysteria node configs that could remain bound to localhost; public inbounds are now normalized to listen on node interfaces.
- Auto SSH installation drains and verifies the initial node jobs synchronously and reports a real failure when a core, config, credential sync, or service start fails.
- Added node-native OpenVPN/Hysteria2 authentication metadata and real SSH account synchronization; full panel database copies are no longer required for these node protocols.
- Added Telegram Proxy runtime transfer to node config bundles.
- Subscription profiles are now grouped with the main server first, followed by each node with its location flag, server name, host, and node-specific downloads.
- Fixed node profile 404 errors by persisting deterministic per-node files and added a complete ZIP download.
- Xray raw subscriptions now preserve the main link first and append separate direct-node links.
- Automatic backups are skipped by default during update/reinstall for faster deployment. Set `IRONPANEL_UPDATE_BACKUP=1` or `IRONPANEL_INSTALL_BACKUP=1` to opt in.

## 19.9.8 — Node Direct Location Rebuild + Panel Watchdog

- بخش Nodes از نو بازنویسی شد و مدل پیش‌فرض آن Direct Location Subscription شد.
- فرم جدید نود شامل نام سرور، نام نود، آدرس سرور نود، دامنه کانفیگ، پروتکل‌ها و پورت جداگانه هر پروتکل است.
- هنگام ثبت نود، اطلاعات SSH به‌صورت رمزنگاری‌شده ذخیره و نصب خودکار در صف Job قرار می‌گیرد؛ نصب دیگر داخل request وب اجرا نمی‌شود و باعث Down شدن پنل نمی‌شود.
- نصب خودکار از طریق SSH هسته‌ها را نصب/Repair می‌کند، Agent نود را وصل می‌کند، کانفیگ پروتکل‌ها و کاربران را Sync می‌کند و Health Check می‌سازد.
- کانفیگ‌های نود به Subscription اضافه می‌شوند ولی UUID/Password/Identity از پنل اصلی می‌آید؛ مصرف Main و همه نودها روی همان quota مشترک کاربر محاسبه می‌شود.
- Heartbeat نود گزارش مصرف را ارسال می‌کند و پنل اصلی delta مصرف را روی کاربر اعمال می‌کند.
- Watchdog جدید اضافه شد تا اگر ironpanel فعال نبود یا /healthz پاسخ نداد، سرویس را خودکار restart کند.
- systemd پنل harden شد: Restart سریع‌تر، KillMode mixed، TimeoutStopSec و watchdog timer.


## 19.9.7 - Node Page 500 Fix
- Fixed `/nodes` HTTP 500 caused by missing Direct Location template helpers after v19.9.5.
- Added a runtime Node schema guard so the Nodes page can self-heal missing SQLite columns before querying Node records.
- Added safe fallback rendering for the Nodes page so a migration/schema issue is shown as an admin warning instead of crashing the panel.
- Added defensive Direct Location port parsing for add/edit node forms.

## 19.9.6 - SQLite Migration Lock Guard

- Added SQLite busy timeout and WAL tuning for the default IronPanel database.
- Wrapped `init-db` and `upgrade-db` with retry/backoff when SQLite is temporarily locked.
- Added `scripts/upgrade_db_safe.sh` to stop background DB writers, run migrations safely, and restore timers/services.
- Updated `upgrade.sh`, Safe Update, Repair DB, and Xray repair flows to use the safe migration wrapper.
- This fixes upgrade failures like `sqlite3.OperationalError: database is locked` when usage sync, node sync, bots, or the web service are still holding the database.

# Changelog

## 19.9.5 — Direct Location Subscriptions
- Add Direct Location delivery mode for nodes: relay/direct/both/disabled.
- Nodes can appear as separate locations in subscriptions with their own host and per-protocol public ports.
- Master-generated identity is reused on every location, so one user can have many configs while traffic quota remains shared.
- Xray raw subscriptions now include main plus direct-location links.
- Profile payloads can include extra OpenVPN/WireGuard/text configs per location.
- Node heartbeat reports best-effort per-user usage counters for Xray, WireGuard and OpenVPN; master applies deltas to the same VpnUser quota.
- Node auto-sync continues every few minutes for configs/users and now carries usage-related identity metadata.

## 19.9.4 - LicensePanel Guide Site SEO & Motion Refresh

- Full package updates the LicensePanel-installed IronPanel guide website with a more modern animated responsive design.
- Added IronPanel-focused SEO metadata and structured data for the public documentation site.
- Removed the unwanted LicensePanel installation text from the guide-site hero section.

## 19.9.3 - LicensePanel Guide Site

- Added documentation for the LicensePanel-installed IronPanel guide website on port 443.
- Full package includes the actual guide-site installer and static website assets.


## v19.9.2 - Modern Pages UI Refresh

- بازطراحی بصری صفحات Quick Create، Users & Configs، Usage & Reports، Online Users، حساب من، Core Settings، Firewall و Update Manager.
- اضافه شدن hero cardهای مدرن، کارت‌های KPI، فرم‌های خلوت‌تر، آکاردئون برای تنظیمات پیشرفته و action grid ریسپانسیو.
- صفحه Users & Configs کارت‌بندی شد و فرم ساخت کاربر داخل بخش کشویی قرار گرفت تا لیست کاربران شلوغ نباشد.
- صفحه Core Settings به کارت‌های جداگانه و بخش‌های کشویی برای پورت‌ها، WireGuard/Hysteria2 و Telegram تقسیم شد.
- صفحه Firewall و Update Manager با جدول‌های responsive، کارت‌های امن‌تر و لاگ/پیشرفت خواناتر به‌روزرسانی شدند.
- بهبود تجربه موبایل با breakpointهای جدید، کارت‌های قابل لمس و فرم‌های تک‌ستونه در صفحه‌های کوچک.

# 19.9.1 - README Refresh

- README اصلی بازنویسی و مرتب شد.
- تاریخچه طولانی نسخه‌ها از README حذف شد و به CHANGELOG/docs ارجاع داده شد.
- معرفی امکانات IronPanel، Node Gateway، Transparent Relay، Auto SSH Node Installer، پلن‌ها و دستورات کاربردی شفاف‌تر شد.

# 19.9.0 — Node Auto SSH Installer

- Added Pro/Admin-only Auto SSH Installer for nodes.
- Supports encrypted saved SSH password/private-key credentials.
- Runs node install/repair, core install, config sync, user sync and health check from the panel.
- Added install logs and credential clearing UI.

## 19.8.22 - Transparent Node Relay Mode
- Keep client configs pointed at the main panel in gateway mode.
- Add userspace transparent relay service for TCP/UDP node forwarding so replies return through the main panel.
- Use REDIRECT to local relay ports for TCP/UDP protocols; keep DNAT/SNAT only as GRE fallback.
- Add relay logs and systemd service for easier troubleshooting.

## 19.8.21 - Node Direct Endpoint Fallback
- Generate direct node endpoints for protocols forced to Fixed/Fixed Only nodes, while keeping main-panel DNAT forwarding as backwards-compatible fallback for old client configs.
- Xray subscription links now use the selected node host/port when Xray is forced to a node.
- OpenVPN, WireGuard, Ocserv, L2TP, PPTP, Hysteria2, Telegram Proxy and SSH generated profiles now also honor forced node endpoints.
- Flush stale conntrack entries for forwarded protocol ports when applying Node Gateway rules.

## 19.8.20 - Node Gateway Return Path Fix
- Harden Node Gateway forwarding with deterministic SNAT/MASQUERADE return path.
- Add bidirectional FORWARD rules for node forwarded protocol ports.
- Disable rp_filter per interface to avoid asymmetric DNAT drops on VPS kernels.
- Add node TCP port probes and more complete Gateway NAT/FORWARD/POSTROUTING logs.
- Keep node core/config/user sync flow from 19.8.19.

## v19.8.19 — Node Auto Sync
- نصب نود بعد از بالا آمدن Agent، نصب هسته‌ها، Sync کانفیگ پروتکل‌ها و Sync کاربران را همان لحظه درخواست و اجرا می‌کند.
- هر چند دقیقه، بر اساس `node_auto_sync_interval_sec`، کانفیگ پروتکل‌های Force شده و کاربران فعال دوباره روی نود Sync می‌شوند.
- هنگام Force کردن پروتکل به نود، full sync شامل core/config/users صف می‌شود تا نود فقط پورت فوروارد نداشته باشد و واقعاً آماده اتصال باشد.

## 19.8.19 - Node Gateway Direct DNAT + Node Egress Fix
- Make Node Gateway DNAT rules match incoming protocol traffic directly and exclude node-source loops.
- Add restricted NAT OUTPUT hook for local forwarding tests.
- Normalize synced Xray configs on nodes by removing copied `sendThrough` bindings so egress leaves through the node IP.
- Add clearer gateway logs/counters and note that client configs still show the main-panel address by design.

## 19.8.17 - Node Gateway Xray Public Ports
- Exclude Xray internal/API/stat ports such as 10085 from Node Gateway plan and forwarding rules.
- Normalize synced Xray and Hysteria2 node configs so public inbounds listen on 0.0.0.0 on the node instead of the main server IP.
- Add gateway counter snapshots to /var/log/ironpanel-node-gateway.log for easier DNAT/FORWARD verification.

## 19.8.16 - Node Gateway Pipefail and HTTPS Fix
- Fix apply_node_gateway.sh exiting before applying rules when there are no old MASQUERADE rules under set -euo pipefail.
- Keep the actual current request scheme for node install commands, so panels running HTTPS on custom ports such as 8001 generate HTTPS master URLs instead of forcing HTTP.
- Improve Node Gateway apply logging and fail when no rules are applied or host resolution fails.
- Keep force-protocol route crash-safe and continue syncing protocol configs from the main server to nodes.

## 19.8.15 - Node Dynamic Protocol Ports
- Node Gateway now reads actual configured ports for Xray, Hysteria2 and Telegram Proxy instead of fixed defaults.
- Xray Gateway forwards all enabled Xray Builder inbound ports.
- Hysteria2 and Telegram Proxy ports are detected from AppSetting aliases and runtime config files.
- Node config sync runs core/firewall repair again after configs are copied, so node-side firewall opens the real protocol ports.
- Gateway plan table now shows the exact ports that will be forwarded to nodes.

## 19.8.14 - Node Force Route Crash Fix + Verified Forwarding
- Fix Internal Server Error on `/nodes/<id>/force-protocols` by calling the force routine correctly and adding safe rollback.
- Queue protocol core/config sync whenever a node is created, repaired, or forced for a protocol.
- Restrict Node Gateway DNAT to traffic whose destination is the main server local IP, preventing unrelated forwarded traffic from being captured.
- Add safer gateway apply logging and panel-port skip protection.
- Extend node config sync to include common IronPanel runtime SSL/settings/scripts needed by protocol auth hooks.

## 19.8.13 - Node Real Forward + Config Sync + Reset
- Apply real iptables DNAT/FORWARD/MASQUERADE for protocols forced to nodes.
- Forward all protocol-specific ports, including OpenVPN UDP/TCP, Ocserv TCP/UDP, L2TP/IPsec ports and PPTP GRE.
- Sync selected protocol config files from main server to target nodes and restart related services.
- Add Node Gateway reset action to clear all forwards and return protocols to the main server.
- Install Node Gateway forwarding as a systemd oneshot service for reboot persistence.

## 19.8.12 - Node Force Route Cores Metrics
- Add Fixed Only mode to route selected protocols only to one node with no local/other-node failover.
- Add per-node quick action to force one or more protocols to the selected node.
- Include selected protocol core installation in node install commands.
- Add node core installer for VPN/proxy prerequisites and firewall openings.
- Improve Node Agent CPU/RAM/Disk/Ping/health reporting and persist ping metrics on master.

## 19.8.11 - Node Heartbeat Verify
- Fix Node installer accepting https://IP:custom-port based on a superficial ping/root check.
- Prefer http://IP:panel-port for raw IP panels on custom ports such as 8001.
- Verify the real /api/v2/node/heartbeat endpoint with the node token before saving the master URL.
- Re-order Node Agent fallback candidates so stale https://IP:8001 configs try HTTP first.
- Add clearer installer diagnostics for token, firewall, SSL, and master URL problems.

## 19.8.10 - Node Connection Fix
- Add a public `/api/v2/node/ping` endpoint for node installer connectivity checks.
- Make `install_node.sh` resolve legacy/broken master URLs such as `https://IP` to the reachable panel URL with the real port, including common panel port fallback.
- Harden Node Agent heartbeat with HTTP fallback, optional insecure TLS for IP/self-signed HTTPS, better errors, and one-shot post-install heartbeat test.
- Install `ca-certificates` and create an `ironpanel-node-agent` systemd alias for compatibility.

## 19.8.9 - Node Master Port + Node Edit Delete
- Generate Node Agent install commands with the actual panel port, for example http://IP:8001 instead of https://IP without a port.
- Avoid forcing HTTPS for raw IP/localhost master URLs on non-443 panel ports.
- Add edit and delete actions for every node in the Nodes page.
- Clean up user node assignments, sessions, port rows, routing maps and queued jobs when a node is deleted.

## 19.8.8 - Firewall IP Ban
- Add full IP/CIDR ban controls to the IronPanel Firewall page.
- Rebuild a dedicated IRONPANEL-BAN chain for INPUT, FORWARD, and OUTPUT.
- Persist ban rules with iptables-save/netfilter-persistent when available.
- Add toggle/delete/reapply controls for firewall rules and IP bans.
- Add safety checks against banning the whole internet, loopback, or the current admin IP by accident.

## 19.8.3 - Plan Protocol Matrix
- Beginner/Free now only allows OpenVPN and Xray.
- Plus allows all VPN protocols but disables Nodes/Node Agent, Sales Bot and Billing.
- Pro enables all operational features except Billing.
- Admin enables the full panel.
- LicensePanel sales bot no longer offers Admin plans for public purchase.

## 19.8.2 - Real Update Completion + Menu/Health Fix
- Fix inline Update Manager false 100% by waiting for upgrade.exit=0 instead of scanning command text for a marker.
- Defer panel restart until the tracked upgrade process really exits successfully.
- Run inline/terminal updates in fast safe mode and leave heavy protocol repairs to Health & Repair.
- Fix More Settings sidebar layout so details menus do not collapse or overlap on mobile/tablet/desktop.
- Always show Repair for every protocol row in Health & Repair, even when healthy.
- Keep Plus license access to Nodes and Node Agent enabled in IronPanel and LicensePanel feature flags.

# Changelog

## 19.8.1 - Menu Health Plus Nodes
- Fix More Setting sidebar overlap/collapse behavior on desktop and mobile.
- Always show protocol Repair buttons in Health & Repair, including healthy protocols.
- Add dedicated L2TP repair script.
- Enable Nodes and Node Agent for Plus licenses.
- Parse newer Xray Reality x25519 output labels correctly.
- Make terminal GitHub update skip heavy protocol repair loops by default so source updates can finish cleanly.

## 19.8.0 - Smart Core Reload + Reliable Update Manager
- Add Smart Core Reload so user create/edit/delete only reloads affected VPN protocol cores.
- Apply WireGuard peer updates with `wg syncconf` when available instead of restarting all WireGuard sessions.
- Avoid restarting OpenSSH for normal SSH user sync.
- Fix Update Manager false 100% by clearing stale update logs per run and relying on current-run completion markers.
- Add updater progress markers to terminal/GitHub update logs.

## 19.7.0 - License Control Center Compatibility
- Send richer telemetry to LicensePanel: users, online users, disk, health, update and SSL state.
- Execute only safe remote actions queued by LicensePanel and report results back.
- Keep README focused on IronPanel with install/update commands and feature tables.

## 19.6.0 - Stability Doctor + Safe Updater + Safe Backup
- Add Health Doctor with full service, port, file, DB, SSL, node and speed-limit checks.
- Add per-row Repair actions and full Repair from panel.
- Add Safe Backup/Restore with pre-restore backup and archive path validation.
- Add safe terminal updater: `sudo bash /opt/ironpanel/scripts/safe_update.sh`.
- Improve Update Manager completion detection with status polling and completion markers.

## 19.5.0 - Full Node Manager + Per-User Speed Limits
- Complete Node Gateway management with fixed node, least-users, best-ping and balanced strategies.
- Add node health/protocol health, heartbeat jobs, user sync queue and simple one-command node install flow.
- Add failover and rebalance actions for auto-assigned users.
- Change speed limits from shared per-protocol caps to per-user per-protocol limits with optional user overrides.
- Update README with IronPanel-only node/speed-limit docs and tables.

## 19.4.1 - Responsive Users & Configs
- Replace the wide users table with responsive user cards.
- Hide long per-user protocol lists behind a compact info button.
- Make user actions wrap cleanly on desktop and mobile.
- Clean up user config cards to prevent horizontal scrolling.

## 19.4.0 - Reseller Usage Ledger + Reseller Sales Bots
- Charge reseller quota from actual traffic usage, not allocated config volume.
- Keep reseller consumed quota cumulative even if child users/configs are deleted or reset.
- Enforce exhausted reseller quota by disabling the reseller child users.
- Add owner-aware sales bot settings/plans/orders/customers for main admin and each reseller on Pro/Sales Bot licenses.
- Add systemd template sync for reseller sales bot services.

## 19.3.0 - Pro Node Gateway + Update 100% Fix
- Add Pro-only Node Gateway / Load Balancer page.
- Route each protocol to Local, a fixed node, least-users node, best-ping node, or balanced strategy.
- Gate node pages and node agent features to Pro only.
- Fix Update Manager progress by detecting completion log marker and forcing 100%.
- Add reseller-created badge in the users list.
- Refresh README with IronPanel-only content and tables.

## 19.2.0 - LicensePanel Install Telemetry
- Send periodic install/active/online heartbeat from every IronPanel server to LicensePanel.
- Add systemd heartbeat timer so installed panels are counted even when the UI is idle.
- Report free Beginner installs without requiring a paid license key.

## 19.1.0 - Speed Limits and Routing Rules
- Add per-protocol Mbps speed limit UI and runtime tc apply script.
- Add modern Routing Rules page for protocol-to-outbound mapping.
- Fix inline Update Manager completion progress to 100%.
- Add terminal update command to README.

## 19.0.0 - Famous DNS Presets for WireGuard
- Add famous DNS presets to WireGuard settings: Cloudflare, Google, Quad9, OpenDNS, AdGuard, DNS.SB, Shecan, Electro and Begzar.
- Auto-seed famous DNS profiles in DNS Manager during install/upgrade without deleting custom profiles.
- Add one-click Apply to WireGuard DNS from DNS Manager.
- Keep README tables for protocols, licenses and features updated.

## 17.1.2 - Account, WireGuard DNS and Clean Subscription
- Added self-service account page for admin/resellers to change username and password.
- Added full reseller delete action for main admin.
- Added configurable WireGuard DNS for generated client configs.
- Cleaned subscription popups and per-protocol outputs.



## v17.1.2 - Account Settings + WireGuard DNS

- صفحه **حساب من** برای تغییر نام کاربری و رمز عبور خود ادمین/نماینده اضافه شد.
- ادمین اصلی می‌تواند نماینده را حذف کند؛ کاربران زیرمجموعه به‌صورت پیش‌فرض حذف نمی‌شوند و فقط از نماینده جدا می‌شوند.
- تنظیم **WireGuard DNS** به پنل اضافه شد و DNS کانفیگ‌های WireGuard دیگر ثابت نیست.
- جدول امکانات و لایسنس‌ها در README حفظ و به‌روزرسانی شد.

## 17.1.1 - Subscription Popup UI

- Redesigned public subscription page to show protocol icons/cards only.
- Added per-protocol modal popup for config preview, copy, QR and download.
- Improved mobile readability by hiding raw config clutter until user opens a protocol.

# 17.1.0 — Matrix Login + Login Alerts

- Matrix animated login page.
- Login failure shake animation and clear error message.
- Safe Telegram admin-bot alerts for successful and failed login attempts.
- Preserved custom Telegram Proxy port during update/repair.
- README tables refreshed.

# 17.0.1 — Login UI + Simple Update Manager

- Redesigned the login page with a modern glass/aurora visual style and responsive login layout.
- Added Update Manager as a direct item in the Simple UI menu for main admins.
- Updated project README/README_FA with the new UI and update-manager notes.

# 17.0.0 — SSH Protocol

- Added SSH Tunnel / SSH Proxy protocol with default port `422/tcp`.
- Added OpenSSH repair/install script, Settings UI, user config delivery and README/docs updates.

# v18.6.11 — Telegram Proxy Service Crash Fix

- Hardened `ironpanel-tgproxy.service` startup after reports of `status=1/FAILURE`.
- Rebuilt `repair_telegram_proxy.sh` to validate/rebuild `config.json`, stop legacy per-user units, kill orphan proxy wrappers, choose the real NodeJS binary, check wrapper syntax, open firewall, and write clear diagnostics.
- Added `/var/log/ironpanel-tgproxy.log` with persistent wrapper logs and surfaced recent lines in Telegram Proxy Manager.
- Reworked the shared MTProto wrapper to keep the process alive on client/upstream socket exceptions and to log fatal listener errors such as a busy port.
- Kept the shared-port/per-user-secret accounting model; users still connect to one port, while usage is written per user ID to `usage.json`.
- Updated README/README_FA and version docs.

# v18.6.10 — Telegram Proxy Core + Update Fetch Fix

- Installed and enabled the shared Telegram MTProto proxy core during install/upgrade.
- Added robust `repair_telegram_proxy.sh --sync` behavior for service, runtime config, firewall, and user secret sync.
- Fixed Telegram proxy links by sanitizing server host values.
- Fixed Update Manager `failed fetch` near 45% by tracking the long upgrade phase via a visible pollable task.
- Updated README documentation.

## v18.6.9 — Shared Telegram Proxy Fix
- Changed Telegram Proxy from per-user ports to a single shared port with per-user secrets.
- Added IronPanel MTProto wrapper with per-secret accounting.
- Fixed non-working delivered Telegram proxy links caused by per-user port/service mode.
- Usage quotas now include Telegram Proxy bytes collected from usage.json.

## 18.6.8 - Telegram Proxy Manager + Update Manager Repair
- Keep full Persian README inside the project package.
- Fix Update Manager autostart and controlled restart flow from the same page.
- Add Telegram MTProto Proxy management page for admins.
- Add Telegram Proxy settings: enable toggle, base port and secret salt.
- Improve per-user Telegram Proxy traffic accounting from iptables counters.
- Re-sync/stop per-user Telegram Proxy services when users hit quota.


## v18.6.7 — Telegram Proxy + WireGuard MTU 1280
- Default WireGuard MTU changed to 1280.
- Added per-user Telegram MTProto proxy protocol powered by JSMTProxy-style instances.
- Added per-user Telegram proxy links and downloads in subscription profiles.
- Added Telegram proxy traffic accounting by per-user TCP port and quota enforcement integration.
- Added Telegram proxy repair/install script and Settings controls.

## 18.6.6 - Inline Update Progress + Responsive Subscription Downloads
- Update Manager: step-by-step same-page GitHub update with progress bar.
- Downloaded OpenVPN/WireGuard/Xray/Hysteria2 filenames now use the VPN username.
- Subscription page redesigned to v5 and hardened for mobile responsiveness.
- Global admin UI responsive guard improved for tables, forms, cards and sidebar.

## v18.6.5
- LicensePanel manual licenses can be linked to a Telegram Chat ID.
- Fixed Xray Reality builder link generation and Xray firewall repair.
- Added Hysteria2 hy2:// client alias and UDP firewall repair.


## 18.6.4 - License Reset Manager

- Added LicensePanel web edit page for existing licenses.
- Added admin reset for all activations or one registered server.
- Added Telegram bot My Licenses menu for users to manage only their own licenses.
- Added owner-side activation release from Telegram bot for moving a license to a new server.
- Logged all reset/release actions.

## 18.6.3 - Full Responsive UI + Reliable GitHub Update Manager

- Fixed GitHub Update Manager by launching upgrades through an independent systemd transient unit instead of a child process of the web panel.
- Added update unit/status visibility and stronger log output in the Update Manager page.
- Improved responsive behavior across the panel with a mobile sidebar drawer, safer grids, mobile-safe forms, responsive tables and overflow guards.
- Rebuilt the public Subscription page with a newer animated v4 glass/aurora design and stronger mobile layout.


## 18.6.2 - Responsive UI and Subscription Domain Fix
- Fixed user-list subscription buttons to open with the configured Subscription Domain.
- Exposed subscription URL helpers globally to admin templates.
- Updated API serializers to return absolute subscription URLs.
- Added broad responsive CSS improvements for mobile.
- Redesigned the public Subscription page with a modern animated responsive layout.

## 18.6.1 - WireGuard MTU + Subscription Domain

- Added a dedicated Settings card for custom WireGuard MTU.
- Added a dedicated Settings card for custom subscription domain/subdomain.
- Public subscription links, QR codes, Telegram sales bot messages and reseller API now use the dedicated subscription domain when configured.
- Kept WireGuard MTU default at 1360 and PersistentKeepalive at 25.

# 18.6.0 - Priority Infrastructure, WireGuard MTU, i18n Theme Pack

- Added WireGuard MTU default 1360 and PersistentKeepalive controls across installer, settings, server config, repair scripts and client profiles.
- Converted installer questions and actionable install output to English for safer international deployments.
- Added stronger language/theme foundation with Light/Dark/Auto UI modes, language selector and appearance page.
- Added automatic local job worker service/timer for queued maintenance tasks.
- Added reseller-scoped API endpoints for users, sessions, stats and subscription links.
- Added improved activity logs dashboard with filters and quick operational summaries.
- Added high-priority operations documentation.


## 18.5.9 - Reseller UI, Full GitHub Upgrade & Subscription Redesign

- Fixed reseller UI visibility by adding dashboard and sidebar entry points.
- Added automatic portal path generation for existing sub-admin/reseller accounts.
- Improved reseller table with quota, status, portal URL, copy, edit, suspend and resume controls.
- Removed custom repository/branch install block from README files and updated README image URL.
- Hardened GitHub quick upgrade to run full DB/service/systemd/VPN synchronization.
- Redesigned the public subscription page with modern cards, QR actions and responsive layout.

## 18.5.8 — DB Migration Fix
- Fixed installer/init-db crash on upgraded SQLite databases missing `admin.enabled`.
- Runs lightweight SQLite migration before the first Admin ORM query.
- Keeps reseller portal columns backward-compatible during reinstall/upgrade.

## 18.5.7 - Reseller Portal Link & Quota Controls

- Added generated reseller portal URLs (`/r/<path>` and `/reseller/<path>`).
- Added reseller quota editing for user count and traffic allocation.
- Added reseller panel suspend/resume controls.
- Enforced reseller quota while creating or increasing users.

## 18.5.6 - Installer Bash Compatibility Fix

- Fixed `install.sh: invalid indirect expansion` on one-step GitHub install and local install.
- The installer now reads prompted defaults without unsupported indirect-expansion syntax.
- Direct GitHub install remains: `bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)`.

## 18.5.5 - Cleaner Bot Pages & Start Menus
- Cleaner Sales Bot and Admin Bot configuration pages.
- Configurable /start welcome text for both bots.
- Inline glass-button menus are shown on /start.
- Admin bot buttons remain restricted to allowed Telegram admin IDs.

# 18.5.4 — GitHub Update Alert & Quick Upgrade

- اضافه شدن اعلان نسخه جدید GitHub در داشبورد main admin.
- اضافه شدن دکمه «آپگرید سریع» برای اجرای upgrade از داخل پنل.
- اجرای آپگرید در پس‌زمینه برای جلوگیری از قطع شدن request هنگام restart پنل.
- کش کردن نتیجه بررسی VERSION و مقایسه عددی نسخه‌ها.
- مقاوم‌تر شدن scripts/update_from_github.sh با بکاپ source و /etc/ironpanel قبل از آپگرید.
- اضافه شدن لاگ /var/log/ironpanel-github-upgrade.log.

## 18.5.2
- نصب به یک مسیر واحد `install.sh` تبدیل شد؛ سؤال‌های اصلی پرسیده می‌شوند و مقدار پیش‌فرض امن دارند.
- دستور نصب مستقیم از GitHub به README اضافه شد.
- Hysteria2 auth command، fallback certificate، server config و client output اصلاح شد.
- شلوغی متن‌ها و نام‌های منو کمتر شد.


## 18.5.1 سابق
- نصب ساده و مقاوم‌تر با `install.sh` و لاگ نصب.
- حالت پیش‌فرض رابط کاربری ساده شد و گزینه‌های تخصصی در Advanced جمع شدند.
- ابزار Doctor برای بررسی و ترمیم سریع سرویس‌ها اضافه شد.

## 18.5.0 - 3x-ui Parity UX Pack
- Quick Create User, Xray Pro Builder, IP Limit, GeoFile Manager, Subscription Theme Manager and Admin Telegram Bot settings.

## v18.4.4 - Traffic usage multiplier
- Added a license-independent Traffic Multiplier page for the main admin.
- Raw traffic is kept intact, while effective/charged usage, remaining quota and subscription display can be multiplied by the configured factor.
- Quota enforcement now disables users when effective traffic reaches the user's volume limit.
- Subscription, user list, usage reports and API outputs now expose raw and multiplier-adjusted usage.

## v18.4.3 - Certbot compatibility repair
- Prefer isolated Snap certbot for Auto SSL to avoid system Python pyOpenSSL/cryptography crashes.
- Detect the X509_V_FLAG_NOTIFY_POLICY certbot failure and automatically try Snap, apt repair, then a dedicated certbot venv.
- Store the selected certbot path for SSL renewal and expose it in SSL status.
- Added scripts/repair_certbot.sh for servers with broken certbot packages.

## v18.4.2 - Auto SSL protocol matrix
- Clarified that Hysteria2 and Ocserv/AnyConnect require domain TLS certificates and are wired automatically after Auto SSL issuance.
- Added an Auto SSL service matrix so admins can see which protocols use Let’s Encrypt and which protocols use their own crypto model.
- Made Xray TLS switching optional; Reality remains the default because it does not require a public TLS certificate.

# Changelog

## 18.4.1
- Added Auto SSL center available to all license tiers.
- Automatically issues Let’s Encrypt certificates, stores them under /etc/ironpanel/ssl, and wires them to panel TLS, Ocserv, Hysteria2 and Xray TLS settings.
- Added renewal hook and regenerated runtime configs after SSL changes.

## 18.4
- Beginner is now a built-in free edition with no key and no expiration.
- Added the Upgrade center for Plus, Pro and Admin activation.
- Invalid or expired paid licenses fall back to Beginner instead of locking the panel.
- Added 24-hour paid-feature grace for temporary license-server outages.
- Updated dashboard, settings, installer and feature gating for the free model.
- Updated LicensePanel compatibility and paid-plan sales flow.

## v18.2
- Cisco / Ocserv repair was rebuilt using the working configuration: socket-file, occtl-socket-file, device, port 8445, self-signed certificate, IPv4 pool, DNS, default route and NAT.
- Hysteria2 no longer writes the old Let's Encrypt YOUR_DOMAIN placeholder.
- Hysteria2 now works without public SSL/domain certificates by generating a local self-signed certificate and issuing client configs with insecure=true.
- Hysteria2 restart-loop recovery was added with service reset and regenerated config.
- Kept v18 UI, PPTP, Hysteria2, modern subscription page and QR output.


## v18.3
- Fixed dashboard system metrics rendering for CPU, RAM, Disk, Swap and license remaining days.
- Added safe template fallbacks and robust metrics API refresh.
- Updated LicensePanel package to match the IronPanel v18 VPN-UI teal design language.

## v18.5.3 - Admin Bot + Cisco Online + IronBot Sales Parity
- Fixed Cisco/Ocserv online user visibility with daemon hooks and stronger occtl parsing.
- Added admin Telegram bot inline buttons for online users, user info, panel report and backup request.
- Added daily admin report/backup timer.
- Expanded sales bot with wallet, wallet payment, special-customer request, QR subscription delivery, rules/guide texts and bulk free config creation.

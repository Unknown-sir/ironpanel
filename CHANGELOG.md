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

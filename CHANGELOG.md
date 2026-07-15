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

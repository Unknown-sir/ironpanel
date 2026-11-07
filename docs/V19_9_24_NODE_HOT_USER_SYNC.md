# v19.9.24 - Node Hot User Sync without Core Restarts

- جدا شدن مسیر sync کاربران از مسیر sync کانفیگ/هسته‌های نود.
- `sync_user` و `sync_users_bulk` دیگر `ensure_protocols` یا `sync_protocol_configs` کامل queue نمی‌کنند.
- Auto sync دوره‌ای heartbeat فقط metadata/auth کاربران را به نود می‌فرستد و باعث restart سرویس‌های OpenVPN/Ocserv/Xray/Hysteria2/Telegram Proxy نمی‌شود.
- Node Agent هنگام `sync_protocol_configs` فقط فایل‌هایی را می‌نویسد که واقعاً تغییر کرده‌اند.
- اگر کانفیگ واقعی یک پروتکل تغییر نکرده باشد، همان پروتکل restart نمی‌شود.
- فایل‌های auth مانند `/etc/ocserv/ocpasswd` و `/etc/ppp/chap-secrets` hot-sync می‌شوند و باعث restart سرویس نمی‌شوند.
- اگر تغییر کانفیگ واقعی نیاز به restart داشته باشد ولی روی پورت همان پروتکل اتصال فعال وجود داشته باشد، restart به‌صورت ایمن skip می‌شود و در `/etc/ironpanel-node/pending_protocol_restarts.json` ثبت می‌شود.

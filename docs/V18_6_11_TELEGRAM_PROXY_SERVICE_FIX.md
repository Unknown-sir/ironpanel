# IronPanel v18.6.11 — Telegram Proxy Service Crash Fix

این نسخه برای خطای زیر منتشر شد:

```text
ironpanel-tgproxy.service: Active: activating (auto-restart) (Result: exit-code)
ExecStart=/usr/bin/node /opt/ironpanel-telegram-proxy/ironpanel/ironpanel_mtproxy.js
status=1/FAILURE
```

## اصلاحات

- `repair_telegram_proxy.sh` قبل از اجرای سرویس، config را validate و در صورت خرابی rebuild می‌کند.
- سرویس‌های قدیمی per-user با الگوی `ironpanel-tgproxy-*.service` کامل stop/disable/delete می‌شوند.
- پردازش‌های orphan مربوط به wrapper قبلی kill می‌شوند تا پورت مشترک آزاد شود.
- مسیر واقعی NodeJS با `command -v node` یا `command -v nodejs` پیدا می‌شود و داخل systemd استفاده می‌شود.
- قبل از start، `node --check` روی wrapper اجرا می‌شود.
- لاگ دائمی در مسیر زیر نوشته می‌شود:

```bash
/var/log/ironpanel-tgproxy.log
```

- صفحه `/telegram-proxy` آخرین لاگ‌های سرویس را نمایش می‌دهد.
- wrapper در خطاهای غیرکشنده socket/client دیگر کل سرویس را crash نمی‌کند.

## دستور رفع روی سرور

```bash
sudo bash /opt/ironpanel/scripts/repair_telegram_proxy.sh --sync
systemctl status ironpanel-tgproxy.service --no-pager
journalctl -u ironpanel-tgproxy.service -n 80 --no-pager
tail -80 /var/log/ironpanel-tgproxy.log
```

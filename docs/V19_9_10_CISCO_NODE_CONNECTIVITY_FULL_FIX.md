# IronPanel 19.9.10 — Cisco and Node Connectivity Full Fix

## مشکلات اصلی رفع‌شده

### Cisco / ocserv روی سرور اصلی

در نسخه قبلی، اجرای Repair یا Upgrade می‌توانست فایل `/etc/ironpanel/ocpasswd` را خالی کند. در نتیجه سرویس `ocserv` فعال دیده می‌شد اما تمام نام‌های کاربری و رمزهای صحیح رد می‌شدند. نسخه 19.9.10 فایل احراز هویت را فقط از کاربران دیتابیس و به‌صورت atomic بازسازی می‌کند و Repair دیگر آن را truncate نمی‌کند.

همچنین شبکه داخلی ocserv در کانفیگ `10.44.0.0/24` بود ولی برخی قوانین NAT از `10.10.10.0/24` استفاده می‌کردند. تمام مسیرهای نصب، Repair، Node و Outbound روی `10.44.0.0/24` یکسان شدند.

Repair جدید این موارد را کنترل می‌کند:

- وجود `ocserv` و `ocpasswd`
- اعتبار کانفیگ با `ocserv -t`
- معتبر و هماهنگ بودن certificate و private key
- باز بودن پورت TCP و UDP در iptables/UFW
- فعال بودن IP forwarding و MASQUERADE
- Active بودن سرویس و Listen واقعی روی پورت تنظیم‌شده
- حفظ پورت سفارشی ذخیره‌شده در دیتابیس هنگام Upgrade
- نمایش وضعیت واقعی `ocserv -t`، listenerهای TCP/UDP، مسیر فایل auth و تعداد کاربران در Health پنل

### اتصال و اجرای نود

- Jobهای Agent فقط توسط خود نود دریافت و اجرا می‌شوند.
- Probe نصب دیگر Job واقعی را Running نمی‌کند.
- نصب نود فقط با وجود binary، اجرای سرویس و Listen واقعی موفق محسوب می‌شود.
- کاربران Cisco، L2TP و PPTP از metadata همگام‌شده روی نود ساخته می‌شوند.
- Sync جزئی L2TP دیگر کاربران PPTP را از `chap-secrets` حذف نمی‌کند و برعکس.
- کل `/etc/ironpanel` دیگر به نود کپی نمی‌شود؛ بنابراین دیتابیس، env، اطلاعات لایسنس، بکاپ‌ها یا auth قدیمی روی نود قرار نمی‌گیرند.
- برای سازگاری با Agentهای نصب‌شده نسخه 19.9.9، فقط فایل hash شده `ocpasswd` به‌صورت صریح همگام می‌شود تا Cisco روی نود فعلی نیز قبل از نصب مجدد Agent قابل بازیابی باشد.
- پورت اختصاصی Xray و SSH در Direct Location واقعاً روی سرویس نود اعمال می‌شود.
- Xray و Hysteria روی `0.0.0.0` گوش می‌دهند و localhost باقی نمی‌مانند.
- بعد از هر تغییر کاربر یا Upgrade، Full Config/User Sync برای نودها در صف قرار می‌گیرد.
- نصب نود دیگر از مخزن GitHub ثابت و احتمالاً قدیمی clone نمی‌شود؛ بسته Agent و اسکریپت‌ها با توکن همان نود مستقیماً از نسخه در حال اجرای پنل دریافت می‌شود.
- دانلود و Heartbeat ابتدا TLS معتبر را امتحان می‌کند و فقط برای گواهی self-signed/untrusted همان پنل، fallback ثبت‌شده فعال می‌شود.
- فرمان نصب هم در محیط root و هم در محیط دارای sudo قابل اجرا است و به وجود sudo روی سرور root وابسته نیست.
- Health نود، Active بودن ساده را کافی نمی‌داند؛ listener، config، interface و runtime واقعی باید سالم باشند.

## آپدیت سریع و بکاپ

بکاپ حجیم هنگام آپدیت در همه مسیرها، از جمله updater مرحله‌ای داخل وب، به‌صورت پیش‌فرض غیرفعال است. برای فعال‌کردن اختیاری:

```bash
sudo IRONPANEL_UPDATE_BACKUP=1 bash /opt/ironpanel/scripts/safe_update.sh
```

Fast Update نصب مجدد سنگین همه هسته‌ها را رد می‌کند، اما Repair حیاتی ocserv، بازسازی auth و صف همگام‌سازی نود را همیشه انجام می‌دهد.

## بررسی پس از نصب

```bash
sudo systemctl status ocserv --no-pager
sudo ocserv -t -c /etc/ocserv/ocserv.conf
sudo ss -lntup | grep -E '8445|ocserv'
sudo grep -c '^[^#[:space:]][^:]*:' /etc/ironpanel/ocpasswd
sudo journalctl -u ironpanel-node -n 100 --no-pager
```

پورت واقعی ممکن است در پنل تغییر کرده باشد؛ به‌جای `8445` پورت Cisco تنظیم‌شده را بررسی کنید. فایروال شبکه دیتاسنتر/Cloud Firewall خارج از سیستم‌عامل است و باید همان TCP/UDP port را اجازه دهد.

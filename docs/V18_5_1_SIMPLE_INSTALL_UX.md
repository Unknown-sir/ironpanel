# IronPanel v18.5.2 - Simple Install & Cleaner UX

این نسخه برای کاهش خطاهای نصب و کم کردن سردرگمی داخل پنل ساخته شده است.

## نصب ساده

```bash
sudo bash install.sh
```

نصب با دامنه و ایمیل:

```bash
sudo bash install.sh --domain panel.example.com --email admin@example.com
```

حالت پیشرفته:

```bash
sudo bash install.sh
```

## تغییرات نصب

- نصب پیش‌فرض بدون سؤال‌های زیاد انجام می‌شود.
- لاگ کامل نصب در `/var/log/ironpanel-install.log` ذخیره می‌شود.
- قبل از جایگزینی فایل‌ها از `/opt/ironpanel` و `/etc/ironpanel` بکاپ گرفته می‌شود.
- اگر نصب بعضی هسته‌های VPN روی OS کامل نشود، پنل از کار نمی‌افتد و Health Check امکان ترمیم می‌دهد.
- Certbot سالم به‌صورت safe نصب یا ترمیم می‌شود.
- حالت رابط کاربری پیش‌فرض روی Simple قرار می‌گیرد.

## ابزار ترمیم

```bash
sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh
sudo bash /opt/ironpanel/scripts/ironpanel_doctor.sh --repair
```

## تغییرات UX

- منوی پیش‌فرض ساده شد و فقط مسیرهای اصلی را نشان می‌دهد.
- ابزارهای کم‌استفاده داخل «ابزارهای پیشرفته» جمع شدند.
- از بالای پنل می‌توان بین حالت Simple و Advanced جابه‌جا شد.
- صفحه ساخت سریع کاربر ساده‌تر و راهنمایی‌دار شد.
- تنظیمات سیستم به دو سطح ساده و پیشرفته تقسیم شد.

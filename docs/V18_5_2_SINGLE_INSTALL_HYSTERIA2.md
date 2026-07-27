# IronPanel v18.5.2 - Single Installer + Hysteria2 Fix

## تغییرات نصب

- فقط یک مسیر نصب وجود دارد: `sudo bash install.sh`.
- نصب همچنان سؤال‌های اصلی را می‌پرسد، اما برای موارد تخصصی مقدار پیش‌فرض امن دارد.
- مسیرهای نصب قدیمی حذف شدند تا کاربر سردرگم نشود.
- نصب مستقیم از GitHub به README اضافه شد.

## اصلاح Hysteria2

- auth command طبق فرمت رسمی Hysteria2 اصلاح شد: `addr auth tx`.
- اسکریپت auth حالا آرگومان دوم را به‌عنوان auth/password می‌خواند و نام کاربر را در stdout برمی‌گرداند.
- اگر Auto SSL هنوز گرفته نشده باشد، Hysteria2 با certificate محلی self-signed بالا می‌آید و کانفیگ کاربر با `insecure=1` ساخته می‌شود.
- اگر Auto SSL گرفته شود، مسیر cert/key روی Hysteria2 هم اعمال می‌شود.
- فایل server config با `sniGuard: disable`، bandwidth پیش‌فرض و BBR نوشته می‌شود.

## نصب مستقیم از GitHub

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

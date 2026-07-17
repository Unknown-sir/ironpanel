# IronPanel v19.3.0

![IronPanel](https://s34.picofile.com/file/8490877984/Ironpanel.png)

IronPanel یک پنل مدیریت چندپروتکل VPN و پروکسی است که برای مدیریت کاربران، نمایندگان، سابسکریپشن، SSL، نود، مانیتورینگ و تنظیمات پیشرفته سرور طراحی شده است.

## نصب سریع

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

## آپدیت از ترمینال

```bash
sudo bash /opt/ironpanel/scripts/update_from_github.sh
```

## امکانات مهم نسخه 19.3.0

- Node Gateway و Load Balancer مخصوص لایسنس Pro
- انتخاب نود به‌صورت ثابت، کمترین کاربر آنلاین، بهترین پینگ یا حالت ترکیبی
- اتصال کاربر به آدرس سرور اصلی و هدایت اتصال از سرور اصلی به نود انتخابی
- قوانین پروتکل به نود: هر پروتکل می‌تواند Local، Fixed Node یا Auto Balance باشد
- اصلاح Update Manager تا بعد از ثبت لاگ تکمیل آپدیت، درصد روی 100٪ قرار بگیرد
- نمایش badge برای کاربرانی که توسط نماینده ساخته شده‌اند

## جدول پروتکل‌ها

| پروتکل | وضعیت | پورت پیش‌فرض | توضیح |
|---|---:|---:|---|
| OpenVPN | ✅ | 1194 | ساخت فایل ovpn و مدیریت مصرف |
| WireGuard | ✅ | 51820 | MTU و DNS قابل تنظیم |
| Cisco / Ocserv | ✅ | 443 | مناسب AnyConnect |
| L2TP/IPsec | ✅ | 1701/500/4500 | کانفیگ کلاسیک موبایل و دسکتاپ |
| Xray | ✅ | 443 | Reality/TLS و لینک‌های Subscription |
| Hysteria2 | ✅ | 443 UDP | کانفیگ جدید و خروجی YAML |
| Telegram MTProto Proxy | ✅ | قابل تنظیم | پورت مشترک و secret اختصاصی |
| SSH | ✅ | 422 | اطلاعات اتصال ساده برای کاربر |
| PPTP | ✅ | 1723 | پشتیبانی legacy |

## جدول امکانات پنل

| امکان | Beginner | Plus | Pro |
|---|:---:|:---:|:---:|
| مدیریت کاربران و کانفیگ‌ها | ✅ | ✅ | ✅ |
| Subscription و QR | ✅ | ✅ | ✅ |
| Auto SSL | ✅ | ✅ | ✅ |
| Routing Rules / Outbound | ✅ | ✅ | ✅ |
| Speed Limits | ✅ | ✅ | ✅ |
| DNS Manager و DNS Presets | ✅ | ✅ | ✅ |
| نمایندگان | ✅ | ✅ | ✅ |
| Node Gateway / Multi Server | ❌ | ❌ | ✅ |
| Node Agent و Load Balancer | ❌ | ❌ | ✅ |

## Node Gateway چگونه کار می‌کند؟

در حالت Node Gateway، کاربر همچنان کانفیگ را با آدرس سرور اصلی دریافت می‌کند. سرور اصلی بر اساس قانونی که مدیر تعیین کرده، اتصال هر پروتکل را به یکی از نودهای آنلاین هدایت می‌کند. انتخاب نود می‌تواند ثابت باشد یا به‌صورت خودکار بر اساس کمترین تعداد کاربر آنلاین، بهترین پینگ یا ترکیب این دو انجام شود.

## نکته‌ها

- README فقط اطلاعات IronPanel را پوشش می‌دهد.
- برای استفاده کامل از Node Gateway، لایسنس Pro لازم است.
- بعد از تغییر قوانین نود، از صفحه Node Gateway گزینه Apply را بزنید.

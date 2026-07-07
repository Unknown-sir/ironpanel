# IronPanel v16.6

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

<p align="center">
  <b>پنل حرفه‌ای مدیریت، مانیتورینگ و فروش سرویس‌های VPN با طراحی امنیتی و پشتیبانی کامل از Xray/V2Ray</b>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-v16.6-blue">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Ubuntu-darkgreen">
  <img alt="Protocols" src="https://img.shields.io/badge/protocols-OpenVPN%20%7C%20WireGuard%20%7C%20Xray%20%7C%20Ocserv%20%7C%20L2TP-orange">
</p>

---

## معرفی

**IronPanel** یک پنل مدیریتی مدرن برای راه‌اندازی، مدیریت، مانیتورینگ و فروش سرویس‌های VPN است. این پروژه برای مدیران سرور، فروشندگان سرویس و تیم‌هایی طراحی شده که می‌خواهند چند پروتکل مختلف را از یک پنل واحد کنترل کنند.

نسخه جدید IronPanel با طراحی کاملاً جدید به سبک **Enterprise Security / SOC Dashboard** ساخته شده و امکانات اصلی پنل، کاربران، سرویس‌ها، مصرف ترافیک، سلامت سیستم، وضعیت پروتکل‌ها و کانفیگ‌های Xray/V2Ray را در یک محیط مدرن و حرفه‌ای نمایش می‌دهد.

---

## امکانات اصلی

### داشبورد امنیتی و مدرن

- طراحی جدید با تم تیره، رنگ‌های امنیتی و کارت‌های آماری
- نمایش وضعیت کلی پنل و ریسک سیستم
- نمایش سلامت سرویس‌ها و منابع سرور
- نمایش کاربران فعال و وضعیت اتصال
- نمودارهای ترافیک و مصرف منابع
- کارت‌های وضعیت پروتکل‌ها
- کارت وضعیت نسخه و بروزرسانی
- طراحی هماهنگ برای جدول‌ها، فرم‌ها، منوها و صفحه‌های داخلی

### مدیریت کاربران

- ساخت، ویرایش و حذف کاربر
- تعیین تاریخ انقضا
- تعیین محدودیت حجم
- پشتیبانی از حجم و زمان نامحدود
- فعال و غیرفعال کردن کاربر
- ریست ترافیک کاربر
- مشاهده مصرف آپلود، دانلود و مجموع مصرف
- مشاهده کاربران آنلاین
- اعمال محدودیت مصرف و انقضا روی پروتکل‌های فعال

### پروتکل‌های پشتیبانی‌شده

IronPanel از چندین پروتکل مختلف پشتیبانی می‌کند:

- OpenVPN
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray / V2Ray

---

## Xray / V2Ray Core

در نسخه‌های جدید، هسته Xray به صورت کامل به IronPanel اضافه شده است. مدیر پنل می‌تواند فقط یک نوع کانفیگ Xray را به عنوان کانفیگ فعال انتخاب کند و کاربران در صفحه Subscription فقط همان نوع کانفیگ را دریافت می‌کنند.

### پروفایل‌های Xray

- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + TCP بدون TLS
- VLESS + WebSocket بدون TLS
- VLESS + gRPC بدون TLS
- Trojan + TLS
- Trojan + TCP بدون TLS
- VMess + WebSocket
- VMess + TCP بدون TLS
- Shadowsocks 2022

### امکانات Xray

- نصب و راه‌اندازی خودکار Xray Core
- تولید UUID اختصاصی برای هر کاربر
- ساخت لینک خام کانفیگ مانند `vless://`، `vmess://`، `trojan://` و `ss://`
- تولید فایل `xray.txt` فقط با لینک خام قابل Import
- تولید QR Code برای کانفیگ
- پشتیبانی از Reality Keypair
- پشتیبانی از SNI، Short ID، Fingerprint، Flow و Dest
- پشتیبانی از WebSocket Path و Host
- پشتیبانی از gRPC Service Name
- پشتیبانی از TLS و حالت‌های بدون TLS
- تست کانفیگ قبل از ری‌استارت سرویس
- Repair اختصاصی برای Xray
- اتصال به Health Check پنل
- نمایش وضعیت سرویس Xray
- هماهنگی Xray با سیستم مصرف، انقضا و Subscription

---

## OpenVPN

- تولید فایل `.ovpn` اختصاصی برای هر کاربر
- نام فایل خروجی مطابق نام کاربر
- اتصال Certificate-only بدون نیاز به وارد کردن Username و Password در کلاینت
- پشتیبانی از TCP و UDP بر اساس تنظیمات مدیر
- هماهنگی با سیستم مصرف ترافیک و انقضا
- ثبت نشست‌های آنلاین
- اسکریپت تعمیر OpenVPN

---

## WireGuard

- تولید کلید اختصاصی برای هر کاربر
- تولید کانفیگ WireGuard
- نمایش کانفیگ در صفحه Subscription
- پشتیبانی از QR Code
- محاسبه مصرف از خروجی WireGuard
- هماهنگی با محدودیت حجم و تاریخ

---

## Cisco AnyConnect / Ocserv

- نصب و مدیریت Ocserv
- ساخت کاربر برای اتصال AnyConnect
- مدیریت وضعیت سرویس
- نمایش وضعیت اتصال کاربران
- هماهنگی با محدودیت زمان و حجم

---

## L2TP/IPsec

- نصب و مدیریت سرویس‌های مورد نیاز
- تولید اطلاعات اتصال برای کاربر
- نمایش اطلاعات اتصال در صفحه Subscription
- بررسی وضعیت سرویس‌ها در Health Check

---

## Subscription کاربران

صفحه Subscription برای هر کاربر خروجی‌های لازم را آماده می‌کند:

- فایل OpenVPN
- فایل WireGuard
- لینک یا فایل Xray/V2Ray
- QR Code
- اطلاعات اتصال AnyConnect
- اطلاعات اتصال L2TP/IPsec
- وضعیت سرویس کاربر
- حجم مصرف‌شده و باقی‌مانده
- تاریخ انقضا و زمان باقی‌مانده

برای Xray، فقط همان نوع کانفیگی که مدیر در پنل انتخاب کرده است به کاربر تحویل داده می‌شود.

---

## ربات فروش تلگرام

IronPanel دارای ربات فروش داخلی برای مدیریت فروش سرویس‌ها است.

### امکانات ربات فروش

- کار با دکمه‌های شیشه‌ای / Inline Keyboard
- خرید سرویس توسط کاربر
- نمایش پلن‌های فعال
- انتخاب مدت سرویس
- انتخاب حجم سرویس
- فروش سرویس‌های کلاسیک
- فروش سرویس Xray/V2Ray
- فروش سرویس ترکیبی همه پروتکل‌ها
- سیستم تست رایگان قابل مدیریت
- تست فقط یک‌بار برای هر Telegram ID
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار کاربر پس از تأیید پرداخت
- ارسال لینک Subscription برای کاربر
- ارسال فایل Xray/V2Ray برای کاربر
- تمدید سرویس
- افزایش حجم
- مشاهده سرویس‌های فعال کاربر
- ارسال اعلان انقضا و مصرف حجم

### امکانات مدیر در ربات

- مشاهده سفارش‌های در انتظار تأیید
- تأیید یا رد پرداخت
- مدیریت پلن‌ها
- فعال یا غیرفعال کردن پلن
- مشاهده آمار فروش
- ارسال پیام همگانی
- مشاهده کاربران نزدیک به انقضا
- مشاهده کاربران نزدیک به اتمام حجم

---

## مدیریت پلن فروش

مدیر می‌تواند داخل پنل پلن‌های فروش تعریف کند:

- نام پلن
- مدت پلن
- حجم پلن
- قیمت
- واحد پول
- پروتکل‌های مجاز
- امکان فروش فقط Xray/V2Ray
- امکان فروش همه پروتکل‌ها
- امکان فروش پروتکل‌های کلاسیک بدون Xray
- فعال یا غیرفعال بودن پلن
- توضیحات پلن

---

## Health Check / Repair

IronPanel دارای بخش بررسی سلامت و تعمیر سرویس‌ها است.

### سرویس‌های قابل بررسی

- IronPanel
- OpenVPN
- WireGuard
- Ocserv
- L2TP/IPsec
- Xray
- ربات فروش
- سرویس‌های دیتابیس و شبکه

### امکانات Health Check

- نمایش وضعیت سرویس‌ها
- نمایش خطای سرویس
- نمایش خروجی `systemctl status`
- نمایش خروجی `journalctl`
- اجرای تعمیر خودکار برای مشکلات رایج
- ری‌استارت سرویس‌ها از پنل

---

## بروزرسانی از داخل پنل

IronPanel دارای بخش Update Manager است.

- بررسی نسخه فعلی
- بررسی نسخه موجود روی GitHub
- نمایش پیشنهاد بروزرسانی
- بروزرسانی با یک دکمه از داخل پنل
- امکان اجرای بروزرسانی از طریق ترمینال

---

## پیش‌نیازها

برای نصب IronPanel بهتر است از یک سرور تمیز استفاده شود.

### سیستم‌عامل پیشنهادی

- Ubuntu 20.04
- Ubuntu 22.04
- Ubuntu 24.04
- Debian 11 / 12

### منابع پیشنهادی

- CPU: حداقل 1 Core
- RAM: حداقل 1GB، پیشنهادی 2GB یا بیشتر
- Disk: حداقل 10GB
- دسترسی Root
- IP عمومی ثابت
- دامنه اختیاری برای TLS / Reality / Subscription

---

## نصب از GitHub

برای نصب، ابتدا پروژه را از GitHub روی سرور دانلود کن، سپس وارد پوشه پروژه شو و فایل نصب را اجرا کن.

### 1. نصب ابزارهای اولیه

```bash
sudo apt update
sudo apt install -y git curl wget unzip ca-certificates
```

### 2. دانلود پروژه از GitHub

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
```

### 3. ورود به پوشه پروژه

```bash
cd ironpanel
```

### 4. دادن دسترسی اجرا به فایل نصب

```bash
chmod +x install.sh
```

### 5. اجرای نصب

```bash
sudo bash install.sh
```

در زمان نصب، اسکریپت موارد لازم را نصب و تنظیم می‌کند. بسته به نسخه و تنظیمات، ممکن است اطلاعاتی مثل نام کاربری مدیر، رمز عبور، پورت پنل، دامنه یا IP و تنظیمات اولیه از شما پرسیده شود.

---

## ورود به پنل

بعد از نصب، آدرس پنل معمولاً به شکل زیر خواهد بود:

```text
http://SERVER_IP:PANEL_PORT
```

نمونه:

```text
http://192.0.2.10:8000
```

اگر برای پنل دامنه تنظیم کرده باشی، می‌توانی از دامنه استفاده کنی.

---

## دستورات مدیریتی سرویس‌ها

### وضعیت IronPanel

```bash
sudo systemctl status ironpanel --no-pager
```

### ری‌استارت IronPanel

```bash
sudo systemctl restart ironpanel
```

### وضعیت ربات فروش

```bash
sudo systemctl status ironpanel-sales-bot --no-pager
```

### ری‌استارت ربات فروش

```bash
sudo systemctl restart ironpanel-sales-bot
```

### وضعیت Xray

```bash
sudo systemctl status xray --no-pager
```

### ری‌استارت Xray

```bash
sudo systemctl restart xray
```

### مشاهده لاگ IronPanel

```bash
sudo journalctl -u ironpanel -n 100 --no-pager
```

### مشاهده لاگ Xray

```bash
sudo journalctl -u xray -n 100 --no-pager
```

---

## تعمیر سرویس‌ها از ترمینال

### تعمیر OpenVPN

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
```

### تعمیر Xray

```bash
sudo bash /opt/ironpanel/scripts/repair_xray.sh
```

### تعمیر کلی پنل

```bash
sudo bash /opt/ironpanel/scripts/repair.sh
```

---

## بروزرسانی از GitHub

برای بروزرسانی نسخه نصب‌شده از GitHub:

```bash
cd ironpanel
git pull
sudo bash upgrade.sh
```

بعد از بروزرسانی، سرویس‌های اصلی را ری‌استارت کن:

```bash
sudo systemctl restart ironpanel
sudo systemctl restart ironpanel-sales-bot
sudo systemctl restart xray
```

---

## مسیرهای مهم

```text
/opt/ironpanel
/etc/ironpanel/ironpanel.env
/usr/local/etc/xray/config.json
/var/log/xray/access.log
/var/log/xray/error.log
/var/log/openvpn/ironpanel-auth.log
```

---

## نکات مهم برای Xray

- بعد از تغییر نوع کانفیگ Xray، تنظیمات را ذخیره و سرویس Xray را ری‌استارت کن.
- برای Reality، ابتدا کلیدها را از داخل پنل بساز.
- فایل `xray.txt` باید فقط شامل لینک خام کانفیگ باشد.
- برای تست کانفیگ، از کلاینت‌هایی مثل v2rayNG، Hiddify، Nekoray، Sing-box یا Clash Meta استفاده کن.
- اگر کانفیگ کار نکرد، ابتدا از داخل پنل Health Check را اجرا کن و سپس لاگ Xray را بررسی کن.

---

## نکات امنیتی

- پس از نصب، رمز مدیر را تغییر بده.
- فقط پورت‌های مورد نیاز را باز بگذار.
- برای پنل از رمز قوی استفاده کن.
- در صورت استفاده از دامنه، TLS را فعال کن.
- دسترسی SSH را محدود کن.
- از فایل تنظیمات پنل بکاپ بگیر.
- Bot Token تلگرام را عمومی منتشر نکن.

---

## ساختار پیشنهادی استفاده

1. نصب IronPanel روی سرور
2. ورود به پنل
3. تنظیم دامنه یا IP
4. فعال‌سازی پروتکل‌های مورد نیاز
5. انتخاب نوع کانفیگ Xray در بخش Xray Core
6. ساخت پلن‌های فروش
7. تنظیم ربات فروش تلگرام
8. ساخت کاربر تست
9. بررسی Subscription
10. تست اتصال با کلاینت‌ها

---

## کلاینت‌های پیشنهادی

### OpenVPN

- OpenVPN Connect
- OpenVPN GUI
- Tunnelblick

### WireGuard

- WireGuard Official Client

### Xray / V2Ray

- v2rayNG
- Hiddify
- Nekoray
- Sing-box
- Clash Meta
- Streisand

### AnyConnect

- Cisco AnyConnect
- OpenConnect

---

## جمع‌بندی

IronPanel v16.6 یک پنل کامل برای مدیریت سرویس‌های VPN، کاربران، فروش، مانیتورینگ، Subscription و کانفیگ‌های مدرن Xray/V2Ray است. طراحی جدید امنیتی، ابزارهای تعمیر، ربات فروش، مدیریت چند پروتکل و خروجی‌های آماده برای کاربران باعث می‌شود این پنل برای راه‌اندازی و مدیریت سرویس حرفه‌ای مناسب باشد.

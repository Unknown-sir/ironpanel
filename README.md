# IronPanel v16.7

<p align="center">
  <img src="https://s34.picofile.com/file/8490837600/Screenshot_6.png" alt="IronPanel Dashboard" width="450">
  <img src="https://s34.picofile.com/file/8490837592/Screenshot_7.png" alt="IronPanel Dashboard" width="450">
</p>

<p align="center">
  <b>Professional VPN Management, Monitoring, Sales Automation and Outbound Routing Panel</b>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-v16.7-blue">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian-darkgreen">
  <img alt="Protocols" src="https://img.shields.io/badge/protocols-OpenVPN%20%7C%20WireGuard%20%7C%20Xray%20%7C%20Ocserv%20%7C%20L2TP-orange">
  <img alt="UI" src="https://img.shields.io/badge/UI-SOC%20Dashboard-red">
</p>

---

## معرفی پروژه

**IronPanel** یک پنل حرفه‌ای برای مدیریت، مانیتورینگ، فروش و کنترل سرویس‌های VPN است. این پروژه برای مدیران سرور، فروشندگان سرویس، تیم‌های زیرساخت و افرادی طراحی شده که می‌خواهند چند پروتکل مختلف را از یک پنل واحد مدیریت کنند.

نسخه **v16.7** علاوه بر طراحی جدید امنیتی/SOC، از چندین پروتکل VPN، ربات فروش تلگرام، Subscription، Xray/V2Ray، Health Check، نودها، مدیریت مصرف، سیستم آپدیت و بخش جدید **Outbound Routing** پشتیبانی می‌کند.

---

## ویژگی‌های کلیدی

- داشبورد مدرن با طراحی امنیتی و تم تیره
- مدیریت کامل کاربران، حجم، تاریخ انقضا و وضعیت اتصال
- پشتیبانی از چند پروتکل در یک پنل واحد
- ساخت خروجی Subscription برای کاربران
- پشتیبانی کامل از Xray / V2Ray
- تحویل فقط یک نوع کانفیگ Xray انتخاب‌شده توسط مدیر
- پشتیبانی از کانفیگ‌های TLS، Reality و بدون TLS
- ربات فروش تلگرام با دکمه‌های شیشه‌ای
- فروش سرویس‌های کلاسیک، Xray/V2Ray یا ترکیبی
- پرداخت دستی و تأیید سفارش توسط مدیر
- Health Check و Repair برای سرویس‌ها
- Update Manager برای بروزرسانی پنل
- Node Management برای مدیریت سرورهای جانبی
- Outbound Routing برای عبور دادن ترافیک پروتکل‌های انتخابی از یک کانفیگ خروجی
- API و ساختار مناسب برای توسعه و اتصال سرویس‌های خارجی

---

## طراحی و داشبورد

در نسخه‌های جدید، ظاهر IronPanel به سبک **Enterprise Security / SOC Dashboard** بازطراحی شده است.

### امکانات داشبورد

- نمایش وضعیت کلی پنل
- نمایش سطح سلامت و ریسک سیستم
- کارت وضعیت سرویس‌ها
- کارت وضعیت نسخه و بروزرسانی
- نمایش مصرف CPU، RAM، Disk و Swap
- نمایش کاربران آنلاین
- نمایش وضعیت پروتکل‌ها
- نمودارهای ترافیک و مصرف
- طراحی جدید جدول‌ها، فرم‌ها، دکمه‌ها و منوی کناری

---

## پروتکل‌های پشتیبانی‌شده

IronPanel از پروتکل‌های زیر پشتیبانی می‌کند:

- **OpenVPN**
- **WireGuard**
- **Cisco AnyConnect / Ocserv**
- **L2TP/IPsec**
- **Xray / V2Ray**

هر کاربر می‌تواند بر اساس تنظیمات مدیر، یک یا چند پروتکل فعال داشته باشد و از صفحه Subscription خروجی‌های لازم را دریافت کند.

---

## Xray / V2Ray Core

بخش Xray به صورت کامل داخل IronPanel اضافه شده و مدیر پنل می‌تواند فقط یک نوع کانفیگ Xray را به عنوان کانفیگ فعال انتخاب کند. کاربران در صفحه Subscription فقط همان یک نوع کانفیگ را دریافت می‌کنند، نه همه مدل‌ها.

### پروفایل‌های پشتیبانی‌شده Xray

- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + TCP بدون TLS
- VLESS + WebSocket بدون TLS
- VLESS + gRPC بدون TLS
- VMess + WebSocket
- VMess + TCP بدون TLS
- Trojan + TLS
- Trojan + TCP بدون TLS
- Shadowsocks 2022

### امکانات Xray

- نصب و مدیریت Xray Core
- تولید UUID اختصاصی برای هر کاربر
- تولید لینک‌های `vless://`، `vmess://`، `trojan://` و `ss://`
- تولید فایل `xray.txt` با لینک خام قابل Import
- تولید QR Code
- پشتیبانی از Reality Keypair
- پشتیبانی از SNI، Short ID، Fingerprint، Flow و Dest
- پشتیبانی از TLS و حالت‌های بدون TLS
- پشتیبانی از WebSocket Path و Host
- پشتیبانی از gRPC Service Name
- تست کانفیگ Xray قبل از اعمال نهایی
- هماهنگی با مصرف ترافیک، انقضا و وضعیت کاربر
- اتصال به Health Check / Repair

---

## Outbound Routing

در نسخه **v16.7** بخش جدید **Outbound Routing** اضافه شده است. این بخش به مدیر اجازه می‌دهد یک کانفیگ خروجی وارد کند و ترافیک پروتکل‌های انتخاب‌شده را از آن مسیر عبور دهد.

### کاربرد Outbound

اگر مدیر یک کانفیگ OpenVPN Client یا Xray/V2Ray وارد کند و تست اتصال موفق باشد، می‌تواند انتخاب کند که ترافیک کدام پروتکل‌های پنل از آن کانفیگ عبور کند.

### نوع کانفیگ‌های Outbound

- OpenVPN Client Config
- VLESS
- VMess
- Trojan
- Shadowsocks

### پروتکل‌های قابل انتخاب برای عبور از Outbound

- OpenVPN
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray / V2Ray

### روند کار Outbound

1. فعال‌سازی بخش Outbound توسط مدیر
2. وارد کردن کانفیگ OpenVPN یا Xray/V2Ray
3. تست اتصال کانفیگ توسط پنل
4. انتخاب پروتکل‌هایی که باید از Outbound عبور کنند
5. اعمال تنظیمات و ری‌استارت سرویس‌های لازم

---

## OpenVPN

- ساخت فایل `.ovpn` اختصاصی برای هر کاربر
- نام فایل خروجی مطابق نام کاربر
- اتصال Certificate-only بدون نیاز به وارد کردن Username و Password در کلاینت
- انتخاب TCP یا UDP توسط مدیر
- هماهنگی با محدودیت حجم و تاریخ انقضا
- ثبت نشست‌های آنلاین
- ابزار Repair اختصاصی برای OpenVPN

---

## WireGuard

- ساخت کلید اختصاصی برای هر کاربر
- تولید کانفیگ WireGuard
- نمایش QR Code
- محاسبه مصرف کاربران
- هماهنگی با محدودیت حجم و تاریخ انقضا
- نمایش وضعیت اتصال کاربران

---

## Cisco AnyConnect / Ocserv

- نصب و مدیریت Ocserv
- ساخت دسترسی برای کاربران
- نمایش اطلاعات اتصال در صفحه Subscription
- بررسی وضعیت سرویس از پنل
- هماهنگی با محدودیت حجم و تاریخ

---

## L2TP/IPsec

- نصب و مدیریت سرویس‌های مورد نیاز
- تولید اطلاعات اتصال برای کاربران
- نمایش اطلاعات اتصال در صفحه Subscription
- بررسی سلامت سرویس‌ها
- هماهنگی با محدودیت زمان و مصرف

---

## Subscription کاربران

صفحه Subscription خروجی‌های مورد نیاز کاربر را یکجا آماده می‌کند.

### خروجی‌های قابل ارائه

- فایل OpenVPN
- فایل WireGuard
- QR Code
- لینک یا فایل Xray/V2Ray
- اطلاعات اتصال AnyConnect
- اطلاعات اتصال L2TP/IPsec
- وضعیت سرویس کاربر
- حجم مصرف‌شده و باقی‌مانده
- تاریخ انقضا و زمان باقی‌مانده

برای Xray/V2Ray فقط همان نوع کانفیگی نمایش داده می‌شود که مدیر در بخش Xray Core انتخاب کرده است.

---

## ربات فروش تلگرام

IronPanel دارای ربات فروش داخلی است که با دکمه‌های شیشه‌ای کار می‌کند و کاربر فقط در بخش‌هایی که لازم است متن یا رسید ارسال می‌کند.

### امکانات ربات فروش

- نمایش پلن‌های فعال
- خرید سرویس توسط کاربر
- انتخاب مدت و حجم سرویس
- فروش سرویس کلاسیک
- فروش سرویس Xray/V2Ray
- فروش سرویس ترکیبی همه پروتکل‌ها
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار کاربر بعد از تأیید پرداخت
- ارسال لینک Subscription
- ارسال فایل Xray/V2Ray
- تمدید سرویس
- افزایش حجم
- مشاهده سرویس‌های فعال کاربر
- اعلان نزدیک شدن به اتمام حجم یا زمان

### امکانات مدیر داخل ربات

- مشاهده سفارش‌های در انتظار تأیید
- مشاهده رسید پرداخت
- تأیید یا رد سفارش
- مدیریت پلن‌ها
- فعال یا غیرفعال کردن پلن
- مشاهده آمار فروش
- ارسال پیام همگانی
- مشاهده کاربران نزدیک به انقضا

---

## مدیریت پلن فروش

مدیر می‌تواند از داخل پنل پلن‌های فروش تعریف کند.

### گزینه‌های پلن

- نام پلن
- مدت زمان
- حجم سرویس
- قیمت
- واحد پول
- پروتکل‌های مجاز
- فروش فقط Xray/V2Ray
- فروش پروتکل‌های کلاسیک
- فروش همه پروتکل‌ها
- فعال یا غیرفعال بودن پلن
- توضیحات پلن

---

## مدیریت کاربران

### امکانات بخش کاربران

- ایجاد کاربر جدید
- ویرایش کاربر
- حذف کاربر
- فعال یا غیرفعال کردن کاربر
- تعیین تاریخ انقضا
- تعیین محدودیت حجم
- پشتیبانی از حجم و تاریخ نامحدود
- ریست ترافیک
- مشاهده مصرف Upload و Download
- مشاهده وضعیت آنلاین
- دریافت کانفیگ‌ها و Subscription

---

## Node Management

IronPanel امکان مدیریت نودها را فراهم می‌کند تا چند سرور در کنار پنل اصلی کنترل شوند.

### امکانات نودها

- افزودن نود جدید
- اتصال نود به پنل اصلی با Token
- انتخاب پروتکل‌های فعال روی هر نود
- بررسی وضعیت آنلاین یا آفلاین بودن نود
- مدیریت سرویس‌ها روی نود
- هماهنگی با Subscription و سیستم کاربران

---

## Health Check / Repair

بخش Health Check برای بررسی و تعمیر سرویس‌های پنل طراحی شده است.

### سرویس‌های قابل بررسی

- IronPanel
- OpenVPN
- WireGuard
- Ocserv
- L2TP/IPsec
- Xray
- ربات فروش
- Outbound Routing
- سرویس‌های دیتابیس و شبکه

### امکانات Health Check

- نمایش وضعیت سرویس‌ها
- نمایش خطای سرویس
- نمایش خروجی `systemctl status`
- نمایش خروجی `journalctl`
- اجرای تعمیر خودکار برای مشکلات رایج
- ری‌استارت سرویس‌ها از داخل پنل

---

## Update Manager

IronPanel دارای بخش مدیریت بروزرسانی است.

### امکانات Update Manager

- نمایش نسخه فعلی
- بررسی نسخه جدید از مخزن پروژه
- نمایش وضعیت بروزرسانی
- اجرای بروزرسانی از داخل پنل
- نمایش خروجی و خطاهای احتمالی
- ری‌استارت سرویس‌های لازم بعد از بروزرسانی

---

## API

IronPanel ساختار API برای اتصال سرویس‌های خارجی، ربات‌ها، سیستم‌های فروش و ابزارهای مانیتورینگ دارد.

### قابلیت‌های API

- مدیریت کاربران
- دریافت وضعیت کاربران
- ایجاد، تمدید و غیرفعال‌سازی کاربر
- دریافت وضعیت سرویس‌ها
- دریافت اطلاعات مانیتورینگ
- مدیریت سفارش‌ها
- دریافت وضعیت نودها
- بررسی Health Check

---

## پیش‌نیازها

برای نصب IronPanel بهتر است از یک سرور تمیز استفاده شود.

### سیستم‌عامل پیشنهادی

- Ubuntu 20.04
- Ubuntu 22.04
- Ubuntu 24.04
- Debian 11
- Debian 12

### منابع پیشنهادی

- CPU: حداقل 1 Core
- RAM: حداقل 1GB، پیشنهادی 2GB یا بیشتر
- Disk: حداقل 10GB
- دسترسی Root
- IP عمومی ثابت
- دامنه اختیاری برای TLS، Reality و Subscription

---

## نصب استاندارد از GitHub

برای نصب، ابتدا پروژه را روی سرور دریافت کنید، سپس وارد پوشه پروژه شوید و فایل نصب را اجرا کنید.

### 1. نصب ابزارهای اولیه

```bash
sudo apt update
sudo apt install -y git curl wget unzip ca-certificates
```

### 2. دریافت پروژه

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
```

### 3. ورود به پوشه پروژه

```bash
cd ironpanel
```

### 4. اجرای فایل نصب

```bash
sudo bash install.sh
```

در زمان نصب، بسته به تنظیمات پروژه، اطلاعات اولیه مثل نام کاربری مدیر، رمز عبور، پورت پنل، دامنه یا IP از شما پرسیده می‌شود.

---

## ورود به پنل

بعد از نصب، پنل معمولاً از آدرس زیر در دسترس است:

```text
http://SERVER_IP:PANEL_PORT
```

نمونه:

```text
http://192.0.2.10:8000
```

اگر دامنه برای پنل تنظیم کرده باشید، می‌توانید از دامنه استفاده کنید.

---

## دستورات مدیریتی

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

### وضعیت Outbound OpenVPN

```bash
sudo systemctl status ironpanel-outbound-openvpn --no-pager
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

### غیرفعال‌سازی Outbound

```bash
sudo bash /opt/ironpanel/scripts/apply_outbound.sh disable
```

### تعمیر کلی پنل

```bash
sudo bash /opt/ironpanel/scripts/repair.sh
```

---

## بروزرسانی پروژه

برای بروزرسانی نسخه نصب‌شده:

```bash
cd /opt/ironpanel
sudo git pull origin main
sudo bash upgrade.sh
sudo systemctl restart ironpanel
sudo systemctl restart ironpanel-sales-bot
sudo systemctl restart xray
```

بعد از بروزرسانی، بهتر است کش مرورگر را پاک کنید یا صفحه پنل را با `Ctrl + F5` دوباره بارگذاری کنید.

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

- پس از تغییر نوع کانفیگ Xray، تنظیمات را ذخیره و سرویس Xray را ری‌استارت کنید.
- برای Reality ابتدا کلیدها را از داخل پنل تولید کنید.
- فایل `xray.txt` باید فقط شامل لینک خام کانفیگ باشد.
- برای تست کانفیگ، از کلاینت‌های سازگار با Xray/V2Ray استفاده کنید.
- اگر کانفیگ کار نکرد، ابتدا Health Check را اجرا کنید و سپس لاگ Xray را بررسی کنید.

---

## نکات مهم برای Outbound

- قبل از فعال‌سازی Outbound، کانفیگ خروجی باید تست موفق داشته باشد.
- اگر کانفیگ واردشده OpenVPN باشد، سرویس `ironpanel-outbound-openvpn` استفاده می‌شود.
- اگر کانفیگ واردشده Xray/V2Ray باشد، تنظیمات مربوط به Routing در هسته Xray اعمال می‌شود.
- فقط پروتکل‌هایی که مدیر انتخاب می‌کند از Outbound عبور داده می‌شوند.
- قبل از اعمال Outbound روی سرور عملیاتی، بهتر است ابتدا روی یک کاربر تست بررسی شود.

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

## نکات امنیتی

- پس از نصب، رمز عبور مدیر را تغییر دهید.
- فقط پورت‌های مورد نیاز را باز بگذارید.
- برای پنل از رمز قوی استفاده کنید.
- در صورت استفاده از دامنه، TLS را فعال کنید.
- دسترسی SSH را محدود کنید.
- از فایل تنظیمات و دیتابیس پنل بکاپ بگیرید.
- Bot Token تلگرام را عمومی منتشر نکنید.
- قبل از فعال‌سازی Outbound روی چند پروتکل، عملکرد مسیر خروجی را تست کنید.

---

## پیشنهاد استفاده

1. نصب IronPanel روی سرور
2. ورود به پنل مدیریت
3. تنظیم دامنه یا IP
4. فعال‌سازی پروتکل‌های مورد نیاز
5. انتخاب نوع کانفیگ Xray در بخش Xray Core
6. ساخت کاربر تست
7. بررسی Subscription
8. تست اتصال همه پروتکل‌ها
9. تعریف پلن‌های فروش
10. تنظیم ربات فروش
11. در صورت نیاز، فعال‌سازی Outbound Routing
12. بررسی Health Check بعد از هر تغییر مهم

---

## نسخه فعلی

```text
IronPanel v16.7
```

### تمرکز نسخه v16.7

- اضافه شدن Outbound Routing
- پشتیبانی از کانفیگ OpenVPN Client برای Outbound
- پشتیبانی از کانفیگ Xray/V2Ray برای Outbound
- انتخاب پروتکل‌های عبوری از Outbound توسط مدیر
- هماهنگی Outbound با طراحی جدید پنل
- حفظ کامل امکانات Xray/V2Ray، ربات فروش، Subscription و داشبورد امنیتی

---

## جمع‌بندی

IronPanel v16.7 یک پنل کامل برای مدیریت سرویس‌های VPN، کاربران، فروش، مانیتورینگ، Xray/V2Ray، Subscription، نودها و Outbound Routing است. طراحی جدید امنیتی، ابزارهای تعمیر، ربات فروش و پشتیبانی از چند پروتکل باعث می‌شود این پروژه برای مدیریت حرفه‌ای سرویس‌های VPN مناسب باشد.

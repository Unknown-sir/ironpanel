<div align="center">

# IronPanel

### Modern Multi‑Protocol VPN Management Panel  
### پنل مدرن مدیریت چند پروتکل VPN

![Version](https://img.shields.io/badge/version-7.1-blue)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04-orange)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/License-Commercial-red)

OpenVPN • WireGuard • Cisco AnyConnect / Ocserv • L2TP/IPsec

</div>

---

## 🇮🇷 فارسی

### معرفی

IronPanel یک پنل مدیریت VPN چندپروتکل است که برای ارائه‌دهندگان VPN و مدیران سرور طراحی شده است. این پنل امکان مدیریت کاربران، ساخت کانفیگ، محدودیت حجم، تاریخ انقضا، مانیتورینگ لحظه‌ای سرور و بررسی آنلاین لایسنس را از طریق یک رابط کاربری مدرن فراهم می‌کند.

ریپوی رسمی پیشنهادی:

```text
https://github.com/Unknown-sir/ironpanel
```

---

### امکانات اصلی

- داشبورد مدرن و واکنش‌گرا
- مانیتورینگ لحظه‌ای CPU، RAM، Swap و Disk
- نمایش تعداد روز باقی‌مانده لایسنس در داشبورد
- مدیریت کاربران
- حذف کاربر
- فعال/غیرفعال‌سازی کاربر
- محدودیت حجم مصرفی
- تاریخ انقضا برای کاربر
- صفحه سابسکریپشن اختصاصی کاربر
- تولید خودکار کانفیگ‌ها
- پشتیبانی از آدرس تانل یا دامنه جایگزین برای کانفیگ‌ها
- OpenVPN با گواهی اختصاصی کاربر و بدون نیاز به وارد کردن یوزرنیم/پسورد در کلاینت
- فایل OpenVPN با نام همان کاربر، مثل `username.ovpn`
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- انتخاب TCP/UDP برای پروتکل‌های قابل تنظیم از داخل پنل
- API اختصاصی با API Key
- سیستم تیکت
- مدیریت نمایندگان / Reseller
- لاگ کاربران و مدیران
- نصب خودکار هسته تمام پروتکل‌ها
- ترمیم خودکار سرویس‌ها هنگام آپدیت
- سیستم بررسی لایسنس آنلاین
- قفل کامل پنل در صورت نبود یا انقضای لایسنس

---

### پروتکل‌های پشتیبانی‌شده

| پروتکل | وضعیت |
|---|---|
| OpenVPN | ✅ |
| WireGuard | ✅ |
| Cisco AnyConnect / Ocserv | ✅ |
| L2TP/IPsec | ✅ |

---

### نصب

روی Ubuntu 22.04 اجرا کنید:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

یا بعد از دانلود پروژه:

```bash
sudo bash install.sh
```

---

### بروزرسانی

```bash
sudo bash upgrade.sh
```

---

### سیستم موردنیاز

حداقل:

- Ubuntu 22.04 LTS
- 1 CPU
- 1GB RAM
- 20GB Disk

پیشنهادی:

- Ubuntu 22.04 LTS
- 2 CPU
- 2GB RAM
- 40GB Disk

---

### سیستم لایسنس

IronPanel برای اجرا به لایسنس معتبر نیاز دارد. پنل به‌صورت آنلاین لایسنس را از سرور لایسنس بررسی می‌کند.

سرور لایسنس پیش‌فرض:

```text
http://license.skyshield.space:8002
```

در صورت نبود لایسنس، نامعتبر بودن لایسنس یا پایان تاریخ انقضا:

- صفحه ورود پنل نمایش داده نمی‌شود.
- کاربران امکان استفاده از سرویس‌ها را نخواهند داشت.
- صفحه فعال‌سازی لایسنس نمایش داده می‌شود.
- امکان ثبت لایسنس جدید وجود دارد.
- لینک پشتیبانی نمایش داده می‌شود.

---

### دریافت یا تمدید لایسنس

برای خرید، دریافت یا تمدید لایسنس IronPanel به پشتیبانی تلگرام پیام دهید:

```text
https://t.me/unknown_eng
```

---

### مانیتورینگ داشبورد

در داشبورد موارد زیر به‌صورت لحظه‌ای نمایش داده می‌شوند:

- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- Remaining License Days

---

### نکات مهم

- نصب باید با دسترسی `root` یا `sudo` انجام شود.
- پورت‌های موردنیاز پروتکل‌ها باید در فایروال سرور و فایروال دیتاسنتر باز باشند.
- اگر از تانل، CDN، Reverse Proxy یا IP دیگر استفاده می‌کنید، آدرس تانل را از بخش تنظیمات پنل ثبت کنید تا داخل کانفیگ‌ها جایگذاری شود.

---

## 🇺🇸 English

### Overview

IronPanel is a modern multi‑protocol VPN management panel designed for VPN providers and server administrators. It provides user management, automatic configuration generation, traffic limits, expiration control, live server monitoring, and online license verification through a modern web interface.

Official repository target:

```text
https://github.com/Unknown-sir/ironpanel
```

---

### Main Features

- Modern responsive dashboard
- Live CPU, RAM, Swap, and Disk monitoring
- Remaining license days widget
- User management
- User deletion
- User enable/disable control
- Traffic limitation
- User expiration date
- Dedicated user subscription page
- Automatic configuration generation
- Tunnel host / alternative domain support for generated configs
- OpenVPN certificate authentication without client username/password prompt
- OpenVPN file name based on the username, for example `username.ovpn`
- WireGuard support
- Cisco AnyConnect / Ocserv support
- L2TP/IPsec support
- TCP/UDP selection for configurable protocols
- REST API with API key
- Ticket system
- Reseller management
- User and admin logs
- Automatic VPN core installation
- Automatic service repair during upgrades
- Online license verification
- Full panel lock when the license is missing or expired

---

### Supported Protocols

| Protocol | Status |
|---|---|
| OpenVPN | ✅ |
| WireGuard | ✅ |
| Cisco AnyConnect / Ocserv | ✅ |
| L2TP/IPsec | ✅ |

---

### Installation

Run on Ubuntu 22.04:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

Or after downloading the project:

```bash
sudo bash install.sh
```

---

### Update

```bash
sudo bash upgrade.sh
```

---

### Requirements

Minimum:

- Ubuntu 22.04 LTS
- 1 CPU
- 1GB RAM
- 20GB Disk

Recommended:

- Ubuntu 22.04 LTS
- 2 CPU
- 2GB RAM
- 40GB Disk

---

### License System

IronPanel requires a valid online license. The panel checks the license using the default license server.

Default license server:

```text
http://license.skyshield.space:8002
```

When the license is missing, invalid, or expired:

- The login page will not be displayed.
- Users will not be able to use VPN services.
- The license activation page will be displayed.
- A new license can be submitted.
- The support link will be shown.

---

### Purchase or Renew License

To purchase, receive, or renew your IronPanel license, please contact Telegram support:

```text
https://t.me/unknown_eng
```

---

### Dashboard Monitoring

The dashboard displays the following live metrics:

- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- Remaining License Days

---

### Important Notes

- Installation must be executed with `root` or `sudo` privileges.
- Required protocol ports must be opened in both server firewall and provider/datacenter firewall.
- If you use a tunnel, CDN, reverse proxy, or another public IP/domain, set the tunnel host in panel settings so generated configs use the correct address.

---

## Support / پشتیبانی

Telegram:

```text
https://t.me/unknown_eng
```

---

## Author

Unknown  
GitHub: `https://github.com/Unknown-sir`  
Telegram: `https://t.me/unknown_eng`

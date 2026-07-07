<div align="center">

# ⚡ IronPanel

### Modern Multi‑Protocol VPN Management Panel  
### پنل حرفه‌ای مدیریت چندپروتکلی VPN

<br>

![Version](https://img.shields.io/badge/version-v15.3-blue?style=for-the-badge)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20LTS-orange?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-green?style=for-the-badge)
![Flask](https://img.shields.io/badge/Backend-Flask-black?style=for-the-badge)
![License](https://img.shields.io/badge/License-Commercial-red?style=for-the-badge)

<br>

**OpenVPN • WireGuard • Cisco AnyConnect / Ocserv • L2TP/IPsec**

<br>

[🇮🇷 فارسی](#-فارسی) • [🇺🇸 English](#-english) • [API Docs](docs/API_GUIDE.md) • [Support](https://t.me/unknown_eng)

</div>

---

# 🇮🇷 فارسی

## معرفی
<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

**IronPanel** یک پنل حرفه‌ای، مدرن و چندپروتکلی برای مدیریت سرویس‌های VPN است. این پروژه برای مدیران سرور، فروشندگان سرویس VPN، نمایندگان فروش، تیم‌های زیرساخت و مجموعه‌هایی طراحی شده که به یک پنل کامل برای مدیریت کاربران، پروتکل‌ها، حجم، تاریخ انقضا، فروش، مانیتورینگ، لایسنس، API، بکاپ و بروزرسانی نیاز دارند.

IronPanel تلاش می‌کند تمام بخش‌های مهم مدیریت سرویس VPN را در یک رابط کاربری یکپارچه، قابل توسعه و مناسب استفاده تجاری ارائه کند.

---

## فهرست

- [امکانات اصلی](#امکانات-اصلی)
- [پروتکل‌های پشتیبانی‌شده](#پروتکلهای-پشتیبانیشده)
- [نوع‌های لایسنس و محدودیت امکانات](#نوعهای-لایسنس-و-محدودیت-امکانات)
- [داشبورد و مانیتورینگ](#داشبورد-و-مانیتورینگ)
- [ربات فروش IronPanel](#ربات-فروش-ironpanel)
- [سیستم لایسنس](#سیستم-لایسنس)
- [نصب](#نصب)
- [بروزرسانی](#بروزرسانی)
- [Health Check / Repair](#health-check--repair)
- [Subscription](#subscription)
- [API](#api)
- [ساختار پروژه](#ساختار-پروژه)
- [English](#-english)

---

## امکانات اصلی

### مدیریت کاربران

- ساخت کاربر VPN
- ویرایش کاربر
- حذف کاربر
- تمدید کاربر
- فعال / غیرفعال کردن کاربر
- ریست حجم مصرفی
- تعیین حجم کل
- تعیین تاریخ انقضا
- تعیین محدودیت دستگاه
- مقدار `0` برای حجم و تاریخ به معنی **نامحدود**
- نمایش حجم مصرف‌شده، حجم باقی‌مانده، آپلود و دانلود
- قطع یا غیرفعال‌سازی خودکار کاربر بعد از عبور از محدودیت حجم یا انقضا

### پروتکل‌ها

- نصب خودکار هسته پروتکل‌ها
- ساخت کانفیگ خودکار
- OpenVPN با Certificate Authentication
- WireGuard Peer Management
- Cisco AnyConnect / Ocserv
- L2TP/IPsec با StrongSwan و xl2tpd
- انتخاب TCP / UDP برای پروتکل‌های قابل پشتیبانی
- Sync کاربران بین پنل و سرویس‌های VPN

### مانیتورینگ

- مانیتورینگ لحظه‌ای CPU
- مانیتورینگ RAM
- مانیتورینگ Swap
- مانیتورینگ Disk
- نمایش کاربران آنلاین
- نمایش وضعیت سرویس‌ها
- نمایش وضعیت نسخه و آپدیت
- نمایش وضعیت لایسنس و روزهای باقی‌مانده
- Health Check / Repair
- مشاهده خطای سرویس‌ها از داخل پنل

### فروش و مدیریت تجاری

- ربات فروش تلگرام برای فروش سرویس VPN
- مدیریت پلن‌ها توسط مدیر فروش ربات
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار کاربر بعد از تأیید پرداخت
- تست رایگان قابل فعال / غیرفعال‌سازی
- تست فقط یک بار برای هر Telegram ID
- یادآوری انقضا و اتمام حجم
- سیستم مالی و فروش، وابسته به نوع لایسنس

### امنیت و مدیریت

- Login History
- Security Center
- IP Whitelist
- 2FA / TOTP
- Fail2Ban Integration
- API Key و Bearer Token
- محدودسازی امکانات بر اساس نوع لایسنس
- Backup / Restore
- Auto Backup
- Multi Server / Cluster / HA
- Load Balancer
- Firewall Manager
- DNS Manager
- Domain Manager
- SSL Manager

---

## پروتکل‌های پشتیبانی‌شده

| Protocol | Status | توضیح |
|---|---:|---|
| OpenVPN | ✅ | Certificate-based، بدون نیاز به وارد کردن یوزر/پسورد در کلاینت |
| WireGuard | ✅ | ساخت Peer اختصاصی، فایل کانفیگ و QR |
| Cisco AnyConnect / Ocserv | ✅ | مدیریت کاربران Ocserv |
| L2TP/IPsec | ✅ | StrongSwan + xl2tpd |

---

## نوع‌های لایسنس و محدودیت امکانات

IronPanel امکانات پنل را بر اساس نوع لایسنس فعال یا غیرفعال می‌کند.

| نوع لایسنس | توضیح | امکانات غیرفعال |
|---|---|---|
| `beginer` | مناسب استفاده پایه و سبک | بخش Nodes، ربات فروش، بخش مالی، بخش شبکه |
| `plus` | مناسب استفاده عمومی با امکانات بیشتر | ربات فروش، بخش مالی، بخش شبکه |
| `pro` | مناسب سرویس‌دهندگان حرفه‌ای | بخش مالی |
| `admin` | کامل‌ترین لایسنس | همه بخش‌ها فعال |
| `trial` | تست ۷ روزه | همه بخش‌ها فعال، فقط ۷ روزه |

مدت لایسنس‌های غیر Trial:

| مدت | وضعیت |
|---|---:|
| ۱ ماهه | ✅ |
| ۳ ماهه | ✅ |
| ۶ ماهه | ✅ |
| ۱۲ ماهه | ✅ |

> نکته: بخش **Update Manager** برای همه نوع‌های لایسنس فعال است تا همه کاربران بتوانند پنل را بروزرسانی کنند.

---

## داشبورد و مانیتورینگ

داشبورد IronPanel شامل کارت‌های مرتب و خوانا برای وضعیت سرور، لایسنس و نسخه است.

### کارت‌های داشبورد

- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- Online Users
- VPN Services
- License Status
- License Type
- License Remaining Days
- Current Version
- Latest Version
- Update Status

### وضعیت نسخه و آپدیت

IronPanel نسخه نصب‌شده را با ریپوی GitHub بررسی می‌کند:

```text
https://github.com/Unknown-sir/ironpanel
```

اگر نسخه جدید موجود باشد، در داشبورد پیشنهاد بروزرسانی نمایش داده می‌شود و از بخش **Update Manager** می‌توان با یک دکمه پنل را از GitHub بروزرسانی کرد.

---

## ربات فروش IronPanel

IronPanel دارای ربات فروش تلگرام برای فروش سرویس VPN است. تمام عملیات کاربر و مدیر تا حد امکان با دکمه‌های شیشه‌ای / Inline انجام می‌شود و فقط بخش‌هایی که واقعاً نیاز به ورودی دارند تایپی هستند.

### امکانات ربات فروش

- خرید سرویس VPN
- نمایش پلن‌ها
- تست رایگان، در صورت فعال بودن
- تست فقط یک‌بار برای هر Telegram ID
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار کاربر VPN بعد از تأیید پرداخت
- ارسال Subscription Link به کاربر
- نمایش وضعیت سرویس کاربر
- تمدید سرویس
- خرید حجم اضافه
- یادآوری انقضا
- یادآوری نزدیک شدن به پایان حجم

### مدیریت ربات فروش

مدیر فروش که Telegram ID او داخل پنل ثبت شده، می‌تواند پلن‌ها را مدیریت کند:

- ساخت پلن
- تعیین نام پلن
- تعیین زمان پلن
- تعیین حجم پلن
- تعیین قیمت
- تعیین واحد پول
- فعال / غیرفعال کردن پلن
- فعال / غیرفعال کردن تست
- تعیین مدت تست
- تعیین حجم تست
- تنظیم متن پرداخت دستی

### مسیر تنظیمات ربات داخل پنل

```text
مالی و فروش → ربات فروش
```

### سرویس systemd ربات

```bash
sudo systemctl status ironpanel-sales-bot
sudo systemctl restart ironpanel-sales-bot
```

---

## سیستم لایسنس

IronPanel با LicensePanel ارتباط می‌گیرد و وضعیت لایسنس را بررسی می‌کند.

آدرس پیش‌فرض License Server:

```text
http://license.skyshield.space:8002
```

در صورت نبود یا انقضای لایسنس:

- صفحه ورود پنل نمایش داده نمی‌شود.
- صفحه ثبت لایسنس نمایش داده می‌شود.
- کاربران VPN غیرفعال می‌شوند.
- لینک پشتیبانی نمایش داده می‌شود.

### دریافت یا تمدید لایسنس

برای دریافت، خرید یا تمدید لایسنس با پشتیبانی تلگرام تماس بگیرید:

```text
https://t.me/unknown_eng
```

---

## پیش‌نیازها

| مورد | حداقل | پیشنهادی |
|---|---:|---:|
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| CPU | 1 Core | 2+ Core |
| RAM | 1GB | 2GB+ |
| Disk | 20GB | 40GB+ |
| Access | Root | Root |

---

## نصب

### نصب سریع از GitHub

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

### نصب دستی

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash install.sh
```

---

## بروزرسانی

### بروزرسانی از پوشه پروژه

```bash
cd ironpanel
sudo bash upgrade.sh
```

### بروزرسانی از فایل ZIP

```bash
unzip Ironpanel_v15_3.zip
cd ironpanel_v15_3
sudo bash upgrade.sh
```

### بروزرسانی از داخل پنل

از بخش زیر می‌توانید بروزرسانی را با یک دکمه انجام دهید:

```text
سیستم → آپدیت
```

---

## Health Check / Repair

بخش Health Check / Repair وضعیت سرویس‌ها و اجزای مهم پنل را بررسی می‌کند.

### سرویس‌های بررسی‌شده

- IronPanel
- OpenVPN
- WireGuard
- Ocserv
- StrongSwan
- xl2tpd
- Firewall
- Database
- License
- Disk
- Network
- Usage Sync
- Sales Bot

اگر هر بخش خطا داشته باشد، کنار همان بخش دکمه **مشاهده خطا** نمایش داده می‌شود. مدیر می‌تواند خروجی `systemctl status` و `journalctl` همان سرویس را از داخل پنل ببیند.

### دستورات مفید

```bash
sudo systemctl status ironpanel
sudo journalctl -u ironpanel -n 100 --no-pager
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

---

## Subscription

صفحه Subscription برای هر کاربر اطلاعات زیر را نمایش می‌دهد:

- ظرفیت کل حجم
- حجم مصرف‌شده
- حجم باقی‌مانده
- آپلود
- دانلود
- تاریخ انقضا
- زمان باقی‌مانده
- وضعیت کاربر
- دانلود OpenVPN
- دانلود WireGuard
- اطلاعات Cisco AnyConnect / Ocserv
- اطلاعات L2TP/IPsec

برای امنیت بیشتر، محتوای خام فایل‌های OpenVPN و WireGuard در صفحه نمایش داده نمی‌شود و فقط لینک دانلود ارائه می‌شود.

---

## محاسبه مصرف واقعی

IronPanel مصرف کاربران را با واحد byte ثبت می‌کند تا حتی مصرف‌های کمتر از 1MB هم نمایش داده شوند.

### منابع محاسبه مصرف

- OpenVPN status log و hookهای connect/disconnect
- WireGuard transfer counters
- Ocserv session data
- L2TP PPP hooks

### تایمر Sync مصرف

```bash
sudo systemctl enable --now ironpanel-usage-sync.timer
sudo systemctl status ironpanel-usage-sync.timer
```

اجرای دستی:

```bash
cd /opt/ironpanel
sudo /opt/ironpanel/.venv/bin/flask --app run.py sync-usage
sudo /opt/ironpanel/.venv/bin/flask --app run.py enforce-limits
```

---

## کاربران آنلاین

IronPanel کاربران آنلاین را از منابع زیر تشخیص می‌دهد:

- OpenVPN `status.log`
- WireGuard handshake و endpoint
- Ocserv `occtl show users`
- L2TP PPP up/down hooks

اطلاعات قابل نمایش:

- نام کاربر
- پروتکل
- IP
- Device / Endpoint
- زمان شروع
- آخرین مشاهده
- مصرف نشست

---

## API

IronPanel دارای API برای اتصال به ربات، سایت فروش، CRM، Billing System و ابزارهای شخص ثالث است.

مستندات API:

```text
docs/API_GUIDE.md
docs/openapi.yaml
```

نمونه درخواست با API Key:

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_SERVER/api/v1/users
```

نمونه درخواست با Bearer Token:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://YOUR_SERVER/api/v2/users
```

---

## ساختار پروژه

```text
ironpanel/
├── app/
├── api/
├── bot/
│   ├── handlers/
│   ├── keyboards/
│   ├── services/
│   └── main.py
├── docs/
│   ├── API_GUIDE.md
│   └── openapi.yaml
├── installer/
├── scripts/
├── static/
├── templates/
├── systemd/
├── screenshots/
├── install.sh
├── upgrade.sh
├── uninstall.sh
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── SECURITY.md
└── CONTRIBUTING.md
```

---

## دستورات کاربردی

Restart IronPanel:

```bash
sudo systemctl restart ironpanel
```

مشاهده لاگ IronPanel:

```bash
sudo journalctl -u ironpanel -n 100 --no-pager
```

Restart OpenVPN:

```bash
sudo systemctl restart openvpn-server@server
```

Restart WireGuard:

```bash
sudo systemctl restart wg-quick@wg0
```

Restart Ocserv:

```bash
sudo systemctl restart ocserv
```

Restart L2TP/IPsec:

```bash
sudo systemctl restart strongswan
sudo systemctl restart xl2tpd
```

Restart Sales Bot:

```bash
sudo systemctl restart ironpanel-sales-bot
```

---

## نکات امنیتی

- از Ubuntu تمیز استفاده کنید.
- پنل را فقط روی سرور قابل اعتماد نصب کنید.
- از رمز عبور قوی استفاده کنید.
- 2FA را فعال کنید.
- API Key را عمومی نکنید.
- License Key را داخل GitHub قرار ندهید.
- Bot Token را داخل GitHub قرار ندهید.
- فایل‌های private key و certificate را منتشر نکنید.
- پورت‌های غیرضروری را ببندید.
- Backup دوره‌ای داشته باشید.

---

## استفاده قانونی

این پروژه فقط برای مدیریت قانونی سرورها و سرویس‌های VPN طراحی شده است. مسئولیت استفاده از نرم‌افزار بر عهده کاربر نهایی است.

---

## پشتیبانی

```text
Telegram: https://t.me/unknown_eng
GitHub: https://github.com/Unknown-sir/ironpanel
```

---

# 🇺🇸 English

## Overview

**IronPanel** is a modern multi-protocol VPN management panel designed for VPN providers, server administrators, resellers and infrastructure teams.

It provides a unified dashboard to manage users, VPN protocols, traffic limits, expiration dates, subscriptions, sales, monitoring, licensing, health checks, backups, API access and updates.

---

## Main Features

- User management
- User create/edit/delete/renew
- Traffic reset
- Expiration management
- `0` means unlimited for traffic and expiration
- Real traffic accounting in bytes
- Online users tracking
- OpenVPN certificate-based authentication
- WireGuard peer management
- Cisco AnyConnect / Ocserv support
- L2TP/IPsec support
- Subscription page
- Sales Telegram bot
- Manual payment workflow
- Admin approval workflow
- Free trial control
- License-based feature access
- Live server monitoring
- Health Check / Repair
- View service errors from the panel
- Update Manager with GitHub version check
- API v1 / API v2
- Backup / Restore
- Firewall / DNS / Domain / SSL managers
- Security Center
- Multi-server / Cluster / HA

---

## Supported Protocols

| Protocol | Status | Description |
|---|---:|---|
| OpenVPN | ✅ | Certificate-based authentication |
| WireGuard | ✅ | Dedicated peer and config generation |
| Cisco AnyConnect / Ocserv | ✅ | Ocserv user management |
| L2TP/IPsec | ✅ | StrongSwan and xl2tpd support |

---

## License Types

| License Type | Description | Disabled Features |
|---|---|---|
| `beginer` | Basic usage | Nodes, Sales Bot, Finance, Network |
| `plus` | General usage | Sales Bot, Finance, Network |
| `pro` | Professional usage | Finance |
| `admin` | Full license | None |
| `trial` | 7-day trial | None, limited to 7 days |

Available durations for paid licenses:

- 1 month
- 3 months
- 6 months
- 12 months

The Update Manager is available for all license types.

---

## Dashboard

The dashboard includes organized cards for:

- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- Online Users
- VPN Services
- License Status
- License Type
- Remaining License Days
- Current Version
- Latest Version
- Update Status

IronPanel checks the latest version from:

```text
https://github.com/Unknown-sir/ironpanel
```

If a new version is available, the panel displays an update notice and allows updating from the Update Manager.

---

## Sales Bot

IronPanel includes a Telegram sales bot for selling VPN services. Most actions are handled through inline buttons. Typing is only required for values such as plan name, price, traffic, duration and manual payment text.

### Bot Features

- Buy VPN service
- View plans
- Free trial if enabled
- One trial per Telegram ID
- Manual payment with receipt upload
- Admin payment approval/rejection
- Automatic VPN user creation after approval
- Send subscription link to user
- Renew service
- Buy extra traffic
- Expiration reminders
- Traffic usage reminders

### Admin Features

- Create sales plans
- Set plan name
- Set plan duration
- Set plan traffic
- Set plan price
- Set currency
- Enable/disable plans
- Enable/disable trial
- Set trial duration and traffic
- Set manual payment instructions

Sales bot settings path:

```text
Finance & Sales → Sales Bot
```

Systemd service:

```bash
sudo systemctl status ironpanel-sales-bot
sudo systemctl restart ironpanel-sales-bot
```

---

## License System

Default License Server:

```text
http://license.skyshield.space:8002
```

If the license is invalid or expired:

- Login page is disabled.
- License activation page is displayed.
- VPN users are disabled.
- Support link is displayed.

License support:

```text
https://t.me/unknown_eng
```

---

## Requirements

| Item | Minimum | Recommended |
|---|---:|---:|
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| CPU | 1 Core | 2+ Core |
| RAM | 1GB | 2GB+ |
| Disk | 20GB | 40GB+ |
| Access | Root | Root |

---

## Installation

Quick install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

Manual install:

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash install.sh
```

---

## Update

From project directory:

```bash
cd ironpanel
sudo bash upgrade.sh
```

From ZIP package:

```bash
unzip Ironpanel_v15_3.zip
cd ironpanel_v15_3
sudo bash upgrade.sh
```

From panel:

```text
System → Update
```

---

## Health Check / Repair

Health Check validates:

- IronPanel
- OpenVPN
- WireGuard
- Ocserv
- StrongSwan
- xl2tpd
- Firewall
- Database
- License
- Disk
- Network
- Usage Sync
- Sales Bot

If a service has an error, the panel displays a dedicated **View Error** button and shows `systemctl status` and `journalctl` output safely without crashing the page.

---

## Subscription Page

The subscription page displays:

- Total traffic
- Used traffic
- Remaining traffic
- Upload
- Download
- Expiration date
- Remaining time
- User status
- OpenVPN download
- WireGuard download
- Other protocol connection details

Raw OpenVPN and WireGuard configs are not displayed for security reasons.

---

## API Documentation

```text
docs/API_GUIDE.md
docs/openapi.yaml
```

Example API Key request:

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_SERVER/api/v1/users
```

Example Bearer Token request:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://YOUR_SERVER/api/v2/users
```

---

## Useful Commands

```bash
sudo systemctl restart ironpanel
sudo journalctl -u ironpanel -n 100 --no-pager
sudo systemctl restart openvpn-server@server
sudo systemctl restart wg-quick@wg0
sudo systemctl restart ocserv
sudo systemctl restart strongswan
sudo systemctl restart xl2tpd
sudo systemctl restart ironpanel-sales-bot
```

---

## Security Notes

- Use a clean Ubuntu server.
- Use strong admin passwords.
- Enable 2FA.
- Keep API keys private.
- Keep bot tokens private.
- Keep license keys private.
- Never publish private keys or certificates.
- Use firewall rules.
- Backup regularly.

---

## Legal Notice

This project is intended only for lawful VPN infrastructure management. The end user is responsible for how this software is deployed and used.

---

## Support

```text
Telegram: https://t.me/unknown_eng
GitHub: https://github.com/Unknown-sir/ironpanel
```

---

<div align="center">

Made for professional VPN infrastructure management.

</div>

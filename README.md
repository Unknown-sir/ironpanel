<div align="center">

# ⚡ IronPanel

### Modern Multi-Protocol VPN Management Panel  
### پنل حرفه‌ای مدیریت چندپروتکلی VPN

<br>

![Version](https://img.shields.io/badge/version-13.3-blue)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20LTS-orange)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![Flask](https://img.shields.io/badge/Backend-Flask-black)
![License](https://img.shields.io/badge/License-Commercial-red)

<br>

**OpenVPN • WireGuard • Cisco AnyConnect / Ocserv • L2TP/IPsec**

<br>

[🇮🇷 فارسی](#-فارسی) • [🇺🇸 English](#-english) • [API Docs](docs/API_GUIDE.md)

</div>

---

# 🇮🇷 فارسی

## معرفی

**IronPanel** یک پنل حرفه‌ای، مدرن و چندپروتکلی برای مدیریت سرویس‌های VPN است.  
این پنل برای مدیران سرور، فروشندگان VPN، نمایندگان، تیم‌های زیرساخت و کسب‌وکارهایی طراحی شده که نیاز به مدیریت کاربران، حجم، تاریخ انقضا، کانفیگ‌ها، مانیتورینگ، لایسنس، API، بکاپ، چندسروره و سیستم پشتیبانی دارند.

IronPanel از چندین پروتکل محبوب VPN پشتیبانی می‌کند و تلاش شده تمام موارد لازم برای نصب، مدیریت، مانیتورینگ، تعمیر و توسعه در یک پنل واحد فراهم شود.

---

## امکانات اصلی

- داشبورد مدرن و واکنش‌گرا
- مانیتورینگ لحظه‌ای CPU، RAM، Swap و Disk
- نمایش روز باقی‌مانده لایسنس در داشبورد
- مدیریت کاربران
- ساخت، ویرایش، حذف و تمدید کاربر
- ریست حجم مصرفی کاربر
- محدودیت حجم
- محدودیت تاریخ انقضا
- پشتیبانی از مقدار `0` به عنوان نامحدود برای حجم و تاریخ
- ساخت کانفیگ خودکار
- صفحه Subscription برای هر کاربر
- دانلود فایل OpenVPN و WireGuard فقط از طریق Subscription
- عدم نمایش محتوای خام کانفیگ OpenVPN و WireGuard برای کاربر
- نمایش ظرفیت حجم، حجم مصرف‌شده، حجم باقی‌مانده، تاریخ انقضا و زمان باقی‌مانده در صفحه Subscription
- محاسبه مصرف واقعی OpenVPN
- محاسبه مصرف واقعی WireGuard
- Sync مصرف کاربران هر ۱ دقیقه
- انتخاب TCP / UDP برای پروتکل‌های قابل پشتیبانی
- نصب خودکار هسته پروتکل‌ها
- Health Check / Repair
- مشاهده خطای سرویس‌ها با دکمه اختصاصی
- سیستم Ticket
- مدیریت نمایندگان
- سیستم مالی و فروش
- API v1 و API v2
- مستندات کامل API
- Security Center
- Login History
- Fail2Ban Integration
- IP Whitelist
- 2FA / TOTP
- Backup / Restore
- Auto Backup
- Multi Server
- Cluster / HA
- Load Balancer
- Firewall Manager
- DNS Manager
- SSL Manager
- Domain Manager
- Telegram Bot
- User Portal
- Session Management
- Online Users
- GeoIP
- License Verification
- ارتباط با LicensePanel
- مناسب برای ارائه روی GitHub

---

## پروتکل‌های پشتیبانی‌شده

| Protocol | Status | توضیح |
|---|---:|---|
| OpenVPN | ✅ | Certificate Based، بدون نیاز به یوزر و پسورد داخل کلاینت |
| WireGuard | ✅ | ساخت peer و فایل کانفیگ اختصاصی |
| Cisco AnyConnect / Ocserv | ✅ | مدیریت کاربران Ocserv |
| L2TP/IPsec | ✅ | پشتیبانی از xl2tpd و StrongSwan |

---

## داشبورد

داشبورد IronPanel شامل اطلاعات مهم و لحظه‌ای سرور است:

- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- Network Status
- Online Users
- Active Services
- Remaining License Days
- Latest Logs
- VPN Core Status

برای اضافه کردن اسکرین‌شات، فایل‌های زیر را در مسیر `screenshots/` قرار دهید:

```text
screenshots/dashboard.png
screenshots/users.png
screenshots/subscription.png
screenshots/monitoring.png
screenshots/settings.png
```

نمونه:

```md
![Dashboard](screenshots/dashboard.png)
```

---

## سیستم لایسنس

IronPanel دارای سیستم لایسنس آنلاین است و اعتبار لایسنس از طریق License Server بررسی می‌شود.

آدرس پیش‌فرض License Server:

```text
http://license.skyshield.space:8002
```

در صورت منقضی شدن یا نامعتبر بودن لایسنس:

- صفحه ورود پنل نمایش داده نمی‌شود.
- کاربران امکان استفاده از سرویس‌ها را نخواهند داشت.
- صفحه فعال‌سازی لایسنس نمایش داده می‌شود.
- مدیر می‌تواند لایسنس جدید ثبت کند.
- لینک پشتیبانی برای تمدید یا دریافت لایسنس نمایش داده می‌شود.

---

## دریافت یا تمدید لایسنس

برای دریافت، خرید یا تمدید لایسنس با پشتیبانی تلگرام در ارتباط باشید:

### Telegram Support

```text
https://t.me/unknown_eng
```

---

## پیش‌نیازها

سیستم پیشنهادی:

| مورد | حداقل | پیشنهادی |
|---|---:|---:|
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| CPU | 1 Core | 2+ Core |
| RAM | 1GB | 2GB+ |
| Disk | 20GB | 40GB+ |
| Access | Root | Root |

---

## نصب سریع

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

---

## نصب دستی

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash install.sh
```

---

## بروزرسانی

```bash
cd ironpanel
sudo bash upgrade.sh
```

یا اگر از فایل ZIP استفاده می‌کنید:

```bash
unzip Ironpanel_v13_3.zip
cd ironpanel_v13_3
sudo bash upgrade.sh
```

---

## وضعیت سرویس‌ها

```bash
sudo systemctl status ironpanel
sudo systemctl status openvpn-server@server
sudo systemctl status wg-quick@wg0
sudo systemctl status ocserv
sudo systemctl status strongswan
sudo systemctl status xl2tpd
```

---

## Sync مصرف کاربران

IronPanel برای محاسبه مصرف واقعی کاربران از تایمر اختصاصی استفاده می‌کند:

```bash
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 50 --no-pager
```

فعال‌سازی دستی:

```bash
sudo systemctl enable --now ironpanel-usage-sync.timer
```

---

## Health Check / Repair

در بخش Health Check / Repair وضعیت سرویس‌های زیر بررسی می‌شود:

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

اگر هر سرویس خطا داشته باشد، کنار همان سرویس دکمه **View Error / مشاهده خطا** نمایش داده می‌شود.  
مدیر می‌تواند خروجی `systemctl status` و `journalctl` مربوط به همان سرویس را مشاهده کند.

---

## Subscription Page

صفحه Subscription برای هر کاربر شامل اطلاعات زیر است:

- ظرفیت کل حجم
- حجم مصرف‌شده
- حجم باقی‌مانده
- آپلود
- دانلود
- تاریخ انقضا
- زمان باقی‌مانده
- وضعیت کاربر
- دانلود فایل OpenVPN
- دانلود فایل WireGuard
- دریافت کانفیگ‌های سایر پروتکل‌ها

برای امنیت بیشتر، محتوای خام فایل‌های OpenVPN و WireGuard نمایش داده نمی‌شود و فقط لینک دانلود ارائه می‌شود.

---

## مقدار نامحدود

در IronPanel مقدار `0` به عنوان نامحدود در نظر گرفته می‌شود:

| فیلد | مقدار 0 |
|---|---|
| حجم کاربر | نامحدود |
| تاریخ انقضا | نامحدود |
| محدودیت دستگاه | نامحدود، در صورت فعال بودن این حالت |

---

## API

IronPanel دارای API کامل برای اتصال به ربات، سایت فروش، CRM، Billing System و ابزارهای شخص ثالث است.

مستندات کامل API:

```text
docs/API_GUIDE.md
docs/openapi.yaml
```

نمونه احراز هویت:

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_SERVER/api/v1/users
```

نمونه Bearer Token:

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

Restart پنل:

```bash
sudo systemctl restart ironpanel
```

مشاهده لاگ پنل:

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

---

## نکات امنیتی

- همیشه از Ubuntu تمیز استفاده کنید.
- پنل را فقط روی سرور قابل اعتماد نصب کنید.
- پورت‌های غیرضروری را ببندید.
- از رمز عبور قوی استفاده کنید.
- 2FA را فعال کنید.
- از Backup دوره‌ای استفاده کنید.
- License Key را عمومی منتشر نکنید.
- API Key را داخل GitHub قرار ندهید.
- فایل‌های کانفیگ و گواهی‌ها را عمومی نکنید.

---

## استفاده قانونی

این پروژه فقط برای مدیریت قانونی سرورها و سرویس‌های VPN طراحی شده است.  
مسئولیت استفاده از این نرم‌افزار بر عهده کاربر نهایی است.

---

## پشتیبانی

برای دریافت لایسنس، تمدید لایسنس یا پشتیبانی:

```text
Telegram: https://t.me/unknown_eng
```

---

# 🇺🇸 English

## Overview

**IronPanel** is a modern multi-protocol VPN management panel designed for VPN providers, server administrators, resellers and infrastructure teams.

It provides a unified dashboard to manage users, traffic limits, expiration dates, VPN profiles, subscriptions, monitoring, billing, API access, licensing, backups, health checks and multi-server infrastructure.

---

## Key Features

- Modern responsive dashboard
- Live CPU, RAM, Swap and Disk monitoring
- Remaining license days widget
- User management
- Create, edit, renew and delete users
- Reset user traffic
- Traffic limit management
- Expiration management
- `0` means unlimited for traffic and expiration
- Automatic VPN configuration generation
- User subscription page
- OpenVPN and WireGuard files downloadable only from Subscription page
- Raw OpenVPN and WireGuard configs are not displayed to users
- Subscription page displays total traffic, used traffic, remaining traffic, expiration and remaining time
- Real OpenVPN traffic accounting
- Real WireGuard traffic accounting
- Usage sync every 1 minute
- TCP / UDP protocol selection where supported
- Automatic VPN core installation
- Health Check / Repair
- View service errors directly from the panel
- Ticket system
- Reseller management
- Billing and sales modules
- API v1 and API v2
- Full API documentation
- Security Center
- Login history
- Fail2Ban integration
- IP whitelist
- 2FA / TOTP
- Backup / Restore
- Auto Backup
- Multi Server
- Cluster / HA
- Load Balancer
- Firewall Manager
- DNS Manager
- SSL Manager
- Domain Manager
- Telegram Bot
- User Portal
- Session Management
- Online Users
- GeoIP
- Online License Verification
- LicensePanel integration
- GitHub ready project structure

---

## Supported Protocols

| Protocol | Status | Description |
|---|---:|---|
| OpenVPN | ✅ | Certificate based authentication |
| WireGuard | ✅ | Dedicated peer and config generation |
| Cisco AnyConnect / Ocserv | ✅ | Ocserv user management |
| L2TP/IPsec | ✅ | StrongSwan and xl2tpd support |

---

## Dashboard

IronPanel dashboard includes:

- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- Network Status
- Online Users
- Active Services
- Remaining License Days
- Latest Logs
- VPN Core Status

Suggested screenshot paths:

```text
screenshots/dashboard.png
screenshots/users.png
screenshots/subscription.png
screenshots/monitoring.png
screenshots/settings.png
```

---

## License System

IronPanel requires a valid online license.

Default License Server:

```text
http://license.skyshield.space:8002
```

If the license is expired or invalid:

- Login page will be disabled.
- VPN users will not be able to use the services.
- License activation page will be displayed.
- Admin can submit a new license.
- Support link will be shown.

---

## Purchase or Renew License

To purchase or renew your license, contact Telegram support:

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

## Quick Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

---

## Manual Installation

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash install.sh
```

---

## Update

```bash
cd ironpanel
sudo bash upgrade.sh
```

Or from ZIP package:

```bash
unzip Ironpanel_v13_3.zip
cd ironpanel_v13_3
sudo bash upgrade.sh
```

---

## Service Status

```bash
sudo systemctl status ironpanel
sudo systemctl status openvpn-server@server
sudo systemctl status wg-quick@wg0
sudo systemctl status ocserv
sudo systemctl status strongswan
sudo systemctl status xl2tpd
```

---

## User Traffic Sync

IronPanel uses a dedicated timer to sync real user traffic usage:

```bash
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 50 --no-pager
```

Enable manually:

```bash
sudo systemctl enable --now ironpanel-usage-sync.timer
```

---

## Health Check / Repair

The Health Check / Repair section checks:

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

If a service has an error, a dedicated **View Error** button will appear next to that service.  
The admin can view `systemctl status` and `journalctl` output directly from the panel.

---

## Subscription Page

The user subscription page displays:

- Total traffic
- Used traffic
- Remaining traffic
- Upload
- Download
- Expiration date
- Remaining time
- User status
- OpenVPN download button
- WireGuard download button
- Other protocol configs

For security reasons, raw OpenVPN and WireGuard configuration content is not displayed.

---

## Unlimited Values

IronPanel treats `0` as unlimited:

| Field | Value 0 |
|---|---|
| User traffic | Unlimited |
| Expiration date | Unlimited |
| Device limit | Unlimited when enabled |

---

## API Documentation

IronPanel includes full API documentation for integrations with bots, billing systems, websites, CRM systems and third-party tools.

API documents:

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

## Project Structure

```text
ironpanel/
├── app/
├── api/
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

## Useful Commands

Restart IronPanel:

```bash
sudo systemctl restart ironpanel
```

View IronPanel logs:

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

---

## Security Notes

- Use a clean Ubuntu server.
- Use strong admin passwords.
- Enable 2FA.
- Keep your license key private.
- Never publish API keys on GitHub.
- Never publish VPN certificates or private keys.
- Enable firewall rules.
- Use backup and restore regularly.
- Keep the panel updated.

---

## Legal Notice

This project is intended only for lawful VPN infrastructure management.  
The end user is responsible for how this software is deployed and used.

---

## Support

For license purchase, renewal or support:

```text
Telegram: https://t.me/unknown_eng
```

---

## Author

```text
GitHub: https://github.com/Unknown-sir
Support: https://t.me/unknown_eng
```

---

<div align="center">

Made for professional VPN infrastructure management.

</div>

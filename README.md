<div align="center">

# ⚡ IronPanel

### Modern Multi-Protocol VPN Management Panel  
### پنل حرفه‌ای مدیریت چندپروتکلی VPN

<br>

![Version](https://img.shields.io/badge/version-13.5-blue)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20LTS-orange)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![Backend](https://img.shields.io/badge/Backend-Flask-black)
![VPN](https://img.shields.io/badge/VPN-Multi--Protocol-purple)
![License](https://img.shields.io/badge/License-Commercial-red)

<br>

**OpenVPN • WireGuard • Cisco AnyConnect / Ocserv • L2TP/IPsec**

<br>

[🇮🇷 فارسی](#-فارسی) • [🇺🇸 English](#-english) • [API Docs](docs/API_GUIDE.md) • [OpenAPI](docs/openapi.yaml)

</div>

---

# 🇮🇷 فارسی

## معرفی

**IronPanel** یک پنل حرفه‌ای، مدرن و چندپروتکلی برای مدیریت سرویس‌های VPN است. این پنل برای مدیران سرور، فروشندگان VPN، نمایندگان، تیم‌های زیرساخت و کسب‌وکارهایی طراحی شده که نیاز به مدیریت کاربران، حجم، تاریخ انقضا، کانفیگ‌ها، مانیتورینگ، لایسنس، API، بکاپ، چندسروره، سیستم مالی و پشتیبانی دارند.

IronPanel تلاش می‌کند همه ابزارهای لازم برای نصب، راه‌اندازی، مدیریت، مانیتورینگ، محدودسازی، عیب‌یابی، توسعه و فروش سرویس VPN را در یک پنل واحد ارائه کند.

---

## امکانات اصلی

- داشبورد مدرن و واکنش‌گرا
- منوی دسته‌بندی‌شده و جمع‌شونده برای جلوگیری از شلوغی و اسکرول زیاد
- مانیتورینگ لحظه‌ای CPU، RAM، Swap، Disk و Network
- نمایش تعداد کاربران آنلاین در داشبورد
- نمایش روز باقی‌مانده لایسنس در داشبورد
- مدیریت کاربران
- ساخت، ویرایش، حذف و تمدید کاربر
- ریست حجم مصرفی کاربر
- محدودیت حجم کاربر
- محدودیت تاریخ انقضا
- پشتیبانی از مقدار `0` به عنوان نامحدود برای حجم، تاریخ و محدودیت دستگاه
- ساخت کانفیگ خودکار برای پروتکل‌های فعال
- صفحه Subscription اختصاصی برای هر کاربر
- نمایش ظرفیت حجم، حجم مصرف‌شده، حجم باقی‌مانده، آپلود، دانلود، تاریخ انقضا و زمان باقی‌مانده در صفحه Subscription
- دانلود فایل OpenVPN و WireGuard فقط از طریق صفحه Subscription
- عدم نمایش محتوای خام کانفیگ OpenVPN و WireGuard برای کاربر
- محاسبه مصرف واقعی OpenVPN و WireGuard
- ذخیره مصرف با دقت byte برای جلوگیری از صفر ماندن مصرف‌های کمتر از 1MB
- Sync مصرف کاربران هر ۱ دقیقه با systemd timer
- قطع و غیرفعال‌سازی خودکار کاربر پس از عبور از محدودیت حجم یا تاریخ
- نمایش کاربران آنلاین برای OpenVPN، WireGuard، Ocserv و L2TP
- نمایش IP، پروتکل، Device، زمان شروع اتصال و آخرین مشاهده کاربر آنلاین
- انتخاب TCP / UDP برای پروتکل‌های قابل پشتیبانی
- نصب خودکار هسته تمام پروتکل‌ها
- Health Check / Repair
- نمایش خطای سرویس‌ها با دکمه اختصاصی View Error / مشاهده خطا
- Ticket System
- Reseller Management
- Billing / Finance
- Coupon / Invoice / Wallet structure
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
- Telegram Bot structure
- User Portal
- Session Management
- Online Users
- GeoIP structure
- License Verification
- اتصال به LicensePanel
- آماده برای آپلود روی GitHub

---

## پروتکل‌های پشتیبانی‌شده

| Protocol | Status | توضیح |
|---|---:|---|
| OpenVPN | ✅ | Certificate Based، بدون نیاز به ورود یوزر/پسورد در کلاینت |
| WireGuard | ✅ | ساخت Peer و فایل کانفیگ اختصاصی |
| Cisco AnyConnect / Ocserv | ✅ | مدیریت کاربران Ocserv |
| L2TP/IPsec | ✅ | پشتیبانی از StrongSwan و xl2tpd |

---

## نصب خودکار هسته VPNها

IronPanel در زمان نصب یا آپدیت، هسته سرویس‌های موردنیاز را نصب و تنظیم می‌کند:

- OpenVPN
- WireGuard
- Ocserv / Cisco AnyConnect
- StrongSwan / IPsec
- xl2tpd / L2TP

پس از نصب، کاربرانی که در پنل ساخته می‌شوند می‌توانند از پروتکل‌های فعال‌شده توسط مدیر استفاده کنند.

---

## داشبورد و مانیتورینگ

داشبورد IronPanel شامل وضعیت لحظه‌ای سرور و سرویس‌ها است:

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
---

## کاربران آنلاین

در نسخه 13.5، بخش کاربران آنلاین بهبود داده شده و وضعیت اتصال از منابع واقعی خوانده می‌شود:

- OpenVPN از فایل `status.log` و hookهای اتصال/قطع
- WireGuard از `wg show wg0 dump`، handshake و endpoint
- Ocserv از `occtl show users`
- L2TP از hookهای `ppp ip-up` و `ppp ip-down`

اطلاعات قابل نمایش:

- نام کاربر
- پروتکل
- IP واقعی / endpoint
- IP داخلی VPN
- زمان شروع اتصال
- آخرین مشاهده
- آپلود و دانلود
- وضعیت نشست

دستورات تست:

```bash
sudo cat /var/log/openvpn/status.log
sudo wg show wg0 dump
sudo occtl show users
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

---

## محاسبه مصرف و محدودیت حجم

IronPanel مصرف کاربران را به صورت دوره‌ای Sync می‌کند و مقدار مصرف را با دقت byte ذخیره می‌کند.

در نسخه 13.4 و 13.5 موارد زیر اصلاح شده‌اند:

- جلوگیری از صفر ماندن مصرف برای ترافیک‌های کمتر از 1MB
- اضافه شدن `used_upload_bytes`
- اضافه شدن `used_download_bytes`
- محاسبه آپلود و دانلود جداگانه
- نمایش مصرف در صفحه کاربران و Subscription
- Enforce خودکار محدودیت حجم
- غیرفعال‌سازی کاربر پس از عبور از سقف حجم
- حذف Peer از WireGuard بعد از اتمام حجم
- جلوگیری از اتصال جدید OpenVPN با `client-connect`
- ثبت مصرف نهایی اتصال OpenVPN با `client-disconnect`

بررسی تایمر مصرف:

```bash
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

فعال‌سازی دستی:

```bash
sudo systemctl enable --now ironpanel-usage-sync.timer
```

اجرای دستی Sync و Enforcement:

```bash
cd /opt/ironpanel
sudo /opt/ironpanel/.venv/bin/flask --app run.py sync-usage
sudo /opt/ironpanel/.venv/bin/flask --app run.py enforce-limits
```

---

## صفحه Subscription

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
- دریافت اطلاعات اتصال سایر پروتکل‌ها

برای امنیت بیشتر، محتوای خام فایل‌های OpenVPN و WireGuard در صفحه نمایش داده نمی‌شود و فقط لینک دانلود ارائه می‌شود.

---

## مقدار نامحدود

در IronPanel مقدار `0` به عنوان نامحدود در نظر گرفته می‌شود:

| فیلد | مقدار 0 |
|---|---|
| حجم کاربر | نامحدود |
| تاریخ انقضا | نامحدود |
| محدودیت دستگاه | نامحدود، در صورت فعال بودن این قابلیت |

---

## سیستم لایسنس



در صورت منقضی شدن یا نامعتبر بودن لایسنس:

- صفحه ورود پنل نمایش داده نمی‌شود.
- کاربران امکان استفاده از سرویس‌ها را نخواهند داشت.
- صفحه فعال‌سازی لایسنس نمایش داده می‌شود.
- مدیر می‌تواند لایسنس جدید ثبت کند.
- لینک پشتیبانی برای دریافت یا تمدید لایسنس نمایش داده می‌شود.

---

## دریافت یا تمدید لایسنس

برای دریافت، خرید یا تمدید لایسنس با پشتیبانی تلگرام در ارتباط باشید:

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
unzip Ironpanel_v13_5.zip
cd ironpanel_v13_5
sudo bash upgrade.sh
```

پس از آپدیت به نسخه 13.5:

```bash
sudo systemctl restart openvpn-server@server
sudo systemctl restart wg-quick@wg0
sudo systemctl restart ocserv
sudo systemctl restart xl2tpd
sudo systemctl restart ironpanel
sudo systemctl enable --now ironpanel-usage-sync.timer
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

اگر هر سرویس خطا داشته باشد، کنار همان سرویس دکمه **View Error / مشاهده خطا** نمایش داده می‌شود. مدیر می‌تواند خروجی `systemctl status` و `journalctl` مربوط به همان سرویس را از داخل پنل ببیند.

---

## API

IronPanel دارای API کامل برای اتصال به ربات، سایت فروش، CRM، Billing System و ابزارهای شخص ثالث است.

مستندات کامل API:

```text
docs/API_GUIDE.md
docs/openapi.yaml
```

نمونه احراز هویت با API Key:

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_SERVER/api/v1/users
```

نمونه احراز هویت با Bearer Token:

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
- فایل‌های کانفیگ، کلید خصوصی و گواهی‌ها را عمومی نکنید.
- دسترسی SSH را محدود کنید.

---

## استفاده قانونی

این پروژه فقط برای مدیریت قانونی سرورها و سرویس‌های VPN طراحی شده است. مسئولیت استفاده از این نرم‌افزار بر عهده کاربر نهایی است.

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

It provides a unified dashboard to manage users, traffic limits, expiration dates, VPN profiles, subscriptions, monitoring, online users, billing, API access, licensing, backups, health checks and multi-server infrastructure.

---

## Key Features

- Modern responsive dashboard
- Grouped and collapsible sidebar menu
- Live CPU, RAM, Swap, Disk and Network monitoring
- Online users widget
- Remaining license days widget
- User management
- Create, edit, renew and delete users
- Reset user traffic
- Traffic limit management
- Expiration management
- `0` means unlimited for traffic, expiration and device limit
- Automatic VPN configuration generation
- User subscription page
- OpenVPN and WireGuard files downloadable only from Subscription page
- Raw OpenVPN and WireGuard configs are not displayed to users
- Subscription page displays total traffic, used traffic, remaining traffic, upload, download, expiration and remaining time
- Real OpenVPN traffic accounting
- Real WireGuard traffic accounting
- Byte-accurate traffic counters
- Usage sync every 1 minute
- Automatic user suspension after traffic or expiration limit is reached
- Online user detection for OpenVPN, WireGuard, Ocserv and L2TP
- Online user details: IP, protocol, device, start time and last seen
- TCP / UDP protocol selection where supported
- Automatic VPN core installation
- Health Check / Repair
- View service errors directly from the panel
- Ticket system
- Reseller management
- Billing and finance modules
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
- Telegram Bot structure
- User Portal
- Session Management
- Online Users
- GeoIP structure
- Online License Verification
- LicensePanel integration
- GitHub-ready project structure

---

## Supported Protocols

| Protocol | Status | Description |
|---|---:|---|
| OpenVPN | ✅ | Certificate based authentication |
| WireGuard | ✅ | Dedicated peer and config generation |
| Cisco AnyConnect / Ocserv | ✅ | Ocserv user management |
| L2TP/IPsec | ✅ | StrongSwan and xl2tpd support |

---

## VPN Core Installation

IronPanel installs and configures the required VPN cores during installation or upgrade:

- OpenVPN
- WireGuard
- Ocserv / Cisco AnyConnect
- StrongSwan / IPsec
- xl2tpd / L2TP

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
---

## Online Users

In version 13.5, online session detection has been improved and reads real connection data from protocol-specific sources:

- OpenVPN from `status.log` and connect/disconnect hooks
- WireGuard from `wg show wg0 dump`, handshake and endpoint
- Ocserv from `occtl show users`
- L2TP from `ppp ip-up` and `ppp ip-down` hooks

Displayed data:

- Username
- Protocol
- Real IP / endpoint
- VPN internal IP
- Session start time
- Last seen
- Upload and download
- Session status

Useful test commands:

```bash
sudo cat /var/log/openvpn/status.log
sudo wg show wg0 dump
sudo occtl show users
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

---

## Traffic Accounting and Limit Enforcement

IronPanel syncs real user usage periodically and stores traffic counters with byte precision.

Version 13.4 and 13.5 include:

- Fix for traffic remaining zero when usage is less than 1MB
- `used_upload_bytes`
- `used_download_bytes`
- Separate upload and download counters
- Traffic display in users and subscription pages
- Automatic traffic limit enforcement
- Automatic user suspension after exceeding the traffic limit
- WireGuard peer removal after the limit is reached
- OpenVPN `client-connect` validation for expired or traffic-limited users
- OpenVPN `client-disconnect` usage accounting

Check usage sync timer:

```bash
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

Enable manually:

```bash
sudo systemctl enable --now ironpanel-usage-sync.timer
```

Run sync and enforcement manually:

```bash
cd /opt/ironpanel
sudo /opt/ironpanel/.venv/bin/flask --app run.py sync-usage
sudo /opt/ironpanel/.venv/bin/flask --app run.py enforce-limits
```

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
- Other protocol connection information

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

## License System
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
unzip Ironpanel_v13_5.zip
cd ironpanel_v13_5
sudo bash upgrade.sh
```

After updating to v13.5:

```bash
sudo systemctl restart openvpn-server@server
sudo systemctl restart wg-quick@wg0
sudo systemctl restart ocserv
sudo systemctl restart xl2tpd
sudo systemctl restart ironpanel
sudo systemctl enable --now ironpanel-usage-sync.timer
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

If a service has an error, a dedicated **View Error** button will appear next to that service. The admin can view `systemctl status` and `journalctl` output directly from the panel.

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
- Restrict SSH access.

---

## Legal Notice

This project is intended only for lawful VPN infrastructure management. The end user is responsible for how this software is deployed and used.

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

<div align="center">

# ⚡ IronPanel

### Modern Multi‑Protocol VPN Management & Sales Platform  
### پنل حرفه‌ای مدیریت، فروش و مانیتورینگ چندپروتکلی VPN

<br>

![Version](https://img.shields.io/badge/version-v15.5-blue?style=for-the-badge)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20LTS-orange?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-green?style=for-the-badge)
![Flask](https://img.shields.io/badge/Backend-Flask-black?style=for-the-badge)
![License](https://img.shields.io/badge/License-Commercial-red?style=for-the-badge)

<br>

**OpenVPN • WireGuard • Cisco AnyConnect / Ocserv • L2TP/IPsec**

<br>

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

[🇮🇷 فارسی](#-فارسی) • [🇺🇸 English](#-english) • [API Docs](docs/API_GUIDE.md) • [Support](https://t.me/unknown_eng)

</div>

---

# 🇮🇷 فارسی

## معرفی

**IronPanel** یک پنل مدرن و حرفه‌ای برای مدیریت سرویس‌های VPN، فروش اشتراک، مانیتورینگ سرور، کنترل مصرف کاربران، مدیریت لایسنس، ربات فروش و مدیریت چندسروره است.

این پروژه برای مدیران سرور، فروشندگان VPN، نمایندگان، تیم‌های زیرساخت و کسب‌وکارهایی طراحی شده که می‌خواهند چندین پروتکل VPN را از یک پنل مرکزی مدیریت کنند و فرآیند فروش، تمدید، پشتیبانی و کنترل کاربران را ساده‌تر کنند.

---

## قابلیت‌های اصلی

- داشبورد مدرن و واکنش‌گرا
- مانیتورینگ زنده CPU، RAM، Swap، Disk و Network
- نمایش وضعیت نسخه و لایسنس به‌صورت کارت‌بندی‌شده
- بررسی آخرین نسخه از GitHub
- بخش Update Manager برای آپدیت پنل از GitHub
- مدیریت کاربران VPN
- ساخت، ویرایش، حذف، تمدید و غیرفعال‌سازی کاربر
- ریست حجم مصرفی کاربر
- پشتیبانی از حجم و تاریخ نامحدود با مقدار `0`
- محاسبه مصرف واقعی کاربران
- کنترل محدودیت حجم و قطع کاربر در صورت عبور از سقف مجاز
- نمایش کاربران آنلاین
- نمایش مصرف در صفحه کاربران و Subscription
- صفحه Subscription اختصاصی برای هر کاربر
- دانلود فایل OpenVPN و WireGuard فقط از طریق Subscription
- عدم نمایش خام کانفیگ OpenVPN و WireGuard برای امنیت بیشتر
- پشتیبانی از Tunnel Host / Domain جایگزین در کانفیگ‌ها
- انتخاب TCP / UDP برای پروتکل‌های قابل پشتیبانی
- نصب و ترمیم خودکار هسته پروتکل‌ها
- Health Check / Repair با امکان مشاهده خطای هر سرویس
- ربات فروش تلگرام برای IronPanel
- پرداخت دستی با ارسال رسید
- مدیریت پلن‌های فروش از داخل ربات و پنل
- تست رایگان قابل کنترل توسط مدیر
- سیستم Ticket و پشتیبانی
- مدیریت نمایندگان / Reseller
- سیستم مالی و سفارش‌ها
- Backup / Restore
- Auto Backup
- Multi Server و Node Management
- Cluster / HA و Load Balancer
- Firewall Manager
- DNS Manager
- Domain Manager
- SSL Manager
- Security Center
- Login History
- IP Whitelist
- Fail2Ban Integration
- 2FA / TOTP
- API v1 و API v2
- مستندات کامل API
- اتصال به LicensePanel

---

## پروتکل‌های پشتیبانی‌شده

| Protocol | Status | توضیح |
|---|---:|---|
| OpenVPN | ✅ | Certificate‑Only، بدون نیاز به نام کاربری و رمز در کلاینت |
| WireGuard | ✅ | ساخت Peer اختصاصی و فایل کانفیگ |
| Cisco AnyConnect / Ocserv | ✅ | مدیریت کاربران و اتصال AnyConnect |
| L2TP/IPsec | ✅ | پشتیبانی از StrongSwan و xl2tpd |

---

## تغییر مهم OpenVPN در v15.5

در نسخه **v15.5** مشکل خطای `User authentication failed` در برخی کلاینت‌های OpenVPN اصلاح شده است.

موارد اصلاح‌شده:

- احراز هویت OpenVPN به‌صورت Certificate‑Only
- حذف وابستگی اشتباه به Username/Password در فایل کانفیگ
- اصلاح اسکریپت‌های `client-connect` و `client-disconnect`
- اضافه شدن ابزار ترمیم OpenVPN
- جلوگیری از Reject اشتباه کاربر معتبر هنگام ثبت Session یا Sync مصرف

بعد از آپدیت، برای ترمیم OpenVPN اجرا کنید:

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
sudo systemctl restart openvpn-server@server
sudo systemctl restart ironpanel
```

سپس فایل OpenVPN کاربر را دوباره از صفحه Subscription دانلود کنید.

---

## سیستم لایسنس

IronPanel دارای سیستم لایسنس آنلاین است و امکانات پنل بر اساس نوع لایسنس فعال یا محدود می‌شود.

License Server پیش‌فرض:

```text
http://license.skyshield.space:8002
```

### انواع لایسنس

| License Type | امکانات |
|---|---|
| `beginer` | بخش Node، ربات فروش، مالی و شبکه غیرفعال است |
| `plus` | همه بخش‌ها فعال هستند به‌جز ربات فروش، مالی و شبکه |
| `pro` | همه بخش‌ها فعال هستند به‌جز بخش مالی |
| `admin` | همه امکانات فعال است |
| `trial` | همه امکانات فعال، فقط ۷ روزه |

لایسنس‌های اصلی می‌توانند به‌صورت ۱، ۳، ۶ یا ۱۲ ماهه صادر شوند.

---

## دریافت یا تمدید لایسنس

برای دریافت، خرید یا تمدید لایسنس با پشتیبانی تلگرام در ارتباط باشید:

```text
https://t.me/unknown_eng
```

---

## ربات فروش IronPanel

ربات فروش IronPanel برای فروش سرویس VPN به کاربران نهایی طراحی شده است.

قابلیت‌ها:

- دکمه‌های شیشه‌ای / Inline برای تمام عملیات کاربر و مدیر
- خرید سرویس VPN
- انتخاب پلن
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار کاربر VPN پس از تأیید پرداخت
- ارسال لینک Subscription به کاربر
- نمایش وضعیت سرویس کاربر
- تمدید سرویس
- خرید حجم اضافه
- تست رایگان فقط در صورت فعال بودن توسط مدیر
- مدیریت پلن‌ها توسط مدیر فروش ثبت‌شده در پنل
- یادآوری نزدیک شدن به انقضا و اتمام حجم

مدیر فروش در ربات می‌تواند پلن‌ها را تعریف کند:

- نام پلن
- مدت زمان
- حجم
- قیمت
- واحد پول
- وضعیت فعال یا غیرفعال

---

## LicensePanel و ربات فروش لایسنس

پکیج کامل پروژه شامل LicensePanel نیز هست. LicensePanel برای مدیریت، صدور و فروش لایسنس IronPanel استفاده می‌شود.

فلو خرید لایسنس در ربات فروش LicensePanel:

```text
خرید لایسنس
↓
نمایش توضیح کوتاه انواع لایسنس
↓
انتخاب نوع لایسنس: beginer / plus / pro / admin
↓
انتخاب مدت: 1 / 3 / 6 / 12 ماهه
↓
نمایش مبلغ و اطلاعات پرداخت دستی
↓
ارسال رسید توسط کاربر
↓
تأیید مدیر
↓
ساخت و ارسال لایسنس
```

---

## داشبورد

داشبورد IronPanel شامل بخش‌های زیر است:

- وضعیت کلی سرور
- وضعیت لایسنس
- نوع لایسنس
- روز باقی‌مانده لایسنس
- وضعیت نسخه فعلی و آخرین نسخه GitHub
- CPU Usage
- RAM Usage
- Swap Usage
- Disk Usage
- کاربران آنلاین
- سرویس‌های فعال
- خطاهای مهم
- دکمه Update در صورت وجود نسخه جدید

---

## Health Check / Repair

در بخش Health Check / Repair وضعیت سرویس‌های اصلی بررسی می‌شود:

- IronPanel
- OpenVPN
- WireGuard
- Ocserv
- StrongSwan
- xl2tpd
- Firewall
- Database
- License
- Network
- Disk
- Usage Sync Timer

اگر هر بخش خطا داشته باشد، کنار همان بخش دکمه **مشاهده خطا / View Error** نمایش داده می‌شود و مدیر می‌تواند خروجی `systemctl status` و `journalctl` همان سرویس را ببیند.

---

## Subscription Page

صفحه Subscription کاربر شامل اطلاعات زیر است:

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
- اطلاعات اتصال سایر پروتکل‌ها

برای امنیت بیشتر، محتوای خام فایل‌های OpenVPN و WireGuard نمایش داده نمی‌شود و فقط لینک دانلود ارائه می‌شود.

---

## محاسبه مصرف و محدودیت حجم

IronPanel مصرف کاربران را با دقت Byte ذخیره و محاسبه می‌کند.

برای OpenVPN:

- استفاده از `status.log`
- استفاده از hookهای اتصال و قطع اتصال
- Sync مصرف با timer اختصاصی

برای WireGuard:

- خواندن مصرف از `wg show wg0 transfer`
- شناسایی Peer بر اساس کلید عمومی

فعال‌سازی تایمر Sync:

```bash
sudo systemctl enable --now ironpanel-usage-sync.timer
sudo systemctl status ironpanel-usage-sync.timer
```

مشاهده لاگ:

```bash
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
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

یا از فایل ZIP:

```bash
unzip Ironpanel_v15_5.zip
cd ironpanel_v15_5
sudo bash upgrade.sh
```

---

## دستورات مهم

وضعیت پنل:

```bash
sudo systemctl status ironpanel
```

Restart پنل:

```bash
sudo systemctl restart ironpanel
```

Restart ربات فروش:

```bash
sudo systemctl restart ironpanel-sales-bot
sudo systemctl status ironpanel-sales-bot
```

Restart OpenVPN:

```bash
sudo systemctl restart openvpn-server@server
```

ترمیم OpenVPN:

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
```

مشاهده لاگ OpenVPN Auth:

```bash
sudo tail -n 100 /var/log/openvpn/ironpanel-auth.log
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

## API

IronPanel دارای API کامل برای اتصال به سایت فروش، ربات، CRM، Billing System و ابزارهای شخص ثالث است.

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

## نکات امنیتی

- پنل را فقط روی سرور تمیز و قابل اعتماد نصب کنید.
- رمز عبور مدیر را قوی انتخاب کنید.
- 2FA را فعال کنید.
- API Key و License Key را عمومی منتشر نکنید.
- فایل‌های گواهی و کانفیگ کاربران را داخل GitHub قرار ندهید.
- فقط پورت‌های ضروری را باز نگه دارید.
- از Backup دوره‌ای استفاده کنید.
- لاگ‌ها را مرتب بررسی کنید.
- از نسخه‌های جدید پنل استفاده کنید.

---

## استفاده قانونی

این پروژه فقط برای مدیریت قانونی زیرساخت VPN طراحی شده است. مسئولیت استفاده از این نرم‌افزار بر عهده کاربر نهایی است.

---

# 🇺🇸 English

## Overview

**IronPanel** is a modern multi‑protocol VPN management and sales platform for VPN providers, server administrators, resellers and infrastructure teams.

It provides a unified interface for user management, VPN configuration generation, traffic accounting, subscription delivery, server monitoring, sales automation, licensing, updates, health checks and multi‑server operations.

---

## Main Features

- Modern responsive dashboard
- Live CPU, RAM, Swap, Disk and Network monitoring
- Clean license and version status cards
- GitHub version checking
- Update Manager with one‑click update flow
- VPN user management
- Create, edit, delete, renew and disable users
- Reset user traffic
- Unlimited traffic and expiration with value `0`
- Real traffic accounting
- Automatic quota enforcement
- Online users page
- User Subscription page
- OpenVPN and WireGuard files downloadable only from Subscription page
- Raw OpenVPN and WireGuard configs are hidden for security
- Tunnel Host support
- TCP / UDP selection where supported
- Automatic VPN core installation and repair
- Health Check / Repair with service error details
- Telegram sales bot for IronPanel
- Manual payment workflow
- Sales plan management by the registered sales admin
- Trial control by admin
- Ticket system
- Reseller management
- Billing and order modules
- Backup / Restore
- Auto Backup
- Multi Server and Node Management
- Cluster / HA and Load Balancer
- Firewall Manager
- DNS Manager
- Domain Manager
- SSL Manager
- Security Center
- Login History
- IP Whitelist
- Fail2Ban Integration
- 2FA / TOTP
- API v1 and API v2
- Full API documentation
- LicensePanel integration

---

## Supported Protocols

| Protocol | Status | Description |
|---|---:|---|
| OpenVPN | ✅ | Certificate‑Only authentication |
| WireGuard | ✅ | Dedicated peer and config generation |
| Cisco AnyConnect / Ocserv | ✅ | AnyConnect compatible user management |
| L2TP/IPsec | ✅ | StrongSwan and xl2tpd support |

---

## OpenVPN Fix in v15.5

Version **v15.5** fixes OpenVPN `User authentication failed` issues in some clients.

Fixes include:

- Certificate‑Only OpenVPN authentication
- Removal of legacy username/password dependency
- Improved `client-connect` and `client-disconnect` hooks
- OpenVPN repair helper script
- Preventing valid users from being rejected when session or usage sync fails

Repair OpenVPN after update:

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
sudo systemctl restart openvpn-server@server
sudo systemctl restart ironpanel
```

Then download a fresh OpenVPN file from the user Subscription page.

---

## License System

IronPanel uses online license verification and enables or disables features based on the license type.

Default License Server:

```text
http://license.skyshield.space:8002
```

### License Types

| License Type | Features |
|---|---|
| `beginer` | Nodes, Sales Bot, Billing and Network modules are disabled |
| `plus` | All modules enabled except Sales Bot, Billing and Network |
| `pro` | All modules enabled except Billing |
| `admin` | All features enabled |
| `trial` | All features enabled for 7 days |

Regular licenses can be issued for 1, 3, 6 or 12 months.

---

## License Purchase / Renewal

For license purchase or renewal, contact Telegram support:

```text
https://t.me/unknown_eng
```

---

## LicensePanel Sales Bot Flow

```text
Buy License
↓
Show short license type descriptions
↓
Select license type: beginer / plus / pro / admin
↓
Select duration: 1 / 3 / 6 / 12 months
↓
Show manual payment instructions
↓
User sends payment receipt
↓
Admin approves
↓
License is generated and sent to the user
```

---

## Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

Manual installation:

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

From ZIP package:

```bash
unzip Ironpanel_v15_5.zip
cd ironpanel_v15_5
sudo bash upgrade.sh
```

---

## Useful Commands

```bash
sudo systemctl status ironpanel
sudo systemctl restart ironpanel
sudo systemctl restart ironpanel-sales-bot
sudo systemctl restart openvpn-server@server
sudo systemctl restart wg-quick@wg0
sudo systemctl restart ocserv
sudo systemctl restart strongswan
sudo systemctl restart xl2tpd
```

OpenVPN repair:

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
```

OpenVPN auth logs:

```bash
sudo tail -n 100 /var/log/openvpn/ironpanel-auth.log
```

Usage sync status:

```bash
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

---

## API Documentation

```text
docs/API_GUIDE.md
docs/openapi.yaml
```

Example:

```bash
curl -H "X-API-KEY: YOUR_API_KEY" \
  http://YOUR_SERVER/api/v1/users
```

---

## Security Notes

- Use a clean Ubuntu 22.04 server.
- Use strong admin passwords.
- Enable 2FA.
- Keep API keys and license keys private.
- Never publish VPN certificates or private keys.
- Enable firewall rules.
- Use backups regularly.
- Keep the panel updated.

---

## Legal Notice

This project is intended only for lawful VPN infrastructure management. The end user is responsible for deployment and usage.

---

## Author & Support

```text
GitHub: https://github.com/Unknown-sir
Support: https://t.me/unknown_eng
```

<div align="center">

Made for professional VPN infrastructure management.

</div>

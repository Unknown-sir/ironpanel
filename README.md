<div align="center">

# IronPanel v16.5

### پنل حرفه‌ای مدیریت، فروش و تحویل کانفیگ VPN با پشتیبانی کامل Xray / V2Ray

**OpenVPN · WireGuard · Cisco AnyConnect/Ocserv · L2TP/IPsec · Xray Core · VLESS · VMess · Trojan · Shadowsocks**

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

</div>

---

## معرفی

**IronPanel** یک پنل مدیریتی مدرن برای راه‌اندازی، مدیریت، فروش و مانیتورینگ سرویس‌های VPN است. این نسخه علاوه بر پروتکل‌های کلاسیک مثل OpenVPN، WireGuard، Cisco AnyConnect/Ocserv و L2TP/IPsec، از **Xray Core** به‌صورت کامل پشتیبانی می‌کند و می‌تواند کانفیگ‌های سازگار با کلاینت‌های V2Ray، Hiddify، Nekoray، v2rayNG، Sing-box و Clash Meta را بسازد و تحویل دهد.

در نسخه **v16.5**، ربات فروش داخلی IronPanel با امکانات جدید پنل همگام شده است؛ یعنی مدیر می‌تواند پلن‌هایی مخصوص فروش کانفیگ **Xray / V2Ray** تعریف کند و کاربر پس از تأیید پرداخت دستی، لینک Subscription و فایل `xray.txt` را مستقیماً از ربات دریافت کند.

---

## قابلیت‌های اصلی

### مدیریت چندپروتکلی VPN

- OpenVPN با کانفیگ certificate-only
- WireGuard با فایل کانفیگ و QR Code
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray Core با پروفایل‌های پیشرفته
- تحویل کانفیگ از طریق صفحه Subscription
- محدودیت حجم، زمان و تعداد اتصال
- غیرفعال‌سازی خودکار کاربر بعد از اتمام حجم یا انقضا

### Xray / V2Ray Core

IronPanel v16.5 از Xray به‌صورت کامل پشتیبانی می‌کند و مدیر فقط **یک نوع کانفیگ فعال** را انتخاب می‌کند؛ سپس همان نوع کانفیگ در صفحه Subscription و ربات فروش به کاربر تحویل داده می‌شود.

پروفایل‌های قابل انتخاب:

- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + TCP بدون TLS
- VLESS + WebSocket بدون TLS
- VLESS + gRPC بدون TLS
- VLESS + gRPC + TLS
- Trojan + TLS
- Trojan + TCP بدون TLS
- VMess + WebSocket
- VMess + TCP بدون TLS
- Shadowsocks AEAD / 2022

امکانات Xray:

- ساخت UUID اختصاصی برای هر کاربر
- ساخت فایل `xray.txt` قابل Import در کلاینت‌ها
- ساخت لینک خام `vless://`، `vmess://`، `trojan://` یا `ss://`
- Reality Key Generator
- تنظیم SNI، Dest، Short ID، Fingerprint و Flow
- تنظیم WebSocket Path و Host
- تنظیم gRPC Service Name
- تنظیم DNS، Routing، Sniffing و Log Level
- Stats API برای محاسبه مصرف
- Health Check و Repair مخصوص Xray
- بازسازی خودکار کانفیگ Xray بعد از تغییر کاربر یا پلن

### ربات فروش IronPanel

ربات فروش داخلی برای فروش مستقیم سرویس به کاربران تلگرام طراحی شده است.

امکانات کاربر:

- خرید سرویس VPN
- خرید مستقیم کانفیگ Xray / V2Ray
- دریافت تست رایگان
- مشاهده سرویس‌های فعال
- دریافت لینک Subscription
- دریافت فایل `xray.txt` از ربات
- تمدید سرویس
- ارسال رسید پرداخت دستی
- ارتباط با پشتیبانی

امکانات مدیر داخل ربات:

- ساخت پلن با دکمه‌های شیشه‌ای
- تعریف نام، زمان، حجم، قیمت و واحد پول پلن
- انتخاب نوع کانفیگ پلن با دکمه:
  - فقط Xray / V2Ray
  - همه پروتکل‌ها
  - کلاسیک بدون Xray
  - انتخاب دستی پروتکل‌ها
- مشاهده سفارش‌ها
- تأیید یا رد رسید پرداخت
- مشاهده وضعیت Xray / V2Ray
- تنظیم تست رایگان
- تنظیم متن پرداخت دستی
- مشاهده آمار فروش

### سیستم پرداخت دستی

- نمایش متن پرداخت به کاربر
- دریافت تصویر یا فایل رسید
- ارسال رسید برای مدیران فروش
- تأیید یا رد پرداخت از داخل ربات یا پنل
- ساخت خودکار کاربر VPN پس از تأیید پرداخت
- ارسال Subscription و کانفیگ Xray / V2Ray بعد از تأیید

### LicensePanel

LicensePanel برای مدیریت لایسنس‌های IronPanel استفاده می‌شود.

نوع لایسنس‌ها:

| نوع لایسنس | توضیح |
|---|---|
| Beginer | بخش‌های Nodes، ربات فروش، مالی و شبکه غیرفعال هستند؛ Xray فعال است. |
| Plus | همه بخش‌های اصلی فعال هستند؛ ربات فروش، مالی و شبکه غیرفعال هستند؛ Xray فعال است. |
| Pro | همه بخش‌ها فعال هستند غیر از مالی؛ Xray فعال است. |
| Admin License | همه بخش‌ها فعال هستند. |
| Trial | تست ۷ روزه با همه امکانات فعال. |

مدت لایسنس‌ها:

- ۱ ماهه
- ۳ ماهه
- ۶ ماهه
- ۱۲ ماهه
- Trial هفت‌روزه

ربات فروش لایسنس ابتدا توضیح کوتاه انواع لایسنس را نمایش می‌دهد، سپس کاربر نوع لایسنس را انتخاب می‌کند، بعد مدت را انتخاب می‌کند و در نهایت وارد پرداخت دستی می‌شود.

### داشبورد و مانیتورینگ

- نمایش مصرف CPU، RAM، Swap و Disk
- نمایش وضعیت سرویس‌ها
- وضعیت لایسنس و روزهای باقی‌مانده
- وضعیت نسخه و بررسی آپدیت از GitHub
- نمایش کاربران آنلاین
- نمایش مصرف کاربران
- لاگ‌ها و فعالیت‌ها
- Health Check / Repair

### سیستم آپدیت

- بررسی آخرین نسخه از GitHub
- نمایش وضعیت نسخه در داشبورد
- بخش Update Manager
- آپدیت پنل با دکمه از داخل پنل
- پشتیبانی از Release Channel

### امنیت

- ورود مدیر با رمز عبور
- پشتیبانی از 2FA و Recovery Code
- API Token
- محدودسازی امکانات بر اساس لایسنس
- بررسی IP، دامنه و Machine Binding در LicensePanel
- ثبت لاگ ورود و فعالیت‌ها

---

## ساختار پروژه

```text
ironpanel/
├── app/
│   ├── api/
│   ├── api_v2/
│   ├── core/
│   ├── services/
│   │   ├── license.py
│   │   ├── provisioning.py
│   │   └── xray.py
│   ├── templates/
│   └── web.py
├── bot/
│   ├── main.py
│   └── reminders.py
├── docs/
├── scripts/
│   ├── repair_openvpn.sh
│   ├── repair_xray.sh
│   ├── update_from_github.sh
│   └── vpn_core_status.sh
├── install.sh
├── upgrade.sh
├── requirements.txt
└── VERSION
```

---

## سرویس‌های systemd

IronPanel از سرویس‌های جداگانه برای پنل، ربات و هسته‌ها استفاده می‌کند:

```bash
systemctl status ironpanel
systemctl status ironpanel-sales-bot
systemctl status xray
systemctl status openvpn-server@server
systemctl status wg-quick@wg0
systemctl status ocserv
```

برای بررسی Xray:

```bash
sudo systemctl status xray --no-pager
sudo journalctl -u xray -n 100 --no-pager
sudo bash /opt/ironpanel/scripts/repair_xray.sh
```

---

## Subscription

هر کاربر از صفحه Subscription خود به این موارد دسترسی دارد:

- OpenVPN profile
- WireGuard profile
- Cisco AnyConnect information
- L2TP/IPsec information
- Xray / V2Ray profile
- فایل `xray.txt`
- لینک قابل استفاده در کلاینت‌های سازگار

در Xray، فقط همان پروفایلی که مدیر در بخش **Xray Core** انتخاب کرده است به کاربر تحویل داده می‌شود.

---

## Publish کردن پروژه روی GitHub

برای انتشار تمیز پروژه روی GitHub، بهتر است ساختار پروژه را مرتب نگه دارید و فایل‌های حساس را داخل ریپو قرار ندهید.

### 1. ساخت ریپو

در GitHub یک Repository جدید بسازید؛ برای مثال:

```text
ironpanel
```

### 2. آماده‌سازی پوشه پروژه

در سیستم خود داخل پوشه پروژه بروید:

```bash
cd ironpanel
```

فایل‌های حساس زیر نباید داخل GitHub قرار بگیرند:

```text
.env
*.db
*.sqlite
license.key
private.key
/etc/ironpanel/*
/var/log/*
*.pem
*.crt
*.key
```

### 3. نمونه `.gitignore`

```gitignore
__pycache__/
*.pyc
*.pyo
*.pyd
*.db
*.sqlite
*.log
.env
.venv/
venv/
instance/
profiles/
*.key
*.pem
*.crt
license.key
.DS_Store
```

### 4. ثبت فایل‌ها در Git

```bash
git init
git add .
git commit -m "Release IronPanel v16.5"
```

### 5. اتصال به GitHub

```bash
git branch -M main
git remote add origin https://github.com/USERNAME/ironpanel.git
git push -u origin main
```

به‌جای `USERNAME` نام کاربری GitHub خود را قرار دهید.

### 6. ساخت Release

در GitHub وارد بخش **Releases** شوید و یک Release جدید با Tag زیر بسازید:

```text
v16.5
```

برای فایل Release می‌توانید فایل ZIP نهایی پنل را پیوست کنید.

### 7. پیشنهاد برای README

فایل `README.md` را در ریشه پروژه قرار دهید تا GitHub آن را در صفحه اصلی ریپو نمایش دهد.

---

## نکات مهم امنیتی

- Bot Token تلگرام را داخل GitHub قرار ندهید.
- License Key را داخل ریپو نگذارید.
- کلیدهای TLS، Reality Private Key و فایل‌های دیتابیس را منتشر نکنید.
- قبل از پابلیک کردن ریپو، `.gitignore` را بررسی کنید.
- اگر اشتباهی توکن یا کلید خصوصی را منتشر کردید، فوراً آن را revoke و مجدد ایجاد کنید.

---

## وضعیت نسخه

آخرین نسخه این README برای:

```text
IronPanel v16.5
LicensePanel v16.5
```

تهیه شده است.

---

## پشتیبانی

برای گزارش مشکل، پیشنهاد قابلیت جدید یا مشارکت در توسعه، از GitHub Issues استفاده کنید.

</div>

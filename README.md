<div align="center">

# ⚡ IronPanel v16.5

### پنل حرفه‌ای مدیریت، فروش و مانیتورینگ سرویس‌های VPN و Xray

**IronPanel** یک پنل مدیریتی مدرن برای راه‌اندازی، مدیریت، فروش و کنترل سرویس‌های VPN چندپروتکلی است. این پنل از پروتکل‌های کلاسیک VPN و همچنین هسته‌ی پیشرفته **Xray / V2Ray** پشتیبانی می‌کند و برای فروشندگان سرویس، مدیران سرور، تیم‌های پشتیبانی و ارائه‌دهندگان VPN طراحی شده است.

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

</div>

---

## فهرست مطالب

- [معرفی](#معرفی)
- [امکانات اصلی](#امکانات-اصلی)
- [پروتکل‌های پشتیبانی‌شده](#پروتکلهای-پشتیبانیشده)
- [Xray Core](#xray-core)
- [ربات فروش IronPanel](#ربات-فروش-ironpanel)
- [LicensePanel](#licensepanel)
- [سطح دسترسی لایسنس‌ها](#سطح-دسترسی-لایسنسها)
- [نیازمندی‌های سرور](#نیازمندیهای-سرور)
- [پورت‌های پیشنهادی](#پورتهای-پیشنهادی)
- [نصب دستی IronPanel](#نصب-دستی-ironpanel)
- [نصب دستی LicensePanel](#نصب-دستی-licensepanel)
- [تنظیم فایل‌های محیطی](#تنظیم-فایلهای-محیطی)
- [مدیریت سرویس‌ها](#مدیریت-سرویسها)
- [تعمیر و عیب‌یابی](#تعمیر-و-عیبیابی)
- [ساخت و تحویل کانفیگ‌ها](#ساخت-و-تحویل-کانفیگها)
- [Subscription](#subscription)
- [امنیت](#امنیت)
- [ساختار پروژه](#ساختار-پروژه)
- [تغییرات مهم نسخه v16.5](#تغییرات-مهم-نسخه-v165)
- [سلب مسئولیت](#سلب-مسئولیت)

---

## معرفی

IronPanel برای مدیریت کامل سرویس‌های VPN طراحی شده و چند بخش اصلی دارد:

- پنل مدیریت کاربران و سرویس‌ها
- سیستم ساخت کانفیگ برای چند پروتکل
- داشبورد مانیتورینگ سرور
- سیستم لایسنس تجاری
- ربات فروش تلگرام برای فروش سرویس VPN
- پشتیبانی از Xray / V2Ray با کانفیگ‌های پیشرفته
- بخش تعمیر خودکار سرویس‌ها
- سیستم بروزرسانی پنل
- API برای اتصال ربات، سایت فروش یا ابزارهای خارجی

هدف IronPanel این است که مدیر بتواند از یک محیط واحد، کاربران، پروتکل‌ها، فروش، محدودیت حجم، زمان، وضعیت سرویس‌ها و وضعیت لایسنس را مدیریت کند.

---

## امکانات اصلی

### مدیریت کاربران

- ایجاد کاربر جدید
- ویرایش کاربر
- حذف کاربر
- فعال و غیرفعال‌سازی کاربر
- تعیین تاریخ انقضا
- تعیین محدودیت حجم
- ریست ترافیک مصرفی
- مشاهده مصرف آپلود، دانلود و مجموع مصرف
- مشاهده وضعیت آنلاین کاربران
- اعمال محدودیت مصرف و انقضا روی پروتکل‌های فعال

### داشبورد مدیریتی

- نمایش مصرف CPU
- نمایش مصرف RAM
- نمایش Swap
- نمایش Disk
- نمایش وضعیت سرویس‌های VPN
- نمایش وضعیت Xray
- نمایش وضعیت نسخه پنل
- نمایش وضعیت لایسنس
- نمایش زمان باقی‌مانده لایسنس
- کارت‌بندی وضعیت نسخه و لایسنس
- هشدار بروزرسانی در صورت وجود نسخه جدید

### Health Check / Repair

- بررسی وضعیت OpenVPN
- بررسی وضعیت WireGuard
- بررسی وضعیت Ocserv
- بررسی وضعیت L2TP/IPsec
- بررسی وضعیت Xray
- مشاهده خطای سرویس‌ها
- مشاهده لاگ systemd
- اجرای تعمیر خودکار سرویس‌ها
- تعمیر کانفیگ‌های خراب
- ساخت دوباره فایل‌های موردنیاز

### سیستم فروش

- تعریف پلن فروش
- تعیین قیمت پلن
- تعیین حجم پلن
- تعیین مدت پلن
- فعال یا غیرفعال کردن تست رایگان
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار سرویس بعد از تأیید پرداخت
- ارسال Subscription و کانفیگ به کاربر

---

## پروتکل‌های پشتیبانی‌شده

IronPanel از پروتکل‌های زیر پشتیبانی می‌کند:

| پروتکل | وضعیت | توضیح |
|---|---:|---|
| OpenVPN | فعال | ساخت فایل `.ovpn` اختصاصی برای هر کاربر |
| WireGuard | فعال | ساخت کانفیگ و QR Code |
| Cisco AnyConnect / Ocserv | فعال | اتصال با کلاینت AnyConnect / OpenConnect |
| L2TP/IPsec | فعال | مناسب کلاینت‌های داخلی سیستم‌عامل‌ها |
| Xray / V2Ray | فعال | پشتیبانی از کانفیگ‌های پیشرفته Xray |

---

## Xray Core

از نسخه v16 به بعد، هسته Xray به IronPanel اضافه شده و در نسخه v16.5 با ربات فروش و سیستم پلن‌ها هماهنگ شده است.

### ویژگی‌های Xray

- فعال برای تمام نوع لایسنس‌ها
- انتخاب فقط یک نوع کانفیگ فعال توسط مدیر
- تحویل فقط همان کانفیگ انتخاب‌شده به کاربر
- ساخت URI خام برای کلاینت‌ها
- ساخت فایل `xray.txt`
- ساخت QR Code
- پشتیبانی از Subscription
- اتصال به سیستم محدودیت حجم و زمان
- اتصال به Health Check / Repair
- اتصال به Usage Sync
- اتصال به ربات فروش IronPanel

### پروفایل‌های Xray

| پروفایل | TLS | توضیح |
|---|---:|---|
| VLESS + Reality + Vision | دارد | گزینه پیشرفته و مدرن برای Reality |
| VLESS + WebSocket + TLS | دارد | مناسب اتصال پشت CDN و وب‌سرور |
| Trojan + TLS | دارد | سازگار با بسیاری از کلاینت‌ها |
| VMess + WebSocket | اختیاری | مناسب کلاینت‌های V2Ray |
| Shadowsocks 2022 | اختیاری | سبک و سریع |
| VLESS + TCP بدون TLS | ندارد | کانفیگ ساده بدون TLS |
| VLESS + WebSocket بدون TLS | ندارد | مناسب شبکه‌های داخلی یا تانل‌ها |
| VLESS + gRPC بدون TLS | ندارد | مناسب سناریوهای gRPC |
| VMess + TCP بدون TLS | ندارد | حالت ساده VMess |
| Trojan + TCP بدون TLS | ندارد | حالت ساده Trojan |

### نکته مهم درباره Xray

مدیر پنل در بخش **Xray Core** فقط یک نوع کانفیگ فعال را انتخاب می‌کند. کاربر در صفحه Subscription یا در ربات فروش، فقط همان نوع کانفیگ را دریافت می‌کند و همه کانفیگ‌ها به کاربر تحویل داده نمی‌شود.

---

## ربات فروش IronPanel

IronPanel دارای ربات فروش تلگرام برای فروش سرویس VPN است. این ربات با امکانات جدید پنل، به‌خصوص Xray / V2Ray، هماهنگ شده است.

### امکانات ربات فروش

- خرید سرویس VPN
- خرید کانفیگ Xray / V2Ray
- مشاهده سرویس‌های فعال
- دریافت Subscription
- دریافت فایل OpenVPN
- دریافت فایل WireGuard
- دریافت کانفیگ Xray
- دریافت QR Code
- تمدید سرویس
- خرید حجم اضافه
- ارسال رسید پرداخت
- ثبت سفارش دستی
- تأیید سفارش توسط مدیر
- رد سفارش توسط مدیر
- اطلاع‌رسانی انقضا
- اطلاع‌رسانی مصرف حجم
- پشتیبانی از دکمه‌های شیشه‌ای تلگرام

### پلن‌های فروش در ربات

مدیر می‌تواند برای هر پلن مشخص کند:

- نام پلن
- قیمت
- واحد پول
- مدت سرویس
- حجم سرویس
- نوع سرویس قابل فروش
- وضعیت فعال یا غیرفعال بودن پلن
- فعال بودن تست رایگان

### نوع سرویس در پلن فروش

- فقط Xray / V2Ray
- همه پروتکل‌ها
- پروتکل‌های کلاسیک بدون Xray
- انتخاب دستی پروتکل‌ها

---

## LicensePanel

LicensePanel بخش جداگانه‌ای برای مدیریت لایسنس‌های IronPanel است. این پنل به مدیر اصلی اجازه می‌دهد لایسنس بسازد، تمدید کند، مسدود کند و وضعیت پنل‌های فعال را بررسی کند.

### امکانات LicensePanel

- ساخت لایسنس
- تمدید لایسنس
- تعلیق لایسنس
- مسدودسازی لایسنس
- مشاهده پنل‌های آنلاین
- مشاهده پنل‌های آفلاین
- اتصال به ربات فروش لایسنس
- فروش دستی لایسنس
- تعریف قیمت برای لایسنس‌ها
- تعریف مدت‌های ۱، ۳، ۶ و ۱۲ ماهه
- Trial هفت‌روزه
- ثبت لاگ بررسی لایسنس
- ارسال هشدار انقضا

### ربات فروش لایسنس

فلو خرید در ربات فروش لایسنس به این شکل است:

1. کاربر دکمه خرید لایسنس را می‌زند.
2. توضیح کوتاه انواع لایسنس نمایش داده می‌شود.
3. کاربر نوع لایسنس را انتخاب می‌کند.
4. کاربر مدت ۱، ۳، ۶ یا ۱۲ ماهه را انتخاب می‌کند.
5. اطلاعات پرداخت دستی نمایش داده می‌شود.
6. کاربر رسید پرداخت را ارسال می‌کند.
7. مدیر سفارش را تأیید یا رد می‌کند.
8. بعد از تأیید، لایسنس ساخته و برای کاربر ارسال می‌شود.

---

## سطح دسترسی لایسنس‌ها

| نوع لایسنس | توضیح | دسترسی‌ها |
|---|---|---|
| beginer | پلن پایه | بدون نودها، بدون ربات فروش، بدون مالی، بدون شبکه |
| plus | پلن متوسط | همه بخش‌ها به‌جز ربات فروش، مالی و شبکه |
| pro | پلن حرفه‌ای | همه بخش‌ها به‌جز مالی |
| admin license | کامل | همه بخش‌ها فعال |
| trial | تست ۷ روزه | همه بخش‌ها فعال به مدت ۷ روز |

### نکته درباره Xray

Xray در تمام نوع لایسنس‌ها فعال است و محدود به پلن خاصی نیست.

---

## نیازمندی‌های سرور

### سیستم‌عامل پیشنهادی

- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Debian 11
- Debian 12

### حداقل منابع

| منبع | مقدار پیشنهادی |
|---|---:|
| CPU | 1 Core |
| RAM | 1 GB |
| Disk | 15 GB |
| Network | IPv4 عمومی |

### منابع پیشنهادی برای استفاده تجاری

| منبع | مقدار پیشنهادی |
|---|---:|
| CPU | 2 Core یا بیشتر |
| RAM | 2 GB یا بیشتر |
| Disk | 30 GB یا بیشتر |
| Network | IPv4 عمومی + دامنه |

---

## پورت‌های پیشنهادی

| سرویس | پورت پیشنهادی | پروتکل |
|---|---:|---|
| IronPanel Web | 8000 | TCP |
| LicensePanel Web | 8002 | TCP |
| OpenVPN | 1194 | UDP یا TCP |
| WireGuard | 51820 | UDP |
| Ocserv | 443 | TCP/UDP |
| L2TP/IPsec | 500 / 4500 / 1701 | UDP |
| Xray | قابل تنظیم | TCP/gRPC/WS |

پورت‌ها از داخل تنظیمات پنل قابل تغییر هستند.

---

## نصب دستی IronPanel

این بخش برای نصب دستی پنل است و وابسته به اجرای یک دستور نصب آماده نیست. قبل از شروع، با کاربر `root` یا کاربری که دسترسی `sudo` دارد وارد سرور شوید.

### 1. آماده‌سازی سیستم

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  sqlite3 curl wget unzip git jq \
  iptables iproute2 net-tools \
  systemd ca-certificates openssl \
  nginx
```

### 2. ساخت مسیر نصب

```bash
sudo mkdir -p /opt/ironpanel
sudo mkdir -p /etc/ironpanel
sudo mkdir -p /var/lib/ironpanel
sudo mkdir -p /var/log/ironpanel
sudo chown -R root:root /opt/ironpanel /etc/ironpanel /var/lib/ironpanel /var/log/ironpanel
```

### 3. انتقال فایل‌های پروژه

اگر فایل پروژه را به سرور منتقل کرده‌اید، آن را باز کنید و محتوا را داخل مسیر نصب قرار دهید:

```bash
cd /root
unzip Ironpanel_v16_5.zip
sudo rsync -a ironpanel_v16_5/ /opt/ironpanel/
```

در صورتی که نام پوشه متفاوت بود، همان نام پوشه استخراج‌شده را جایگزین کنید.

### 4. ساخت محیط Python

```bash
cd /opt/ironpanel
sudo python3 -m venv .venv
sudo /opt/ironpanel/.venv/bin/pip install --upgrade pip wheel setuptools
sudo /opt/ironpanel/.venv/bin/pip install -r requirements.txt
```

### 5. ساخت فایل تنظیمات محیطی IronPanel

```bash
sudo nano /etc/ironpanel/ironpanel.env
```

نمونه تنظیمات:

```env
IRONPANEL_ENV=production
IRONPANEL_HOST=0.0.0.0
IRONPANEL_PORT=8000
IRONPANEL_SECRET_KEY=CHANGE_THIS_SECRET_KEY
IRONPANEL_DATABASE_URI=sqlite:////var/lib/ironpanel/ironpanel.db
IRONPANEL_ADMIN_USERNAME=admin
IRONPANEL_ADMIN_PASSWORD=CHANGE_THIS_PASSWORD
IRONPANEL_PUBLIC_HOST=your-domain.com
IRONPANEL_LICENSE_SERVER_URL=http://license.skyshield.space:8002
IRONPANEL_SUPPORT_URL=https://t.me/unknown_eng
```

سطح دسترسی فایل را محدود کنید:

```bash
sudo chmod 600 /etc/ironpanel/ironpanel.env
```

### 6. ساخت دیتابیس و اجرای مهاجرت‌ها

```bash
cd /opt/ironpanel
sudo set -a
sudo . /etc/ironpanel/ironpanel.env
sudo set +a
sudo /opt/ironpanel/.venv/bin/python -m app upgrade-db
```

اگر پروژه از Flask CLI استفاده می‌کند:

```bash
cd /opt/ironpanel
sudo set -a
sudo . /etc/ironpanel/ironpanel.env
sudo set +a
sudo /opt/ironpanel/.venv/bin/flask db upgrade
```

### 7. نصب سرویس systemd برای IronPanel

```bash
sudo nano /etc/systemd/system/ironpanel.service
```

محتوا:

```ini
[Unit]
Description=IronPanel Web Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/ironpanel
EnvironmentFile=/etc/ironpanel/ironpanel.env
ExecStart=/opt/ironpanel/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 app:create_app()
Restart=always
RestartSec=3
User=root
Group=root

[Install]
WantedBy=multi-user.target
```

فعال‌سازی سرویس:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ironpanel
sudo systemctl restart ironpanel
sudo systemctl status ironpanel --no-pager
```

### 8. نصب سرویس ربات فروش IronPanel

ابتدا فایل محیطی ربات را بسازید یا در همان فایل اصلی متغیرهای ربات را قرار دهید:

```bash
sudo nano /etc/ironpanel/ironpanel-bot.env
```

نمونه:

```env
IRONPANEL_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
IRONPANEL_BOT_ADMIN_IDS=123456789,987654321
IRONPANEL_API_BASE=http://127.0.0.1:8000
IRONPANEL_API_TOKEN=CHANGE_THIS_API_TOKEN
```

سرویس systemd:

```bash
sudo nano /etc/systemd/system/ironpanel-sales-bot.service
```

محتوا:

```ini
[Unit]
Description=IronPanel Sales Bot
After=network-online.target ironpanel.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/ironpanel
EnvironmentFile=/etc/ironpanel/ironpanel.env
EnvironmentFile=/etc/ironpanel/ironpanel-bot.env
ExecStart=/opt/ironpanel/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
```

فعال‌سازی:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ironpanel-sales-bot
sudo systemctl restart ironpanel-sales-bot
sudo systemctl status ironpanel-sales-bot --no-pager
```

### 9. نصب و آماده‌سازی OpenVPN

```bash
sudo apt install -y openvpn easy-rsa
sudo mkdir -p /etc/openvpn/server
sudo mkdir -p /var/log/openvpn
sudo mkdir -p /etc/ironpanel/openvpn
```

بعد از نصب پنل، از بخش OpenVPN داخل پنل تنظیمات را ذخیره کنید یا اسکریپت تعمیر را اجرا کنید:

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
sudo systemctl restart openvpn-server@server
sudo systemctl status openvpn-server@server --no-pager
```

### 10. نصب و آماده‌سازی WireGuard

```bash
sudo apt install -y wireguard wireguard-tools
sudo mkdir -p /etc/wireguard
sudo chmod 700 /etc/wireguard
```

سپس:

```bash
sudo bash /opt/ironpanel/scripts/repair_wireguard.sh
sudo systemctl restart wg-quick@wg0
sudo systemctl status wg-quick@wg0 --no-pager
```

### 11. نصب و آماده‌سازی Ocserv

```bash
sudo apt install -y ocserv
sudo mkdir -p /etc/ocserv
```

سپس:

```bash
sudo bash /opt/ironpanel/scripts/repair_ocserv.sh
sudo systemctl restart ocserv
sudo systemctl status ocserv --no-pager
```

### 12. نصب و آماده‌سازی L2TP/IPsec

```bash
sudo apt install -y strongswan xl2tpd ppp
```

سپس:

```bash
sudo bash /opt/ironpanel/scripts/repair_l2tp.sh
sudo systemctl restart strongswan-starter || sudo systemctl restart strongswan
sudo systemctl restart xl2tpd
```

### 13. نصب و آماده‌سازی Xray

```bash
sudo mkdir -p /usr/local/etc/xray
sudo mkdir -p /var/log/xray
sudo useradd --system --no-create-home --shell /usr/sbin/nologin xray 2>/dev/null || true
sudo chown -R xray:xray /var/log/xray
sudo chmod 750 /var/log/xray
```

اگر باینری Xray نصب نیست، آن را طبق روش رسمی یا بسته نصب‌شده در پروژه نصب کنید. پس از نصب:

```bash
sudo bash /opt/ironpanel/scripts/repair_xray.sh
sudo systemctl daemon-reload
sudo systemctl enable xray
sudo systemctl restart xray
sudo systemctl status xray --no-pager
```

برای بررسی کانفیگ:

```bash
sudo /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
```

### 14. فعال‌سازی IP Forwarding

```bash
echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-ironpanel.conf
sudo sysctl --system
```

### 15. تنظیم فایروال

نمونه با UFW:

```bash
sudo apt install -y ufw
sudo ufw allow 8000/tcp
sudo ufw allow 1194/udp
sudo ufw allow 51820/udp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw allow 500/udp
sudo ufw allow 4500/udp
sudo ufw allow 1701/udp
sudo ufw enable
```

در صورتی که پورت‌های پنل را تغییر داده‌اید، پورت‌های جدید را جایگزین کنید.

### 16. ورود به پنل

بعد از فعال شدن سرویس:

```text
http://SERVER_IP:8000
```

نام کاربری و رمز عبور همان مقادیری هستند که در فایل `/etc/ironpanel/ironpanel.env` ثبت شده‌اند.

---

## نصب دستی LicensePanel

LicensePanel برای ساخت و مدیریت لایسنس‌های IronPanel استفاده می‌شود.

### 1. آماده‌سازی مسیرها

```bash
sudo mkdir -p /opt/license-panel
sudo mkdir -p /etc/license-panel
sudo mkdir -p /var/lib/license-panel
sudo mkdir -p /var/log/license-panel
```

### 2. انتقال فایل‌ها

```bash
cd /root
unzip LicensePanel_v16_5.zip
sudo rsync -a license_panel_v16_5/ /opt/license-panel/
```

### 3. ساخت محیط Python

```bash
cd /opt/license-panel
sudo python3 -m venv .venv
sudo /opt/license-panel/.venv/bin/pip install --upgrade pip wheel setuptools
sudo /opt/license-panel/.venv/bin/pip install -r requirements.txt
```

### 4. ساخت فایل محیطی LicensePanel

```bash
sudo nano /etc/license-panel/license-panel.env
```

نمونه:

```env
LICENSE_PANEL_ENV=production
LICENSE_PANEL_HOST=0.0.0.0
LICENSE_PANEL_PORT=8002
LICENSE_PANEL_SECRET_KEY=CHANGE_THIS_SECRET_KEY
LICENSE_PANEL_DATABASE_URI=sqlite:////var/lib/license-panel/license-panel.db
LICENSE_PANEL_ADMIN_USERNAME=admin
LICENSE_PANEL_ADMIN_PASSWORD=CHANGE_THIS_PASSWORD
LICENSE_SALES_BOT_TOKEN=YOUR_LICENSE_SALES_BOT_TOKEN
LICENSE_SALES_BOT_ADMIN_IDS=123456789
LICENSE_PAYMENT_TEXT=شماره کارت یا توضیحات پرداخت را اینجا قرار دهید
LICENSE_SUPPORT_URL=https://t.me/unknown_eng
```

سطح دسترسی:

```bash
sudo chmod 600 /etc/license-panel/license-panel.env
```

### 5. ساخت دیتابیس

```bash
cd /opt/license-panel
sudo set -a
sudo . /etc/license-panel/license-panel.env
sudo set +a
sudo /opt/license-panel/.venv/bin/python -m app upgrade-db
```

### 6. ساخت سرویس LicensePanel

```bash
sudo nano /etc/systemd/system/license-panel.service
```

محتوا:

```ini
[Unit]
Description=LicensePanel Web Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/license-panel
EnvironmentFile=/etc/license-panel/license-panel.env
ExecStart=/opt/license-panel/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8002 app:create_app()
Restart=always
RestartSec=3
User=root
Group=root

[Install]
WantedBy=multi-user.target
```

فعال‌سازی:

```bash
sudo systemctl daemon-reload
sudo systemctl enable license-panel
sudo systemctl restart license-panel
sudo systemctl status license-panel --no-pager
```

### 7. ساخت سرویس ربات فروش لایسنس

```bash
sudo nano /etc/systemd/system/license-sales-bot.service
```

محتوا:

```ini
[Unit]
Description=LicensePanel Sales Bot
After=network-online.target license-panel.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/license-panel
EnvironmentFile=/etc/license-panel/license-panel.env
ExecStart=/opt/license-panel/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
```

فعال‌سازی:

```bash
sudo systemctl daemon-reload
sudo systemctl enable license-sales-bot
sudo systemctl restart license-sales-bot
sudo systemctl status license-sales-bot --no-pager
```

---

## تنظیم فایل‌های محیطی

### IronPanel

مسیر اصلی:

```text
/etc/ironpanel/ironpanel.env
```

موارد مهم:

| متغیر | توضیح |
|---|---|
| IRONPANEL_PORT | پورت پنل |
| IRONPANEL_DATABASE_URI | مسیر دیتابیس |
| IRONPANEL_PUBLIC_HOST | دامنه یا IP عمومی |
| IRONPANEL_LICENSE_SERVER_URL | آدرس LicensePanel |
| IRONPANEL_SUPPORT_URL | لینک پشتیبانی |

### LicensePanel

مسیر اصلی:

```text
/etc/license-panel/license-panel.env
```

موارد مهم:

| متغیر | توضیح |
|---|---|
| LICENSE_PANEL_PORT | پورت پنل لایسنس |
| LICENSE_PANEL_DATABASE_URI | مسیر دیتابیس |
| LICENSE_SALES_BOT_TOKEN | توکن ربات فروش لایسنس |
| LICENSE_PAYMENT_TEXT | متن پرداخت دستی |
| LICENSE_SUPPORT_URL | لینک پشتیبانی |

---

## مدیریت سرویس‌ها

### IronPanel

```bash
sudo systemctl status ironpanel --no-pager
sudo systemctl restart ironpanel
sudo journalctl -u ironpanel -n 100 --no-pager
```

### ربات فروش IronPanel

```bash
sudo systemctl status ironpanel-sales-bot --no-pager
sudo systemctl restart ironpanel-sales-bot
sudo journalctl -u ironpanel-sales-bot -n 100 --no-pager
```

### LicensePanel

```bash
sudo systemctl status license-panel --no-pager
sudo systemctl restart license-panel
sudo journalctl -u license-panel -n 100 --no-pager
```

### ربات فروش لایسنس

```bash
sudo systemctl status license-sales-bot --no-pager
sudo systemctl restart license-sales-bot
sudo journalctl -u license-sales-bot -n 100 --no-pager
```

### Xray

```bash
sudo systemctl status xray --no-pager
sudo systemctl restart xray
sudo journalctl -u xray -n 100 --no-pager
```

---

## تعمیر و عیب‌یابی

### تعمیر OpenVPN

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
sudo systemctl restart openvpn-server@server
```

### تعمیر WireGuard

```bash
sudo bash /opt/ironpanel/scripts/repair_wireguard.sh
sudo systemctl restart wg-quick@wg0
```

### تعمیر Ocserv

```bash
sudo bash /opt/ironpanel/scripts/repair_ocserv.sh
sudo systemctl restart ocserv
```

### تعمیر L2TP/IPsec

```bash
sudo bash /opt/ironpanel/scripts/repair_l2tp.sh
sudo systemctl restart xl2tpd
```

### تعمیر Xray

```bash
sudo bash /opt/ironpanel/scripts/repair_xray.sh
sudo systemctl daemon-reload
sudo systemctl restart xray
sudo systemctl status xray --no-pager
```

### تست کانفیگ Xray

```bash
sudo /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
```

### بررسی دسترسی لاگ Xray

```bash
sudo ls -lah /var/log/xray
sudo stat /var/log/xray/access.log
sudo journalctl -u xray -n 100 --no-pager
```

---

## ساخت و تحویل کانفیگ‌ها

IronPanel برای هر کاربر، بر اساس سرویس‌های فعال، کانفیگ اختصاصی تولید می‌کند.

### OpenVPN

- فایل اختصاصی `.ovpn`
- نام فایل مطابق نام کاربر
- اتصال certificate-based
- بدون نیاز به ورود username/password در کلاینت

### WireGuard

- فایل کانفیگ
- QR Code
- کلید اختصاصی برای هر کاربر

### Ocserv

- اطلاعات اتصال AnyConnect / OpenConnect
- اتصال با نام کاربری کاربر

### L2TP/IPsec

- اطلاعات اتصال L2TP
- PSK قابل تنظیم

### Xray / V2Ray

- فایل `xray.txt`
- لینک خام اتصال
- QR Code
- سازگار با کلاینت‌هایی مانند v2rayNG، Hiddify، Nekoray، Sing-box و Clash Meta

---

## Subscription

صفحه Subscription برای تحویل تنظیمات به کاربر استفاده می‌شود.

موارد قابل تحویل:

- فایل OpenVPN
- فایل WireGuard
- QR Code WireGuard
- اطلاعات Ocserv
- اطلاعات L2TP/IPsec
- فایل Xray
- لینک Xray
- QR Code Xray
- لینک Subscription کلی

در Xray فقط همان پروفایل فعال‌شده توسط مدیر به کاربر تحویل داده می‌شود.

---

## امنیت

برای استفاده امن‌تر:

- رمز عبور پیش‌فرض را تغییر دهید.
- توکن ربات‌ها را محرمانه نگه دارید.
- فایل‌های `.env` را عمومی نکنید.
- دسترسی فایل‌های محیطی را روی `600` قرار دهید.
- پورت‌های غیرضروری را ببندید.
- برای پنل از HTTPS استفاده کنید.
- از دیتابیس بکاپ منظم بگیرید.
- لاگ‌های سرویس‌ها را بررسی کنید.

### فایل‌های حساس

```text
/etc/ironpanel/ironpanel.env
/etc/ironpanel/ironpanel-bot.env
/etc/license-panel/license-panel.env
/var/lib/ironpanel/ironpanel.db
/var/lib/license-panel/license-panel.db
/usr/local/etc/xray/config.json
```

---

## ساختار پروژه

```text
ironpanel/
├── app/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   ├── static/
│   └── models/
├── bot/
│   ├── handlers/
│   ├── keyboards/
│   ├── services/
│   └── main.py
├── scripts/
│   ├── repair_openvpn.sh
│   ├── repair_wireguard.sh
│   ├── repair_ocserv.sh
│   ├── repair_l2tp.sh
│   └── repair_xray.sh
├── docs/
├── systemd/
├── requirements.txt
├── README.md
└── CHANGELOG.md
```

---

## تغییرات مهم نسخه v16.5

- هماهنگ‌سازی ربات فروش IronPanel با Xray / V2Ray
- اضافه شدن فروش کانفیگ Xray از داخل ربات
- اضافه شدن نوع سرویس در پلن فروش
- تحویل فایل `xray.txt` از طریق ربات
- ارسال کانفیگ قابل import برای کلاینت‌های رایج
- هماهنگ‌سازی LicensePanel با قابلیت‌های جدید
- فعال بودن Xray برای تمام نوع لایسنس‌ها
- حفظ مدل انتخاب یک پروفایل Xray توسط مدیر
- بهبود خروجی Subscription
- بهبود تعمیر Xray و سرویس systemd
- حفظ پروفایل‌های بدون TLS
- بهبود مستندات پروژه

---

## سلب مسئولیت

IronPanel یک ابزار مدیریتی برای مدیریت سرور و سرویس‌های VPN است. مسئولیت استفاده از این پروژه، رعایت قوانین کشور محل استفاده، سیاست‌های دیتاسنتر و شرایط سرویس‌دهنده اینترنت بر عهده کاربر نهایی است.

---

<div align="center">

**IronPanel v16.5**  
ساخته‌شده برای مدیریت حرفه‌ای VPN، فروش سرویس و کنترل کامل کاربران

</div>

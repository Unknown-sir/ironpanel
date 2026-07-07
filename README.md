<div align="center">

# ⚡ IronPanel v16.5

### پنل حرفه‌ای مدیریت، فروش و مانیتورینگ سرویس‌های VPN، Xray و V2Ray

**IronPanel** یک پنل مدیریتی مدرن برای راه‌اندازی، کنترل، فروش و مانیتورینگ سرویس‌های VPN چندپروتکلی است. این پروژه برای مدیران سرور، فروشندگان سرویس VPN، تیم‌های پشتیبانی و ارائه‌دهندگان سرویس طراحی شده و امکانات مدیریت کاربران، ساخت کانفیگ، کنترل مصرف، فروش تلگرامی، مانیتورینگ و بروزرسانی را در یک محیط واحد ارائه می‌دهد.

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-v16.5-blue">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-green">
  <img alt="VPN" src="https://img.shields.io/badge/VPN-Multi--Protocol-purple">
  <img alt="Xray" src="https://img.shields.io/badge/Xray%20%2F%20V2Ray-Advanced-orange">
</p>

</div>

---

## فهرست مطالب

- [معرفی](#معرفی)
- [امکانات اصلی](#امکانات-اصلی)
- [پروتکل‌های پشتیبانی‌شده](#پروتکلهای-پشتیبانیشده)
- [Xray Core و V2Ray](#xray-core-و-v2ray)
- [ربات فروش تلگرام](#ربات-فروش-تلگرام)
- [داشبورد و مانیتورینگ](#داشبورد-و-مانیتورینگ)
- [Subscription و تحویل کانفیگ](#subscription-و-تحویل-کانفیگ)
- [نصب از روی سرور](#نصب-از-روی-سرور)
- [تنظیمات بعد از نصب](#تنظیمات-بعد-از-نصب)
- [مدیریت سرویس‌ها](#مدیریت-سرویسها)
- [تعمیر و عیب‌یابی](#تعمیر-و-عیبیابی)
- [ساختار پروژه](#ساختار-پروژه)
- [پورت‌های پیشنهادی](#پورتهای-پیشنهادی)
- [امنیت](#امنیت)
- [تغییرات مهم v16.5](#تغییرات-مهم-v165)
- [سلب مسئولیت](#سلب-مسئولیت)

---

## معرفی

IronPanel برای مدیریت کامل سرویس‌های VPN طراحی شده است. مدیر پنل می‌تواند از طریق یک داشبورد واحد کاربران را بسازد، محدودیت حجم و زمان تعریف کند، پروتکل‌های فعال را کنترل کند، وضعیت سرویس‌ها را ببیند، کانفیگ بسازد، فروش تلگرامی انجام دهد و لینک Subscription در اختیار کاربر قرار دهد.

تمرکز نسخه جدید روی سه بخش مهم است:

1. **مدیریت چندپروتکلی VPN** شامل OpenVPN، WireGuard، Cisco AnyConnect / Ocserv و L2TP/IPsec  
2. **پشتیبانی کامل از Xray / V2Ray** با پروفایل‌های پیشرفته، بدون اینکه چند کانفیگ همزمان به کاربر تحویل داده شود  
3. **ربات فروش تلگرام** برای فروش سرویس VPN و کانفیگ‌های Xray / V2Ray با پرداخت دستی

---

## امکانات اصلی

### مدیریت کاربران

- ساخت کاربر جدید
- ویرایش اطلاعات کاربر
- حذف کاربر
- فعال یا غیرفعال کردن کاربر
- تعیین تاریخ انقضا
- تعیین محدودیت حجم
- حالت نامحدود برای حجم یا زمان
- ریست ترافیک مصرفی
- مشاهده مصرف آپلود، دانلود و مجموع مصرف
- مشاهده وضعیت آنلاین کاربران
- اعمال محدودیت حجم و انقضا روی پروتکل‌های فعال
- ساخت کانفیگ اختصاصی برای هر کاربر

### مدیریت پروتکل‌ها

- فعال یا غیرفعال کردن سرویس‌ها
- تنظیم پورت‌ها
- تنظیم IP یا دامنه اتصال
- تنظیم TLS، Reality، WebSocket، gRPC و TCP برای Xray
- تنظیم OpenVPN روی TCP یا UDP
- ساخت کانفیگ OpenVPN به‌صورت certificate-only
- ساخت فایل WireGuard و QR Code
- تحویل اطلاعات Cisco AnyConnect / Ocserv
- تحویل اطلاعات L2TP/IPsec
- تحویل لینک خام Xray / V2Ray برای کلاینت‌های سازگار

### کنترل مصرف و انقضا

- ثبت مصرف کاربران
- تفکیک آپلود و دانلود
- ریست مصرف
- غیرفعال‌سازی خودکار کاربر بعد از پایان حجم
- غیرفعال‌سازی خودکار کاربر بعد از پایان زمان
- سینک مصرف برای پروتکل‌های مختلف
- اتصال مصرف Xray به سیستم اصلی کاربران

---

## پروتکل‌های پشتیبانی‌شده

| پروتکل | نوع خروجی | توضیح |
|---|---|---|
| OpenVPN | فایل `.ovpn` | اتصال certificate-only بدون نیاز به ورود نام کاربری و رمز در کلاینت |
| WireGuard | فایل config و QR Code | مناسب موبایل و دسکتاپ |
| Cisco AnyConnect / Ocserv | اطلاعات اتصال | مناسب کلاینت‌های AnyConnect و OpenConnect |
| L2TP/IPsec | اطلاعات اتصال | سازگار با کلاینت‌های داخلی سیستم‌عامل‌ها |
| Xray / V2Ray | لینک خام، فایل `xray.txt` و QR Code | پشتیبانی از VLESS، VMess، Trojan و Shadowsocks |

---

## Xray Core و V2Ray

در IronPanel v16.5، هسته Xray به‌صورت کامل به پنل اضافه شده است. مدیر پنل از داخل بخش **Xray Core** فقط یک نوع کانفیگ فعال را انتخاب می‌کند و همان یک نوع کانفیگ به کاربر تحویل داده می‌شود. این کار باعث می‌شود کاربر سردرگم نشود و ساختار فروش سرویس هم مرتب‌تر بماند.

### پروفایل‌های قابل انتخاب

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

### تنظیمات پیشرفته Xray

- Reality SNI
- Reality Destination
- Reality Public Key
- Reality Private Key
- Short ID
- Fingerprint
- Flow
- TLS Certificate Path
- TLS Key Path
- WebSocket Path
- WebSocket Host
- gRPC Service Name
- DNS
- Routing
- Sniffing
- Log Level
- Stats API برای خواندن مصرف
- تست کانفیگ قبل از ری‌استارت Xray
- تعمیر دسترسی‌های systemd و لاگ‌ها

### خروجی Xray برای کاربر

در صفحه Subscription، خروجی Xray فقط شامل همان کانفیگی است که مدیر انتخاب کرده است:

```text
vless://...
vmess://...
trojan://...
ss://...
```

فایل `xray.txt` فقط شامل لینک خام کانفیگ است تا در کلاینت‌هایی مثل v2rayNG، Hiddify، Nekoray، Sing-box و Clash Meta بهتر شناسایی شود.

---

## ربات فروش تلگرام

IronPanel دارای ربات فروش تلگرام برای فروش سرویس VPN است. مدیر پنل می‌تواند از داخل پنل، توکن ربات، آیدی مدیران، متن پرداخت، پلن‌ها و تنظیمات فروش را ثبت کند.

### امکانات سمت کاربر

- مشاهده پلن‌ها
- خرید سرویس VPN
- خرید کانفیگ Xray / V2Ray
- انتخاب مدت سرویس
- انتخاب حجم سرویس
- مشاهده وضعیت سرویس فعال
- دریافت لینک Subscription
- دریافت کانفیگ Xray / V2Ray
- دریافت فایل OpenVPN
- دریافت فایل WireGuard
- مشاهده مصرف و زمان باقی‌مانده
- تمدید سرویس
- ارسال رسید پرداخت دستی
- ارتباط با پشتیبانی

### امکانات سمت مدیر در ربات

- مشاهده سفارش‌های در انتظار بررسی
- مشاهده رسید پرداخت
- تأیید سفارش
- رد سفارش
- ساخت خودکار کاربر بعد از تأیید پرداخت
- تمدید سرویس کاربر
- افزایش حجم
- فعال یا غیرفعال کردن کاربر
- ارسال پیام عمومی
- مشاهده آمار فروش
- مشاهده سرویس‌های فعال

### مدل فروش Xray / V2Ray

در نسخه v16.5، ربات فروش با قابلیت‌های جدید Xray هماهنگ شده است. مدیر هنگام ساخت پلن فروش می‌تواند مشخص کند که پلن مربوط به کدام دسته باشد:

- فقط Xray / V2Ray
- همه پروتکل‌ها
- پروتکل‌های کلاسیک بدون Xray
- انتخاب دستی پروتکل‌ها

بعد از تأیید پرداخت، ربات بر اساس پلن انتخابی، لینک Subscription و کانفیگ‌های مجاز را برای کاربر ارسال می‌کند.

---

## داشبورد و مانیتورینگ

داشبورد IronPanel برای نمایش سریع وضعیت سرور و سرویس‌ها طراحی شده است.

### موارد قابل نمایش

- مصرف CPU
- مصرف RAM
- مصرف Swap
- مصرف Disk
- تعداد کاربران
- کاربران فعال
- کاربران منقضی‌شده
- کاربران آنلاین
- وضعیت OpenVPN
- وضعیت WireGuard
- وضعیت Ocserv
- وضعیت L2TP/IPsec
- وضعیت Xray
- وضعیت ربات فروش
- وضعیت نسخه نصب‌شده
- بررسی بروزرسانی از مخزن پروژه

---

## Subscription و تحویل کانفیگ

هر کاربر می‌تواند از طریق صفحه Subscription کانفیگ‌های مجاز خودش را دریافت کند. این صفحه برای استفاده ساده کاربران نهایی طراحی شده است.

### خروجی‌های قابل ارائه

- فایل OpenVPN با نام کاربر
- فایل WireGuard
- QR Code وایرگارد
- اطلاعات Cisco AnyConnect / Ocserv
- اطلاعات L2TP/IPsec
- لینک Xray / V2Ray
- QR Code برای Xray / V2Ray
- لینک Subscription قابل استفاده در کلاینت‌های سازگار

در بخش Xray، فقط یک کانفیگ انتخاب‌شده توسط مدیر تحویل داده می‌شود، نه همه پروفایل‌ها.

---

## نصب از روی سرور

برای نصب IronPanel روی سرور، ابتدا وارد سرور لینوکسی خود شوید و پروژه را از مخزن GitHub دریافت کنید.

### 1. بروزرسانی سیستم و نصب ابزارهای پایه

```bash
sudo apt update
sudo apt install -y git curl wget unzip ca-certificates
```

### 2. دانلود پروژه از GitHub روی سرور

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

### 5. اجرای فایل نصب

```bash
sudo bash install.sh
```

در زمان نصب، اطلاعات لازم مثل پورت پنل، نام کاربری مدیر، رمز مدیر، دامنه یا IP سرور و تنظیمات اولیه از شما دریافت می‌شود.

### 6. ورود به پنل

بعد از پایان نصب، آدرس ورود به پنل در ترمینال نمایش داده می‌شود. معمولاً ساختار آدرس به این شکل است:

```text
http://SERVER-IP:PANEL-PORT
```

مقدار `SERVER-IP` را با IP یا دامنه سرور و مقدار `PANEL-PORT` را با پورتی که هنگام نصب انتخاب کرده‌اید جایگزین کنید.

---

## تنظیمات بعد از نصب

بعد از ورود به پنل، پیشنهاد می‌شود این موارد را بررسی و تنظیم کنید:

1. تنظیم دامنه یا IP اتصال کاربران
2. تنظیم پورت پنل
3. تنظیم پورت‌های OpenVPN، WireGuard، Ocserv، L2TP/IPsec و Xray
4. فعال یا غیرفعال کردن پروتکل‌های موردنیاز
5. انتخاب نوع کانفیگ فعال Xray
6. ساخت Reality Key در صورت استفاده از Reality
7. تنظیم متن پرداخت دستی برای ربات فروش
8. ثبت Bot Token ربات فروش
9. ثبت Telegram Admin ID مدیران فروش
10. ساخت پلن‌های فروش
11. بررسی وضعیت سرویس‌ها از بخش Health Check / Repair

---

## مدیریت سرویس‌ها

### IronPanel

```bash
sudo systemctl restart ironpanel
sudo systemctl status ironpanel --no-pager
sudo journalctl -u ironpanel -n 100 --no-pager
```

### ربات فروش IronPanel

```bash
sudo systemctl restart ironpanel-sales-bot
sudo systemctl status ironpanel-sales-bot --no-pager
sudo journalctl -u ironpanel-sales-bot -n 100 --no-pager
```

### Xray

```bash
sudo systemctl restart xray
sudo systemctl status xray --no-pager
sudo journalctl -u xray -n 100 --no-pager
```

### OpenVPN

```bash
sudo systemctl restart openvpn-server@server
sudo systemctl status openvpn-server@server --no-pager
sudo journalctl -u openvpn-server@server -n 100 --no-pager
```

### WireGuard

```bash
sudo systemctl restart wg-quick@wg0
sudo systemctl status wg-quick@wg0 --no-pager
```

### Ocserv

```bash
sudo systemctl restart ocserv
sudo systemctl status ocserv --no-pager
```

---

## تعمیر و عیب‌یابی

IronPanel دارای اسکریپت‌های تعمیر برای بخش‌های مختلف است. این اسکریپت‌ها برای اصلاح دسترسی‌ها، بازسازی کانفیگ‌ها و بررسی سرویس‌ها استفاده می‌شوند.

### تعمیر Xray

```bash
sudo bash /opt/ironpanel/scripts/repair_xray.sh
sudo systemctl daemon-reload
sudo systemctl restart xray
sudo systemctl status xray --no-pager
```

### تعمیر OpenVPN

```bash
sudo bash /opt/ironpanel/scripts/repair_openvpn.sh
sudo systemctl restart openvpn-server@server
```

### تعمیر دیتابیس

```bash
sudo bash /opt/ironpanel/scripts/repair_db.sh
sudo systemctl restart ironpanel
```

### مشاهده لاگ‌های مهم

```bash
sudo journalctl -u ironpanel -n 100 --no-pager
sudo journalctl -u xray -n 100 --no-pager
sudo journalctl -u ironpanel-sales-bot -n 100 --no-pager
sudo tail -n 100 /var/log/openvpn/ironpanel-auth.log
```

---

## ساختار پروژه

```text
ironpanel/
├── app/
│   ├── api/
│   ├── api_v2/
│   ├── core/
│   ├── services/
│   ├── static/
│   └── templates/
├── bot/
│   ├── handlers/
│   ├── keyboards/
│   └── services/
├── docs/
├── scripts/
│   ├── install_vpn_core.sh
│   ├── repair_openvpn.sh
│   ├── repair_xray.sh
│   ├── update_from_github.sh
│   └── ironpanelctl
├── systemd/
├── install.sh
├── upgrade.sh
├── requirements.txt
├── run.py
└── VERSION
```

---

## پورت‌های پیشنهادی

| سرویس | پورت پیشنهادی | نوع |
|---|---:|---|
| IronPanel Web | 8000 | TCP |
| OpenVPN UDP | 1194 | UDP |
| OpenVPN TCP | 443 یا 1194 | TCP |
| WireGuard | 51820 | UDP |
| Ocserv / AnyConnect | 443 | TCP/UDP |
| L2TP | 1701 | UDP |
| IPsec IKE | 500 | UDP |
| IPsec NAT-T | 4500 | UDP |
| Xray | قابل تنظیم | TCP/UDP بر اساس پروفایل |

در صورت استفاده از فایروال، پورت‌های فعال را باز کنید.

---

## امنیت

برای استفاده امن‌تر از IronPanel این موارد پیشنهاد می‌شود:

- رمز عبور مدیر را قوی انتخاب کنید.
- فقط پورت‌های لازم را باز نگه دارید.
- دسترسی SSH را محدود کنید.
- از دامنه و TLS معتبر برای سرویس‌های حساس استفاده کنید.
- فایل‌های کانفیگ و کلیدها را عمومی منتشر نکنید.
- از دیتابیس و تنظیمات پنل بکاپ بگیرید.
- توکن ربات تلگرام را در اختیار دیگران قرار ندهید.
- بعد از تغییرات مهم، وضعیت سرویس‌ها را از Health Check بررسی کنید.

---

## تغییرات مهم v16.5

- هماهنگ‌سازی ربات فروش IronPanel با Xray / V2Ray
- اضافه شدن فروش پلن‌های مخصوص Xray / V2Ray
- ارسال کانفیگ Xray / V2Ray از طریق ربات فروش
- ارسال فایل `xray.txt` با لینک خام و قابل import
- بهبود Subscription برای تحویل فقط یک نوع کانفیگ Xray انتخاب‌شده توسط مدیر
- بهبود Health Check / Repair برای Xray
- اصلاح سرویس systemd مربوط به Xray
- پشتیبانی از پروفایل‌های بدون TLS برای Xray
- بهبود سازگاری با v2rayNG، Hiddify، Nekoray، Sing-box و Clash Meta
- بهبود ساختار README و مستندات نصب از مخزن پروژه

---

## سلب مسئولیت

IronPanel یک ابزار مدیریتی برای راه‌اندازی و کنترل سرویس‌های شبکه و VPN است. مسئولیت استفاده از این پروژه، رعایت قوانین کشور محل استفاده، قوانین دیتاسنتر و سیاست‌های سرویس‌دهنده بر عهده استفاده‌کننده است.

---

<div align="center">

**IronPanel v16.5**  
ساخته‌شده برای مدیریت حرفه‌ای VPN، Xray و فروش سرویس از طریق تلگرام

</div>

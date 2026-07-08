<div dir="rtl" align="right">

# IronPanel v17

**IronPanel** یک پنل مدیریتی پیشرفته، چندپروتکلی و چندنودی برای مدیریت، فروش، مانیتورینگ و تحویل سرویس‌های VPN است. این پروژه برای مدیران سرور، فروشندگان سرویس VPN و تیم‌هایی طراحی شده که به یک سیستم کامل برای مدیریت کاربران، پروتکل‌ها، نودها، سابسکریپشن، ربات فروش، مسیریابی خروجی و پایش سلامت سرویس‌ها نیاز دارند.

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

---

## نمای کلی

IronPanel تا نسخه **v17** از یک پنل تک‌سروره ساده به یک پلتفرم کامل مدیریت VPN تبدیل شده است. این نسخه شامل مدیریت چند پروتکل، Xray/V2Ray پیشرفته، سیستم نود، Outbound Routing، ربات فروش، سابسکریپشن حرفه‌ای، مانیتورینگ زنده، بکاپ و ریستور، Bulk Action، API و داشبورد امنیتی مدرن است.

---

## امکانات اصلی

### مدیریت چند پروتکل

IronPanel از پروتکل‌های مختلف برای ساخت سرویس VPN پشتیبانی می‌کند:

- OpenVPN
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray / V2Ray
- VLESS
- VMess
- Trojan
- Shadowsocks
- Reality
- WebSocket
- gRPC
- TCP بدون TLS
- TLS / Reality / No TLS profiles

مدیر پنل می‌تواند پروتکل‌های فعال را مدیریت کند و برای هر کاربر خروجی مناسب را در صفحه Subscription ارائه دهد.

---

## Xray / V2Ray Core

در نسخه‌های 16 و 17 هسته Xray به‌صورت کامل به IronPanel اضافه شده است. مدیر پنل فقط یک نوع کانفیگ Xray را به‌عنوان کانفیگ فعال انتخاب می‌کند و کاربران فقط همان نوع کانفیگ را دریافت می‌کنند، نه همه کانفیگ‌ها.

### قابلیت‌های Xray

- انتخاب نوع کانفیگ فعال توسط مدیر
- ساخت لینک‌های استاندارد `vless://`، `vmess://`، `trojan://` و `ss://`
- خروجی خام مخصوص v2rayNG، Hiddify، Nekoray، Sing-box و Clash Meta
- تولید QR Code
- تست کانفیگ قبل از تحویل به کاربر
- ساخت خودکار UUID
- ساخت خودکار Reality Key و Short ID
- پشتیبانی از Reality Vision
- پشتیبانی از WebSocket + TLS
- پشتیبانی از WebSocket بدون TLS
- پشتیبانی از TCP بدون TLS
- پشتیبانی از gRPC
- نمایش وضعیت سرویس Xray در پنل
- Repair خودکار Xray
- ثبت مصرف کاربران Xray
- افزودن Xray به ربات فروش

---

## Subscription پیشرفته

صفحه Subscription یکی از بخش‌های اصلی IronPanel است. کاربر می‌تواند خروجی سرویس خود را به شکل قابل استفاده در کلاینت‌های مختلف دریافت کند.

### خروجی‌های قابل ارائه

- فایل OpenVPN
- فایل WireGuard
- QR Code برای WireGuard
- اطلاعات AnyConnect / Ocserv
- اطلاعات L2TP/IPsec
- لینک Xray / V2Ray
- فایل `xray.txt`
- خروجی Raw
- خروجی Hiddify
- خروجی Sing-box
- خروجی Clash Meta
- لینک Subscription اختصاصی
- Reset Token برای لینک Subscription

---

## سیستم نود در نسخه v17

نسخه v17 شامل Node System پیشرفته‌تر است. با این قابلیت می‌توان پنل اصلی را روی یک سرور نصب کرد و سرورهای دیگر را به‌عنوان Node به آن متصل نمود.

### قابلیت‌های Node System

- ساخت نود از داخل پنل اصلی
- تولید Node Token
- نصب Node Agent روی سرورهای دیگر
- اتصال امن نود به پنل اصلی
- نمایش Online / Offline بودن نودها
- Heartbeat دوره‌ای
- نمایش CPU، RAM، Disk و Traffic هر نود
- انتخاب پروتکل‌های فعال روی هر نود
- انتخاب نود هنگام ساخت کاربر
- انتقال کاربر بین نودها
- Bulk migration کاربران
- Health Check و Repair برای نودها
- نمایش لاگ Node Agent

---

## Outbound Routing

بخش Outbound Routing برای عبور دادن ترافیک پروتکل‌های پنل از یک خروجی خارجی استفاده می‌شود. مدیر می‌تواند یک یا چند کانفیگ خروجی تعریف کند و مشخص کند ترافیک کدام پروتکل‌ها از آن عبور کند.

### قابلیت‌ها

- تعریف Outbound با OpenVPN Client Config
- تعریف Outbound با لینک‌های Xray/V2Ray
- پشتیبانی از `vless://`، `vmess://`، `trojan://` و `ss://`
- تست اتصال قبل از اعمال
- انتخاب پروتکل‌های تحت پوشش Outbound
- Failover
- Kill Switch
- انتخاب Route Mode
- تست IP خروجی
- تست DNS Leak
- امکان فعال/غیرفعال‌سازی سریع Outbound

---

## ربات فروش تلگرام

IronPanel دارای ربات فروش داخلی برای فروش سرویس‌های VPN است. ربات فروش با امکانات نسخه 17 هماهنگ شده و می‌تواند سرویس‌های کلاسیک و Xray/V2Ray را به کاربران بفروشد.

### قابلیت‌های ربات فروش

- ثبت Bot Token از داخل پنل
- ثبت Telegram Admin IDs
- ساخت پلن فروش
- تعیین نام پلن، حجم، قیمت و مدت
- انتخاب پروتکل‌های قابل ارائه در پلن
- فروش سرویس Xray/V2Ray
- فروش سرویس کلاسیک بدون Xray
- فروش پلن همه‌پروتکل‌ها
- تست رایگان با محدودیت زمان و حجم
- جلوگیری از دریافت تست چندباره برای یک Telegram ID
- پرداخت دستی با ارسال رسید
- تأیید یا رد سفارش توسط مدیر
- ساخت خودکار کاربر بعد از تأیید سفارش
- ارسال Subscription بعد از خرید
- ارسال فایل Xray / V2Ray
- تمدید سرویس
- خرید حجم اضافه
- نمایش وضعیت سرویس کاربر
- پیام یادآوری انقضا و مصرف حجم

---

## مدیریت کاربران

IronPanel سیستم کامل مدیریت کاربران را ارائه می‌دهد.

### امکانات مدیریت کاربر

- ساخت کاربر
- ویرایش کاربر
- حذف کاربر
- فعال/غیرفعال‌سازی کاربر
- تمدید سرویس
- تغییر حجم
- تغییر تاریخ انقضا
- Reset Traffic
- محدودیت حجم
- محدودیت زمان
- 0 به‌عنوان نامحدود برای حجم یا زمان
- نمایش مصرف آپلود و دانلود
- نمایش وضعیت Online / Offline
- نمایش پروتکل‌های فعال کاربر
- دریافت کانفیگ‌های کاربر
- Bulk Actions
- تمدید گروهی
- حذف گروهی
- ریست ترافیک گروهی
- انتقال گروهی کاربران به نود دیگر

---

## مانیتورینگ و Health Check

نسخه v17 شامل مانیتورینگ پیشرفته و Live Logs است.

### بخش‌های مانیتورینگ

- وضعیت CPU
- وضعیت RAM
- وضعیت Disk
- وضعیت Swap
- وضعیت سرویس‌ها
- وضعیت OpenVPN
- وضعیت WireGuard
- وضعیت Ocserv
- وضعیت L2TP/IPsec
- وضعیت Xray
- وضعیت ربات فروش
- وضعیت Node Agent
- وضعیت Outbound
- وضعیت دیتابیس
- وضعیت GitHub Update
- Live Logs برای سرویس‌ها
- دکمه Repair برای سرویس‌ها

---

## Backup / Restore

IronPanel v17 دارای سیستم بکاپ و ریستور پیشرفته است.

### امکانات بکاپ

- بکاپ دیتابیس
- بکاپ کاربران
- بکاپ تنظیمات پنل
- بکاپ تنظیمات OpenVPN
- بکاپ تنظیمات WireGuard
- بکاپ تنظیمات Xray
- بکاپ تنظیمات Outbound
- بکاپ تنظیمات ربات فروش
- بکاپ Node Config
- دانلود بکاپ از پنل
- ریستور از فایل بکاپ
- بکاپ روزانه زمان‌بندی‌شده
- بکاپ قبل از آپدیت

---

## داشبورد و طراحی

طراحی IronPanel از نسخه 16.6 به سبک **Enterprise Security / SOC Dashboard** تغییر کرده است.

### ویژگی‌های UI

- تم تیره امنیتی
- کارت‌های مدرن و حرفه‌ای
- داشبورد وضعیت سلامت و ریسک
- نمایش وضعیت پروتکل‌ها
- نمایش کاربران آنلاین
- نمایش مصرف سیستم
- Topbar جدید
- Sidebar دسته‌بندی‌شده
- جدول‌ها و فرم‌های بازطراحی‌شده
- سازگاری با صفحات Xray، Outbound، Nodes و Monitoring

---

## API v17

IronPanel دارای API برای اتصال سرویس‌ها و سیستم‌های خارجی است.

### بخش‌های API

- Users API
- Subscription API
- Nodes API
- Monitoring API
- Outbound API
- Health API
- Sales Bot API
- Logs API
- Backup API

---

## ساختار سطح دسترسی لایسنس‌ها

IronPanel با ساختار لایسنس چندسطحی سازگار است. امکانات جدید نسخه 17 با لایسنس‌ها هماهنگ شده‌اند.

### انواع لایسنس

- Beginer
- Plus
- Pro
- Admin License
- Trial

### نکته مهم

در نسخه‌های جدید، قابلیت‌های پایه Xray و Outbound برای همه لایسنس‌ها قابل فعال‌سازی هستند، اما دسترسی به بعضی بخش‌های مدیریتی مثل نودها، مالی، فروش یا شبکه می‌تواند بر اساس نوع لایسنس کنترل شود.

---

# نصب دستی پنل اصلی

این بخش نصب دستی پنل اصلی را توضیح می‌دهد. این روش شامل دانلود پروژه از GitHub، ورود به پوشه پروژه و اجرای فایل نصب است.

## پیش‌نیازها

- Ubuntu 20.04 / 22.04 / 24.04 یا Debian 11 / 12
- دسترسی root یا sudo
- دامنه یا IP معتبر برای پنل
- دسترسی اینترنت روی سرور
- باز بودن پورت‌های مورد نیاز

## دریافت پروژه از GitHub

```bash
sudo apt update
sudo apt install -y git curl unzip
cd /opt
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
```

## اجرای نصب پنل

```bash
sudo bash install.sh
```

در زمان نصب، اطلاعات مورد نیاز مثل پورت پنل، نام کاربری مدیر، رمز عبور، دامنه یا IP پنل و تنظیمات اولیه پرسیده می‌شود.

## بررسی وضعیت سرویس‌ها

```bash
sudo systemctl status ironpanel --no-pager
sudo systemctl status ironpanel-sales-bot --no-pager
sudo systemctl status xray --no-pager
```

## ری‌استارت سرویس‌ها

```bash
sudo systemctl restart ironpanel
sudo systemctl restart ironpanel-sales-bot
sudo systemctl restart xray
```

## مسیرهای مهم

```text
/opt/ironpanel
/etc/ironpanel/ironpanel.env
/usr/local/etc/xray/config.json
/var/log/ironpanel
/var/log/xray
```

---

# نصب دستی نود

برای استفاده از چند سرور، ابتدا پنل اصلی را نصب کنید، سپس از داخل پنل یک نود بسازید و Node Token دریافت کنید.

## ساخت نود در پنل اصلی

داخل پنل اصلی وارد مسیر زیر شوید:

```text
VPN و زیرساخت → Nodes → Add Node
```

اطلاعات زیر را وارد کنید:

```text
Node Name
Node IP / Domain
Location
Active Protocols
```

بعد از ذخیره، پنل یک **Node Token** ایجاد می‌کند.

## نصب Node Agent روی سرور نود

روی سرور نود دستورهای زیر را اجرا کنید:

```bash
sudo apt update
sudo apt install -y git curl unzip
cd /opt
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash scripts/install_node.sh
```

در زمان نصب نود، اطلاعات زیر را وارد کنید:

```text
Master Panel URL
Node Token
Node Public IP / Domain
Protocols
```

نمونه:

```text
Master Panel URL: https://panel.example.com
Node Token: NODE_TOKEN_HERE
Node Host: node1.example.com
Protocols: openvpn,wireguard,xray,ocserv,l2tp
```

## بررسی وضعیت نود

```bash
sudo systemctl status ironpanel-node --no-pager
sudo journalctl -u ironpanel-node -n 100 --no-pager
```

## ری‌استارت Node Agent

```bash
sudo systemctl restart ironpanel-node
```

## بررسی اتصال از پنل اصلی

بعد از نصب، به پنل اصلی برگردید و در بخش Nodes روی گزینه زیر بزنید:

```text
Check Connection
```

اگر همه چیز درست باشد وضعیت نود باید Online شود.

---

## پورت‌های پیشنهادی

```text
22/tcp      SSH
80/tcp      HTTP / ACME
443/tcp     HTTPS / TLS / Xray / Ocserv
443/udp     Ocserv UDP / QUIC profiles
1194/tcp    OpenVPN TCP
1194/udp    OpenVPN UDP
51820/udp   WireGuard
500/udp     IPsec
4500/udp    IPsec NAT-T
1701/udp    L2TP
8443/tcp    پنل یا سرویس سفارشی
```

نمونه باز کردن پورت‌ها با UFW:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw allow 1194/tcp
sudo ufw allow 1194/udp
sudo ufw allow 51820/udp
sudo ufw allow 500/udp
sudo ufw allow 4500/udp
sudo ufw allow 1701/udp
sudo ufw reload
```

---

## ساختار پیشنهادی پروژه

```text
ironpanel/
├── app/
│   ├── blueprints/
│   ├── services/
│   ├── templates/
│   └── static/
├── bot/
├── scripts/
├── docs/
├── systemd/
├── migrations/
├── install.sh
├── upgrade.sh
└── README.md
```

---

## مناسب برای چه کسانی است؟

- فروشندگان VPN
- مدیران سرور
- تیم‌های پشتیبانی شبکه
- ارائه‌دهندگان سرویس چندنودی
- کسانی که به پنل مدیریت چندپروتکلی نیاز دارند
- کسانی که فروش خودکار با ربات تلگرام می‌خواهند
- کسانی که Xray/V2Ray و OpenVPN/WireGuard را در یک پنل واحد می‌خواهند

---

## وضعیت پروژه

IronPanel v17 یک نسخه بزرگ با تمرکز بر چندنودی شدن، پایداری Xray/V2Ray، Outbound Routing، مانیتورینگ حرفه‌ای، Backup/Restore و Subscription پیشرفته است.

</div>

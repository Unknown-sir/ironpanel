<div align="center">

# ⚙️ IronPanel

### پنل حرفه‌ای مدیریت VPN، Proxy، کاربران، نودها و تونل‌های چندسروری

![IronPanel](https://s34.picofile.com/file/8490877984/Ironpanel.png)

**IronPanel** برای مدیریت متمرکز سرویس‌های VPN/Proxy، کاربران، سابسکریپشن‌ها، نمایندگان، نودها، SSL، DNS، محدودیت سرعت، مانیتورینگ و عملیات نگهداری سرور طراحی شده است.

</div>

---

## ✨ خلاصه قابلیت‌ها

IronPanel فقط یک پنل ساخت اکانت نیست؛ یک مرکز کنترل کامل برای مدیریت سرویس‌های چندپروتکلی و چندسروری است.

- مدیریت کاربران، حجم، تاریخ انقضا، محدودیت سرعت و دسترسی پروتکل‌ها
- ساخت کانفیگ و Subscription با QR Code و لینک اختصاصی
- پشتیبانی از چند پروتکل محبوب VPN و Proxy
- نصب، تعمیر و مانیتورینگ هسته‌ها از داخل پنل
- Auto SSL برای دامنه پنل و پروتکل‌های نیازمند گواهی
- DNS Manager، DNS Presets و WireGuard MTU
- Routing Rules، Outbound Rules و Speed Limits
- سیستم نمایندگان، محدودیت مصرف واقعی و ربات فروش اختصاصی
- Health Doctor، Safe Backup، Safe Restore و Safe Update
- Firewall IP/CIDR Ban با chain اختصاصی
- Node Agent، Node Gateway، Transparent Relay و Auto Sync
- نصب خودکار نود با SSH برای لایسنس‌های Pro و Admin

---

## 🚀 نصب سریع

روی سرور اصلی اجرا کنید:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

بعد از نصب، اطلاعات ورود و آدرس پنل در خروجی ترمینال نمایش داده می‌شود.

---

## 🔄 آپدیت از ترمینال

آپدیت سریع از GitHub:

```bash
sudo bash /opt/ironpanel/scripts/update_from_github.sh
```

آپدیت امن همراه با بکاپ، health check و لاگ کامل:

```bash
sudo bash /opt/ironpanel/scripts/safe_update.sh
```

---

## 🧩 پروتکل‌های پشتیبانی‌شده

| پروتکل | وضعیت | کاربرد | توضیح |
|---|:---:|---|---|
| OpenVPN | ✅ | عمومی و پایدار | خروجی `.ovpn`، مدیریت مصرف و auth hook |
| WireGuard | ✅ | سبک و سریع | DNS، MTU، peer management و QR |
| Cisco / Ocserv | ✅ | AnyConnect | مناسب موبایل و دسکتاپ |
| L2TP/IPsec | ✅ | کلاسیک | سازگار با کلاینت‌های داخلی سیستم‌عامل‌ها |
| PPTP | ✅ | Legacy | برای سناریوهای قدیمی و سازگاری خاص |
| Xray | ✅ | VLESS/Reality/TLS | Subscription، QR، inboundهای قابل مدیریت |
| Hysteria2 | ✅ | UDP پرسرعت | خروجی YAML و مناسب شبکه‌های پرنوسان |
| Telegram MTProto Proxy | ✅ | MTProto | secret اختصاصی و پورت قابل تنظیم |
| SSH | ✅ | SSH Tunnel | ساخت دسترسی SSH برای کاربران |

---

## 👥 مدیریت کاربران و سابسکریپشن

در IronPanel می‌توانید برای هر کاربر این موارد را مدیریت کنید:

- حجم کل، مصرف‌شده و باقی‌مانده
- تاریخ انقضا و وضعیت فعال/غیرفعال
- پروتکل‌های مجاز برای هر کاربر
- محدودیت سرعت کلی یا اختصاصی برای هر پروتکل
- Reset Traffic و تمدید سریع
- لینک Subscription و QR Code
- فایل‌های کانفیگ اختصاصی برای هر پروتکل
- نمایش آنلاین‌ها و sessionهای فعال در پروتکل‌های پشتیبانی‌شده

---

## 🧠 Smart Core Reload

IronPanel هنگام تغییر کاربر، همه سرویس‌ها را بی‌دلیل restart نمی‌کند. فقط همان پروتکلی که واقعاً تحت تأثیر تغییر قرار گرفته reload یا restart می‌شود.

نمونه‌ها:

- تغییر حجم یا تاریخ انقضا بدون restart سنگین
- WireGuard در صورت امکان با `wg syncconf`
- Xray/Hysteria2 فقط هنگام تغییر کاربران همان پروتکل
- کاهش قطعی کاربران هنگام ویرایش‌های روزمره

---

## 🛰️ Node Gateway و Transparent Relay

IronPanel برای معماری‌های چندسروری و تونلی طراحی شده است. در حالت Transparent Relay، کاربر همچنان به IP یا دامنه سرور اصلی وصل می‌شود، اما پنل اصلی پشت‌صحنه اتصال را به نود انتخابی منتقل می‌کند.

مسیر پیشنهادی برای سناریوهای تونلی:

```text
User / Iran Tunnel
        ↓
Main Panel Public Endpoint
        ↓
IronPanel Transparent Relay
        ↓
Selected Node
        ↓
IronPanel Transparent Relay
        ↓
User / Iran Tunnel
```

مزیت این مدل:

- کانفیگ کاربر همچنان آدرس سرور اصلی را دارد
- IP/Domain نود مستقیم به کاربر داده نمی‌شود
- مسیر رفت و برگشت برای تونل‌های واسط قابل کنترل‌تر است
- امکان Force کردن هر پروتکل به نود خاص وجود دارد
- Sync کانفیگ‌ها و کاربران روی نودها انجام می‌شود

---

## 🤖 نصب خودکار نود با SSH

از نسخه 19.9، نصب نود می‌تواند مستقیم از داخل پنل انجام شود. ادمین اطلاعات SSH نود را وارد می‌کند و IronPanel خودش مراحل نصب را انجام می‌دهد.

قابلیت‌ها:

- ورود با SSH Password
- ورود با SSH Private Key
- پشتیبانی از Key Passphrase
- پشتیبانی از Sudo Password برای کاربر غیر root
- ذخیره credentialها به‌صورت رمزنگاری‌شده
- نصب dependencies، Clone/Update پروژه و اجرای `install_node.sh`
- نصب/Repair هسته‌های انتخاب‌شده
- Sync کانفیگ پروتکل‌ها و کاربران
- Health Check نود بعد از نصب
- Apply مجدد Gateway و Relay بعد از آماده شدن نود

> این قابلیت فقط برای لایسنس‌های **Pro** و **Admin** فعال است.

---

## 📦 ماتریس پلن‌ها

| قابلیت | Beginner / Free | Plus | Pro | Admin |
|---|:---:|:---:|:---:|:---:|
| نصب و استفاده بدون لایسنس | ✅ | ❌ | ❌ | ❌ |
| OpenVPN | ✅ | ✅ | ✅ | ✅ |
| Xray | ✅ | ✅ | ✅ | ✅ |
| سایر پروتکل‌ها | ❌ | ✅ | ✅ | ✅ |
| Subscription و QR | ✅ | ✅ | ✅ | ✅ |
| DNS Manager و DNS Presets | ✅ | ✅ | ✅ | ✅ |
| Speed Limits و Routing Rules | ✅ | ✅ | ✅ | ✅ |
| نمایندگان | ✅ | ✅ | ✅ | ✅ |
| Node Gateway / Node Agent | ❌ | ❌ | ✅ | ✅ |
| Transparent Relay | ❌ | ❌ | ✅ | ✅ |
| Node Auto SSH Installer | ❌ | ❌ | ✅ | ✅ |
| ربات فروش اختصاصی | ❌ | ❌ | ✅ | ✅ |
| امکانات مالی کامل | ❌ | ❌ | ❌ | ✅ |

---

## 🛡️ امنیت و کنترل دسترسی

IronPanel برای استفاده روی سرور واقعی چندین لایه امنیتی دارد:

- ذخیره رمزنگاری‌شده اطلاعات SSH نود
- امکان حذف credential ذخیره‌شده از پنل
- محدودسازی قابلیت Node Auto Installer به Pro/Admin
- Firewall IP/CIDR Ban برای بلاک کامل IP یا subnet
- اجرای فرمان‌های مدیریتی فقط از مسیرهای کنترل‌شده
- جلوگیری از restartهای غیرضروری و عملیات پرریسک
- تفکیک دسترسی‌ها بر اساس پلن و مجوز لایسنس
- لاگ‌گذاری عملیات مهم برای بررسی و دیباگ

اعمال دوباره قوانین Firewall:

```bash
sudo bash /opt/ironpanel/scripts/apply_firewall_rules.sh
```

---

## 🧰 Health Doctor، Repair و نگهداری

بخش Health & Repair وضعیت سرویس‌ها، پورت‌ها، هسته‌ها، دیتابیس، SSL، نودها و منابع سیستم را بررسی می‌کند.

قابلیت‌ها:

- بررسی نصب و وضعیت سرویس‌ها
- Repair جداگانه برای هر پروتکل
- Repair کامل پنل و سرویس‌ها
- نمایش وضعیت CPU، RAM، Disk، Swap و License
- بررسی Node Agent، heartbeat، sync و gateway

دستور تعمیر از ترمینال:

```bash
sudo ironpanelctl repair
```

یا:

```bash
cd /opt/ironpanel
sudo bash scripts/ironpanel_doctor.sh
```

---

## 💾 Backup و Restore امن

IronPanel می‌تواند از بخش‌های مهم سیستم بکاپ بگیرد:

- دیتابیس پنل
- تنظیمات پروتکل‌ها
- فایل‌های کانفیگ کاربران
- SSL و certificateها
- فایل‌های systemd
- تنظیمات نود و gateway

ساخت بکاپ دستی:

```bash
cd /opt/ironpanel
sudo /opt/ironpanel/.venv/bin/flask --app run.py safe-backup
```

---

## 📊 امکانات مدیریتی مهم

- داشبورد منابع سیستم و وضعیت لایسنس
- مدیریت نمایندگان و محدودیت مصرف واقعی
- ربات ادمین تلگرام برای گزارش‌ها و مدیریت سریع
- ربات فروش برای پلن‌ها و کاربران
- لاگ‌های نصب، آپدیت، نود، gateway و relay
- API داخلی برای ارتباط Node Agent و سرویس‌ها
- نمایش کاربران آنلاین و مصرف واقعی تا حد امکان هر پروتکل

---

## 🔧 دستورات کاربردی

وضعیت پنل:

```bash
systemctl status ironpanel --no-pager
```

ری‌استارت پنل:

```bash
sudo systemctl restart ironpanel
```

لاگ پنل:

```bash
journalctl -u ironpanel -n 150 --no-pager
```

اعمال Gateway نود:

```bash
sudo bash /opt/ironpanel/scripts/apply_node_gateway.sh --apply
```

پاک‌کردن Gateway و برگشت به سرور اصلی:

```bash
sudo bash /opt/ironpanel/scripts/apply_node_gateway.sh --clear
```

لاگ Gateway:

```bash
tail -n 150 /var/log/ironpanel-node-gateway.log
```

لاگ Transparent Relay:

```bash
tail -n 150 /var/log/ironpanel-node-gateway-relay.log
```

---

## 📁 مستندات بیشتر

مستندات نسخه‌ها و قابلیت‌های تخصصی داخل پوشه `docs/` قرار دارد. برای تاریخچه کامل تغییرات، فایل زیر را ببینید:

```text
CHANGELOG.md
```

---

## ✅ مناسب برای چه کسانی است؟

IronPanel برای مدیرانی مناسب است که نیاز دارند:

- چند پروتکل را از یک پنل مدیریت کنند
- برای کاربران subscription و QR بسازند
- نماینده و فروشنده داشته باشند
- چند سرور یا نود را پشت یک پنل کنترل کنند
- مسیر تونلی بین کاربر، سرور اصلی و نود داشته باشند
- نصب نود را بدون SSH دستی و از داخل پنل انجام دهند
- بکاپ، آپدیت و تعمیر امن داشته باشند

---

<div align="center">

### IronPanel — یک پنل، چند پروتکل، چند نود، مدیریت کامل

</div>

<div align="center">

<img src="https://s34.picofile.com/file/8491039084/IronpanelN.png" alt="IronPanel" width="140"/>

# IronPanel

**پنل حرفه‌ای مدیریت VPN چندپروتکلی و چندسروری — کاربران، نمایندگان، نودها و تونل‌ها از یک کنسول واحد**

![Version](https://img.shields.io/badge/version-2.0.5-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-informational)
![Flask](https://img.shields.io/badge/flask-3.0-green)
![Platform](https://img.shields.io/badge/platform-Ubuntu%2022.04%2F24.04%20%7C%20Debian-orange)
![License](https://img.shields.io/badge/license-Commercial-red)

[🇬🇧 English](README_EN.md) · [🇮🇷 فارسی](README.md) · [تاریخچه تغییرات](CHANGELOG.md)

</div>

---

## معرفی

IronPanel فقط یک «سازنده اکانت» نیست؛ یک مرکز کنترل کامل برای مدیریت متمرکز سرویس‌های VPN/Proxy است: provisioning کاربران روی هسته‌های واقعی، حسابداری ترافیک لحظه‌ای، سابسکریپشن و QR، سیستم کامل نمایندگان فروش، معماری چندسروری با Node Gateway و Transparent Relay، محدودیت سرعت واقعی per-user، بکاپ مهاجرتی و API عمومی.

---

## ✨ قابلیت‌ها

| حوزه | توضیح |
|---|---|
| **کاربران** | حجم/انقضا/پروتکل‌های مجاز، عملیات گروهی، ساخت عمده، حذف انتخابی و حذف کامل، صفحه‌بندی سریع |
| **اعتبار از اولین اتصال** | گزینه‌ای اختیاری: روزهای اعتبار هر کاربر از اولین اتصال *خودش* شروع می‌شود (OpenVPN آنی، سایر ≤۱۵ ثانیه) |
| **سابسکریپشن** | صفحه اختصاصی هر کاربر با QR، دانلود تکی/ZIP، خروجی Clash/Sing-box/Hiddify و تم قابل تنظیم |
| **محدودیت سرعت** | سه لایه: پیش‌فرض پروتکل / محدودیت کاربر / override هر کاربر-هر پروتکل — با اعمال واقعی tc روی هر کاربر |
| **نمایندگان فروش** | پنل اختصاصی `/r/<path>`، سقف کاربر و حجم واقعی، تعلیق/بازیابی خودکار، **دامنه اختصاصی کانفیگ‌ها** |
| **شارژ کارت به کارت** | بدون درگاه پرداخت: نماینده گیگ وارد می‌کند، مبلغ تقریبی را می‌بیند، واریز و فیش بارگذاری می‌کند؛ مدیر اصلی تأیید یا رد می‌کند و حجم اضافه می‌شود |
| **چندسروری** | Node Agent، Node Gateway، Transparent Relay، نصب خودکار نود با SSH (Pro/Admin) |
| **تلگرام** | ربات فروش owner-aware، ربات ادمین با گزارش دوره‌ای و بکاپ ۲۴ساعته، MTProto Proxy مدیریت‌شده |
| **API** | REST نسخه ۱ و ۲ + سازگاری MirzaBot Custom Panel |
| **عملیات** | Health Doctor با Repair پس‌زمینه‌ای، بکاپ/ریستور Migration-grade، آپدیت مرحله‌ای GitHub، Watchdog |
| **امنیت** | 2FA (TOTP)، تاریخچه ورود، IP/CIDR Ban، رمزنگاری credential نودها، لاگ ممیزی کامل |

---

## 🚀 نصب سریع

**نیازمندی‌ها:** Ubuntu 22.04/24.04 یا Debian · دسترسی root · Python 3.10+

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

اسکریپت نصب به‌صورت کامل انجام می‌دهد: venv و وابستگی‌ها، دیتابیس و migration، هسته‌های پروتکل، یونیت‌های systemd و تایمرها، و اختیاراً Auto-SSL.

| مسیر | توضیح |
|---|---|
| `/opt/ironpanel` | کد اپلیکیشن و venv |
| `/etc/ironpanel` | دیتابیس SQLite، کانفیگ‌ها، بکاپ‌ها |
| پورت پیش‌فرض پنل | `8080` (قابل تغییر از Settings) |

اطلاعات ورود بعد از نصب در خروجی ترمینال نمایش داده می‌شود.

---

## 🔄 به‌روزرسانی

```bash
# سریع از GitHub
sudo bash /opt/ironpanel/scripts/update_from_github.sh

# امن، با health-check و لاگ کامل
sudo bash /opt/ironpanel/scripts/safe_update.sh

# با بکاپ خودکار قبل از آپدیت
sudo IRONPANEL_UPDATE_BACKUP=1 bash /opt/ironpanel/scripts/safe_update.sh
```

---

## 🧩 پروتکل‌های پشتیبانی‌شده

| پروتکل | کاربرد | نکته |
|---|---|---|
| OpenVPN | عمومی و پایدار | خروجی `.ovpn`، auth hook زنده برای اعمال سهمیه |
| WireGuard | سبک و سریع | peer management، DNS/MTU، QR |
| Cisco / Ocserv | AnyConnect | مناسب موبایل |
| L2TP/IPsec | کلاسیک | IKEv2 EAP + PSK legacy |
| PPTP | Legacy | برای سازگاری خاص |
| Xray | VLESS/Reality/TLS/WS/gRPC | Builder چند-inbound، لینک و QR |
| Hysteria2 | UDP پرسرعت | مناسب شبکه‌های پرنوسان |
| Telegram MTProto | MTProxy | instance اختصاصی و secret برای هر کاربر |
| SSH Tunnel | تونل SSH | اکانت محدودشده per-user |

---

## 👥 کاربران و سابسکریپشن

- حجم کل/مصرف/باقی‌مانده با ضریب مصرف قابل تنظیم و ثبت واقعی از runtime همه پروتکل‌ها
- انقضای نامحدود یا تاریخ‌دار + گزینه **«شروع اعتبار از اولین اتصال»** (حتی در ساخت گروهی، هر کاربر مستقل)
- انتخاب دقیق پروتکل‌های هر کاربر؛ پروتکل تیک‌نخورده نه ساخته می‌شود نه نمایش داده می‌شود
- عملیات گروهی: وصل/قطع، ریست حجم، **حذف اکانت‌های انتخاب‌شده** و حذف کامل همه (با موتور bulk که گواهی‌ها و runtime را هم پاک می‌کند)
- نمایش لحظه‌ای آنلاین‌ها، تاریخ اولین اتصال، IP Limit و Speed Limit هر کاربر
- Smart Core Reload: فقط هستهٔ تحت‌تأثیر reload می‌شود، نه همه سرویس‌ها

---

## ⚡ محدودیت سرعت — واقعاً per-user

| سطح | دامنه اثر |
|---|---|
| پیش‌فرض پروتکل | هر کاربرِ آن پروتکل، جداگانه و همزمان |
| محدودیت کاربر (⚡) | تمام پروتکل‌های *فقط همان کاربر* (یک کلاس مشترک tc) |
| Override کاربر×پروتکل | دقیقاً همان ترکیب |

اعمال با `tc/iptables` روی ترافیک خروجی است؛ شناسایی هر کاربر بر اساس IP عمومی نشست فعال او انجام می‌شود (OpenVPN/WG/Ocserv/L2TP از status زنده، **Xray از access.log با email اختصاصی هر کاربر** — loglevel خودکار تنظیم می‌شود، Hysteria2 از journal، Telegram Proxy با پورت اختصاصی هر کاربر). ترافیک رله‌ای نودها هم از زنجیره FORWARD شکل می‌گیرد. موارد فنی غیرقابل‌تفکیک صراحتاً در Status صفحه Speed Limits علامت می‌خورند.

---

## 🤝 نمایندگان فروش

- پنل اختصاصی با مسیر دلخواه، سقف تعداد اکانت و **حجم واقعی مصرف‌شده** (نه allocated)
- تعلیق خودکار هنگام اتمام سقف + بازیابی خودکارِ فقط کاربران سالم پس از رفع محدودیت
- انتخاب پروتکل‌های مجاز هر نماینده با اعمال سمت سرور
- **دامنه اختصاصی کانفیگ‌ها**: اگر نماینده دامنه ثبت کند، کانفیگ کاربران *فقط خودش* با همان آدرس ساخته می‌شود؛ خالی = آدرس اصلی پنل
- **ربات فروش خارجی با ۴ نوع API اختصاصی**: ربات‌ساز داخلی برای نماینده‌ها فعال نیست؛ هر نماینده چهار کلید API مجزا (نسخه ۱، نسخه ۲، میرزا بات و 3x-ui) برای اتصال ربات دارد

---

## 💳 شارژ کارت به کارت (بدون درگاه پرداخت)

سیستم شارژ پنل‌های نمایندگی کاملاً دستی و **بدون هیچ درگاه پرداختی** است:

- مدیر اصلی در بخش **«شارژ کارت به کارت»** (`/cards`) شماره کارت مقصد، نام دارنده حساب، متن راهنمای پرداخت، قیمت هر گیگ (ریال) و حداقل مبلغ درخواست را تنظیم می‌کند.
- نماینده در **«شارژ پنل»** (`/reseller/storage`) تعداد گیگ موردنیاز را وارد می‌کند؛ مبلغ تقریبی (= گیگ × قیمت هر گیگ) همان لحظه نمایش داده می‌شود، به کارت مدیر واریز و **تصویر فیش** را با درخواست بارگذاری می‌کند.
- درخواست‌ها با کلیک روی کارت در یک **پنجره بازشو (modal)** در همان صفحه بررسی می‌شوند: عکس فیش، حجم درخواستی، مبلغ و نماینده. **«تأیید»** حجم را به سقف نماینده اضافه می‌کند و پنلِ متوقف‌شده را دوباره فعال می‌کند؛ **«رد»** بدون اضافه‌کردن حجم، درخواست را می‌بندد. فقط درخواست‌های **در انتظار** نمایش داده می‌شوند و درخواست بررسی‌شده از لیست حذف می‌شود.
- اگر حجم یک نماینده تمام شود، پنل به‌صورت خودکار متوقف، پیام **«پنل غیر فعال به علت تمام شدن حجم»** نمایش داده می‌شود و نماینده فقط به بخش شارژ دسترسی دارد؛ هر چهار API هم تا تأیید شارژ، ساخت/تمدید/ویرایش سرویس را با خطای 403 مسدود می‌کنند (خواندن، ارسال ساب و حذف کاربر همچنان ممکن است).

---

## 🤖 ربات فروش نمایندگی — اتصال ربات خارجی با API اختصاصی

ربات‌ساز داخلی پنل برای نماینده‌ها استفاده **نمی‌شود**. هر نماینده در صفحه **«ربات فروش (API)»** (`/reseller/bot`) به‌صورت خودکار **چهار کلید API** دارد و ربات خارجی خود را به یکی از آن‌ها وصل می‌کند:

| API | نقطه اتصال | احراز هویت | توضیح |
|---|---|---|---|
| **نسخه ۱** (کلاسیک) | `/api/v1` | `X-API-KEY` | اسکریپت‌ها و ربات‌های قدیمی |
| **نسخه ۲** | `/api/v2` | `Authorization: Bearer <token>` | توکن اختصاصی نماینده |
| **میرزا بات** | `/api/mirzabot/v1` | `X-API-Key` | اکشن‌های سازگار با میرزا بات |
| **3x-ui** (جدید) | `/api/xui` | `X-API-KEY` یا `POST /api/xui/login` | سازگار با [3x-ui](https://github.com/MHSanaei/3x-ui) |

API نسخه 3x-ui شامل `POST /login`، `GET /panel/api/inbounds/list`، `POST /panel/api/inbounds/addClient` (ساخت کاربر → برگرداندن **لینک سابسکریپشن**)، `GET /panel/api/inbounds/getClientTraffics/{email}`، `POST /panel/api/inbounds/updateClient/{inboundId}/{email}`، `POST /panel/api/inbounds/delClient/{inboundId}/{email}`، `POST /panel/api/inbounds/delDepletedClients/{inboundId}` و `GET /sub/{subId}` (محتوای خام ساب) است.

ربات می‌تواند کاربر **بسازد**، کاربران و اطلاعاتشان را **بخواند**، لینک سابسکریپشن را برای مشتری **ارسال** کند و کاربر را **ویرایش یا حذف** کند. تمام درخواست‌ها فقط به کاربران خودِ نماینده محدود است و در حالت تمام‌شدن حجم (یا رسیدن به سقف کاربران)، ساخت و ویرایش/تمدید با خطای 403 رد می‌شود؛ فقط خواندن، ارسال ساب و حذف کاربر باقی می‌ماند.

---

## 🛰️ نودها، Gateway و Transparent Relay

```
User ──► Main Panel Endpoint ──► Transparent Relay ──► Selected Node
```

- کاربر همچنان به آدرس سرور اصلی وصل می‌ماند؛ IP نود افشا نمی‌شود
- Direct Location: کانفیگ مستقل هر نود در سابسکریپشن با پرچم و برچسب
- Rebalance خودکار بر اساس پینگ/بار، Force پروتکل به نود مشخص
- نصب خودکار نود از داخل پنل با SSH (password/key/passphrase/sudo) — فقط Pro/Admin

---

## 🔌 API

| نسخه | مسیر | احراز |
|---|---|---|
| v1 | `/api/v1` | `X-API-Key` |
| v2 | `/api/v2` | Token-based (`POST /api/v2/auth/token`) |
| MirzaBot | `/api/mirzabot/v1` | `X-API-Key` اختصاصی |

مستندات کامل: [`docs/API_GUIDE.md`](docs/API_GUIDE.md) · [`docs/API.md`](docs/API.md) · [`docs/openapi.yaml`](docs/openapi.yaml)

---

## 💾 بکاپ و ریستور مهاجرتی

بکاپ Migration-grade شامل snapshot اتمیک دیتابیس + هویت کامل پروتکل‌ها (OpenVPN PKI/tls-crypt، WireGuard، SSL/Let's Encrypt، Ocserv، L2TP/IKEv2، Xray، Hysteria2، env/secrets و یونیت‌ها)؛ ریستور با اعتبارسنجی checksum/schema و rollback خودکار.

```bash
cd /opt/ironpanel && sudo .venv/bin/flask --app run.py safe-backup
```

---

## 🧰 دستورات کاربردی

```bash
systemctl status ironpanel --no-pager          # وضعیت پنل
sudo systemctl restart ironpanel               # ری‌استارت
journalctl -u ironpanel -n 150 --no-pager      # لاگ
sudo ironpanelctl repair                       # تعمیر کلی
sudo bash scripts/ironpanel_doctor.sh          # عیب‌یاب کامل
sudo bash scripts/update_from_github.sh        # آپدیت
```

---

## 🗂 مستندات بیشتر

- [CHANGELOG.md](CHANGELOG.md) — تاریخچه کامل نسخه‌ها
- [`docs/`](docs/) — یادداشت تخصصی هر نسخه + OpenAPI
- [SECURITY.md](SECURITY.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 لایسنس

IronPanel تحت [لایسنس تجاری اختصاصی](LICENSE) منتشر می‌شود؛ نسخه رایگان Beginner بدون کلید کار می‌کند (OpenVPN + Xray). مقایسه امکانات:

| قابلیت | 🆓 Beginner | 💠 Plus | 🚀 Pro | 👑 Admin | 🎁 Trial |
|---|---|---|---|---|---|
| همه پروتکل‌ها (OpenVPN/Xray/WG/Ocserv/L2TP/PPTP/Hysteria2/MTProto/SSH) | فقط OpenVPN + Xray | ✅ | ✅ | ✅ | ✅ |
| Networking / Subscriptions / Monitoring | ❌ | ✅ | ✅ | ✅ | ✅ |
| Node Agent و Node Auto Installer | ❌ | ❌ | ✅ | ✅ | ✅ (بدون Auto Installer) |
| ربات فروش (Sales Bot) | ❌ | ❌ | ✅ | ✅ | ✅ |
| مالی و فاکتور (Billing) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Node Gateway / Multi-server | ❌ | ❌ | ✅ | ✅ | ✅ |
| API عمومی و آپدیت | ✅ | ✅ | ✅ | ✅ | ✅ |

<div align="center">

**IronPanel — یک پنل، چند پروتکل، چند نود، مدیریت کامل**

</div>

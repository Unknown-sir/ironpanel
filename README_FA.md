# IronPanel v18.4

**IronPanel** یک پنل مدیریتی حرفه‌ای برای مدیریت، فروش، مانیتورینگ و تحویل کانفیگ سرویس‌های VPN است. نسخه v18.4 با حالت رایگان Beginner، مرکز آپگرید داخلی و طراحی جدید **VPN-UI Dark Teal**، پشتیبانی از پروتکل‌های بیشتر، صفحه سابسکریپشن مدرن‌تر، QR Code برای کانفیگ‌ها، بهبود WireGuard و Cisco AnyConnect/Ocserv و اضافه شدن PPTP و Hysteria2 آماده شده است.

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

## ویژگی‌های اصلی

- طراحی جدید شبیه داشبوردهای Core Settings / VPN-UI
- داشبورد تیره، مدرن، کارت‌بندی‌شده و مناسب مانیتورینگ سرویس‌ها
- مدیریت کامل کاربران، حجم، انقضا، وضعیت فعال/غیرفعال و پروتکل‌های مجاز
- صفحه سابسکریپشن مدرن با نمایش وضعیت کاربر، حجم، انقضا و کانفیگ‌ها
- QR Code برای WireGuard، Xray/V2Ray و Hysteria2 در صفحه سابسکریپشن
- سیستم فروش داخلی با ربات تلگرام و پرداخت دستی
- Multi-Node System با Node Agent و اتصال امن به پنل اصلی
- Outbound Routing برای عبور ترافیک پروتکل‌های انتخاب‌شده از کانفیگ خروجی
- Backup / Restore، Health Check / Repair، Live Logs و Update Manager
- API برای مدیریت کاربران، مانیتورینگ، نودها، سابسکریپشن و عملیات مدیریتی

## پروتکل‌های پشتیبانی‌شده تا v18

| پروتکل | وضعیت | توضیح |
|---|---:|---|
| OpenVPN | فعال | کانفیگ Certificate-only بدون نیاز به Username/Password در کلاینت |
| WireGuard | فعال | ساخت کلید، IP اختصاصی، QR Code و تعمیر خودکار NAT/IP Forwarding |
| Cisco AnyConnect / Ocserv | فعال | پورت پیش‌فرض جدید `8445` و تنظیمات سازگار با کلاینت Cisco/OpenConnect |
| L2TP/IPsec | فعال | اتصال با PSK و Username/Password |
| Xray / V2Ray | فعال | VLESS/Reality، TLS، No TLS، VMess، Trojan، Shadowsocks و خروجی Subscription |
| PPTP | فعال | برای کلاینت‌های قدیمی و سناریوهای Legacy |
| Hysteria2 | فعال | خروجی URI، YAML و QR Code، مناسب شبکه‌های ناپایدار و UDP/QUIC-based |

## امکانات Xray / V2Ray

- انتخاب فقط یک نوع کانفیگ توسط مدیر برای تحویل به کاربر
- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + TCP بدون TLS
- VLESS + WebSocket بدون TLS
- VLESS + gRPC بدون TLS
- Trojan + TLS / بدون TLS
- VMess + WebSocket / TCP
- Shadowsocks
- ساخت لینک خام، فایل `xray.txt`، QR Code و خروجی‌های مخصوص کلاینت‌ها
- پشتیبانی از خروجی‌های Hiddify، Sing-box، Clash Meta و Raw
- تست کانفیگ قبل از تحویل

## صفحه سابسکریپشن جدید

در v18 صفحه سابسکریپشن با طراحی جدید ساخته شده و شامل موارد زیر است:

- نمایش وضعیت کاربر
- نمایش حجم کل، مصرف‌شده و باقی‌مانده
- نمایش تاریخ انقضا و روزهای باقی‌مانده
- دانلود فایل‌های کانفیگ فعال
- QR Code برای لینک سابسکریپشن
- QR Code برای WireGuard
- QR Code برای Xray/V2Ray
- QR Code برای Hysteria2
- مخفی‌سازی محتوای OpenVPN و WireGuard برای امنیت بیشتر

## نصب دستی پنل اصلی

روی سرور اصلی Ubuntu 22.04 یا 24.04 این مراحل را انجام دهید:

```bash
sudo apt update
sudo apt install -y git curl unzip
```

پروژه را از GitHub دریافت کنید:

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
```

فایل نصب را اجرا کنید:

```bash
sudo bash install.sh
```

در زمان نصب، پنل موارد زیر را از شما می‌پرسد:

- نام کاربری مدیر
- رمز عبور مدیر
- پورت پنل
- IP یا دامنه عمومی سرور
- آدرس تونل برای کانفیگ‌ها
- پنل به‌صورت پیش‌فرض در حالت رایگان Beginner نصب می‌شود و کلید لایسنس نمی‌خواهد
- پورت OpenVPN
- پورت Cisco/Ocserv؛ مقدار پیش‌فرض `8445`
- پورت WireGuard
- پورت Xray
- پورت PPTP
- پورت Hysteria2

بعد از نصب، پنل را با آدرس زیر باز کنید:

```text
http://SERVER_IP:PANEL_PORT
```

## نصب دستی نود

ابتدا داخل پنل اصلی وارد بخش زیر شوید:

```text
VPN & Infrastructure → Nodes → Add Node
```

یک نود جدید بسازید و Token آن را دریافت کنید. سپس روی سرور نود اجرا کنید:

```bash
sudo apt update
sudo apt install -y git curl unzip

git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash scripts/install_node.sh
```

در زمان نصب نود، موارد زیر را وارد کنید:

```text
Master Panel URL: https://panel.example.com
Node Token: TOKEN_FROM_PANEL
Node Public IP/Domain: node1.example.com
Protocols: openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2
```

پس از نصب، در پنل اصلی روی گزینه **Check Connection** بزنید تا وضعیت نود Online شود.

## پورت‌های پیشنهادی

| سرویس | پورت | نوع |
|---|---:|---|
| Panel | 8080 | TCP |
| OpenVPN UDP | 1194 | UDP |
| OpenVPN TCP | 1195 | TCP |
| Cisco/Ocserv | 8445 | TCP/UDP |
| WireGuard | 51820 | UDP |
| Xray/V2Ray | 443 | TCP |
| Xray API | 10085 | Local TCP |
| L2TP | 1701 | UDP |
| IPsec IKE | 500 | UDP |
| IPsec NAT-T | 4500 | UDP |
| PPTP | 1723 | TCP |
| Hysteria2 | 4433 | UDP |

## تعمیر سریع پروتکل‌ها

اگر بعد از نصب یا آپدیت یکی از سرویس‌ها متصل نشد، از بخش Health Check / Repair پنل استفاده کنید یا دستورهای زیر را اجرا کنید:

```bash
sudo bash /opt/ironpanel/scripts/repair_wireguard.sh
sudo bash /opt/ironpanel/scripts/repair_ocserv.sh
sudo bash /opt/ironpanel/scripts/repair_pptp.sh
sudo bash /opt/ironpanel/scripts/repair_hysteria2.sh
sudo bash /opt/ironpanel/scripts/repair_xray.sh
```

## ساختار نسخه‌ها و آپگرید

IronPanel بعد از نصب، بدون نیاز به کلید در حالت **Beginner Free** فعال است. این نسخه تاریخ انقضا ندارد و در صورت قطع بودن LicensePanel نیز قابل استفاده باقی می‌ماند.

برای ارتقا، مدیر از منوی زیر وارد مرکز آپگرید می‌شود:

```text
Dashboard → Upgrade
```

در این صفحه کلید Plus، Pro یا Admin ثبت می‌شود. بعد از اعتبارسنجی، امکانات همان سطح فوراً آزاد می‌شوند. اگر کلید نامعتبر، منقضی یا حذف شود، پنل قفل نمی‌شود و به Beginner Free برمی‌گردد.

| نوع | وضعیت | امکانات |
|---|---|---|
| Beginner Free | رایگان، بدون کلید و بدون انقضا | بخش‌های پایه، پروتکل‌ها، Subscription، QR، Monitoring، Backup و API؛ بدون Nodes، ربات فروش، مالی و Network Manager |
| Plus | نیازمند لایسنس | امکانات Beginner به‌همراه Multi-Node و Node Agent |
| Pro | نیازمند لایسنس | امکانات Plus به‌همراه ربات فروش و Network/Domain Manager |
| Admin License | نیازمند لایسنس | همه امکانات |
| Trial | لایسنس آزمایشی ۷ روزه | همه امکانات در بازه آزمایشی |


## مسیرهای مهم

```text
/opt/ironpanel                 مسیر نصب برنامه
/etc/ironpanel                 دیتابیس، تنظیمات و کانفیگ‌های کاربران
/etc/wireguard/wg0.conf        تنظیمات WireGuard
/etc/ocserv/ocserv.conf        تنظیمات Cisco/Ocserv
/usr/local/etc/xray/config.json تنظیمات Xray
/etc/hysteria/config.yaml      تنظیمات Hysteria2
```

## مناسب برای

- فروشندگان سرویس VPN
- مدیران چند سرور
- مدیریت چند پروتکل روی یک پنل
- فروش سرویس با ربات تلگرام
- مانیتورینگ کاربران، مصرف، نودها و سلامت سرویس‌ها
- تحویل کانفیگ مدرن با QR Code و Subscription

## License

این پروژه برای استفاده مدیریت‌شده و تجاری طراحی شده است. شرایط استفاده، فروش و توزیع باید طبق سیاست مالک پروژه انجام شود.

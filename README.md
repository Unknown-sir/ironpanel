# IronPanel

![IronPanel](https://s34.picofile.com/file/8490877984/Ironpanel.png)

IronPanel یک پنل چندپروتکل برای مدیریت کاربران VPN، نمایندگان، سابسکریپشن، SSL، ربات‌ها، LicensePanel و پروتکل‌های متنوع است.

## نصب سریع

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

## پروتکل‌های پشتیبانی‌شده

- OpenVPN
- WireGuard
- Cisco / Ocserv
- L2TP/IPsec
- PPTP
- Xray / V2Ray
- Hysteria2
- Telegram MTProto Proxy
- SSH Tunnel / SSH Proxy با پورت پیش‌فرض `422`

## امکانات مهم

- مدیریت کاربر با محدودیت حجم، تاریخ انقضا، اتصال همزمان و IP Limit
- صفحه Subscription مدرن با QR و دانلود فایل‌ها
- Auto SSL برای دامنه پنل و پروتکل‌های نیازمند SSL
- بخش نمایندگان با محدودیت کاربر و حجم
- Update Manager داخل پنل با لاگ و درصد پیشرفت
- Telegram Proxy با سرویس مشترک و secret اختصاصی هر کاربر
- WireGuard با MTU پیش‌فرض 1280 و قابلیت تغییر از پنل
- پروتکل SSH با پورت پیش‌فرض 422 و فایل `ssh.txt` برای هر کاربر
- LicensePanel و ربات فروش/مدیریت
- README، docs و changelog به‌روز در هر نسخه

## SSH Protocol

از نسخه `17.0.0` پروتکل SSH به پنل اضافه شده است. برای هر کاربر فعال، اکانت سیستم با نام امن‌شده ساخته می‌شود و اطلاعات اتصال در صفحه کانفیگ/سابسکریپشن تحویل داده می‌شود.

پورت پیش‌فرض:

```text
422/tcp
```

Repair:

```bash
sudo bash /opt/ironpanel/scripts/repair_ssh.sh --sync
```

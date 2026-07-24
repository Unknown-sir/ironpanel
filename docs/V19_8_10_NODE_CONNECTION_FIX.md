# IronPanel v19.8.10 — Node Connection Fix

این نسخه مشکل Online نشدن نود بعد از نصب را از چند لایه اصلاح می‌کند:

- Master URL در دستور نصب نود با scheme و پورت واقعی پنل ساخته می‌شود.
- اگر دستور قدیمی یا اشتباه مثل `https://IP` بدون پورت اجرا شود، `install_node.sh` قبل از نصب سرویس چند مسیر رایج مثل `http://IP:8001`، `http://IP:8080` و `http://IP:5000` را تست می‌کند.
- endpoint سبک `/api/v2/node/ping` برای تست ارتباط بدون نیاز به توکن اضافه شده است.
- Node Agent خطاهای SSL/IP/self-signed و پورت ناقص را بهتر مدیریت می‌کند و در صورت امکان به HTTP fallback می‌کند.
- بعد از نصب، یک heartbeat تستی اجرا می‌شود تا خطا همان لحظه در ترمینال دیده شود.

دستور بررسی روی نود:

```bash
systemctl status ironpanel-node --no-pager
journalctl -u ironpanel-node -n 100 --no-pager
cat /etc/ironpanel-node/node.env
```

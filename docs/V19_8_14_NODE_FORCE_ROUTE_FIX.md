# v19.8.14 — Node Force Route Crash Fix + Verified Forwarding

این نسخه مشکل خطای Internal Server Error در مسیر `/nodes/<id>/force-protocols` را رفع می‌کند و Force واقعی پروتکل به نود را پایدارتر می‌سازد.

## تغییرات
- اصلاح route مربوط به Force Protocols که اشتباهاً تابع Reset را با آرگومان اشتباه صدا می‌زد.
- اضافه شدن rollback امن در صورت خطای iptables یا دیتابیس.
- Queue شدن Sync کانفیگ و نصب/Repair هسته‌ها برای نود هنگام Add Node، Ensure Node و Force Protocol.
- DNAT فقط برای ترافیکی اعمال می‌شود که مقصدش IP خود سرور اصلی است؛ بنابراین ترافیک عادی VPN یا سایر forwardingها خراب نمی‌شوند.
- برای جلوگیری از قفل شدن پنل، فوروارد TCP روی پورت پنل skip می‌شود.

## دستور بررسی روی سرور اصلی
```bash
sudo bash /opt/ironpanel/scripts/apply_node_gateway.sh --apply
sudo tail -n 120 /var/log/ironpanel-node-gateway.log
sudo iptables -t nat -S IRONPANEL_NODE_GW
```

## دستور بررسی روی نود
```bash
systemctl status ironpanel-node --no-pager
journalctl -u ironpanel-node -n 120 --no-pager
```

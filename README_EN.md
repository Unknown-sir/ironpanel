# IronPanel v19.8.12 v19.8.1

IronPanel is a multi-protocol VPN/proxy management panel with users, resellers, subscriptions, Auto SSL, DNS presets, speed limits, routing rules and Pro-only Node Gateway load balancing.

Install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

Update from terminal:

```bash
sudo bash /opt/ironpanel/scripts/update_from_github.sh
```


## v19.6.0 Stability
Adds Health Doctor, Safe Backup/Restore and Safe Update command: `sudo bash /opt/ironpanel/scripts/safe_update.sh`.


## 19.7.0
- Rich installation telemetry and safe restricted management actions.
- IronPanel README remains focused on IronPanel only.


### Firewall IP Ban
The Firewall page can now fully block an IPv4/IPv6 address or CIDR through the dedicated `IRONPANEL-BAN` chain.


## نسخه 19.8.18 — Node Gateway Direct DNAT

- فوروارد واقعی پروتکل‌ها به نود با DNAT مستقیم‌تر و بدون گیرکردن روی شرط `dst-type LOCAL` انجام می‌شود.
- برای تست‌های local یک hook محدود روی NAT OUTPUT اضافه شد.
- هنگام Sync کانفیگ Xray روی نود، مقدارهای `sendThrough` که ممکن است مربوط به IP سرور اصلی باشند حذف می‌شوند تا خروجی اینترنت از IP خود نود انجام شود.
- توجه: در کلاینت‌هایی مثل v2rayN/V2rayN همچنان آدرس سرور در کانفیگ می‌تواند IP پنل اصلی باشد؛ چون Gateway با DNAT کار می‌کند. ملاک واقعی، IP نمایش‌داده‌شده داخل سایت‌های تست IP بعد از اتصال است.

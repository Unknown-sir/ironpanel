# IronPanel / آیرون پنل

Modern multi-protocol VPN management panel with online license verification.

پنل مدیریت حرفه‌ای VPN با پشتیبانی از چند پروتکل و سیستم لایسنس آنلاین.

## Features / امکانات

- OpenVPN, WireGuard, Cisco AnyConnect/Ocserv, L2TP/IPsec
- Automatic VPN core installation and repair
- User create/edit/delete, traffic reset, expiration edit
- `0` traffic or expiration means unlimited
- Per-user protocol permissions
- Device/session limit field
- Subscription page and QR-ready WireGuard configs
- Live CPU/RAM/Swap/Disk monitoring
- Remaining license days widget
- Backup and restore
- Health check and repair page
- Telegram notification settings
- Daily/monthly usage report foundation
- Multi-server node registry
- Reseller, ticket, logs and REST API structure
- Online license check via `http://license.skyshield.space:8002`

## نصب

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

## Update / بروزرسانی

```bash
sudo bash upgrade.sh
```

## License / لایسنس

IronPanel requires a valid online license. If the license expires, login and VPN access are blocked and a license activation/support page is displayed.

این نرم‌افزار نیاز به لایسنس معتبر دارد. در صورت منقضی شدن لایسنس، ورود به پنل و اتصال کاربران مسدود می‌شود و صفحه فعال‌سازی لایسنس نمایش داده می‌شود.

### دریافت یا تمدید لایسنس

برای خرید یا تمدید لایسنس پیام بدهید:

Telegram Support: https://t.me/unknown_eng

## Requirements / پیش‌نیاز

Ubuntu 22.04/24.04 LTS recommended.

Minimum: 1 CPU, 1GB RAM, 20GB disk.

## Repository

GitHub: https://github.com/Unknown-sir/ironpanel

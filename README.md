# IronPanel V13.2

🇮🇷 پنل مدیریت حرفه‌ای VPN چندپروتکل با لایسنس آنلاین، Multi-Server، مانیتورینگ، سیستم مالی، امنیت پیشرفته و Health Check/Repair.

🇺🇸 Professional multi-protocol VPN management panel with online licensing, multi-server management, monitoring, billing, advanced security, and Health Check/Repair.

## نصب / Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

## دریافت لایسنس / Purchase License

برای دریافت یا تمدید لایسنس پیام بدهید:

Telegram: https://t.me/unknown_eng

## Highlights

- OpenVPN, WireGuard, Cisco AnyConnect/Ocserv, L2TP/IPsec
- TCP/UDP protocol settings where supported
- User edit, reset traffic, unlimited time/traffic with `0`
- Dashboard realtime CPU/RAM/Swap/Disk/License days
- Cluster, HA, load balancing, backup/restore
- User Portal, QR Code, GeoIP, sessions and kick
- Billing, Wallet, Plans, Coupons, Invoices
- API v2 + OpenAPI + token auth
- Telegram Bot commands
- Security Center: 2FA, recovery codes, login history, IP whitelist settings, Fail2Ban settings
- Update Manager and Release Channels
- Health Check / Repair with per-service error detail button


## API Documentation / راهنمای API

راهنمای کامل API برای اتصال سایت فروش، ربات تلگرام، سیستم نمایندگی، ساخت و تمدید کاربر، مانیتورینگ و Health Check اضافه شده است:

- [راهنمای کامل API / Full API Guide](docs/API_GUIDE.md)
- [OpenAPI YAML](docs/openapi.yaml)

The API guide includes Persian and English explanations, authentication methods, endpoint tables, curl examples, Python/Node.js examples, and security notes.

## License

Commercial licensed software. Contact Telegram support for license.

### v13.5 Usage Accounting / محاسبه مصرف

IronPanel now syncs real traffic usage from OpenVPN and WireGuard every minute using `ironpanel-usage-sync.timer`. The subscription page displays total traffic, used traffic, remaining traffic, expiration date, and remaining service time. OpenVPN and WireGuard files are downloadable only from the subscription page and their raw configuration content is not displayed publicly.

در نسخه ۱۳.۳ مصرف واقعی OpenVPN و WireGuard هر یک دقیقه همگام‌سازی می‌شود. صفحه سابسکراپشن ظرفیت حجم، حجم مصرف‌شده، حجم باقی‌مانده، تاریخ انقضا و زمان باقی‌مانده را نمایش می‌دهد. فایل‌های OpenVPN و WireGuard فقط از طریق لینک سابسکراپشن قابل دانلود هستند و متن کانفیگ به‌صورت عمومی نمایش داده نمی‌شود.


## v13.4 Traffic Accounting & Quota Enforcement

IronPanel v13.4 uses exact byte counters for OpenVPN and WireGuard traffic. The previous MB-only accounting could lose small deltas; now the panel keeps `used_upload_bytes` and `used_download_bytes` and derives MB values from them.

Quota enforcement runs every minute with `ironpanel-usage-sync.timer`. When a user reaches the configured traffic limit, IronPanel disables the user, removes runtime access from VPN cores, restarts VPN services, and blocks new OpenVPN sessions through the OpenVPN client-connect gate.

Check usage sync:

```bash
sudo systemctl status ironpanel-usage-sync.timer
sudo journalctl -u ironpanel-usage-sync.service -n 100 --no-pager
```

Manual sync/enforcement:

```bash
cd /opt/ironpanel
sudo /opt/ironpanel/.venv/bin/flask --app run.py sync-usage
sudo /opt/ironpanel/.venv/bin/flask --app run.py enforce-limits
```

## Telegram Sales Bot for VPN Accounts

IronPanel includes an internal Telegram sales bot for selling VPN accounts directly from the panel.

Main features:

- Register bot token and sales manager Telegram IDs from IronPanel.
- Sales managers can define plans from inside the bot.
- Each plan can have custom duration, traffic, price, currency and protocols.
- Manual payment system with receipt upload.
- Admin approval or rejection from the bot or web panel.
- Automatic VPN user creation after payment approval.
- Subscription link delivery after approval.
- Free trial can be enabled or disabled by admin.
- Trial duration and trial traffic are configurable.
- Each Telegram account can receive the trial only once.
- Expiration and traffic reminders via Telegram.

### Sales Bot Setup

1. Open IronPanel.
2. Go to **Financial & Sales → Sales Bot**.
3. Enable the bot.
4. Enter the Telegram bot token.
5. Enter sales manager Telegram IDs, separated by commas.
6. Enter manual payment instructions.
7. Save settings.
8. Restart the bot if needed:

```bash
sudo systemctl restart ironpanel-sales-bot
sudo systemctl status ironpanel-sales-bot
```

### Bot Admin Commands

```text
/addplan Plan Name|Days|TrafficGB|Price|Currency
/plans
/toggleplan ID
/trial_on
/trial_off
/trial DAYS TrafficGB
/payment Manual payment instructions
/orders
```

Example:

```text
/addplan 1 Month 50GB|30|50|120000|IRT
```



## v15.1
- License type feature gating: Beginer, Plus, Pro, Admin, Trial.
- Update Manager checks GitHub and can update from https://github.com/Unknown-sir/ironpanel with one button.
- Sales bot admin workflow now uses inline buttons; text input is only used where necessary.


## v15.2 Notes

- Dashboard License & Version cards were redesigned.
- Health Check / Repair now shows service errors safely instead of returning Internal Server Error.
- License feature gating and Update Manager remain available according to the active license type.

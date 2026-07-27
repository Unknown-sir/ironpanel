# IronPanel v18.5.3 — Admin Bot, Cisco Online Fix, IronBot Sales Parity

## Cisco / Ocserv online status
- Added `scripts/ocserv_session_hook.sh` and attached it to `connect-script` / `disconnect-script` in `repair_ocserv.sh`.
- Improved `refresh_online_sessions()` to read hook rows, multiple `occtl` formats/sockets, JSON/text output and journal fallback.
- AnyConnect/Ocserv users should now appear in Dashboard, Monitoring, Sessions, API and Admin Telegram Bot.

## Admin Telegram Bot
- Added real polling service: `ironpanel-admin-bot`.
- Admin-only inline buttons:
  - Online users
  - User information
  - Request backup
  - Panel report
- Added daily report/backup timer: `ironpanel-admin-report.timer`.
- Backup file delivery can be enabled from the Admin Bot settings page.

## Sales Bot parity with IronBot ideas
- Wallet balance per Telegram user.
- Wallet charge requests and admin approval.
- Pay orders from wallet.
- Customer special/agency request workflow.
- Rules and connection-guide texts.
- Subscription QR delivery toggle.
- Admin bulk free config creation.
- Plan connection/IP limit used when creating VPN users.

## Services
```bash
systemctl status ironpanel-admin-bot
systemctl status ironpanel-admin-report.timer
systemctl restart ironpanel-admin-bot
```

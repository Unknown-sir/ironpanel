# Changelog

## v9.1
- Fixed SQLite upgrade migration for older Ironpanel databases.
- Upgrade now stops Ironpanel before copying files and migrating DB to avoid schema race errors.
- Added scripts/repair_db.sh for field repair.

# Changelog

## v9
- Backup and restore.
- Telegram notifications settings and test.
- Daily/user traffic report page.
- Device limit field.
- Per-user protocol permissions.
- VPN service health check and repair page.
- Multi-server node registry.
- Extended REST/API-ready structure.
- Improved v8 fixes: unlimited 0 traffic/expiry, edit user, reset traffic, VPN core sync.


# IronPanel v19.6.0 — Stability Doctor + Safe Updater + Safe Backup

## Health Doctor
- Checks panel files, DB integrity, systemd units, protocol services, listening ports, SSL, node/gateway and speed limit service.
- Supports per-row Repair and full Repair.
- CLI: `flask --app run.py doctor --repair` or `ironpanelctl repair`.

## Safe Updater
- Creates a backup before update.
- Runs the GitHub updater, migrations, service reconciliation and Health Doctor repair.
- Writes progress markers and always emits `IRONPANEL_UPDATE_COMPLETE` when completed.
- Terminal command: `sudo bash /opt/ironpanel/scripts/safe_update.sh`.

## Safe Backup / Restore
- Backup includes `/etc/ironpanel`, IronPanel systemd units and optionally `/opt/ironpanel` source.
- Restore validates tar paths, creates a pre-restore backup, then syncs runtime configs.
- Page: `/backups`.

# v19.10.10 Admin Bot 24h Backup

- Admin bot automatic backup delivery is enabled by default after activation.
- The admin report timer now runs on boot and every 24 hours using `OnUnitActiveSec=24h`.
- Backups are sent as Telegram documents to all configured admin bot admins.
- Duplicate/heavy backup loops are prevented with `admin_bot_last_backup_sent_at`.
- The Admin Bot settings page preserves unrelated checkbox settings when saving access fields.
- A standalone installer is available at `scripts/install_admin_bot_backup_timer.sh` for manual patch deployments.

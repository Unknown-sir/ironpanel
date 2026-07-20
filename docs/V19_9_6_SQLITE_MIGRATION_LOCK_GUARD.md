# V19.9.6 - SQLite Migration Lock Guard

This release makes IronPanel upgrades safer on SQLite-backed installations.

## Fixed

- `flask upgrade-db` can fail with `sqlite3.OperationalError: database is locked` when the panel, usage sync, job worker, bots or node sync are still writing to the SQLite database.
- Added retry/backoff inside the Flask `upgrade-db` and `init-db` commands.
- Added SQLite busy timeout and WAL tuning.
- Added `scripts/upgrade_db_safe.sh` to stop background DB writers before migrations and restore services after a successful upgrade.
- Updated upgrade and repair flows to use the safe DB upgrade wrapper.

## Manual recovery

```bash
sudo bash /opt/ironpanel/scripts/upgrade_db_safe.sh
sudo systemctl restart ironpanel
```

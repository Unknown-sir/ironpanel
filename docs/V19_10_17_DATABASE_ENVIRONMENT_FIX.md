# IronPanel v19.10.17 — Database Environment / Doctor Fix

## Problem
Manual Flask/Doctor invocations did not inherit `/etc/ironpanel/ironpanel.env` from systemd. The application fallback database was `/opt/ironpanel/ironpanel.db`, so SQLAlchemy could silently create an empty SQLite file and commands failed with `no such table: vpn_user` / `app_setting`.

## Fix
- Default SQLite database now resolves to `${IRONPANEL_CONFIG_ROOT:-/etc/ironpanel}/ironpanel.db`.
- `ironpanel_doctor.sh` loads and exports the runtime env before Flask starts.
- Doctor validates that the configured SQLite file is non-empty and contains `app_setting` and `vpn_user`, refusing repair against an unrelated empty DB.
- `safe_update.sh` and `v17_backup.sh` export the environment for child Flask/Python processes.
- Usage diagnostics print an env-aware forced-sync command.

## Recovery
An accidentally-created `/opt/ironpanel/ironpanel.db` is not used by v19.10.17. Verify `/etc/ironpanel/ironpanel.db` first, then archive/remove the stray file only after confirmation.

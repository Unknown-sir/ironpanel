# IronPanel v19.10.10 — OpenConnect port, async repair and web performance

## OpenConnect / Ocserv port consistency

Health Repair and manual `repair_ocserv.sh` now read the saved panel settings directly from `/etc/ironpanel/ironpanel.db` when environment exports are not present. This prevents custom Cisco/OpenConnect ports such as `1195` from being overwritten back to the old default `8445` during repair.

The repair script now logs a clear warning when OpenVPN TCP and Ocserv are configured on the same TCP port, because only one daemon can listen on a TCP port.

## Health Doctor repair safety

The web `/health` repair buttons no longer run long repair scripts inside the Flask request. Repairs are queued in a detached background process and their status/tail log is stored under:

- `/etc/ironpanel/health_repair_status.json`
- `/etc/ironpanel/health_repair.log`

Full repair was also made leaner: it avoids full `install_vpn_core.sh` reinstall by default and runs targeted repair scripts with timeouts.

## Web performance

- Dashboard service status is cached for a few seconds instead of calling `systemctl` for every service on every page load.
- Online session refresh is started in the background on dashboard/monitoring/session pages.
- Usage refresh on read-only usage pages is no longer blocking.
- Runtime apply no longer forces `sync_all_users(restart=True)` internally; callers explicitly choose safe sync/restart behavior.
- GitHub version check timeout is reduced to avoid slow dashboard loads when upstream is unreachable.

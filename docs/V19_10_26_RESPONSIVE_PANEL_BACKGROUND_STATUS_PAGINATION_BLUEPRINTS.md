# V19.10.26 — Responsive Panel: Background Status, 4 Workers, Pagination, Blueprints

## Goal

The admin panel felt heavy on small VPSs: page loads occasionally stalled for
seconds, and the whole panel queued behind only two gunicorn workers. Root
causes were synchronous `systemctl` probes inside web requests, a tiny worker
pool and unbounded list queries. The 3,000-line monolithic `app/web.py` also
made every change risky.

## Changes

### 1. Web UI split into domain modules (`app/web/` package)

* `app/web.py` was replaced by a package with one module per domain:
  `auth`, `dashboard`, `users`, `resellers`, `subscriptions`, `nodes`,
  `network`, `billing`, `ops`, `system`, `bots` plus `common.py`
  (shared helpers + the app-wide context processor / before / after hooks).
* Every module registers routes on the **same** blueprint named `web`, so all
  `url_for('web.*')` calls in templates, bots and docs keep working with zero
  template changes.
* Verified: AST-extracted route map (rule + methods + endpoint) is byte-for-byte
  identical before/after (122/122 entries).

### 2. Service status moved out of the request path

* New `probe_service_status()` writes `{ts, data}` to
  `$CONFIG_ROOT/service_status_cache.json` (atomic rename), shared by all
  gunicorn workers and CLI timers.
* The existing 15s `ironpanel-usage-sync.timer` now refreshes the snapshot via
  `refresh_service_status_cache()` (called at the end of the `sync-usage`
  CLI command). No new systemd unit is required; existing servers pick it up
  after pulling code and restarting.
* `service_status()` serves memory/file cache instantly (60s freshness window),
  spawns a throttled background refresh when stale, and only blocks once on a
  completely cold start.

### 3. Gunicorn capacity

* Installer unit, `upgrade.sh --restart-only` rewrite and the SSL TLS drop-in
  now run `-w 4 --threads 2` instead of `-w 2`.

### 4. Server-side pagination

* Users table: 25/page (search preserved), Activity Logs: 50/page (filters
  preserved), Login History: 50/page.
* Shared `_pagination.html` include renders Prev/Next + windowed page numbers;
  new `.pager` CSS matches existing themes.

## Upgrade notes

1. Pull code, then run `sudo bash upgrade.sh --restart-only` (or restart
   `ironpanel`).
2. Nothing else is required: the status cache file is created automatically,
   and no database migration ships with this release.

## Known pre-existing issue (unchanged)

* `POST /cluster` without a valid action still references an undefined
  `plan_protocols` variable (latent NameError since v10). Preserved verbatim
  during the split to keep this release behaviour-neutral; fix separately.

# IronPanel v18.6.0 Priority Infrastructure, i18n and WireGuard MTU

## Added

- WireGuard MTU default: `1360` on server and client profiles.
- WireGuard PersistentKeepalive default: `25`.
- English installer prompts.
- Language and theme foundation: Persian, English, Arabic, Russian plus Dark/Light/Auto.
- Local job worker service/timer: `ironpanel-job-worker.timer`.
- Reseller API endpoints under `/api/reseller/v1/*` and API v2 reseller management.
- Improved activity logs dashboard with filters and operational counters.

## Why MTU 1360

MTU 1360 is safer for mobile networks, CGNAT and nested tunnels while still keeping good throughput. Admins can override it in Settings.

## Upgrade behavior

The GitHub updater performs source sync, dependencies, DB migration, systemd reconciliation, protocol repair and restarts. New services such as the job worker are enabled automatically.

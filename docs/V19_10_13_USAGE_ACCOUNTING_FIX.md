# IronPanel v19.10.13 — Real Traffic Accounting Fix

This release fixes traffic that was consumed by VPN users but remained stale or zero in the admin panel and public subscription page.

## What changed

- Traffic-sensitive pages perform a bounded accounting refresh before rendering, then reload ORM state.
- A cross-process file lock prevents the web process and `ironpanel-usage-sync.timer` from applying the same runtime sample concurrently.
- Runtime accounting now covers OpenVPN, WireGuard, Xray, Telegram Proxy, Cisco/OpenConnect (Ocserv), L2TP/PPTP (PPP), and Hysteria2.
- Ocserv and PPP disconnect hooks write atomic JSON events instead of opening the application database from authentication/session scripts.
- Node agents report all supported traffic sources with stable per-session identifiers and persist final events until the panel accepts them.
- Xray usage is read with one Stats API query rather than two subprocesses per user.
- Collector health data is stored in `app_setting`; `scripts/usage_diagnose.sh` prints timer, service, error, and runtime-source status.

## Upgrade

```bash
sudo bash upgrade.sh
```

The normal upgrade path reconciles the affected protocol configs and installs the safe session hooks. After upgrading, verify the collector with:

```bash
sudo bash /opt/ironpanel/scripts/usage_diagnose.sh
sudo systemctl status ironpanel-usage-sync.timer --no-pager
```

Traffic that was never persisted and is no longer present in a daemon/session counter cannot be reconstructed retroactively. Active sessions and all new traffic are accounted after the upgrade.

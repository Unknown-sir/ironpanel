# IronPanel v18.6.7 — Telegram Proxy + WireGuard MTU 1280

## Changes

- Changed WireGuard default MTU to `1280` across installer, settings, runtime generation and repair scripts.
- Added `telegram_proxy` as a first-class protocol in IronPanel.
- Added per-user Telegram MTProto proxy delivery using JSMTProxy-style `config.json` instances.
- Each user receives a dedicated TCP port and secret.
- Telegram proxy traffic is counted against the same user traffic quota using per-user iptables counters.
- If the user reaches the volume limit, the normal enforcement disables the user and the Telegram proxy service is removed on sync.
- Added Settings section for Telegram Proxy base port and repair/install action.

## Runtime layout

- JSMTProxy source: `/opt/ironpanel-telegram-proxy/JSMTProxy`
- Instances: `/opt/ironpanel-telegram-proxy/instances/<username>/`
- Services: `ironpanel-tgproxy-<username>.service`
- Profile file: `telegram_proxy.txt`

## Repair

```bash
sudo bash /opt/ironpanel/scripts/repair_telegram_proxy.sh --sync
```

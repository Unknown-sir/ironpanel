# IronPanel v18.6.8 — Telegram Proxy Manager + Update Manager Repair

## Summary

This release fixes the Update Manager flow, adds a dedicated Telegram MTProto Proxy management page, and makes Telegram Proxy traffic accounting part of the user's quota enforcement path.

## Update Manager

- `/dashboard/quick-upgrade` now opens `/updates?autostart=1`.
- The Update Manager starts the inline step-by-step updater automatically when requested.
- The page shows percentage progress and log output.
- When the final upgrade step finishes, the panel schedules a controlled restart automatically.

## Telegram MTProto Proxy

- New admin page: `/telegram-proxy`.
- Admin can enable/disable the protocol globally, change the base port, change secret salt, install/repair the core, sync users, collect traffic usage, restart and stop all proxy instances.
- Each user has a dedicated TCP port and secret.
- Generated link format: `tg://proxy?server=SERVER&port=PORT&secret=SECRET`.

## Traffic accounting

- Per-user traffic is collected from iptables counters matching `ironpanel-tgproxy-USER_ID`.
- INPUT and OUTPUT counters are tracked separately.
- The usage sync timer includes Telegram Proxy usage.
- If a user reaches the data limit, IronPanel disables that user and re-syncs services so the Telegram Proxy instance stops too.

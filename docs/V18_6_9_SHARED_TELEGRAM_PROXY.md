# IronPanel v18.6.9 — Shared Telegram Proxy Fix

- Replaced per-user Telegram proxy ports with one shared TCP port.
- Added `scripts/ironpanel_mtproxy.js`, a multi-secret MTProto proxy wrapper.
- Each user still receives a unique MTProto secret and link.
- Per-user usage is collected from `/opt/ironpanel-telegram-proxy/ironpanel/usage.json`.
- Quota enforcement now includes Telegram Proxy usage by user secret.
- Legacy `ironpanel-tgproxy-*.service` units are disabled automatically.

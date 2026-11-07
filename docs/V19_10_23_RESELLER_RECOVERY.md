# IronPanel v19.10.23 — Reseller recovery

Reseller automatic suspensions are now reversible and reason-aware.

- `admin.disabled_reason`: `manual`, `traffic_quota`, `user_limit`, or empty.
- `vpn_user.disabled_reason`: own reasons (`expired`, `traffic_limit`, `ip_limit`, `manual`) or reseller reasons (`reseller_traffic_quota`, `reseller_user_limit`, `reseller_manual`).
- A healthy reseller auto-recovers after limits are edited or account count drops.
- Only users whose disable reason is reseller-managed are restored.
- Usage Sync runs reseller reconciliation periodically.
- Main-admin user listing keeps `owner_id` and shows the reseller name for disabled users.

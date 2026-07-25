# v19.1.0 — Speed Limits and Routing Rules

- Added a modern **Speed Limits** page at `/speed-limits`.
- Admin can set Mbps limits per protocol: OpenVPN, WireGuard, Ocserv, L2TP/IPsec, Xray, PPTP, Hysteria2, Telegram Proxy and SSH.
- Runtime rules are applied with Linux `tc` and persisted by `ironpanel-speed-limits.service`.
- Added a modern **Routing Rules** page at `/routing-rules` for mapping protocols to outbound profiles or direct routing.
- Update Manager now marks successful upgrades as 100% complete immediately after the upgrade task exits successfully, then schedules final repair/restart work.
- README includes terminal update commands.

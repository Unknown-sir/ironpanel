# IronPanel v19.10.20 — Direct per-user Speed Limit

## Behavior

- `VpnUser.speed_limit_mbps > 0`: one user-wide cap, applied to all matching protocols for that user.
- `0`: no user-wide override; existing per-user/per-protocol and protocol defaults remain in effect.
- Main admin can change every user.
- Resellers are protected by `owner_id` checks and can change only their own users.
- Runtime config uses one `group_key` per user so protocol match rules share a single tc class when the direct user-wide limit is enabled.

## Upgrade

`flask upgrade-db` adds `vpn_user.speed_limit_mbps INTEGER DEFAULT 0` for existing SQLite databases.

## Runtime refresh

WireGuard uses `wg show wg0 endpoints` to identify a specific peer by public endpoint IP and UDP port. The regular usage-sync cycle regenerates the speed map after online-session refresh and reapplies tc/iptables only if that generated map changed.

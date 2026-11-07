# V19.10.29 — True Per-User Speed Limits

## Required semantics

1. **Per-protocol default** (`Speed Limits` page): caps *every* user
   individually on that protocol.
2. **User-wide limit** (⚡ on user card / edit form / per-user matrix): caps
   *all* protocols of that single user only, sharing one tc class
   (`group_key=user-<id>`).

Both were already expressed correctly in `speed_limits.conf`; the real problem
was that several protocols never produced usable match rules.

## Root causes fixed

| Protocol | Before | Now |
|---|---|---|
| OpenVPN / WireGuard / Ocserv / L2TP | worked (session IP based) | unchanged |
| SSH | worked (Linux uid owner match) | unchanged |
| Telegram Proxy | pending forever (no detector) | always precise: dedicated per-user MTProxy port → `port_only` tc rule |
| **Xray** | pending forever | **true per-user**: access.log parser maps `email=ip-{id}-{username}` ↔ client public IP |
| Hysteria2 | pending forever | best-effort journal parser; single-limited-user ports fall back to whole-port cap |
| PPTP | pending forever | single-limited-user whole-port cap (GRE payload outside scope) |

### Xray details

* Clients already carry `email = ip-{id}-{username}` in generated configs.
* When any speed limit is configured, the panel flips `xray_loglevel` to
  `info`, writes `/etc/logrotate.d/ironpanel-xray` and restarts Xray once, so
  `/var/log/xray/access.log` records `client-ip … email:` lines.
* New `_refresh_xray_sessions()` parses the last ~512KB every cycle and upserts
  `OnlineSession(username, 'xray', public_ip)` — exactly what
  `_match_for_user()` needs for `-d <client-ip>` tc marking, per user.

### Node relays

An extra `iptables -t mangle FORWARD -j IRONPANEL_SPEED_MARK` hook shapes
DNAT/gateway-relayed client traffic that bypasses OUTPUT.

## Operational notes

* After upgrade press **Save & Apply** (or ⚡) once so the loglevel switch and
  regenerated rules land.
* Multi-user shared-port cases that cannot be separated at L4 stay explicitly
  visible as `# NOTE pending …` lines in the Speed Limits status output — no
  silent no-ops.

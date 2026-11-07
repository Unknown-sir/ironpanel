# V19.10.28 — Delete-All Users and First-Connection Validity

## 1. Delete all users (main admin only)

* New card at the bottom of **Users & Configs**: "حذف همه کاربران" (Danger zone).
* `POST /users/delete-all` — restricted to `main_admin`, shows the total count,
  requires a browser confirm, writes a `delete_all_users` activity-log entry.
* Uses the existing bulk-delete engine (`delete_users_bulk`) so OpenVPN certs
  are revoked asynchronously, WireGuard/Xray/auth files are rebuilt once,
  password daemons reload and nodes receive a full resync — one shared runtime
  rebuild instead of N individual deletions.

## 2. Validity starts on first connection

### Model / storage (no manual migration)

New `vpn_user` columns added to the SQLite light migration:

| column | meaning |
|---|---|
| `start_on_first_connect` | option armed at creation/edit |
| `pending_expiry_days` | days to apply at first connection |
| `first_connected_at` | recorded at the first successful connection |

While armed and not yet connected: `expires_at = NULL` and
`VpnUser.expired` is forced `False` → the account can never be auto-disabled
for expiry before its first use.

### Activation points

1. **OpenVPN — instant.** `scripts/ironpanel_openvpn_auth.py` (client-connect)
   applies `expires_at = now + pending_expiry_days` directly in the panel DB on
   the very first handshake.
2. **All other protocols — ≤15s.** `sync-usage` timer now calls
   `activate_first_connection_expiries(online_usernames)`; detection is based on
   live `OnlineSession` rows which include WireGuard, Ocserv, L2TP and
   node/Direct Location sessions reported by agents.

Each bulk-created user activates independently at its own first connection.

### UI

* Checkbox «شروع اعتبار از اولین اتصال» in: create form, Quick Create, bulk
  creation and the edit form.
* User cards show **اولین اتصال** timestamp once connected, or a
  «در انتظار اولین اتصال» badge with the armed day count while pending.
* Edit form displays the recorded first-connection moment (read-only).

## Upgrade notes

Pull code and restart; the light migration adds the three columns automatically.

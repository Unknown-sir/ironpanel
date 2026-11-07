# IronPanel v2.0.7 — Per-Reseller Daily Traffic Cap (Per-User, Auto-Reset)

Alongside the v2.0.6 per-reseller speed limit, the main admin can now also set a
**daily traffic cap** for each reseller. It is a **per-user, per-day** limit, distinct
for every user owned by the reseller.

## Two independent dimensions ("0 = unlimited")

| Dimension        | Field on the reseller form         | Meaning when set                        |
|------------------|------------------------------------|-----------------------------------------|
| **Speed**        | سرعت هر کاربر (مگابیت بر ثانیه)      | Max bandwidth Mb/s **per user**         |
| **Daily volume** | مصرف روزانه هر کاربر (مگابایت)      | Max traffic MB **per user per day**     |

- If **both are 0** → the reseller's users are unrestricted.
- If **either** is set → that limit is applied (speed caps bandwidth; daily volume caps
  traffic used per day).
- Each user of the reseller gets the cap **independently** (not a shared pool).

## How the daily cap works (automatic reset)

- The cap is compared against each user's **today's** usage, tracked in the
  `DailyUsage` table (keyed by calendar day `YYYY-MM-DD`).
- When a user hits **today's** cap they are disabled with
  `disabled_reason='daily_cap'` and dropped from the services (synced out) so they
  cannot use more that day.
- Because `DailyUsage` is per-day, usage resets automatically at the start of the next
  day: the user is re-enabled by the enforcement pass and then limited again once the
  new day's cap is reached. This gives a fully automatic daily cycle with no manual reset.

## Where it's enforced

- The usage-sync timer (every 15s) calls `enforce_reseller_daily_limits()` immediately
  after traffic accounting, so a user is stopped as soon as today's cap is crossed and
  re-enabled once a new day starts.
- The reseller edit page has an **"apply daily cap to existing users"** checkbox that
  runs the enforcement immediately.

## Where to configure

Admin menu → **Business & access → Resellers** (`/resellers`):

- **Create reseller** form: field **"مصرف روزانه هر کاربر (مگابایت)"** (per-user daily
  traffic in MB; `0` = unlimited).
- **Edit reseller** form: same field pre-filled plus the apply-to-existing checkbox.

## Storage

Per-owner `AppSetting` key `reseller_daily_limit_owner_<id>` (value in MB/day,
`0` = unlimited). No database schema migration is required.

## Implementation

- `app/services/speed_limit.py`: `get_reseller_daily_limit(owner_id)` /
  `set_reseller_daily_limit(owner_id, mb)`.
- `app/services/provisioning.py`: `enforce_reseller_daily_limits(commit=True)` run from
  the usage-sync cycle.
- `app/web/resellers.py` + `app/templates/resellers.html`: admin create/edit UI.

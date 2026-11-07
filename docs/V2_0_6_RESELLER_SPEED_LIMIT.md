# IronPanel v2.0.6 — Per-Reseller Speed Limit (Per-User Cap)

The main admin can now assign a **speed limit to each reseller independently**. When
set, that value becomes the **hard per-user speed cap** for **every user owned by the
reseller**.

## What it means ("per user", not "shared")

- Admin sets a reseller's limit to **8** (Mb/s).
- Every user of that reseller is capped at **8 Mb/s**, each user independently.
- It is **not** a shared/aggregate pool: user A using 8 Mb/s does not reduce what user B
  can use. Each user gets its own 8 Mb/s cap.
- No user of that reseller can be configured with a higher speed.

## Where to configure

Admin menu → **Business & access → Resellers** (`/resellers`):

- **Create reseller** form has a new field **"سرعت هر کاربر (مگابیت بر ثانیه)"**
  (per-user speed in Mb/s; `0` = no limit).
- **Edit reseller** form has the same field plus **"محدودیت سرعت جدید روی کاربران فعلی
  نماینده هم اعمال شود"** (re-apply to existing users) checkbox — when set, all owned
  users are re-capped and the runtime speed limits are refreshed.

## Enforcement everywhere

A reseller's per-user cap is applied at every place a reseller creates or edits a user:

- Reseller's own panel: quick-create, users create, bulk create, and user edit.
- **v1 API**: `/api/v1/users/create` and `/api/v1/users/:id/speed-limit`.
- **v2 API**: `/api/v2/users` (POST) and `PATCH /api/v2/users/:id`.
- **MirzaBot API**: user creation.
- **3x-ui compatible API**: user creation.

## Storage

Stored per-owner in the `AppSetting` table under key `reseller_speed_limit_owner_<id>`
(value in Mb/s; `0` = unlimited). No database schema migration is required.

## Implementation

New helpers in `app/services/speed_limit.py`:
- `get_reseller_speed_limit(owner_id)` / `set_reseller_speed_limit(owner_id, mbps)`.
- `enforce_reseller_speed_limit(user, requested_mbps)` — caps when editing.
- `cap_user_speed_for_owner(owner_id, mbps)` — caps when creating (no user yet).

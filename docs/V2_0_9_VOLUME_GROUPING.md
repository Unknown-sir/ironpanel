# IronPanel v2.0.9 — Volume-Based User Grouping + Group Bulk Actions

The **Users & Configs** page (`/users`) no longer renders every user as one long flat
list. It now **automatically groups users by their config traffic volume**, so you can
scan, understand and manage a large panel much faster.

## Auto-detected volume groups

Each user is placed into a bucket automatically from its `data_limit_mb` (0 = unlimited):

| Bucket key | Label (FA) | Label (EN) | data_limit_mb range |
|---|---|---|---|
| `unlimited` | نامحدود | Unlimited | `0` |
| `1-10GB` | 1 تا 10 گیگ | 1-10 GB | `1 … 10*1024` |
| `10-50GB` | 10 تا 50 گیگ | 10-50 GB | `10*1024 … 50*1024` |
| `50-100GB` | 50 تا 100 گیگ | 50-100 GB | `50*1024 … 100*1024` |
| `100-500GB` | 100 تا 500 گیگ | 100-500 GB | `100*1024 … 500*1024` |
| `500GB+` | بالای 500 گیگ | 500+ GB | `> 500*1024` |

(The upper boundary is inclusive in the lower bucket, e.g. exactly 10 GB lands in
**1-10 GB**, exactly 50 GB in **10-50 GB**, etc.)

Grouping happens **per page** within the existing pagination, and is detected from the
value stored on each user — the panel does it automatically with no manual tagging.

## Group bulk actions

Every group header carries its own action dropdown, operating on **all** users that
fall into that volume group at once (whole scope, not just the visible page):

- ✅ **وصل / فعال همه** — enable every user in the group.
- ⛔ **قطع / غیرفعال همه** — disable every user in the group.
- 🗑 **حذف همه گروه** — permanently delete every user in the group (DB + configs +
  OpenVPN certs, same engine as the existing selected-delete).

Scope follows the logged-in role: the main admin operates on all users, a reseller only
on its own users. Confirmations guard the destructive/disable actions.

## Implementation

- `app/web/users.py`:
  - `_VOLUME_BUCKETS`, `volume_bucket(mb)`, `_volume_bucket_query(q, key)`,
    `group_users_page(users)` (+ small `OrderedTuple` accessor).
  - `/users` view passes `user_groups` (ordered list of `(key, label_fa, label_en, users)`).
  - new route `POST /users/group-action` with `bucket` + `action`
    (`enable` / `disable` / `delete`).
- `app/templates/users.html`: group sections + group action dropdown + `groupActionConfirm()` JS.
- `app/static/css/style.css`: `.volume-group*` styles.

No schema migration required. VERSION = 2.0.9, cache-buster bumped to 2.0.9.

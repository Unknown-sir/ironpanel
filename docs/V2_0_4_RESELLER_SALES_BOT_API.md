# v2.0.4 — Reseller Sales Bot via 4 API Families + Card-To-Card Modal Review

## 1. Reseller sales bot = external bot + dedicated API (no built-in bot builder)

For resellers the panel's **built-in sales bot is disabled**. Instead, every reseller
owns **four API credentials**, generated automatically on **"Sales bot (API)"** —
`/reseller/bot` — and connects any external bot to them.

| API | Endpoint | Auth | Purpose |
|---|---|---|---|
| **v1 (classic)** | `/api/v1` | `X-API-KEY` | legacy scripts/bots |
| **v2** | `/api/v2` | `Authorization: Bearer <token>` | token based bots |
| **MirzaBot** | `/api/mirzabot/v1` | `X-API-Key` | MirzaBot-compatible actions |
| **3x-ui** (new) | `/api/xui` | `X-API-KEY` or `POST /api/xui/login` | mirrors MHSanaei/3x-ui |

The keys live in the `api_token` table:
- `owner_id` → the `admin.id` of the reseller (main-admin tokens keep `owner_id = NULL` and unrestricted access);
- `api_type` → `v1` / `v2` / `mirzabot` / `xui` (v1 is served from the reseller's own `Admin.api_key`).

Both new columns are added automatically by the SQLite light migration
(`_sqlite_light_migration` in `app/commands.py`) for upgraded installs.

### 3x-ui API (`/api/xui`) — what the bot can do

The bot can only **create** users, **read** users and their info, **send the
subscription** link/content to customers and **delete/edit** users:

| Method / path | JSON `{success,msg,obj}` | Notes |
|---|---|---|
| `POST /login` | `{token}` + `3x-ui` cookie | username = reseller panel user, password = the API key |
| `GET /panel/api/inbounds/list` | `{obj:[{id,remark,clientStats}]}` | all users of the token owner |
| `POST /panel/api/inbounds/addClient` | `{id,email,subscriptionUrl}` | create user (see payload below) |
| `GET /panel/api/inbounds/getClientTraffics/{email}` | inbound with `clientStats` | per-user traffic |
| `POST /panel/api/inbounds/updateClient/{inboundId}/{email}` | id/email/subscriptionUrl | renew/edit/charge |
| `POST /panel/api/inbounds/delClient/{inboundId}/{email}` | id/email | delete user |
| `POST /panel/api/inbounds/delDepletedClients/{inboundId}` | removed[] | bulk cleanup |
| `GET /sub/{subId}` | raw subscription text | public, mirrors `GET /s/<token>` |

`addClient`/`updateClient` accept 3x-ui style bodies: `settings` as a JSON string
(and base64-encoded JSON for update), client fields `email`, `total` (bytes),
`expiryTime` (ms epoch), `enable`, `limitIp`, `remark`, `subId`, `password`, plus
convenience top-level `days` / `data_limit_mb` / `username`.

### Volume gate at the API level (all four families)

While a reseller is volume-exhausted (or at its user cap) every reseller-scoped
API returns **HTTP 403** for:
- creating a new user;
- editing / renewing / charging / toggling / resetting a user.

Reading info, sending the subscription and deleting users still work. The same
check that powers the bot gate in v2.0.3 is now shared in
`app/services/reseller_api.py` and enforced in `api`, `api_v2`, `api_mirzabot`
and `api_xui`.

## 2. Admin card-to-card review as a modal (only pending shown)

`/cards` charge requests now render as cards that **open in a popup modal** on the
same page (receipt preview, volume, amount, invoice/date and the approve/reject
forms). After approval or rejection the processed request **disappears from the
list** — only `status = 'pending'` requests are rendered, so a reload after each
decision is reflected immediately.

Behavior is unchanged: **Approve** credits the GB to the reseller quota and
re-enables a suspended panel (`reconcile_reseller_access`), **Reject** closes the
request with an optional note.
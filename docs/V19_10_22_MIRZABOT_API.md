# IronPanel v19.10.22 — MirzaBot API

Endpoint: `POST /api/mirzabot/v1`

Authentication: `X-API-Key` (dedicated MirzaBot key from `/mirzabot-api`).

Supported actions: `create_user`, `get_user`, `remove_user`, `reset_user`, `extend_user`, `modify_user`, `change_status`, `count_users`, `revoke_sub`, `extra_volume`, `extra_time`.

The existing `/api/v1` and `/api/v2` APIs are intentionally not modified.

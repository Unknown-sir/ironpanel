# IronPanel v2.0.8 — 3x-ui / Sales-Bot Login Fix

## Problem

Standard sales bots written for MHSanaei/3x-ui connect to `POST /api/xui/login` with
just **username + password** of the panel. IronPanel's login handler previously
required `password` to **be an API key** (`ApiToken`) resolved via
`resolve_api_token`; a reseller who gave the bot its *real panel password* got
`Invalid API Key` (401). The bot appeared to "connect", but authentication actually
failed and every subsequent call (login-gated) — including user creation — was denied.

## Fix

`/api/xui/login` now accepts **both** login styles, in order:

1. **API key as password (unchanged).** If `password` resolves to an enabled `xui`
   `ApiToken`, the token (and its owner scope) is used as before. When a `username` is
   also provided, the token owner must match that reseller.
2. **Real panel login (new fallback).** If the `password` is not an API key, the
   `username` is looked up as a `sub_admin` and verified with
   `Admin.check_password(...)`. On success the reseller's active `xui` `ApiToken` is
   issued. If the reseller has no `xui` key yet, the login returns HTTP 403 with a
   clear message ("This reseller has no active bot (xui) API key yet") instead of an
   ambiguous failure.

The `{token}` response and the `3x-ui` cookie are unchanged, so existing bots keep
working; bots configured with the real panel password now log in correctly too.

## File changed

- `app/api_xui/routes.py` — `login()` fallback to real panel credentials + small
  `_issue_xui_token()` helper for shared response/cookie/log.

No schema migration required. CSS/JS cache-buster bumped to 2.0.8, VERSION = 2.0.8.

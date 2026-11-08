# IronAPP — Android Client Contract / قرارداد اپ اندروید آیرون

> Panel: **2.2.1+** · App: **IronAPP 1.0.0+** · Repo: `https://github.com/Unknown-sir/IronAPP`

This document is the contract between the IronPanel server and the
open-source IronAPP Android client. The app lets a user paste **one
subscription link**, reads **quota + expiry + enabled protocols** from it,
and connects to **any protocol enabled for that user** — and it must refuse
to (re)connect once traffic is exhausted or the account is expired.

---

## 1. Endpoints

The subscription token in the URL **is** the credential (same trust model as
the existing `/s/<token>` pages and feeds). No API key is needed.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/s/<token>/app.json` | Full snapshot for the app (quota, expiry, protocols, configs, links) |
| GET | `/s/<token>/status` | Lightweight polling (call every 30–60s and before every connect) |
| GET | `/s/<token>/raw` | Plain Xray URI list (HTTP **403** when expired/out of traffic) |
| GET | `/s/<token>/clash` | Clash/Meta YAML (HTTP **403** when expired/out of traffic) |
| GET | `/s/<token>/singbox` | sing-box JSON (HTTP **403** when expired/out of traffic) |
| GET | `/s/<token>/hiddify` | Hiddify plain list (HTTP **403** when expired/out of traffic) |

Conventions (panel-wide, unchanged):

- `expires_at: null` and `*_mb: 0` / `total_bytes: 0` mean **unlimited**.
- `app.json`/`status` answer **HTTP 200** even for dead accounts and report
  `"access_ok": false` + `"access_reason(_en)"`, so the app can show *why*.
- All feeds/downloads/QR routes answer **HTTP 403** with the Persian reason
  as the body when `access_ok` is false. The server is the source of truth.

## 2. `app.json` schema (abridged)

```json
{
  "success": true,
  "app": "ironapp",
  "min_app_version": "1.0.0",
  "panel_version": "2.2.1",
  "server_time": "2026-09-29T12:00:00+00:00",
  "user": {
    "username": "ali",
    "enabled": true,
    "access_ok": true,
    "connectable": true,
    "access_reason": "فعال",
    "access_reason_en": "active",
    "protocols": ["openvpn", "wireguard", "xray", "hysteria2"],
    "expires_at": "2026-10-29T12:00:00+00:00",
    "unlimited_time": false,
    "remaining_days": 30,
    "remaining_seconds": 2592000,
    "usage": { "used_bytes": 1, "remaining_bytes": 2, "total_bytes": 3, "...": "..." },
    "subscription": {
      "page": "https://panel:8080/s/TOKEN",
      "raw": "https://panel:8080/s/TOKEN/raw",
      "clash": "https://panel:8080/s/TOKEN/clash",
      "singbox": "https://panel:8080/s/TOKEN/singbox",
      "hiddify": "https://panel:8080/s/TOKEN/hiddify",
      "app_json": "https://panel:8080/s/TOKEN/app.json",
      "status": "https://panel:8080/s/TOKEN/status"
    },
    "configs": {
      "user.ovpn": "<openvpn profile>",
      "wireguard.conf": "<wireguard profile>",
      "ocserv.txt": "<anyconnect credentials>",
      "l2tp.txt": "<l2tp credentials>",
      "xray.txt": "<vless/vmess/trojan/ss URIs, one per line>",
      "pptp.txt": "<pptp credentials>",
      "hysteria2.txt": "<hysteria2 URI>",
      "telegram_proxy.txt": "<mtproto credentials>",
      "ssh.txt": "<ssh credentials>"
    },
    "xray_links": ["vless://uuid@host:443?type=tcp&security=reality#ali"]
  }
}
```

Only protocols that are **both** allowed for the user **and** active on the
panel are listed. When `access_ok` is false, `configs` is `{}` and
`xray_links` is `[]`.

## 3. Required client behaviour

1. **Accept any sub-link form.** Users paste the page URL
   (`https://panel:PORT/s/TOKEN`), any feed URL, or the bare token — the app
   normalises all of them to the token and calls `app.json`.
2. **Show quota + expiry from the snapshot** (progress ring, remaining
   days/hours, per-protocol tabs).
3. **Gate every connect.** Before connecting — and on every `status` poll
   while connected — if `access_ok` is false **or** the feed answers 403,
   the app must **not connect / must disconnect** and must show
   `access_reason` to the user (Persian default, English fallback).
4. **Connect per protocol:**
   - `xray` → in-app Xray core from `xray_links` (VLESS/VMess/Trojan/SS).
   - `wireguard` → in-app WireGuard tunnel from `wireguard.conf`, else the
     official WireGuard app via intent.
   - `openvpn` → in-app OpenVPN core from `*.ovpn`, else OpenVPN Connect /
     ics-openvpn via intent.
   - `hysteria2` → in-app Hysteria2 core from `hysteria2.txt`.
   - `ocserv`/`l2tp`/`pptp`/`ssh`/`telegram_proxy` → native core where the
     OS allows, otherwise hand off to the system client (AnyConnect,
     strongSwan, Telegram) with prefilled credentials.
5. **Poll `status`** every 30–60s in foreground and once before each
   connect; disconnect immediately on `access_ok: false`.
6. **Never cache credentials insecurely** — tokens live in EncryptedShared
   Preferences / DataStore only.

## 4. Versioning

- `min_app_version` in `app.json` tells old app builds to prompt an update.
- Breaking contract changes bump the panel **minor** version and are noted
  here and in `CHANGELOG.md`. Additive fields are safe to ignore.

## 5. Example

```bash
curl -fsSL https://panel:8080/s/TOKEN/app.json | python3 -m json.tool | head -40
curl -fsSL https://panel:8080/s/TOKEN/status
```

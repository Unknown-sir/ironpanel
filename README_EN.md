<div align="center">

<img src="https://s34.picofile.com/file/8491039084/IronpanelN.png" alt="IronPanel" width="140"/>

# IronPanel

**Professional multi-protocol, multi-server VPN management — users, resellers, nodes and tunnels from one console**

![Version](https://img.shields.io/badge/version-2.0.8-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-informational)
![Flask](https://img.shields.io/badge/flask-3.0-green)
![Platform](https://img.shields.io/badge/platform-Ubuntu%2022.04%2F24.04%20%7C%20Debian-orange)
![License](https://img.shields.io/badge/license-Commercial-red)

[🇬🇧 English](README_EN.md) · [🇮🇷 فارسی](README.md) · [Changelog](CHANGELOG.md)

</div>

---

## Overview

IronPanel is more than an account generator: it is a full control center for centralized VPN/Proxy service management — real-core user provisioning, live traffic accounting, subscriptions with QR codes, a complete reseller system, multi-server architectures with Node Gateway & Transparent Relay, genuinely per-user speed limiting, migration-grade backups and a public REST API.

---

## ✨ Features

| Area | Highlights |
|---|---|
| **Users** | Quota/expiry/per-user protocols, bulk operations, range creation, selective & delete-all, fast pagination |
| **First-connection validity** | Optional mode: each user's days start at *their own* first connect (OpenVPN instantly; others ≤15s) |
| **Subscriptions** | Per-user page with QR, single/ZIP downloads, Clash/Sing-box/Hiddify outputs, themable |
| **Speed limits** | Three layers — protocol default / user-wide / per-user×protocol override — enforced for real via tc |
| **Resellers** | Dedicated `/r/<path>` panels, real traffic quotas, auto suspend/restore, **custom config domain** |
| **Card-to-card recharge** | No payment gateway: the reseller enters GB, sees the estimated amount, transfers money and uploads a receipt; the main admin approves or rejects and the volume is credited |
| **Multi-server** | Node Agent, Node Gateway, Transparent Relay, SSH auto node installer (Pro/Admin) |
| **Telegram** | Owner-aware sales bot, admin bot with scheduled reports & 24h backups, managed MTProto proxy |
| **API** | REST v1 & v2 + MirzaBot Custom Panel compatibility |
| **Operations** | Health Doctor with background repair, migration-grade backup/restore, staged GitHub updater, watchdog |
| **Security** | TOTP 2FA, login history, IP/CIDR bans, encrypted node credentials, full audit log |

---

## 🚀 Quick install

**Requirements:** Ubuntu 22.04/24.04 or Debian · root access · Python 3.10+

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

The installer handles everything: venv + dependencies, database & migrations, protocol cores, systemd units/timers, and optional Auto-SSL.

| Path | Purpose |
|---|---|
| `/opt/ironpanel` | Application code & venv |
| `/etc/ironpanel` | SQLite DB, configs, backups |
| Default panel port | `8080` (changeable in Settings) |

Login credentials are printed to the terminal after installation.

---

## 🔄 Updating

```bash
# Fast update from GitHub
sudo bash /opt/ironpanel/scripts/update_from_github.sh

# Safe update with health checks and full logging
sudo bash /opt/ironpanel/scripts/safe_update.sh

# Include an automatic pre-update backup
sudo IRONPANEL_UPDATE_BACKUP=1 bash /opt/ironpanel/scripts/safe_update.sh
```

---

## 🧩 Supported protocols

| Protocol | Use case | Notes |
|---|---|---|
| OpenVPN | General, stable | `.ovpn` output, live auth hook quota enforcement |
| WireGuard | Lightweight & fast | Peer management, DNS/MTU, QR |
| Cisco / Ocserv | AnyConnect | Mobile friendly |
| L2TP/IPsec | Classic | IKEv2 EAP + legacy PSK |
| PPTP | Legacy | Specific compatibility scenarios |
| Xray | VLESS/Reality/TLS/WS/gRPC | Multi-inbound builder, links & QR |
| Hysteria2 | Fast UDP | Great on lossy networks |
| Telegram MTProto | MTProxy | Per-user instance & secret |
| SSH Tunnel | SSH tunneling | Restricted per-user accounts |

---

## 👥 Users & subscriptions

- Total/used/remaining quota with configurable multiplier, measured from every protocol's runtime
- Unlimited or dated expiry + **"start validity on first connection"** (independent per user, even in bulk creation)
- Exact per-user protocol selection: unchecked protocols are neither created nor shown
- Bulk actions: enable/disable, reset traffic, **delete selected accounts**, delete-all (bulk engine also revokes certificates & rebuilds runtime)
- Live online sessions, first-connection timestamp, per-user IP limit & speed limit
- Smart Core Reload: only the affected core reloads, never everything

---

## ⚡ Speed limits — truly per-user

| Layer | Scope |
|---|---|
| Protocol default | Every user of that protocol, individually and simultaneously |
| User-wide limit (⚡) | All protocols of *that one user* (one shared tc class) |
| User×protocol override | Exactly that combination |

Enforcement uses `tc/iptables` egress shaping; each user is identified by their active session's public IP (OpenVPN/WG/Ocserv/L2TP from live status, **Xray from access.log emails** — loglevel is switched automatically, Hysteria2 from the journal, Telegram Proxy via dedicated per-user ports). Node-relayed traffic is shaped through a FORWARD hook too. Technically unseparable cases are surfaced explicitly as pending notes in the Speed Limits status output.

---

## 🤝 Resellers

- Dedicated panel at your own path, account-count cap plus **real consumed traffic** (not allocated)
- Automatic suspension when limits are exhausted + automatic restore of only healthy users afterwards
- Per-reseller allowed protocols, enforced server-side too
- **Custom config domain**: a reseller's own users get configs pointing at that domain; empty = main panel address
- **External sales bot via 4 API families**: resellers don't use the built-in bot builder — each reseller owns dedicated API keys (v1, v2, MirzaBot and a new **3x-ui compatible** API) for an external bot

---

## 💳 Manual card-to-card recharge (no payment gateway)

Reseller panel top-ups are fully manual and **do not involve any payment gateway**:

- The main admin configures the **"Card-to-card recharge"** page (`/cards`): destination card number, account holder, payment instructions text, price per GB (Rial) and the minimum purchase amount.
- On **"Panel recharge"** (`/reseller/storage`) a reseller enters the required GB; the estimated amount (= GB × price per GB) is shown instantly, they transfer the money to the admin's card and upload the **receipt image** with the request.
- Requests show as cards that open in a **popup modal** (receipt image, requested volume, amount and reseller). **Approve** credits the volume to the reseller quota and re-enables a suspended panel; **Reject** closes the request without crediting anything. Only **pending** requests are listed — processed ones disappear.
- When a reseller's volume runs out the panel is automatically suspended, the message **"Panel disabled: volume exhausted"** is shown and only the recharge section is reachable; every reseller API also blocks creating/renewing/charging services until a top-up is approved.

---

## 🤖 Reseller sales bot — connect an external bot with a dedicated API

The panel built-in bot builder is **not** used for resellers. Each reseller automatically gets **four API credentials** on the **"Sales bot API"** page (`/reseller/bot`) and connects any external bot:

| API | Endpoint | Auth | Notes |
|---|---|---|---|
| **v1** (classic) | `/api/v1` | `X-API-KEY` | legacy scripts and bots |
| **v2** | `/api/v2` | `Authorization: Bearer <token>` | reseller-scoped token |
| **MirzaBot** | `/api/mirzabot/v1` | `X-API-Key` | MirzaBot-compatible actions |
| **3x-ui** (new) | `/api/xui` | `X-API-KEY` or `POST /api/xui/login` | mirrors [3x-ui](https://github.com/MHSanaei/3x-ui) |

The 3x-ui family supports `POST /login`, `GET /panel/api/inbounds/list`, `POST /panel/api/inbounds/addClient` (create user → returns the **subscription URL**), `GET /panel/api/inbounds/getClientTraffics/{email}`, `POST /panel/api/inbounds/updateClient/{inboundId}/{email}`, `POST /panel/api/inbounds/delClient/{inboundId}/{email}`, `POST /panel/api/inbounds/delDepletedClients/{inboundId}` and `GET /sub/{subId}` (raw subscription content).

The bot can **create** users, **read** them and their info, **send** the subscription link/config to customers, and **delete/edit** users. Every call is scoped to the reseller's own users, and while the reseller's volume is exhausted (or the user cap is reached) creating and editing/renewing return HTTP 403 — only reading, sending the subscription and deleting keep working.

---

## 🛰️ Nodes, Gateway & Transparent Relay

```
User ──► Main Panel Endpoint ──► Transparent Relay ──► Selected Node
```

- Clients keep connecting to the main endpoint; node IPs are never exposed
- Direct Location: per-node configs inside the subscription with flag & label
- Auto rebalance by ping/load, force protocols onto specific nodes
- In-panel SSH auto installer (password/key/passphrase/sudo) — Pro/Admin only

---

## 🔌 API

| Version | Path | Auth |
|---|---|---|
| v1 | `/api/v1` | `X-API-Key` |
| v2 | `/api/v2` | Token (`POST /api/v2/auth/token`) |
| MirzaBot | `/api/mirzabot/v1` | Dedicated `X-API-Key` |

Full docs: [`docs/API_GUIDE.md`](docs/API_GUIDE.md) · [`docs/API.md`](docs/API.md) · [`docs/openapi.yaml`](docs/openapi.yaml)

---

## 💾 Migration-grade backup & restore

Backups capture an atomic DB snapshot plus complete protocol identities (OpenVPN PKI/tls-crypt, WireGuard keys, SSL/Let's Encrypt, Ocserv, L2TP/IKEv2, Xray, Hysteria2, env/secrets and units); restores validate checksums/schema and keep an automatic rollback copy.

```bash
cd /opt/ironpanel && sudo .venv/bin/flask --app run.py safe-backup
```

---

## 🧰 Handy commands

```bash
systemctl status ironpanel --no-pager          # panel status
sudo systemctl restart ironpanel               # restart
journalctl -u ironpanel -n 150 --no-pager      # logs
sudo ironpanelctl repair                       # general repair
sudo bash scripts/ironpanel_doctor.sh          # full diagnostics
sudo bash scripts/update_from_github.sh        # update
```

---

## 🗂 More documentation

- [CHANGELOG.md](CHANGELOG.md) — full version history
- [`docs/`](docs/) — per-release technical notes + OpenAPI spec
- [SECURITY.md](SECURITY.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

IronPanel is released under its [commercial license](LICENSE). The free **Beginner** edition runs without a key (OpenVPN + Xray). Feature comparison:

| Feature | 🆓 Beginner | 💠 Plus | 🚀 Pro | 👑 Admin | 🎁 Trial |
|---|---|---|---|---|---|
| All protocols (OpenVPN/Xray/WG/Ocserv/L2TP/PPTP/Hysteria2/MTProto/SSH) | OpenVPN + Xray only | ✅ | ✅ | ✅ | ✅ |
| Networking / Subscriptions / Monitoring | ❌ | ✅ | ✅ | ✅ | ✅ |
| Node Agent & Node Auto Installer | ❌ | ❌ | ✅ | ✅ | ✅ (no Auto Installer) |
| Sales bot | ❌ | ❌ | ✅ | ✅ | ✅ |
| Finance & billing | ❌ | ❌ | ❌ | ✅ | ✅ |
| Node Gateway / Multi-server | ❌ | ❌ | ✅ | ✅ | ✅ |
| Public API & updates | ✅ | ✅ | ✅ | ✅ | ✅ |

<div align="center">

**IronPanel — One panel, many protocols, many nodes, complete control**

</div>

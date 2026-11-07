# IronPanel v2.0.5 — Per-Protocol Domain Overrides

The main admin can now assign a **dedicated domain to each VPN protocol** so that the
generated client configs for that protocol use that specific domain instead of the
panel-wide default.

## Where to configure it

- Admin menu → **Network & Domains → Per-protocol domains** (`/protocol-domains`)
- Available only to the **main admin**.

For each protocol you can enter an optional domain:

| Protocol      | Where the domain appears in the client config |
|---------------|-----------------------------------------------|
| OpenVPN       | `remote <host> <port>`                        |
| WireGuard     | `Endpoint = <host>:<port>`                    |
| Ocserv        | `Server: <host>:<port>`                       |
| L2TP / IKEv2  | `Server: <host>`                              |
| PPTP          | `Server: <host>`                              |
| Hysteria2     | `hy2://user@<host>:<port>/...`                |
| SSH           | `Server: <host>`                              |
| Xray          | `vless://...@<host>:<port>`, v2ray/trojan/ss `add` / host |
| Telegram Proxy| `tg://proxy?server=<host>&...`                |

Clash Meta and SingBox subscription formats also honor the per-protocol Xray domain.

## Override behavior

- **Empty field** → the protocol keeps using the panel defaults
  (`Public Host` / `Tunnel Host`, or Xray's own `xray_domain`).
- **Non-empty field** → that domain is used for the protocol's client config.
- Ports and all other protocol settings are still read from the main panel settings.
- The per-reseller `config_domain` still applies for a reseller's own customers, and
  per-node **Direct Location** addresses still take precedence for node-served configs.

## Implementation

- `resolve_protocol_domain(user, protocol, default)` in `app/services/provisioning.py`
  returns the per-protocol override (if any) by reading `AppSetting` key
  `protocol_domain_<protocol>`, else the caller's default.
- Injection points: `generate_profiles()` (OpenVPN/WG/Ocserv/L2TP/PPTP/Hy2/SSH),
  `telegram_proxy_link_for()`, `xray_link()`, and the Clash/SingBox subscription writers.

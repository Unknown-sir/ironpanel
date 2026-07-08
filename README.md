# IronPanel v17

IronPanel v17 is a multi-protocol VPN management and sales platform with advanced multi-node operations, full Xray/V2Ray support, outbound routing, professional subscription outputs, live monitoring, backup/restore, sales automation, and API v2/v17 integrations.

> This repository package intentionally focuses on IronPanel. Installation and publishing instructions are documented separately.

## Major v17 Highlights

- Real multi-node workflow with node token, heartbeat, metrics, remote jobs and per-node protocol support.
- Advanced Xray/V2Ray engine profiles with validation, client-ready outputs and compatibility for v2rayNG, Hiddify, Nekoray, Sing-box and Clash Meta.
- Outbound Routing v2 with multiple outbound profiles, protocol-to-outbound mapping, failover planning, kill-switch mode and connectivity tests.
- Professional subscription outputs: raw links, QR, Clash Meta, Sing-box and Hiddify-compatible feeds.
- Sales bot synchronization with protocol packages, node-aware plans, Xray/V2Ray plan types, renewal, extra traffic, reminders and manual payments.
- Live monitoring and logs for VPN cores, Xray, outbound, node-agent, bots and usage sync.
- Backup / restore v2 with scheduled backup metadata, full config backup, database backup and Telegram delivery hooks.
- UX improvements: setup wizards, user creation wizard, Xray wizard, outbound wizard, filters, bulk user actions and service repair cards.
- API expansion for users, nodes, monitoring, outbound, subscriptions, backups and sales.

## Supported protocols

- OpenVPN
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray / V2Ray

## Xray / V2Ray profiles

- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + WebSocket without TLS
- VLESS + TCP without TLS
- VLESS + gRPC without TLS
- VMess + TCP / WebSocket
- Trojan + TLS / TCP without TLS
- Shadowsocks 2022 compatible mode

Only one active Xray profile is delivered to users. The administrator chooses the active Xray profile in the panel and the subscription page exports only that profile.

## License compatibility

v17 keeps the previous license structure compatible while adding v17 feature flags. Xray, Outbound Routing, Subscription outputs, Backup, Monitoring and API are available across all license types. Features like Nodes, Sales Bot, Billing and Network keep their existing type-based restrictions.

## Dashboard and design

The UI uses the v16.6 Enterprise Security / SOC dark dashboard design and extends it with v17 cards for nodes, routing, backups, subscriptions and live logs.

## Documentation

- `docs/V17_ENTERPRISE.md`
- `docs/V17_NODE_AGENT.md`
- `docs/V17_SUBSCRIPTIONS.md`
- `docs/V17_OUTBOUND_V2.md`
- `docs/API_GUIDE.md`

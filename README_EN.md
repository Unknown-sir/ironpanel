<div align="center">

# ⚙️ IronPanel

### A multi-protocol VPN/proxy control panel with users, subscriptions, nodes, relays and safe operations

![IronPanel](https://s34.picofile.com/file/8490877984/Ironpanel.png)

**IronPanel** is designed to manage VPN/proxy users, subscriptions, resellers, SSL, DNS, speed limits, routing rules, node gateways and maintenance workflows from one central dashboard.

</div>

---

## Highlights

- Multi-protocol user and configuration management
- Subscription links, QR codes and per-protocol outputs
- Auto SSL, DNS presets, WireGuard MTU and routing rules
- Speed limits per protocol and per user
- Health Doctor, protocol repair, safe backup/restore and safe update
- Firewall IP/CIDR ban with dedicated chains
- Node Agent, Node Gateway, Transparent Relay and Auto Sync
- Automatic node installation over SSH for Pro/Admin licenses
- Encrypted SSH credentials for saved node access

---

## Quick Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

## Update

Fast GitHub update:

```bash
sudo bash /opt/ironpanel/scripts/update_from_github.sh
```

Safe update with backup and health checks:

```bash
sudo bash /opt/ironpanel/scripts/safe_update.sh
```

---

## Supported Protocols

| Protocol | Status | Notes |
|---|:---:|---|
| OpenVPN | ✅ | `.ovpn` output, usage accounting and auth hooks |
| WireGuard | ✅ | DNS, MTU, peers and QR codes |
| Cisco / Ocserv | ✅ | AnyConnect-compatible SSL VPN |
| L2TP/IPsec | ✅ | Classic mobile/desktop VPN |
| PPTP | ✅ | Legacy compatibility |
| Xray | ✅ | VLESS/Reality/TLS with subscriptions |
| Hysteria2 | ✅ | High-speed UDP profile output |
| Telegram MTProto Proxy | ✅ | Dedicated secrets and configurable ports |
| SSH | ✅ | SSH tunnel accounts |

---

## Node Gateway and Transparent Relay

IronPanel supports tunnel-style multi-server deployments where the client keeps connecting to the main panel endpoint while the main server relays traffic to the selected node.

```text
User / Tunnel
     ↓
Main Panel Endpoint
     ↓
IronPanel Transparent Relay
     ↓
Selected Node
     ↓
IronPanel Transparent Relay
     ↓
User / Tunnel
```

This keeps node IPs hidden from client configs and makes the response path deterministic for tunnel deployments.

---

## Automatic SSH Node Installer

Starting with v19.9, IronPanel can install nodes directly from the web panel through SSH.

Supported methods:

- SSH username/password
- SSH private key
- key passphrase
- optional sudo password
- encrypted saved credentials
- auto dependency installation
- node agent installation
- core repair/install
- config and user sync
- gateway/relay apply and health checks

This feature is available for **Pro** and **Admin** licenses.

---

## Plan Matrix

| Feature | Beginner / Free | Plus | Pro | Admin |
|---|:---:|:---:|:---:|:---:|
| No-license basic mode | ✅ | ❌ | ❌ | ❌ |
| OpenVPN | ✅ | ✅ | ✅ | ✅ |
| Xray | ✅ | ✅ | ✅ | ✅ |
| Other protocols | ❌ | ✅ | ✅ | ✅ |
| Subscriptions and QR | ✅ | ✅ | ✅ | ✅ |
| DNS, routing and speed limits | ✅ | ✅ | ✅ | ✅ |
| Reseller management | ✅ | ✅ | ✅ | ✅ |
| Node Agent / Node Gateway | ❌ | ❌ | ✅ | ✅ |
| Transparent Relay | ❌ | ❌ | ✅ | ✅ |
| Auto SSH Node Installer | ❌ | ❌ | ✅ | ✅ |
| Sales bots | ❌ | ❌ | ✅ | ✅ |
| Full finance features | ❌ | ❌ | ❌ | ✅ |

---

## Useful Commands

Panel status:

```bash
systemctl status ironpanel --no-pager
```

Restart panel:

```bash
sudo systemctl restart ironpanel
```

Panel logs:

```bash
journalctl -u ironpanel -n 150 --no-pager
```

Apply node gateway:

```bash
sudo bash /opt/ironpanel/scripts/apply_node_gateway.sh --apply
```

Clear node gateway:

```bash
sudo bash /opt/ironpanel/scripts/apply_node_gateway.sh --clear
```

---

## Documentation

Version-specific documentation is available in the `docs/` directory. See `CHANGELOG.md` for the full release history.

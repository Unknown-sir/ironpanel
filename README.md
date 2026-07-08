# IronPanel v17

**فارسی:** [README_FA.md](README_FA.md)

**IronPanel** is an advanced multi-protocol, multi-node VPN management platform designed for server administrators, VPN service providers, support teams, and businesses that need a complete system for managing users, protocols, subscriptions, sales automation, outbound routing, monitoring, backups, and service delivery.

<p align="center">
  <img src="https://s34.picofile.com/file/8490837600/Screenshot_6.png" alt="IronPanel Dashboard" width="420">
  <img src="https://s34.picofile.com/file/8490837600/Screenshot_7.png" alt="IronPanel Dashboard" width="420">
</p>

---

## Overview

IronPanel has evolved into a full VPN management and automation platform by version **v17**. It supports classic VPN protocols, Xray/V2Ray, multi-node infrastructure, advanced outbound routing, Telegram sales automation, professional subscriptions, live monitoring, backup and restore, bulk user operations, API access, and a modern security-focused dashboard.

---

## Core Features

### Multi-Protocol VPN Management

IronPanel supports several VPN and proxy protocols from one unified panel:

- OpenVPN
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray / V2Ray
- VLESS
- VMess
- Trojan
- Shadowsocks
- Reality
- WebSocket
- gRPC
- TCP without TLS
- TLS / Reality / No TLS profiles

Administrators can enable, disable, configure, and deliver protocol-specific configurations from a centralized interface.

---

## Xray / V2Ray Core

Xray Core is fully integrated into IronPanel. The administrator selects one active Xray profile, and users receive only that selected configuration type instead of receiving every available Xray profile.

### Xray Features

- Admin-selected active Xray profile
- Standard `vless://`, `vmess://`, `trojan://`, and `ss://` links
- Raw output for v2rayNG, Hiddify, Nekoray, Sing-box, and Clash Meta
- QR Code generation
- Configuration validation before delivery
- Automatic UUID generation
- Automatic Reality key and Short ID generation
- Reality Vision support
- WebSocket + TLS support
- WebSocket without TLS support
- TCP without TLS support
- gRPC support
- Xray service status monitoring
- Automatic Xray repair tools
- User traffic tracking for Xray
- Xray support inside the Telegram sales bot

---

## Advanced Subscription System

The Subscription page is one of the main user-facing components in IronPanel. It allows users to receive configurations in formats compatible with multiple clients.

### Supported Outputs

- OpenVPN file
- WireGuard file
- WireGuard QR Code
- AnyConnect / Ocserv details
- L2TP/IPsec details
- Xray / V2Ray link
- `xray.txt` file
- Raw subscription
- Hiddify output
- Sing-box output
- Clash Meta output
- Dedicated subscription URL
- Subscription token reset

---

## Node System in v17

IronPanel v17 introduces an advanced Node System. The main panel can run on one server while other servers operate as VPN nodes through the Node Agent.

### Node System Features

- Node creation from the main panel
- Node Token generation
- Node Agent installation on remote servers
- Secure node-to-master connection
- Online / Offline node status
- Periodic heartbeat
- CPU, RAM, Disk, and Traffic monitoring per node
- Protocol selection per node
- Node selection when creating users
- User migration between nodes
- Bulk user migration
- Node-level Health Check and Repair
- Node Agent live logs

---

## Outbound Routing

Outbound Routing allows selected protocol traffic to be routed through an external outbound configuration. Admins can define outbound profiles and choose which protocols should use them.

### Features

- OpenVPN Client configuration as outbound
- Xray/V2Ray outbound links
- Support for `vless://`, `vmess://`, `trojan://`, and `ss://`
- Connection test before applying
- Protocol selection for outbound routing
- Failover support
- Kill Switch support
- Route Mode selection
- Outbound IP check
- DNS leak check
- Quick enable / disable controls

---

## Telegram Sales Bot

IronPanel includes an integrated Telegram sales bot for selling VPN services. The bot is synchronized with v17 features and can sell both classic VPN and Xray/V2Ray services.

### Bot Features

- Bot Token registration from the panel
- Telegram Admin IDs configuration
- Sales plan creation
- Plan name, traffic, price, and duration settings
- Protocol selection per plan
- Xray/V2Ray service sales
- Classic VPN service sales
- All-protocol plan sales
- Free trial with traffic and time limits
- One-time trial per Telegram ID
- Manual payment with receipt upload
- Admin approval or rejection
- Automatic user creation after order approval
- Subscription delivery after purchase
- Xray/V2Ray file delivery
- Service renewal
- Extra traffic purchase
- User service status display
- Expiration and traffic usage reminders

---

## User Management

IronPanel provides a complete user management system.

### User Features

- Create users
- Edit users
- Delete users
- Enable / disable users
- Renew accounts
- Change traffic limit
- Change expiration date
- Reset traffic
- Traffic limit enforcement
- Expiration enforcement
- Unlimited traffic or expiration using `0`
- Upload and download traffic display
- Online / Offline status
- Active protocol display
- User configuration delivery
- Bulk Actions
- Bulk renewal
- Bulk deletion
- Bulk traffic reset
- Bulk migration to another node

---

## Monitoring and Health Check

IronPanel v17 includes advanced monitoring and live logs.

### Monitoring Sections

- CPU usage
- RAM usage
- Disk usage
- Swap usage
- Service status
- OpenVPN status
- WireGuard status
- Ocserv status
- L2TP/IPsec status
- Xray status
- Sales bot status
- Node Agent status
- Outbound status
- Database status
- GitHub update status
- Live service logs
- Service Repair buttons

---

## Backup / Restore

IronPanel v17 includes an advanced backup and restore system.

### Backup Features

- Database backup
- User backup
- Panel settings backup
- OpenVPN settings backup
- WireGuard settings backup
- Xray settings backup
- Outbound settings backup
- Sales bot settings backup
- Node configuration backup
- Backup download from panel
- Restore from backup file
- Scheduled daily backup
- Backup before update

---

## Dashboard and UI

Since version 16.6, IronPanel uses an **Enterprise Security / SOC Dashboard** design style.

### UI Features

- Dark security dashboard theme
- Modern cards and widgets
- Risk and health status cards
- Protocol status overview
- Online user table
- System resource monitoring
- New topbar
- Categorized sidebar
- Redesigned tables and forms
- UI support for Xray, Outbound, Nodes, and Monitoring pages

---

## API v17

IronPanel provides API access for external integrations and automation.

### API Areas

- Users API
- Subscription API
- Nodes API
- Monitoring API
- Outbound API
- Health API
- Sales Bot API
- Logs API
- Backup API

---

## License-Aware Feature Structure

IronPanel is compatible with a multi-level license structure. v17 features are aligned with the licensing system.

### License Types

- Beginer
- Plus
- Pro
- Admin License
- Trial

### Important Note

In newer versions, base Xray and Outbound features can be enabled for all license types, while administrative areas such as Nodes, Finance, Sales, or Network can be controlled according to the active license type.

---

# Manual Main Panel Installation

This section describes manual panel installation by downloading the project from GitHub, entering the project directory, and running the installer file.

## Requirements

- Ubuntu 20.04 / 22.04 / 24.04 or Debian 11 / 12
- Root or sudo access
- A valid domain or IP address for the panel
- Internet access on the server
- Required ports opened on firewall

## Download the Project from GitHub

```bash
sudo apt update
sudo apt install -y git curl unzip
cd /opt
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
```

## Run the Panel Installer

```bash
sudo bash install.sh
```

During installation, the installer asks for required values such as panel port, admin username, admin password, panel domain or IP, and initial configuration options.

## Check Service Status

```bash
sudo systemctl status ironpanel --no-pager
sudo systemctl status ironpanel-sales-bot --no-pager
sudo systemctl status xray --no-pager
```

## Restart Services

```bash
sudo systemctl restart ironpanel
sudo systemctl restart ironpanel-sales-bot
sudo systemctl restart xray
```

## Important Paths

```text
/opt/ironpanel
/etc/ironpanel/ironpanel.env
/usr/local/etc/xray/config.json
/var/log/ironpanel
/var/log/xray
```

---

# Manual Node Installation

To use multiple servers, install the main panel first, then create a node inside the main panel and copy the generated Node Token.

## Create a Node in the Main Panel

Open the main panel and go to:

```text
VPN & Infrastructure → Nodes → Add Node
```

Enter the following information:

```text
Node Name
Node IP / Domain
Location
Active Protocols
```

After saving, the panel generates a **Node Token**.

## Install Node Agent on the Node Server

Run these commands on the node server:

```bash
sudo apt update
sudo apt install -y git curl unzip
cd /opt
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash scripts/install_node.sh
```

During node installation, provide:

```text
Master Panel URL
Node Token
Node Public IP / Domain
Protocols
```

Example:

```text
Master Panel URL: https://panel.example.com
Node Token: NODE_TOKEN_HERE
Node Host: node1.example.com
Protocols: openvpn,wireguard,xray,ocserv,l2tp
```

## Check Node Status

```bash
sudo systemctl status ironpanel-node --no-pager
sudo journalctl -u ironpanel-node -n 100 --no-pager
```

## Restart Node Agent

```bash
sudo systemctl restart ironpanel-node
```

## Verify the Node from Main Panel

Return to the main panel and use:

```text
Check Connection
```

If everything is configured correctly, the node status should become Online.

---

## Recommended Ports

```text
22/tcp      SSH
80/tcp      HTTP / ACME
443/tcp     HTTPS / TLS / Xray / Ocserv
443/udp     Ocserv UDP / QUIC profiles
1194/tcp    OpenVPN TCP
1194/udp    OpenVPN UDP
51820/udp   WireGuard
500/udp     IPsec
4500/udp    IPsec NAT-T
1701/udp    L2TP
8443/tcp    Panel or custom service
```

Example UFW rules:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw allow 1194/tcp
sudo ufw allow 1194/udp
sudo ufw allow 51820/udp
sudo ufw allow 500/udp
sudo ufw allow 4500/udp
sudo ufw allow 1701/udp
sudo ufw reload
```

---

## Suggested Project Structure

```text
ironpanel/
├── app/
│   ├── blueprints/
│   ├── services/
│   ├── templates/
│   └── static/
├── bot/
├── scripts/
├── docs/
├── systemd/
├── migrations/
├── install.sh
├── upgrade.sh
└── README.md
```

---

## Who Is It For?

- VPN sellers
- Server administrators
- Network support teams
- Multi-node service providers
- Operators who need multi-protocol VPN management
- Operators who want Telegram-based automated sales
- Teams that need Xray/V2Ray, OpenVPN, and WireGuard in one platform

---

## Project Status

IronPanel v17 is a major version focused on multi-node operation, Xray/V2Ray stability, outbound routing, advanced monitoring, backup and restore, and professional subscription outputs.

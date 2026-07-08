<div align="center">

# IronPanel v17

### Enterprise VPN Management, Multi-Node Infrastructure, Advanced Routing & Sales Automation

<p>
  <b>IronPanel</b> is a modern multi-protocol VPN management platform for administrators, VPN providers, support teams, and service operators who need centralized control over users, protocols, nodes, subscriptions, monitoring, routing, and sales workflows.
</p>

<p>
  <a href="./README_FA.md">نسخه فارسی README</a>
</p>

<p>
  <img src="https://s34.picofile.com/file/8490837600/Screenshot_6.png" alt="IronPanel Dashboard" width="460">
  <img src="https://s34.picofile.com/file/8490837600/Screenshot_7.png" alt="IronPanel Dashboard" width="460">
</p>

<p>
  <img src="https://img.shields.io/badge/version-v17.0-red?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Multi--Protocol-VPN-blue?style=for-the-badge" alt="Protocols">
  <img src="https://img.shields.io/badge/Xray%20%2F%20V2Ray-Advanced-green?style=for-the-badge" alt="Xray">
  <img src="https://img.shields.io/badge/UI-SOC%20Dashboard-orange?style=for-the-badge" alt="SOC UI">
</p>

</div>

---

## Overview

**IronPanel v17** is a complete VPN management and sales platform designed to manage multiple VPN protocols, users, nodes, subscriptions, Telegram sales automation, traffic limits, service health, backups, and advanced routing from a single modern web panel.

Version 17 focuses on infrastructure-level improvements: advanced node management, stronger Xray/V2Ray integration, smart subscriptions, outbound routing, live logs, backup and restore, API improvements, and better operational tooling.

---

## Core Features

### Multi-Protocol VPN Management

IronPanel supports multiple VPN protocols in one unified dashboard:

- OpenVPN
- WireGuard
- Cisco AnyConnect / Ocserv
- L2TP/IPsec
- Xray / V2Ray

Administrators can create users, manage limits, set expiration dates, reset traffic, disable accounts, view online status, and deliver client-ready configurations from one place.

---

## OpenVPN

OpenVPN support is designed for certificate-based user delivery and stable client operation.

Features:

- Dedicated OpenVPN profile per user
- Profile filename matching the username
- TCP and UDP support based on admin settings
- Certificate-only connection flow
- No username/password prompt for the client profile
- Upload and download traffic tracking
- Online user detection
- OpenVPN service health monitoring
- Repair tools for common OpenVPN issues
- Traffic and expiration enforcement

---

## WireGuard

WireGuard features:

- Per-user key generation
- WireGuard config file delivery
- QR Code generation
- Last handshake status
- Traffic accounting
- Traffic reset
- Subscription integration
- Sales Bot integration

---

## Cisco AnyConnect / Ocserv

Features:

- Ocserv user management
- Service status monitoring
- TCP/UDP support according to service configuration
- Traffic and expiration enforcement
- Connection details through subscription
- Health Check and Repair support

---

## L2TP/IPsec

Features:

- L2TP/IPsec user management
- Service health visibility
- Traffic and expiration integration
- Suitable for legacy devices and clients

---

## Xray / V2Ray Core

Xray/V2Ray support was introduced in the v16 series and is expanded in v17 for more reliable delivery, validation, subscription output, and sales automation.

### Supported Xray Profiles

- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + TCP without TLS
- VLESS + WebSocket without TLS
- VLESS + gRPC without TLS
- VMess + WebSocket
- VMess + TCP without TLS
- Trojan + TLS
- Trojan + TCP without TLS
- Shadowsocks

### Xray / V2Ray Features

- One active Xray profile selected by the administrator
- User receives only the selected Xray profile
- Automatic UUID generation per user
- Reality key and Short ID generation
- QR Code output
- Raw Xray URI output
- `xray.txt` profile delivery
- Config validation before applying changes
- Xray service health check
- Xray repair tools
- TLS, Reality, and no-TLS profile support
- User traffic accounting
- Subscription integration
- Telegram Sales Bot integration

---

## Subscription System

IronPanel provides a flexible subscription system for delivering user configurations to supported clients.

Features:

- Dedicated subscription link per user
- Raw Xray/V2Ray output
- Hiddify-compatible output
- Sing-box-compatible output
- Clash Meta-compatible output
- v2rayNG-compatible output
- Subscription token reset
- User service status display
- Used and remaining traffic display
- Expiration date display
- Delivery for OpenVPN, WireGuard, and Xray based on user access

---

## Node System v17

IronPanel v17 introduces a stronger multi-node architecture for managing multiple servers from the main panel.

Features:

- Multiple node definitions
- Token-based node connection
- Node Agent support
- Heartbeat-based online/offline detection
- CPU, RAM, disk, and traffic metrics per node
- Per-node protocol availability
- User assignment to nodes
- User migration between nodes
- Node Health Check and Repair
- API and monitoring integration

---

## Outbound Routing

Outbound Routing allows the administrator to route selected protocol traffic through an external outbound configuration.

Features:

- OpenVPN client profile as outbound
- V2Ray/Xray URI as outbound
- Support for `vless://`, `vmess://`, `trojan://`, and `ss://`
- Connection test before applying configuration
- Protocol selection for outbound routing
- OpenVPN, WireGuard, Ocserv, L2TP/IPsec, and Xray support
- Multiple outbound profiles
- Failover
- Kill Switch
- Route Mode selection
- Outbound IP and connection status checks

---

## Telegram Sales Bot

IronPanel includes a Telegram-based sales bot for selling VPN services and delivering configurations automatically.

Features:

- Inline-button based user experience
- Admin plan management
- Plan pricing
- Service duration configuration
- Traffic limit configuration
- Free trial enable/disable option
- One-time trial per Telegram ID
- Manual payment flow with receipt submission
- Admin approval or rejection
- Automatic user creation after payment approval
- Subscription delivery after purchase
- Xray/V2Ray profile delivery
- Classic VPN and Xray/V2Ray service sales
- Service renewal
- Extra traffic purchase
- User service status display
- Expiration and traffic usage reminders

---

## Dashboard and User Interface

Since v16.6, IronPanel uses a modern Enterprise Security / SOC-style dashboard design. Version 17 continues this design direction with stronger operational visibility.

Dashboard features:

- Dark modern UI
- System health card
- Risk/status card
- Service status cards
- CPU, RAM, disk, and swap metrics
- Node status overview
- Online users table
- Traffic overview
- Xray and Outbound status
- Panel version status
- License status

---

## Health Check / Repair

The Health Check / Repair module is designed to help administrators detect and fix service issues quickly.

Features:

- OpenVPN checks
- WireGuard checks
- Xray checks
- Ocserv checks
- L2TP/IPsec checks
- Sales Bot checks
- Database checks
- systemd status output
- journalctl output
- Repair buttons for important services
- Safe error rendering to prevent page crashes

---

## Live Logs

Live Logs provide quick access to operational logs directly from the panel.

Log sections:

- IronPanel
- OpenVPN
- WireGuard
- Xray
- Ocserv
- Sales Bot
- Usage Sync
- Node Agent
- Outbound Routing

---

## Backup / Restore v2

Backup and Restore tools are designed to protect panel data and configuration.

Features:

- Database backup
- Panel settings backup
- VPN configuration backup
- Xray configuration backup
- Outbound configuration backup
- Sales Bot settings backup
- User data backup
- Restore from backup file
- Scheduled backups
- Pre-update backup support

---

## User Management

User management features:

- Create users
- Edit users
- Delete users
- Enable or disable users
- Set traffic limits
- Set expiration dates
- Unlimited traffic with value `0`
- Unlimited expiration with value `0`
- Reset traffic
- View online status
- View upload and download usage
- Bulk Actions
- Bulk renewal
- Bulk delete
- Bulk traffic reset
- Bulk node migration

---

## API v17

IronPanel includes API support for external systems, bots, automation, and integrations.

API areas:

- Users
- Nodes
- Monitoring
- Sessions
- Subscription
- Health
- Outbound
- Backup
- Sales
- Logs

Supported authentication methods:

- API Key
- Bearer Token
- Permission-scoped tokens

---

## Update Manager

The Update Manager helps administrators track and apply project updates directly from the panel.

Features:

- Current version status
- Latest version check
- Update Available indicator
- Panel-based update flow
- Update log display
- Related service restart workflow

---

## License Compatibility

IronPanel features are aligned with the configured license tier.

Supported license types:

- beginer
- plus
- pro
- admin license
- trial

Version 17 capabilities such as Xray, Outbound Routing, Backup, Subscription, Monitoring, and Node-related features are aligned with the license compatibility model. Trial licenses are designed as 7-day full-feature evaluation licenses.

---

## Use Cases

IronPanel is suitable for:

- VPN service providers
- Server administrators
- Support teams
- Multi-protocol VPN operators
- Telegram-based VPN sales
- Multi-node infrastructure management
- Xray/V2Ray subscription delivery
- Advanced outbound routing and monitoring workflows

---

## Version 17 Summary

IronPanel v17 is a major infrastructure release that expands the panel from a classic VPN management tool into a complete platform for management, sales, monitoring, nodes, subscriptions, backups, and advanced routing.

Main v17 highlights:

- Multi-Node Management
- Advanced Xray/V2Ray
- Smart Subscription
- Outbound Routing v2
- Sales Bot Integration
- Live Monitoring
- Backup / Restore v2
- API v17
- SOC Dashboard Design

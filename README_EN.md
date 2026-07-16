# IronPanel

![IronPanel](https://s34.picofile.com/file/8490877984/Ironpanel.png)

IronPanel is a multi-protocol VPN/user-management panel with subscriptions, resellers, SSL automation, LicensePanel, Telegram bots and runtime repair tools.

## Quick install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

## Supported protocols

- OpenVPN
- WireGuard
- Cisco / Ocserv
- L2TP/IPsec
- PPTP
- Xray / V2Ray
- Hysteria2
- Telegram MTProto Proxy
- SSH Tunnel / SSH Proxy, default port `422/tcp`

## SSH Protocol

Version `17.0.0` adds SSH as a first-class protocol. IronPanel creates restricted system accounts for enabled users and delivers an `ssh.txt` profile through the user config and subscription pages.

```bash
sudo bash /opt/ironpanel/scripts/repair_ssh.sh --sync
```

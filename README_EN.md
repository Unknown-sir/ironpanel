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

## 17.0.1 — Login UI + Simple Update Manager

- صفحه ورود با طراحی مدرن glass/aurora، حالت responsive و فرم مرتب‌تر بازطراحی شد.
- گزینه Update Manager به منوی ساده مدیر اصلی اضافه شد تا بدون رفتن به بخش‌های پیشرفته قابل دسترسی باشد.
- مستندات پروژه طبق روند جدید به‌روزرسانی شد.



## v17.1.0

- Matrix animated login screen.
- Telegram admin-bot login alerts for successful and failed login attempts.
- Telegram Proxy custom port is preserved during update/repair.
- README tables updated.

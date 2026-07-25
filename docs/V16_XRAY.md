# IronPanel v16 - Advanced Xray Core

IronPanel v16 adds a full Xray Core integration while keeping the subscription output simple for end users.

## Key behavior

- Xray is available for every license type: beginer, plus, pro, admin and trial.
- The admin selects exactly one active Xray profile in the panel.
- Users receive only that selected Xray profile in their subscription page as `xray.txt` plus QR code.
- Existing OpenVPN, WireGuard, Ocserv and L2TP/IPsec behavior remains unchanged.

## Supported Xray profiles

- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- Trojan + TLS
- VMess + WebSocket
- Shadowsocks 2022

## Panel route

`VPN & Infrastructure -> Xray Core`

The page lets the admin configure:

- Xray enable/disable
- single active profile type
- Xray domain/host and port
- Reality destination, SNI, server names, keys, short IDs and fingerprint
- TLS certificate and key paths
- WebSocket path/host
- gRPC service name
- DNS, routing, sniffing, private IP blocking and log level
- local Stats API port for traffic accounting

## Runtime paths

- Xray config: `/usr/local/etc/xray/config.json`
- Xray logs: `/var/log/xray/access.log`, `/var/log/xray/error.log`
- Repair script: `/opt/ironpanel/scripts/repair_xray.sh`

## Useful commands

```bash
sudo bash /opt/ironpanel/scripts/repair_xray.sh
sudo systemctl restart xray
sudo journalctl -u xray -n 100 --no-pager
```

## v16.2 No-TLS Profiles and Repair Fix

`repair_xray.sh` now loads `/etc/ironpanel/ironpanel.env` before touching the Flask app so it uses the real `DATABASE_URL`. It also runs `flask --app run.py upgrade-db` before reading Xray settings, preventing `no such table: app_setting` on manual repair.

Available no-TLS profiles:

- VLESS + TCP without TLS
- VLESS + WebSocket without TLS
- VLESS + gRPC without TLS
- VMess + TCP without TLS
- Trojan + TCP without TLS
- Shadowsocks 2022

Only one selected profile is delivered to each subscriber.

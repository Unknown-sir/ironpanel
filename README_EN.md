# IronPanel v19.8.12 v19.8.1

IronPanel is a multi-protocol VPN/proxy management panel with users, resellers, subscriptions, Auto SSL, DNS presets, speed limits, routing rules and Pro-only Node Gateway load balancing.

Install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

Update from terminal:

```bash
sudo bash /opt/ironpanel/scripts/update_from_github.sh
```


## v19.6.0 Stability
Adds Health Doctor, Safe Backup/Restore and Safe Update command: `sudo bash /opt/ironpanel/scripts/safe_update.sh`.


## 19.7.0
- Rich installation telemetry and safe restricted management actions.
- IronPanel README remains focused on IronPanel only.


### Firewall IP Ban
The Firewall page can now fully block an IPv4/IPv6 address or CIDR through the dedicated `IRONPANEL-BAN` chain.

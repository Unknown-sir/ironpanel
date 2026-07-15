# IronPanel v18.4

**Persian documentation:** [README_FA.md](README_FA.md)

**IronPanel** is a professional VPN management, sales, monitoring and configuration delivery panel. Version v18.4 introduces the built-in free Beginner edition, an in-panel upgrade center, a new **VPN-UI Dark Teal** interface, more protocols, a modern subscription page, QR codes for user configs, improved WireGuard and Cisco AnyConnect/Ocserv reliability, plus PPTP and Hysteria2 support.

<p align="center">
  <img src="https://s34.picofile.com/file/8490835518/Screenshot_5.png" alt="IronPanel Dashboard" width="900">
</p>

## Main Features

- New VPN-UI inspired dark teal dashboard and core settings layout
- User management with expiry, traffic quota, status, protocol permissions and bulk actions
- Modern subscription page with user status, usage summary, downloads and QR codes
- QR Code support for WireGuard, Xray/V2Ray and Hysteria2
- Built-in Telegram sales bot with manual payment workflow
- Multi-node system with Node Agent and secure token connection
- Outbound Routing for routing selected protocols through upstream OpenVPN or Xray/V2Ray profiles
- Backup / Restore, Health Check / Repair, Live Logs and Update Manager
- API for users, nodes, monitoring, subscription outputs and management actions

## Supported Protocols up to v18

| Protocol | Status | Description |
|---|---:|---|
| OpenVPN | Supported | Certificate-only client profiles without client username/password prompt |
| WireGuard | Supported | Key generation, dedicated IP, QR Code and automatic NAT/IP forwarding repair |
| Cisco AnyConnect / Ocserv | Supported | New default port `8445` and Cisco/OpenConnect compatible configuration |
| L2TP/IPsec | Supported | PSK plus username/password authentication |
| Xray / V2Ray | Supported | VLESS/Reality, TLS, No TLS, VMess, Trojan, Shadowsocks and subscription outputs |
| PPTP | Supported | Legacy protocol support for old clients and compatibility scenarios |
| Hysteria2 | Supported | URI, YAML and QR output, suitable for unstable networks and UDP/QUIC-based connections |

## Xray / V2Ray Features

- Admin selects exactly one active Xray profile type for user delivery
- VLESS + Reality + Vision
- VLESS + WebSocket + TLS
- VLESS + TCP without TLS
- VLESS + WebSocket without TLS
- VLESS + gRPC without TLS
- Trojan TLS / No TLS
- VMess WebSocket / TCP
- Shadowsocks
- Raw link, `xray.txt`, QR Code and client-specific outputs
- Hiddify, Sing-box, Clash Meta and raw subscription outputs
- Config validation before delivery

## New Subscription Page

The v18 subscription page includes:

- Account status
- Total, used and remaining traffic
- Expiration date and remaining days
- Download buttons for enabled configs
- Subscription link QR Code
- WireGuard QR Code
- Xray/V2Ray QR Code
- Hysteria2 QR Code
- Hidden OpenVPN and WireGuard raw contents for better safety

## Manual Main Panel Installation

On the main Ubuntu 22.04 or 24.04 server:

```bash
sudo apt update
sudo apt install -y git curl unzip
```

Clone the project from GitHub:

```bash
git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
```

Run the installer:

```bash
sudo bash install.sh
```

During installation, the installer asks for:

- Admin username
- Admin password
- Panel port
- Public server IP or domain
- Tunnel host used inside generated configs
- No license key is required during installation; Beginner Free is enabled automatically
- OpenVPN port
- Cisco/Ocserv port; default is `8445`
- WireGuard port
- Xray port
- PPTP port
- Hysteria2 port

After installation, open:

```text
http://SERVER_IP:PANEL_PORT
```

## Manual Node Installation

First create a node inside the main panel:

```text
VPN & Infrastructure → Nodes → Add Node
```

Copy the generated Node Token. Then run the following commands on the node server:

```bash
sudo apt update
sudo apt install -y git curl unzip

git clone https://github.com/Unknown-sir/ironpanel.git
cd ironpanel
sudo bash scripts/install_node.sh
```

The node installer asks for:

```text
Master Panel URL: https://panel.example.com
Node Token: TOKEN_FROM_PANEL
Node Public IP/Domain: node1.example.com
Protocols: openvpn,wireguard,ocserv,l2tp,xray,pptp,hysteria2
```

After installation, return to the main panel and click **Check Connection** to verify that the node is online.

## Recommended Ports

| Service | Port | Transport |
|---|---:|---|
| Panel | 8080 | TCP |
| OpenVPN UDP | 1194 | UDP |
| OpenVPN TCP | 1195 | TCP |
| Cisco/Ocserv | 8445 | TCP/UDP |
| WireGuard | 51820 | UDP |
| Xray/V2Ray | 443 | TCP |
| Xray API | 10085 | Local TCP |
| L2TP | 1701 | UDP |
| IPsec IKE | 500 | UDP |
| IPsec NAT-T | 4500 | UDP |
| PPTP | 1723 | TCP |
| Hysteria2 | 4433 | UDP |

## Protocol Repair Commands

Use Health Check / Repair inside the panel, or run these commands when needed:

```bash
sudo bash /opt/ironpanel/scripts/repair_wireguard.sh
sudo bash /opt/ironpanel/scripts/repair_ocserv.sh
sudo bash /opt/ironpanel/scripts/repair_pptp.sh
sudo bash /opt/ironpanel/scripts/repair_hysteria2.sh
sudo bash /opt/ironpanel/scripts/repair_xray.sh
```

## Editions and In-Panel Upgrade

IronPanel starts in **Beginner Free** mode immediately after installation. It requires no license key, has no expiration date, and remains usable when the license service is unavailable.

Commercial upgrades are applied from:

```text
Dashboard → Upgrade
```

Enter a Plus, Pro, or Admin key. After successful validation, the matching modules are unlocked immediately. Invalid, expired, removed, or unreachable paid licenses never lock the panel; IronPanel safely falls back to Beginner Free.

| Edition | Licensing | Capabilities |
|---|---|---|
| Beginner Free | No key, no expiration | Core protocols, users, subscriptions, QR codes, monitoring, backup, API; no nodes, sales bot, billing, or network manager |
| Plus | Paid key | Beginner features plus Multi-Node and Node Agent |
| Pro | Paid key | Plus features plus sales bot and network/domain manager |
| Admin License | Paid key | All modules |
| Trial | 7-day trial key | All modules during the trial period |


## Important Paths

```text
/opt/ironpanel                  Application directory
/etc/ironpanel                  Database, settings and user profiles
/etc/wireguard/wg0.conf         WireGuard configuration
/etc/ocserv/ocserv.conf         Cisco/Ocserv configuration
/usr/local/etc/xray/config.json Xray configuration
/etc/hysteria/config.yaml       Hysteria2 configuration
```

## Suitable For

- VPN service providers
- Multi-server VPN operators
- Multi-protocol VPN management
- Telegram-based VPN sales
- User, traffic, node and service monitoring
- Modern subscription and QR based configuration delivery

## License

This project is designed for managed and commercial use. Usage, resale and distribution must follow the project owner's policy.
### Auto SSL for every license tier


Since 18.4.3 Auto SSL also repairs broken system certbot installations. It prefers Snap certbot, detects pyOpenSSL/cryptography failures such as `X509_V_FLAG_NOTIFY_POLICY`, and falls back to a dedicated certbot venv when needed. You can also run `sudo bash scripts/repair_certbot.sh` manually.

Since 18.4.1 the **Auto SSL** page at `/ssl` is available to every tier, including Beginner Free. The panel issues a Let’s Encrypt certificate for the selected domain, stores it under `/etc/ironpanel/ssl/<domain>/`, and wires it to panel TLS, Ocserv/AnyConnect, Hysteria2 and Xray TLS settings. It also updates `public_host` and `tunnel_host` so generated client profiles use the SSL domain.



## نصب مستقیم از GitHub

بعد از اینکه همین نسخه را داخل مخزن GitHub خودت قرار دادی، نصب مستقیم با یک دستور انجام می‌شود:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

اگر مخزن یا branch متفاوت است:

```bash
IRONPANEL_GITHUB_REPO=YOUR_USERNAME/YOUR_REPO IRONPANEL_GITHUB_BRANCH=main bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install.sh)
```

نصب فقط یک مدل دارد: `install.sh`. اسکریپت سؤال‌های اصلی را می‌پرسد و برای گزینه‌های تخصصی مقدار امن پیشنهادی دارد.

## نکته Hysteria2

Hysteria2 روی UDP کار می‌کند. علاوه بر باز بودن پورت داخل سرور، باید UDP پورت انتخابی، پیش‌فرض `4433`، در firewall دیتاسنتر یا Cloud Provider هم باز باشد.

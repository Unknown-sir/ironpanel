# Changelog

## 18.4.1
- Added Auto SSL center available to all license tiers.
- Automatically issues Let’s Encrypt certificates, stores them under /etc/ironpanel/ssl, and wires them to panel TLS, Ocserv, Hysteria2 and Xray TLS settings.
- Added renewal hook and regenerated runtime configs after SSL changes.

## 18.4
- Beginner is now a built-in free edition with no key and no expiration.
- Added the Upgrade center for Plus, Pro and Admin activation.
- Invalid or expired paid licenses fall back to Beginner instead of locking the panel.
- Added 24-hour paid-feature grace for temporary license-server outages.
- Updated dashboard, settings, installer and feature gating for the free model.
- Updated LicensePanel compatibility and paid-plan sales flow.

## v18.2
- Cisco / Ocserv repair was rebuilt using the working configuration: socket-file, occtl-socket-file, device, port 8445, self-signed certificate, IPv4 pool, DNS, default route and NAT.
- Hysteria2 no longer writes the old Let's Encrypt YOUR_DOMAIN placeholder.
- Hysteria2 now works without public SSL/domain certificates by generating a local self-signed certificate and issuing client configs with insecure=true.
- Hysteria2 restart-loop recovery was added with service reset and regenerated config.
- Kept v18 UI, PPTP, Hysteria2, modern subscription page and QR output.


## v18.3
- Fixed dashboard system metrics rendering for CPU, RAM, Disk, Swap and license remaining days.
- Added safe template fallbacks and robust metrics API refresh.
- Updated LicensePanel package to match the IronPanel v18 VPN-UI teal design language.

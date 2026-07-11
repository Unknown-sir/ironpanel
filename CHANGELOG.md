# Changelog

## v18.2
- Cisco / Ocserv repair was rebuilt using the working configuration: socket-file, occtl-socket-file, device, port 8445, self-signed certificate, IPv4 pool, DNS, default route and NAT.
- Hysteria2 no longer writes the old Let's Encrypt YOUR_DOMAIN placeholder.
- Hysteria2 now works without public SSL/domain certificates by generating a local self-signed certificate and issuing client configs with insecure=true.
- Hysteria2 restart-loop recovery was added with service reset and regenerated config.
- Kept v18 UI, PPTP, Hysteria2, modern subscription page and QR output.

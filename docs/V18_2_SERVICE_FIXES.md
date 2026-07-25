# IronPanel v18.2 Service Fixes

## Cisco / Ocserv
The ocserv repair script now writes a complete config with:

- `socket-file = /var/run/ocserv-socket`
- `occtl-socket-file = /var/run/occtl.socket`
- `device = vpns`
- `tcp-port = 8445`
- `udp-port = 8445`
- self-signed certificate paths
- `ipv4-network = 10.44.0.0`
- DNS, default route and NAT

## Hysteria2
Hysteria2 configs no longer use `/etc/letsencrypt/live/YOUR_DOMAIN/...` placeholders. IronPanel generates `/etc/hysteria/server.crt` and `/etc/hysteria/server.key` automatically. Client configs are generated with `insecure: true`, so no public SSL certificate is needed.

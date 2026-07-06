# Security notes

- Ironpanel has no license server or remote activation.
- Change admin password after first login.
- Put the panel behind HTTPS before production use.
- Restrict panel port with firewall rules.
- Review VPN configs under `/etc/ironpanel`, `/etc/openvpn`, `/etc/ocserv`, `/etc/ipsec.conf`, `/etc/xl2tpd`, `/etc/wireguard`.
- Prefer PostgreSQL for high-load multi-admin installations by setting `DATABASE_URL` in `/etc/ironpanel/ironpanel.env`.

# IronPanel Auto SSL

Auto SSL is available in every license tier, including Beginner Free.

Path: `/ssl`

What it does:

- Reads the default domain from `ssl_domain`, `xray_domain`, `tunnel_host` or `public_host`.
- Runs Let’s Encrypt certbot standalone validation for the selected domain.
- Copies the certificate to `/etc/ironpanel/ssl/<domain>/`.
- Updates `public_host` and `tunnel_host` so generated client configs use the SSL domain.
- Wires the certificate to panel Gunicorn TLS, Ocserv, Hysteria2 and Xray TLS settings.
- Optionally switches Xray to `vless-ws-tls`.
- Installs a deploy renewal hook that refreshes copied files and restarts affected services.

Requirements:

- The domain must point to the server IP.
- Port 80 must be reachable from the internet during issuance/renewal.
- The panel must run as root or have permission to write systemd and VPN service files.

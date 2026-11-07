# IronPanel v19.10.10 — OpenVPN TCP/1195 profile and runtime fix

## Fixed

- OpenVPN TCP mode now writes `proto tcp-server` in `/etc/openvpn/server/server.conf`.
- Generated `.ovpn` files now use `proto tcp-client` when OpenVPN transport is TCP.
- Public/Tunnel host values are normalized for VPN profiles; full URLs, panel ports and paths are stripped before writing OpenVPN `remote`, WireGuard `Endpoint`, L2TP, PPTP, SSH and Ocserv profile text.
- Saving Settings now queues `repair_openvpn.sh` in the background, so a changed OpenVPN transport/port is applied to the running daemon instead of only being written to config files.
- `repair_openvpn.sh` was rewritten as a lightweight repair. It no longer performs a heavy full core install or restarts every VPN core.
- If OpenVPN TCP and Ocserv/OpenConnect TCP are configured on the same TCP port, OpenVPN gets priority and Ocserv is moved to a safe fallback port to prevent bind conflicts.

## Why

A common broken state was: panel settings and generated profiles said OpenVPN TCP/1195, but the running daemon was still on the old transport/port or another TCP service already owned that port. Clients then failed although the server/firewall looked healthy.

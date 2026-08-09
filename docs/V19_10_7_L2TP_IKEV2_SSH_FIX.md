# IronPanel v19.10.10 - L2TP/IKEv2 and SSH connection repair

## Why L2TP failed in strongSwan Android

The attached charon log showed `NO_PROPOSAL_CHOSEN` during `IKE_SA_INIT`. That happens when the client starts an IKEv2 profile while the server only exposes the classic IKEv1 L2TP/IPsec-PSK connection.

This version keeps legacy L2TP/IPsec-PSK enabled and adds a modern `IKEv2-EAP` profile for Android/strongSwan clients.

## Changes

- Added `IKEv2-EAP` strongSwan connection next to the existing `L2TP-PSK` connection.
- Added automatic IKEv2 server certificate provisioning under `/etc/ipsec.d`.
- Rewrites `/etc/ipsec.secrets` with both PSK and per-user EAP credentials.
- Keeps `/etc/ppp/chap-secrets` for classic L2TP and PPTP.
- Adds NAT/firewall rules for both `10.20.20.0/24` classic L2TP and `10.21.21.0/24` IKEv2 virtual IPs.
- Updates generated `l2tp.txt` to tell users which client type to choose.
- Fixes SSH mobile tunnel compatibility by removing the forced `/bin/false` command from the IronPanel SSH group.
- Uses `/etc/ssh/sshd_config.d/ironpanel.conf` consistently for SSH config sync.
- Node sync now includes `/etc/ipsec.d` files and hot-syncs IKEv2 EAP users.

## Client choice

- strongSwan Android: choose **IKEv2 EAP (Username/Password)**.
- Legacy native L2TP clients: choose **L2TP/IPsec PSK** and use the PSK from `l2tp.txt`.
- SSH tunnel clients: choose **SSH / SSH Tunnel** with the generated SSH username from `ssh.txt`.

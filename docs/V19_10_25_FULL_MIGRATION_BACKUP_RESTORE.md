# IronPanel v19.10.25 — Full Migration Backup / Restore

This release replaces the old partial backup behavior with a migration-grade backup format.

## What is preserved

- A transactionally consistent SQLite snapshot containing all users, admins/resellers, plans/orders, usage, nodes, domains, AppSettings, API/subscription tokens and ownership relations.
- `/etc/ironpanel` settings, generated profiles, environment/API secret, node credential encryption key and protocol secrets.
- OpenVPN Easy-RSA PKI, client/server certificates, CA private key, CRL and `tls-crypt.key`.
- WireGuard server private key and runtime state. Per-user WireGuard identities remain in the restored DB.
- Let’s Encrypt certificate/account state and IronPanel SSL copies.
- Ocserv, L2TP/IKEv2/strongSwan, PPTP/PPP, Xray, Hysteria2 and Telegram Proxy identity/runtime files.
- IronPanel systemd units and optional application source.

## Restore contract

The target server should first have the same or a newer IronPanel version installed. Restore then:

1. validates archive paths/links and the SQLite snapshot;
2. creates a complete pre-restore rollback backup;
3. stops protocol runtimes briefly;
4. restores config/secrets and the SQLite DB through SQLite's backup API;
5. restores protocol identity paths and verifies identity fingerprints;
6. runs the current `upgrade-db` command;
7. rebuilds runtime configs/users without rotating restored identities;
8. reapplies firewall, speed-limit and node-gateway runtime rules;
9. schedules an IronPanel restart so restored environment/API/secret values are loaded.

For domain-based existing client configs to continue working after a server migration, DNS for the original domains must point to the new server. A client config containing the old server's literal IP address cannot follow a changed IP without editing/reissuing that address.

## Security

Migration archives contain private keys and secrets. Files are created mode `0600`, and the web download route is restricted to the main admin.

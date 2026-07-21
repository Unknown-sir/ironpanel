# IronPanel 19.9.11 — Cisco Auth Path Hotfix

The previous 19.9.10 build fixed several ocserv service issues but one runtime path regression remained: every user profile generation could rewrite `/etc/ocserv/ocserv.conf` with an auth path under `/etc/ironpanel/profiles/<username>/ocpasswd`. That file is not the global ocserv password database, so `ocserv.service` stayed active while login attempts failed with:

```text
plain-auth: error authenticating user '<username>'
worker-auth.c:1724: failed authentication
```

## Fixed behavior

- `/etc/ocserv/ocserv.conf` always contains:

```text
auth = "plain[passwd=/etc/ocserv/ocpasswd]"
```

- `/etc/ocserv/ocpasswd` is rebuilt atomically from enabled IronPanel users that have the Cisco/Ocserv protocol allowed.
- `/etc/ironpanel/ocpasswd` is kept only as a symlink or mirror for old diagnostics and older node agents.
- Hashes are generated in the documented ocserv plain-auth format: `username:groupname:encoded-password`, using SHA-512 crypt.
- `scripts/repair_cisco_auth.sh` can be run after update to force-rebuild credentials and restart ocserv.

## Manual recovery command

```bash
sudo bash /opt/ironpanel/scripts/repair_cisco_auth.sh
```

Then verify:

```bash
sudo grep 'plain\[passwd=' /etc/ocserv/ocserv.conf
sudo grep -c '^[^#[:space:]][^:]*:' /etc/ocserv/ocpasswd
sudo systemctl status ocserv --no-pager
```

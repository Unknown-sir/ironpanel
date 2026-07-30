# IronPanel 19.9.12 — Cisco Cookie/Auth and Node Installer Hotfix

## Fixes

- Rebuilds Cisco/OpenConnect `/etc/ocserv/ocpasswd` with the native `ocpasswd` binary whenever available.
- Forces ocserv plain-auth to the canonical `/etc/ocserv/ocpasswd` path and ignores legacy per-user/profile auth paths.
- Keeps `/etc/ironpanel/ocpasswd` only as a compatibility mirror/symlink.
- Runs critical Cisco auth repair even during fast web updates.
- Improves Node Auto Installer diagnostics after OS probe and writes progress checkpoints into the install job output.
- Makes node bootstrap apt refresh non-fatal while keeping prerequisite install failures explicit.
- Adds clear bootstrap markers for package download, extraction and installer launch.
- Adds timeout-protected Xray/Hysteria2 core installs to avoid hanging silently on blocked upstream downloads.

## Manual repair after upgrade

```bash
sudo bash /opt/ironpanel/scripts/repair_cisco_auth.sh
sudo systemctl restart ocserv
```

Check:

```bash
sudo grep 'plain\[passwd=/etc/ocserv/ocpasswd\]' /etc/ocserv/ocserv.conf
sudo grep -c '^[^#[:space:]][^:]*:' /etc/ocserv/ocpasswd
sudo journalctl -u ocserv -n 80 --no-pager
```

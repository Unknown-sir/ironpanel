# IronPanel 19.9.20 — Node Curl Heartbeat Transport Fix

- Fixed node auto-install failure after an authenticated runtime package download succeeds but Python urllib times out during HTTPS/IP fallback heartbeat probing.
- Node installer now retries heartbeat verification with curl using the same token, endpoint and TLS mode before rejecting the master URL.
- Node Agent now uses curl as a JSON API transport fallback for heartbeat and job-result calls when urllib fails on hardened TLS/proxy stacks.
- Kept strict token validation: HTTP 401/403 still fails instead of installing an offline node.
- Preserved v19.9.18 Hysteria2 sync, Cisco hook removal, direct port normalization and sales-bot random config names.

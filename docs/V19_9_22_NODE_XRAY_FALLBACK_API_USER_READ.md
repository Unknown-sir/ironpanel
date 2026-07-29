# v19.9.22 - Node Xray fallback and API user-read endpoints

- Added robust Xray core installation fallback for direct node installs. If the upstream install script prints progress but leaves no `xray` binary, the node installer downloads the official Xray-core release zip, installs `/usr/local/bin/xray`, installs geo data when present, creates a managed systemd unit, and verifies the binary through multiple paths.
- Added `unzip` to node core prerequisites because the fallback installer extracts official release archives.
- Added API v2 user-read endpoints for sales bots and external systems:
  - `GET /api/v2/users/{user_id}`
  - `GET /api/v2/users/by-username/{username}`
- Kept previous fixes for direct ports, Cisco hook removal, Hysteria2 node sync, sales bot QR delivery, random config names, plan edit and auto approval.

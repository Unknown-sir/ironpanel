# IronPanel v19.9.16 — Node Direct Ports + Sales Bot V2Ray QR Delivery

- Fixed malformed node direct-port JSON such as `{"telegram_proxy":6974}}}` by normalizing and compacting the payload before it is passed to the node bootstrap, stored in `node.env`, consumed by `install_node_cores.sh`, and reused by the node agent.
- Added tolerant legacy payload parsing on the node side so an old bad direct-port value no longer aborts core installation under `set -euo pipefail`.
- Kept direct port overrides authoritative for selected node protocols, especially Telegram Proxy, during initial SSH install, core repair, config sync, and health checks.
- Updated Sales Bot Xray/V2Ray delivery: users now receive the raw config text in chat plus QR Code image(s), instead of a `.txt` document.
- The Sales Bot still respects `sales_bot_qr_enabled`; when disabled, it sends the config text only.

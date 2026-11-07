# v19.8.12 — Node Force Route + Core Install + Metrics

- Add Fixed Only node gateway mode so one or more protocols can be forced to one selected node only.
- Add quick Force selected protocols action on each Node card.
- Include protocol core installation in generated node install commands.
- Add `scripts/install_node_cores.sh` for selected OpenVPN, Ocserv, L2TP, WireGuard, Xray, PPTP, Hysteria2, Telegram Proxy and SSH prerequisites.
- Node Agent now reports CPU, RAM, disk, TCP ping, online connections and protocol/core health more reliably.
- Master stores `ping_ms` from heartbeat and job-result metrics.

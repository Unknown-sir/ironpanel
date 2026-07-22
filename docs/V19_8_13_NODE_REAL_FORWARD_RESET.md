# IronPanel v19.8.13 - Node Real Forward + Config Sync + Reset

- Fixed Only now applies real DNAT/FORWARD/MASQUERADE rules on the main server so users can keep the main-panel IP/domain while selected protocol ports terminate on the selected node.
- Gateway plan now contains every required port for each protocol: OpenVPN UDP/TCP, Ocserv TCP/UDP, L2TP/IPsec 500/4500/1701, PPTP TCP/GRE, WireGuard, Xray, Hysteria2, Telegram Proxy and SSH.
- Added a reset button in Node Gateway to clear all node forwards and return protocols to the main server.
- Main protocol configuration files are synced to target nodes before user sync jobs, then related services are restarted on the node.
- Node Gateway rules are installed as a systemd oneshot service so forwarding can be re-applied after reboot.

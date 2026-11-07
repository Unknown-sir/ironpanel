# IronPanel v19.8.17 - Node Gateway Xray Public Ports

- Excludes Xray API/stats ports such as 10085 from gateway forwarding.
- Parses only public top-level Xray inbounds.
- Normalizes synced Xray/Hysteria2 config binds on the node.
- Adds iptables counter snapshots to gateway logs.

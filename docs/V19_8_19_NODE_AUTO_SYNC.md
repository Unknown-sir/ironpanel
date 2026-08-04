# IronPanel v19.8.19 - Node Auto Sync

- Node Agent now receives full core install, protocol config bundles and bulk user metadata automatically on first heartbeat and every few minutes.
- Forced protocol routes queue full sync jobs before and after gateway apply.
- Node install runs a second one-shot heartbeat to drain initial sync jobs immediately.
- Master host normalization now includes server interface IPs so copied Xray/Hysteria2 configs bind correctly on nodes.

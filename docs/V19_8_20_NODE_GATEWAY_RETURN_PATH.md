# IronPanel v19.8.20 - Node Gateway Return Path Fix

This release hardens real node forwarding after protocol force-to-node.

- Uses deterministic SNAT to the main-panel source IP when routing to the node, with MASQUERADE fallback.
- Adds FORWARD accept rules for new traffic to the node and established return traffic from the node.
- Disables rp_filter on all interfaces to prevent asymmetric DNAT return drops.
- Probes TCP node ports from the main server and logs if a node service/firewall is not reachable.
- Logs PREROUTING, OUTPUT, FORWARD and POSTROUTING hooks with counters.
- Keeps synced protocol configs and users on the node via the existing Auto Sync pipeline.

After upgrading, clear and re-apply Node Gateway rules from the panel or run:

```bash
sudo bash /opt/ironpanel/scripts/apply_node_gateway.sh --clear
sudo systemctl restart ironpanel
```

Then force the protocol again from Nodes or Node Gateway.

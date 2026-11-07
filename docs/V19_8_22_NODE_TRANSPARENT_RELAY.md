# v19.8.22 - Transparent Node Relay Mode

Client configs remain pointed at the main panel. For forced protocols the main server redirects the public protocol port to a local relay. The relay opens a connection to the selected node and returns the response through the main panel. This matches tunnel deployments where traffic must flow Client/Iran -> Main -> Node -> Main -> Client/Iran.

Useful checks:

```bash
systemctl status ironpanel-node-gateway-relay --no-pager
tail -n 120 /var/log/ironpanel-node-gateway.log
tail -n 120 /var/log/ironpanel-node-gateway-relay.log
iptables -t nat -S IRONPANEL_NODE_GW
```

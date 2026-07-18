# IronPanel 19.8.11 - Node Heartbeat Verify

This update fixes node installations that stayed offline after the agent service was installed.

## Fixes

- Raw-IP panel URLs on custom ports now generate `http://IP:PORT` instead of `https://IP:PORT`.
- The node installer no longer accepts a master URL only because `/` or `/api/v2/node/ping` responds.
- The installer now probes `/api/v2/node/heartbeat` with the node token before saving the master URL.
- The node agent tries `http://IP:PORT` before `https://IP:PORT` for raw IP custom ports, so stale configs such as `https://1.2.3.4:8001` can recover after reinstall/update.

## Useful checks

```bash
journalctl -u ironpanel-node -n 100 --no-pager
cat /etc/ironpanel-node/node.env
curl -sS http://MASTER_IP:8001/api/v2/node/ping
```

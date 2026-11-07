# v19.9.24 - Node SSL Domain for Tunnel Scenarios

This release separates the **configuration/subscription host** from the **node SSL/ACME domain**.

Why: in tunnel deployments the domain placed inside user configs may point to the tunnel/front server, not directly to the physical node. The node therefore cannot pass HTTP-01 ACME validation with that domain. Nodes now have a dedicated **Node SSL Domain** field that must resolve directly to the node IP.

Changes:

- Added `node.ssl_domain` to the database/model and SQLite schema guard.
- Added `دامنه SSL سرور نود` to Node create/edit forms.
- Direct subscriptions still use `config_domain` for client links.
- Auto SSH install passes `ssl_domain` into the node runtime as `IRONPANEL_NODE_SSL_DOMAIN`.
- Node core installer uses the SSL domain to issue/reuse Let's Encrypt certificates when it resolves to the node IP.
- Hysteria2, Ocserv and Xray TLS certificate paths are rewritten on the node to use the node certificate where applicable.
- If the SSL domain is empty, the installer falls back to the config domain; if ACME cannot be issued, it uses a local fallback cert without breaking non-TLS protocols.

# IronPanel v19.8.18 — Node Gateway Direct DNAT + Node Egress Fix

- Node Gateway forwarding now uses direct PREROUTING DNAT rules instead of relying only on `addrtype --dst-type LOCAL` inside the custom chain.
- A restricted NAT OUTPUT hook is added only for local tests against local destinations.
- Node source IP is excluded from DNAT rules to avoid forwarding loops.
- Xray node config normalization removes copied `sendThrough` values so node egress uses the node public IP.
- Gateway logs now remind admins that the client app still displays the main panel address because DNAT keeps configs unchanged; the real check is the public IP after connecting through the tunnel.

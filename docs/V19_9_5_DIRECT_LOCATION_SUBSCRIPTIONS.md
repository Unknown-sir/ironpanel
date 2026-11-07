# IronPanel 19.9.5 — Direct Location Subscriptions

This release adds a second use for nodes: direct location delivery inside user subscriptions.

The node receives protocol configs and users from the main panel. The user receives multiple configs, but every config uses the same master-generated identity, so traffic is accounted against one user quota.

Supported in this release:

- Per-node Delivery Mode: Relay, Direct, Both, Disabled
- Per-node Subscription Host, label, flag and per-protocol ports
- Xray raw subscription output with multiple location links
- Extra downloadable profiles for OpenVPN, WireGuard and text protocols
- Best-effort node-side usage reporting for Xray, WireGuard and OpenVPN
- Automatic sync jobs via heartbeat interval

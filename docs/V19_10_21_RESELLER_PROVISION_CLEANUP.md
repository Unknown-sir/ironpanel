# IronPanel v19.10.21

## Instant reseller user provisioning

New users created from the reseller panel are provisioned into the running protocol cores immediately. Xray and the shared Telegram proxy are reloaded only when selected. WireGuard peers are applied live. Password-file/database based protocols do not receive unnecessary restarts.

## One-click cleanup

The Users page exposes one cleanup button for accounts automatically disabled because their expiration date or traffic quota was exhausted. Main admin operates across all users; resellers are restricted to their own users. Manually disabled accounts are not intentionally selected by the cleanup classifier.

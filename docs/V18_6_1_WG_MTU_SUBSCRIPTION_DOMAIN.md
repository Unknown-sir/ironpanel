# IronPanel v18.6.1 — WireGuard MTU + Subscription Domain

## Added

- Dedicated WireGuard MTU card in Settings.
- Dedicated Subscription Domain card in Settings.
- Subscription Theme Manager can also edit the subscription domain.
- Subscription page, QR code, reseller API and sales bot now use the dedicated subscription domain when configured.
- Default WireGuard MTU remains `1360` and PersistentKeepalive remains `25`.

## Behavior

If `subscription_domain` is empty, IronPanel falls back to the panel host and panel port.
If `subscription_domain` is `sub.example.com`, public links become:

```text
https://sub.example.com/s/<token>
```

If an admin enters a full URL such as `http://sub.example.com:8080`, that exact base is used.

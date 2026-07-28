# IronPanel 18.5.9

This release fixes reseller portal visibility, hardens GitHub quick upgrade, and redesigns the public subscription page.

## Resellers
- Existing resellers receive a generated `panel_path` during `init-db` and `upgrade-db`.
- The Resellers page now shows portal URL, copy button, quota edit fields and suspend/resume actions.
- Dashboard and sidebar now expose Resellers as a first-class admin action.

## GitHub quick upgrade
Quick upgrade now performs a full sync: source update, dependencies, DB migration, systemd unit rewrite, timers, VPN repair, service restart and user sync.

## Subscription
The subscription UI was rebuilt as a responsive modern page with status cards, QR sections, protocol cards, copy/download actions and clearer usage display.

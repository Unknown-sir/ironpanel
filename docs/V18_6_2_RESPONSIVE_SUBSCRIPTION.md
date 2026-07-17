# IronPanel v18.6.2 - Responsive UI and Subscription Domain Fix

## Fixes

- User-list subscription buttons now use the dedicated `subscription_domain` setting instead of the panel IP/host.
- User config and Xray pages also render absolute subscription links with the configured subscription domain.
- API v1/v2 user serializers include the fully resolved subscription URL.

## Responsive UI

- Admin cards, grids, forms and action groups are now safer on mobile.
- Wide tables become horizontally scrollable instead of overlapping adjacent content.
- Buttons and form controls wrap cleanly on small screens.
- Sidebar becomes a mobile-friendly stacked navigation.

## Subscription page redesign

- Replaced the older subscription layout with a new animated glass-style responsive page.
- Added modern metrics cards, animated hero, copyable subscription URL, QR card and protocol cards.
- Added reduced-motion support for users/devices that prefer less animation.

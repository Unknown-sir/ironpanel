# IronPanel v2.0.3 - Manual Card-to-Card Recharge

This release removes the Dargahno payment gateway integration completely and replaces
it with a fully manual card-to-card recharge flow for reseller panels.

## What changed

- **No gateway.** All `dargahno_*` settings, the `GatewayPayment` model, the
  `/gateway` admin page and the `payment_success` / `payment_failed` pages are removed.
- New model `ChargeRequest` (table `charge_request`): reseller, requested GB,
  estimated amount (Rial), unique factor number, receipt file name, admin note,
  status (`pending` / `approved` / `rejected`) plus timestamps.
- New settings `card_*`: `card_charge_enabled`, `card_price_per_gb`,
  `card_min_purchase`, `card_number`, `card_holder`, `card_payment_text`, `card_support`.

## Flow

1. Admin configures the "Card-to-card recharge" page (`/cards`): card number,
   holder name, payment text, price per GB and minimum amount.
2. Reseller opens "Panel recharge" (`/reseller/storage`), enters the required GB,
   sees the estimated amount immediately, transfers the money to the admin's card
   and uploads the receipt image (jpg/jpeg/png/webp/gif, max 8 MB).
3. Receipts are stored under `CONFIG_ROOT/receipts` (default `/etc/ironpanel/receipts`).
4. Admin sees each request as an expandable card with the receipt image, volume,
   amount and reseller; **Approve** credits the GB (and calls `reconcile_reseller_access`
   to re-enable a panel auto-disabled by volume exhaustion), **Reject** closes it.

## Volume-exhausted panels

A reseller whose quota ran out gets `enabled=False` / `disabled_reason='traffic_quota'`.
They may still log in but only the recharge page (and logout/static assets) are
reachable; every other page redirects to the charge form with the banner
"Panel disabled: volume exhausted". The reseller sales bot keeps blocking user
creation / renewal / charging until a top-up is approved.

## Files touched

- `app/core/models.py` - `ChargeRequest`; `Admin.is_active` allows traffic-quota disabled sub-admins.
- `app/services/cards.py` (new) / `app/user_schema` settings; `app/services/dargahno.py` (deleted).
- `app/web/cards.py` (new) / `app/web/gateway.py` (deleted); `app/web/__init__.py` import updated.
- `app/web/common.py` - volume-gated before_request hook + `volume_gated` template global.
- `app/web/auth.py` - login for traffic-quota disabled resellers.
- `bot/main.py` - volume gate message wording.
- Templates: `cards.html` (new), `reseller_storage.html` (rewritten), `base.html`
  (nav/cache-buster/volume banner); `gateway.html`, `payment_success.html`, `payment_failed.html` deleted.
- `README.md` / `README_EN.md` - manual recharge docs + license features table; `CHANGELOG.md`; `VERSION`.

No database migration is required by the operator: the new table is created via
`db.create_all()` at startup / CLI migrations. Old `gateway_payment` rows become
orphaned and are harmless.
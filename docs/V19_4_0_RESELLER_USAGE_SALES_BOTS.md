# v19.4.0 - Reseller Usage Ledger + Reseller Sales Bots

- Reseller traffic quota is now charged from real consumed traffic deltas only.
- Deleting a VPN user, detaching a reseller user, or resetting the child user's usage no longer reduces reseller consumed quota.
- When a reseller traffic quota is exhausted, active users of that reseller are disabled to enforce the quota.
- Sales Bot settings, plans, orders, and customers are owner-aware.
- Main admin keeps the global sales bot; each reseller can enable a dedicated sales bot when the license tier allows Sales Bot / Pro features.
- `scripts/sync_sales_bots.sh` manages `ironpanel-sales-bot@OWNER_ID.service` instances.

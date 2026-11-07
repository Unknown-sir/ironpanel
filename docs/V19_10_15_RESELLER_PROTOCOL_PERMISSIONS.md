# IronPanel v19.10.15 — Reseller Protocol Permissions

Main administrators can define which protocols each reseller may assign. The restriction is enforced server-side for normal, quick and bulk user creation, user edits, plan application, API-key creation and the reseller-owned sales bot.

When permissions are edited, the administrator can reconcile existing users. Revoked protocols are removed; a user with no remaining permitted protocol is disabled to avoid legacy empty-protocol fallbacks.

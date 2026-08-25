# V19.10.27 — Reseller Config Domain and Authoritative Protocol Checkboxes

## 1. Unchecked protocols are never created or advertised

### Root cause

`POST /quick-create` treated the Preset dropdown as the source of truth. The
default preset (`all`) passed the **full active protocol list** to user
creation, so the collapsed "manual protocol" checkboxes were ignored: removing
the SSH tick still created the Linux SSH account and `ssh.txt` still appeared
on `/s/<token>`.

### Fix

* The manual checkboxes are now authoritative for every preset:
  `final = preset_base ∩ checked`. With all boxes ticked (default) behavior is
  unchanged; unchecking a protocol excludes it everywhere — runtime accounts,
  generated profile files and subscription sections.
* Added an explanatory hint under the preset select in `quick_create.html`.

Note: the regular create form (`POST /users`), bulk create, edit form, API v2
and sales-bot order creation already stored exactly the selected set and are
unchanged.

## 2. Per-reseller custom config domain

A reseller can brand its own customers' configs with a dedicated address.

### Storage

* `AppSetting['reseller_config_domain_owner_<reseller_id>']` (host-only value).
  No schema migration; empty/absent means "use main panel address".

### Resolution order in config generation

1. Owning reseller's custom domain (only when the user has `owner_id`)
2. Otherwise the main panel Public Host / Tunnel Host as before

Applied consistently across:

* `generate_profiles()` local hosts → OpenVPN `remote`, WireGuard `Endpoint`,
  Ocserv/L2TP/PPTP/SSH/Hysteria2 host lines and Hysteria2 URI
* `xray_link()` connect host (Reality SNI stays on the configured real domain)
* `telegram_proxy_link_for()` server field

Node **Direct Location** configs intentionally keep their own per-node hosts;
the reseller domain only replaces main-server endpoints. Subscription page URLs
still point at the panel so users can reach `/s/<token>`.

### UI

* Reseller self-service page: `/my/config-domain` ("دامنه کانفیگ‌های من"),
  linked in the sidebar for sub-admins.
* Main admin can also set/clear it from the reseller create/edit forms in
  *Resellers*.
* Saving logs `update_own_config_domain` / `reseller_config_domain`; existing
  users pick up the new address on their next profile regeneration
  (`Sync all users` forces it immediately).

## Upgrade notes

Pull code, restart the panel. No migrations, no new services.

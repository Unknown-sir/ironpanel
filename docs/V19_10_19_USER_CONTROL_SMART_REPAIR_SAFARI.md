# IronPanel v19.10.19

This release adds owner-scoped user connect/disconnect, safe auto-disabled cleanup, health-first protocol install/update, OpenVPN PKI/DH reuse, and iPhone Safari copy compatibility.

## Upgrade behavior

`upgrade.sh` runs `smart_protocol_repair.sh`. For every license-active protocol it runs a fast health check first. Healthy cores print `SKIP` and are not repaired. Broken cores are repaired with a bounded timeout and validated again.

## User cleanup

Bulk cleanup requires the user to be disabled, currently expired or over quota, and to have `auto_disable_user` as the latest explicit state-transition log.

## OpenVPN update stall fix

When the active server CA matches a recovery PKI (for example `easy-rsa-new`), normal updates no longer recursively copy every historical Easy-RSA certificate before adopting it. IronPanel saves only critical recovery files, renames the previous canonical PKI in-place, and bounds the adoption copy with a timeout. Full protocol backup remains opt-in with `IRONPANEL_PROTOCOL_FULL_BACKUP=1`.

## Safari copy

Subscription copy buttons use an iOS-safe synchronous textarea/`execCommand('copy')` path inside the original tap gesture, then fall back to the Clipboard API and finally the legacy path. This covers Safari cases where async clipboard access loses the user gesture.

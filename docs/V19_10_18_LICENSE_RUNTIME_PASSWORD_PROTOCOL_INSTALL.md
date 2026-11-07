# IronPanel v19.10.18

## Scope

This release hardens protocol installation/runtime recovery, removes the need to reinstall after a Free/Beginner -> Plus/Pro license upgrade, and adds a permanent automatic user-password policy.

## Protocol installation invariants

- OpenVPN server and generated client certificates use the same canonical `/etc/openvpn/easy-rsa/pki` issuing CA. A recoverable PKI matching the active server CA is adopted before a new CA is generated.
- OpenVPN validates CA, server certificate/key pair, chain, DH, CRL and tls-crypt material before health succeeds.
- WireGuard persists UDP input, forwarding and WAN-scoped MASQUERADE rules in `wg0.conf` and preserves the managed peer block during repair.
- Interrupted dpkg state is repaired before APT protocol dependency installation.
- Telegram Proxy repair no longer contains the command-substitution parsing failure seen in v19.10.17 deployments.
- Protocol health checks remain the final install/upgrade gate unless `IRONPANEL_ALLOW_PARTIAL_CORES=1` is explicitly set.

## License runtime transition

Free/Beginner keeps only OpenVPN and Xray effective. All core dependencies remain installed so a valid paid license can be applied without reinstalling the panel.

Saving a valid paid key:
1. updates the effective license state;
2. expands the saved active protocol set to protocols granted by the license;
3. queues `scripts/reconcile_license_runtime.sh`;
4. repairs/starts newly granted protocol daemons;
5. reapplies runtime configuration and resynchronizes users.

Downgrading returns the effective protocol set to the free tier and stops paid-only protocol daemons while leaving administrator SSH untouched.

## Automatic user-password policy

Settings keys:
- `auto_password_length` (3..128, default 10)
- `auto_password_mode` (`letters`, `numbers`, `both`)

The policy is used by quick create, normal user create, bulk create defaults, API v1 and API v2 whenever no user password is supplied. Security tokens/API keys are intentionally unaffected.

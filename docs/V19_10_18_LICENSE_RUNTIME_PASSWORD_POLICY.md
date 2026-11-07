# IronPanel v19.10.18

## Fixed installation/runtime paths

- Protocol prerequisite installation repairs interrupted `dpkg`, installs required packages/binaries, and performs strict final validation.
- OpenVPN uses `/etc/openvpn/easy-rsa/pki` as the canonical issuing PKI. Repair prefers the PKI matching the active server CA, then synchronizes server CA/cert/key/DH from that same PKI. Existing user certificates are reused only when their chain and private key match.
- WireGuard installation/repair writes UDP input, forwarding, established-return, and interface-specific MASQUERADE rules and derives every stored user public key from its private key.
- Telegram Proxy repair command substitution syntax is fixed.

## License runtime reconciliation

Beginner remains limited to OpenVPN and Xray. Dependencies for all supported protocols are prepared during install. Saving a valid Plus/Pro/Admin license merges the newly granted protocols into `active_protocols`, installs/repairs the required runtime, starts granted services, applies configs, and resynchronizes users. Fresh install and `upgrade.sh` also run the reconciliation so an already-saved paid key is repaired without reinstallation.

## Permanent automatic password policy

Main Admin -> Settings contains a persistent policy for automatically generated user passwords:

- length: 3..128
- letters only
- numbers only
- letters + numbers

The policy is used when Web/API user creation leaves the password blank. Bulk creation defaults to the same policy while still allowing an explicit per-batch override.

# IronPanel v18.6.10 — Telegram Proxy Core + Update Fetch Fix

## Telegram MTProto Proxy Core

- The Telegram Proxy installer now installs NodeJS/Git dependencies, prepares the IronPanel MTProxy runtime, writes `/etc/systemd/system/ironpanel-tgproxy.service`, enables the shared service, opens the shared TCP port, and keeps `config.json` / `usage.json` under `/opt/ironpanel-telegram-proxy/ironpanel/`.
- Fresh installs and upgrades now run `repair_telegram_proxy.sh --sync` so the proxy core is installed and user secrets are synced, instead of only generating Telegram proxy links.
- Old per-user services are disabled and removed automatically. All users use one shared port and separate secrets.
- Telegram proxy links are normalized so the `server` field never contains `http://`, `https://`, a path, or the panel port.

## Update Manager

- Fixed the `failed fetch` issue around 45%. The browser no longer waits for one long upgrade request.
- The long upgrade phase is launched as a visible tracked task, while the Update Manager page polls status/log/progress.
- The page retries transient fetch interruptions and keeps showing live progress.
- Final service reconciliation now includes `ironpanel-tgproxy.service` and `repair_telegram_proxy.sh --sync`.

## README

- README.md and README_FA.md were updated with the latest Telegram Proxy and Update Manager behavior.

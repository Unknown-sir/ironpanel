# v19.9.31 - Office UI polish, responsive form controls and smart subscription

## UI / UX
- Added a final office-grade UI override layer with stable sidebar, mobile drawer, RTL/LTR-aware spacing and safer table/card layout.
- Normalized checkbox/radio groups so protocol selections and settings switches no longer appear oversized or misaligned on desktop/mobile.
- Added client-side localization fallback for common Persian hard-coded labels when the panel language is not Persian. Unsupported translated labels fall back to English instead of Persian.
- Login remains one-column and formal.

## Smart subscription
- `/s/<token>/auto` and `/s/<token>/smart` now detect the client using query parameters and User-Agent when possible.
- Supported explicit forcing: `?format=raw`, `?format=clash`, `?format=singbox`, `?format=hiddify`.
- User-Agent detection maps OpenClash/Clash/Mihomo/Stash to Clash YAML, sing-box/SFA/SFM/SFI to sing-box JSON, Hiddify to Hiddify/raw-compatible output, and v2rayN/v2rayNG/NekoBox/Shadowrocket/Fair to raw/base64 style output.

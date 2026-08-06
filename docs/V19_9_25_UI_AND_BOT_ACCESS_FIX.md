# v19.9.28 - UI refresh and Telegram bot access hardening

## UI refresh
- Original IronPanel theme updated with modern proxy-panel layout standards: stable sidebar, consistent spacing, clean cards, responsive tables, responsive forms and a polished login screen.
- The design is inspired by the structure of modern VPN/proxy dashboards such as PasarGuard and 3x-ui, but it does not copy their UI.
- Mobile sidebar is an off-canvas drawer with an overlay and safe outside-tap close behavior.
- Tables now scroll horizontally on mobile instead of breaking layout.

## Telegram bot access fix
- Admin Telegram IDs are normalized before comparison.
- Persian/Arabic digits are accepted.
- Mixed separators such as comma, Persian comma, semicolon and new line are accepted.
- `admin_bot_admin_ids`, `telegram_chat_id` and `sales_bot_admin_ids` are all considered for the admin bot instead of only the first non-empty field.
- Unauthorized admin-bot callbacks are silently ignored with a light Telegram answer instead of rewriting the message to `⛔ دسترسی مجاز نیست.`.

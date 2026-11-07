# v19.10.0 - Full UI language cleanup

This release focuses on language consistency across the admin panel.

## Changes

- Version bumped to `19.10.0`.
- Main README banner image updated to `https://s34.picofile.com/file/8491039084/IronpanelN.png`.
- Added server-side cleanup for legacy Persian UI strings when the panel language is English, Arabic or Russian.
- Added an `ui()` template helper for Persian/English pairs with Arabic/Russian safe fallbacks.
- The main menu, topbar, account area, common forms, buttons, placeholders and status labels now respect the selected language more consistently.

## Notes

User-generated content such as usernames, reseller names, plan names and custom bot messages is preserved exactly as the admin entered it.

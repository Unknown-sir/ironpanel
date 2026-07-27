# v19.10.3 - Global layout and menu collision fix

This release hardens the main shell layout across every page:

- Adds a new scoped `iron-stable-v19103` layout layer so old experimental UI selectors do not affect the active shell.
- Keeps the sidebar as a fixed-width desktop column and a drawer on mobile/tablet.
- Prevents sidebar/menu content from mixing with page cards, headings, forms, or tables.
- Repairs the malformed `user_edit.html` heading block that injected a card/form into the page title area.
- Normalizes page content, cards, forms, protocol checkboxes, tables and action bars across all base-template pages.
- Preserves the full multi-language cleanup from v19.10.1.

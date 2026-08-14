# v19.10.1 - Full language sweep

This release extends the v19.10.0 language cleanup. It adds an auto-generated phrase catalog from templates, static JavaScript, Flask flash messages and panel helpers, then uses server-side and client-side bridges to remove legacy Persian UI text when the selected language is English, Arabic or Russian.

User-provided content remains untouched unless it exactly matches a known legacy UI label.

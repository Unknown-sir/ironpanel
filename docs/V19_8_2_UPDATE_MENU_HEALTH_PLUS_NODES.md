# v19.8.2 - Real Update Completion + Menu/Health Fix

- Inline Update Manager waits for `/tmp/ironpanel-inline-update/upgrade.exit` to contain `0` before showing 100%.
- Restart scheduling is blocked until the update state is truly completed.
- The update path uses fast mode and skips heavy protocol repair loops; protocol repair is manual from Health & Repair.
- The More Settings/details sidebar menu spans full width and uses static, non-overlapping layout.
- Health & Repair always renders a Repair button for every protocol row.
- Plus license keeps Nodes and Node Agent feature flags enabled.

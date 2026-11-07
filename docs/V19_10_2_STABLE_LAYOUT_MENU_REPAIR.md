# v19.10.2 - Stable layout and menu repair

This release fixes the UI regression where the sidebar/menu could overlap or mix with page content.

## Changes

- Added a final stable application shell class: `iron-stable-v19102`.
- Repaired desktop grid layout so the sidebar and page content are always separated.
- Repaired mobile drawer behavior for both RTL and LTR languages.
- Replaced duplicate JavaScript menu handlers with one stable controller.
- Normalized checkboxes, radios, protocol selector chips, action rows and table wrappers.
- Preserved v19.10.1 multi-language cleanup behavior.

## Upgrade

Run:

```bash
sudo bash upgrade.sh
sudo systemctl restart ironpanel
```

Then hard-refresh the browser with `Ctrl+F5`.

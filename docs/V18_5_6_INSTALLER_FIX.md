# IronPanel v18.5.6 — Installer Bash Compatibility Fix

This release fixes the installer crash:

```text
install.sh: line 152: var: invalid indirect expansion
```

Cause: older/common Bash builds do not support using a default modifier inside indirect expansion as `${!var:-}`.

Fix: the installer now safely checks whether the prompted variable exists before reading its value.

Use one installer only:

```bash
sudo bash install.sh
```

Direct GitHub install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/install.sh)
```

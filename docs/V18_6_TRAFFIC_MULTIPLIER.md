# IronPanel v18.4.4 - Traffic Multiplier

The Traffic Multiplier module is available in every license tier, including Beginner Free.

## Behavior

- Raw uploaded/downloaded bytes remain stored without modification.
- Effective usage is calculated as `raw_usage * traffic_multiplier_value` when the module is enabled.
- User quota enforcement compares effective usage with `data_limit_mb`.
- The public subscription page shows the multiplier-adjusted value and, when enabled, the raw value as a secondary note.
- Disabling the module immediately returns effective usage to the raw usage value.

## Settings

Stored in `app_setting`:

- `traffic_multiplier_enabled`: `1` or `0`
- `traffic_multiplier_value`: decimal value between `0.01` and `100`

## Runtime

The web accounting layer, CLI usage sync, OpenVPN gate script, Hysteria2 auth path, user list, usage report and API serializers all use the effective usage value for access decisions.

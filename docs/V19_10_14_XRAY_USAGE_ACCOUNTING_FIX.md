# IronPanel v19.10.14 — V2Ray/Xray Usage Accounting Fix

## Root cause

Two independent bugs prevented Xray traffic from reaching the panel database:

1. `collect_xray_usage()` called the local command helper with `timeout=8`, while that helper accepted no `timeout` keyword. The collector raised `TypeError` before Xray Stats API was queried.
2. Current Xray CLI output serializes protobuf `int64` counters as quoted JSON strings such as `"value": "2040"`. The previous parser accepted only unquoted digits.

## Fix

- The command helper now supports bounded execution and timeout errors.
- The stats parser accepts current JSON, older JSON, compact JSON, and legacy text-protobuf.
- The master and node collectors query all stats and keep only per-user uplink/downlink counters.
- Node agents discover the API port from the active Xray config.
- Node metadata uses the same deterministic Xray email as the generated client entry.
- The usage diagnostic script prints raw Xray Stats API output.

## Verification

```bash
sudo bash /opt/ironpanel/scripts/usage_diagnose.sh
cd /opt/ironpanel
sudo /opt/ironpanel/.venv/bin/flask --app run.py sync-usage
```

After generating traffic with a VLESS/VMess/Trojan/Shadowsocks profile, the diagnostic output must include records like:

```text
user>>>ip-USER_ID-USERNAME>>>traffic>>>uplink
user>>>ip-USER_ID-USERNAME>>>traffic>>>downlink
```

The next sync applies only the delta from the previous Xray counter snapshot.

#!/usr/bin/env bash
set +e
PY=/opt/ironpanel/.venv/bin/python; [[ -x "$PY" ]] || PY=python3
"$PY" /opt/ironpanel/scripts/ironpanel_usage_event_hook.py ocserv-disconnect >/dev/null 2>&1 || true
exit 0

#!/usr/bin/env bash
set -euo pipefail
systemctl status ironpanel --no-pager || true
systemctl status xray --no-pager || true
systemctl status ironpanel-sales-bot --no-pager || true
systemctl status ironpanel-node --no-pager || true
journalctl -u ironpanel -n 50 --no-pager || true

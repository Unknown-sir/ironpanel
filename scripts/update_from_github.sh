#!/usr/bin/env bash
set -euo pipefail
REPO_URL="${IRONPANEL_GITHUB_REPO:-https://github.com/Unknown-sir/ironpanel.git}"
BRANCH="${IRONPANEL_GITHUB_BRANCH:-main}"
APP_DIR="/opt/ironpanel"
WORK="/tmp/ironpanel-github-update"
mkdir -p "$WORK"
if [[ -d "$APP_DIR/.git" ]]; then
  cd "$APP_DIR"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
  bash "$APP_DIR/upgrade.sh" --restart-only || bash "$APP_DIR/upgrade.sh"
else
  rm -rf "$WORK/ironpanel"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$WORK/ironpanel"
  cd "$WORK/ironpanel"
  bash upgrade.sh
fi

#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_env.sh"

# Keep the 09:00 delta message on the Daily English Discord channel.
DAILY_DELTA_CHANNEL_ID="${DAILY_DELTA_CHANNEL_ID:-channel:1563582194985730098}"

MSG="$("$PY" "$BASE/scripts/send_today_delta.py")"

if [[ -z "${MSG}" ]]; then
  echo "send_today_delta: no new post today, skipping"
  exit 0
fi

"$OPENCLAW" message send \
  --channel discord \
  --target "$DAILY_DELTA_CHANNEL_ID" \
  --message "$MSG"

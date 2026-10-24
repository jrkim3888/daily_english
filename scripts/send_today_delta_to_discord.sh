#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_env.sh"

MSG="$("$PY" "$BASE/scripts/send_today_delta.py")"

if [[ -z "${MSG}" ]]; then
  echo "send_today_delta: no new post today, skipping"
  exit 0
fi

"$OPENCLAW" message send \
  --channel discord \
  --target "$CHANNEL_ID" \
  --message "$MSG"

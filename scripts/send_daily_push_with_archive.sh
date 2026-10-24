#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_env.sh"

MSG="$("$PY" "$BASE/scripts/build_daily_push_message.py")"

if [[ -z "${MSG}" ]]; then
  echo "build_daily_push_message.py produced empty output" >&2
  exit 1
fi

"$OPENCLAW" message send \
  --channel discord \
  --target "$CHANNEL_ID" \
  --message "$MSG"

"$PY" "$BASE/scripts/archive_daily.py"
"$BASE/scripts/publish_site.sh"

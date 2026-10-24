#!/usr/bin/env bash
# 08:30 KST — fetch today's post, then archive + publish the blog
set -euo pipefail
source "$(dirname "$0")/_env.sh"

"$PY" "$BASE/scripts/fetch_ibi_tweineun.py"
"$PY" "$BASE/scripts/archive_daily.py"
"$BASE/scripts/publish_site.sh"

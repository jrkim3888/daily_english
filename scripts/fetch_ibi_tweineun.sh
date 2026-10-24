#!/usr/bin/env bash
# 08:30 KST — fetch today's post, then archive + publish the blog
set -uo pipefail
source "$(dirname "$0")/_env.sh"

# Make sure today's study set exists even if the 00:00 job didn't run (it's deterministic per date).
"$PY" "$BASE/scripts/pick_today_study.py" >/dev/null || echo "pick_today_study failed" >&2

# A fetch failure shouldn't stop today's archive/publish; report it via the exit code instead.
"$PY" "$BASE/scripts/fetch_ibi_tweineun.py"
status=$?

"$PY" "$BASE/scripts/archive_daily.py" || status=1
"$BASE/scripts/publish_site.sh" || status=1
exit $status

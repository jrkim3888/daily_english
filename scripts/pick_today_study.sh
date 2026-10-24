#!/usr/bin/env bash
# 00:00 KST — pick today's study set
set -euo pipefail
source "$(dirname "$0")/_env.sh"

"$PY" "$BASE/scripts/pick_today_study.py"

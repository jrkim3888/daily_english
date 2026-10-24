# Shared settings for cron wrappers. Source this, don't execute it.
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$BASE/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"
OPENCLAW="${OPENCLAW_BIN:-$(command -v openclaw || echo /opt/homebrew/bin/openclaw)}"
CHANNEL_ID="channel:1468007571112591361"

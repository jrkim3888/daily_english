#!/usr/bin/env python3
"""Archive daily English study data for later web viewing.

Creates/updates ONE JSON file per day:
- <repo>/outputs/history/YYYY-MM-DD.json

Contents include:
- today_study (snapshot)
- today_delta (snapshot, if present)
- message (rendered combined message)

This is intended to run once per day after inputs are ready.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
OUT = BASE / 'outputs'
HIST = OUT / 'history'
STUDY = DATA / 'today_study.json'
DELTA = DATA / 'today_delta.json'

# Reuse the same format as sends
BUILD = BASE / 'scripts' / 'build_daily_push_message.py'


def read_json(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}


def main() -> int:
    s = read_json(STUDY)
    d = read_json(DELTA)

    date = (s.get('date') or d.get('date') or '').strip()
    if not date:
        # Fall back to UTC date if missing (should be rare)
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    HIST.mkdir(parents=True, exist_ok=True)
    out_path = HIST / f"{date}.json"
    tmp_path = HIST / f"{date}.json.tmp"

    # Snapshot raw inputs
    today_study = read_json(STUDY)
    today_delta = read_json(DELTA) if DELTA.exists() else {}
    if today_delta.get('date') != date:
        today_delta = {}

    # Render message text (best-effort)
    import subprocess
    try:
        message = subprocess.check_output([sys.executable, str(BUILD)], text=True).strip() + '\n'
    except Exception as e:
        message = f'(message build failed: {e})\n'

    # Skip rewrite when content is unchanged, so repeated sends don't create commits.
    prev = read_json(out_path)
    if (prev.get('today_study'), prev.get('today_delta'), prev.get('message')) == (today_study, today_delta, message):
        print(str(out_path))
        return 0

    payload = {
        'date': date,
        'archivedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'today_study': today_study,
        'today_delta': today_delta,
        'message': message,
    }

    # Atomic-ish write
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp_path.replace(out_path)

    print(str(out_path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

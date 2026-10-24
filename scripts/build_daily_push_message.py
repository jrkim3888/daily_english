#!/usr/bin/env python3
"""Build combined daily study message.

Combines:
- today_study.json (picked at KST 00:00)
- today_delta.json (from 08:30 fetch of witjung post)

Prints message text to stdout. Used by multiple cron sends.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
STUDY = DATA / 'today_study.json'
DELTA = DATA / 'today_delta.json'


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
    # Drop a delta left over from an earlier day (no new post today).
    if s.get('date') and d.get('date') != s.get('date'):
        d = {}
    lines = []
    lines.append("[알림][오늘의영어]")
    lines.append(f"오늘의 영어 공부 ({date})" if date else "오늘의 영어 공부")

    dv = (d.get('vocab') or '').strip()
    ds = (d.get('sentences') or '').strip()
    vocab_today = s.get('vocab') or []
    sent_today = s.get('sentences') or []

    # --- [오늘의 단어] ---
    lines.append('')
    lines.append('[오늘의 단어]')

    if dv:
        for l in dv.split('\n'):
            l = l.strip()
            if l:
                lines.append(f"- {l}" if not l.startswith('- ') else l)

    for v in vocab_today:
        v = str(v).strip()
        if v:
            lines.append(f"- {v}")

    # --- [오늘의 문장] ---
    lines.append('')
    lines.append('[오늘의 문장]')

    if ds:
        for l in ds.split('\n'):
            l = l.strip()
            if l:
                lines.append(f"- {l}" if not l.startswith('- ') else l)

    for x in sent_today:
        x = str(x).strip()
        if x:
            lines.append(f"- {x}")

    if (not dv) and (not ds) and (not vocab_today) and (not sent_today):
        lines.append('(오늘 데이터가 아직 준비되지 않았어요. 00:00/08:30 작업을 확인해 주세요.)')

    print('\n'.join(lines).strip())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Send today's added items (delta) to Discord channel.

Used by cron @ 09:00 KST. It reads data/today_delta.json and prints a ready-to-send
message text to stdout. The cron agentTurn will call message tool to send it.
"""

from __future__ import annotations

import json
from pathlib import Path

DELTA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'today_delta.json'


def main() -> int:
    if not DELTA_PATH.exists():
        print('(오늘 추가된 항목이 아직 없어요.)')
        return 0

    d = json.loads(DELTA_PATH.read_text(encoding='utf-8'))

    lines = []
    lines.append(f"오늘의 영어 공부 항목 ({d.get('date','')})")
    lines.append(d.get('title','').strip())
    lines.append(d.get('link','').strip())

    vocab_raw = (d.get('vocab') or '').strip()
    sent_raw = (d.get('sentences') or '').strip()

    # Clean up (defensive: delta file may contain extra tails)
    vocab_lines = []
    for l in vocab_raw.split('\n') if vocab_raw else []:
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        if ':' in l:
            vocab_lines.append(l)
    vocab = '\n'.join(vocab_lines).strip()

    sent_lines = []
    for l in sent_raw.split('\n') if sent_raw else []:
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        if '※' in l:
            break
        if any(k in l for k in ['입이 트이는', '영어 오디오', '다시듣기']):
            break
        if __import__('re').search(r'[가-힣]', l):
            continue
        if not __import__('re').search(r'[A-Za-z]', l):
            continue
        sent_lines.append(l)
    sent = '\n'.join(sent_lines).strip()

    if vocab:
        lines.append('')
        lines.append('[관련 단어]')
        lines.append(vocab)

    if sent:
        lines.append('')
        lines.append('[암기 문장]')
        lines.append(sent)

    print('\n'.join([l for l in lines if l is not None]).strip())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

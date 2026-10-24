#!/usr/bin/env python3
"""Pick today's study items (vocab 5 + sentences 3) at KST midnight.

Inputs:
- <repo>/data/english_vocab.md
- <repo>/data/english_sentences.md

Output (saved for reuse during the day):
- <repo>/data/today_study.json

Selection:
- Random but deterministic per KST date (seeded by YYYY-MM-DD), so reruns on the same day produce the same picks.
- Deduped.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
VOCAB_PATH = DATA / 'english_vocab.md'
SENT_PATH = DATA / 'english_sentences.md'
OUT_PATH = DATA / 'today_study.json'


def kst_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))


def kst_date_str(dt: datetime | None = None) -> str:
    dt = dt or kst_now()
    return dt.strftime('%Y-%m-%d')


def read_bullets(path: Path) -> List[str]:
    if not path.exists():
        return []
    out: List[str] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('- '):
            val = line[2:].strip()
            if val:
                out.append(val)
    # de-dupe preserving order
    seen = set()
    uniq = []
    for x in out:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq


def pick(items: List[str], n: int, seed: str) -> List[str]:
    if not items:
        return []
    rng = random.Random(seed)
    if len(items) <= n:
        return items[:]
    # sample without replacement
    return rng.sample(items, n)


def _term_from_vocab_line(v: str) -> str:
    return v.split(':', 1)[0].strip()


def _sentence_matches_term(sentence: str, term: str) -> bool:
    s = sentence.lower()
    t = term.lower().strip()
    if not t:
        return False

    # Avoid overly-short terms causing lots of false positives (e.g., "in")
    if len(t) < 3:
        return False

    # Multi-word / hyphenated / apostrophe terms: use substring match
    if re.search(r"[\s\-']", t):
        return t in s

    # Single token: word-boundary match
    return bool(re.search(rf"\b{re.escape(t)}\b", s))


def main() -> int:
    date = kst_date_str()

    vocab_all = read_bullets(VOCAB_PATH)
    # keep only "term: meaning" style for vocab
    vocab_all = [v for v in vocab_all if ':' in v]

    sent_all = read_bullets(SENT_PATH)
    # keep sentence-like lines
    sent_all = [s for s in sent_all if re.search(r'[A-Za-z]', s)]

    vocab = pick(vocab_all, 5, seed=f'vocab:{date}')

    # Prefer sentences that contain at least one picked vocab term.
    terms = [_term_from_vocab_line(v) for v in vocab]
    matched = [s for s in sent_all if any(_sentence_matches_term(s, t) for t in terms)]

    sents = pick(matched, 3, seed=f'sentmatch:{date}')
    # Top up from the rest of the pool when fewer than 3 sentences matched.
    if len(sents) < 3:
        rest = [s for s in sent_all if s not in sents]
        sents += pick(rest, 3 - len(sents), seed=f'sent:{date}')

    payload = {
        'date': date,
        'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'vocab': vocab,
        'sentences': sents,
        'counts': {
            'vocabPool': len(vocab_all),
            'sentencePool': len(sent_all),
        },
    }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(OUT_PATH))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

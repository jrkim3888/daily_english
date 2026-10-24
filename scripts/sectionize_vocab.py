#!/usr/bin/env python3
"""Rewrite english_vocab.md into three sections: Words / Phrasal Verbs / Idioms.

- Keeps only bullet lines that look like "term: meaning".
- Heuristically classifies entries by the *term* (before ':').
- Writes back to english_vocab.md after saving a timestamped backup.

This is a best-effort classifier; you can manually move misclassified items later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

VOCAB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'english_vocab.md'

PARTICLES = {
    'up','down','out','in','on','off','over','away','back','around','through','into','onto','upon','across','along','by','for','with','without','about','after','before'
}

COMMON_FUNCTION_WORDS = {
    'the','a','an','to','of','and','or','but','in','on','at','for','with','without','from','as','by','about','into','over','under','after','before','than'
}


def iter_vocab_bullets(lines: Iterable[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        s = line.strip()
        if not s.startswith('- '):
            continue
        val = s[2:].strip()
        if not val or ':' not in val:
            continue
        out.append(val)
    # de-dupe (case-insensitive) preserving order
    seen = set()
    uniq: List[str] = []
    for x in out:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq


def classify(entry: str) -> str:
    """Return section key: words|phrasal|idioms"""
    term = entry.split(':', 1)[0].strip().lower()
    term = re.sub(r"\s+", " ", term)

    tokens = [t for t in re.split(r"\s+", term) if t]

    # Phrasal verbs (wider): any 2-3 word expression ending with a particle
    # (e.g., "look up", "put off", "get away", "wear out")
    if 2 <= len(tokens) <= 3:
        if tokens[-1] in PARTICLES:
            return 'phrasal'

    # Idioms (wider): multi-word fixed expressions
    if len(tokens) >= 3:
        return 'idioms'

    # Some two-word expressions are idiom-like (e.g., "nest egg", "one-way street")
    if len(tokens) == 2:
        if any(t in COMMON_FUNCTION_WORDS for t in tokens):
            return 'idioms'
        # if it's not clearly a phrasal verb but is a two-word noun phrase, treat as idiom
        return 'idioms'

    return 'words'


def main() -> int:
    if not VOCAB_PATH.exists():
        raise SystemExit(f"Missing: {VOCAB_PATH}")

    raw_lines = VOCAB_PATH.read_text(encoding='utf-8').splitlines()
    bullets = iter_vocab_bullets(raw_lines)

    words: List[str] = []
    phrasal: List[str] = []
    idioms: List[str] = []

    for b in bullets:
        k = classify(b)
        if k == 'phrasal':
            phrasal.append(b)
        elif k == 'idioms':
            idioms.append(b)
        else:
            words.append(b)

    # backup
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    backup = VOCAB_PATH.with_suffix(f".bak.{ts}.md")
    backup.write_text("\n".join(raw_lines) + "\n", encoding='utf-8')

    # write new file
    out: List[str] = []
    out.append('# 📘 영어 단어 정리')
    out.append('')
    out.append('## Words')
    out.append('')
    out.extend([f"- {x}" for x in words])
    out.append('')
    out.append('## Phrasal Verbs')
    out.append('')
    out.extend([f"- {x}" for x in phrasal])
    out.append('')
    out.append('## Idioms')
    out.append('')
    out.extend([f"- {x}" for x in idioms])
    out.append('')

    VOCAB_PATH.write_text("\n".join(out), encoding='utf-8')

    print(f"Backup: {backup}")
    print(f"Wrote:  {VOCAB_PATH}")
    print(f"Counts: words={len(words)}, phrasal={len(phrasal)}, idioms={len(idioms)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch latest '입이 트이는 영어' post from witjung Naver blog (영어 category).

Workflow (used by cron @ 08:30 KST):
- Read RSS: https://rss.blog.naver.com/witjung.xml
- Pick the latest item where category contains '영어' AND title contains '입이 트이는 영어'
- If already processed (state.json), exit 0 with no changes.
- Fetch mobile post HTML (m.blog.naver.com) and extract sections:
  - 관련 단어
  - 암기 문장
- Prepend extracted content to:
  - <repo>/data/english_vocab.md
  - <repo>/data/english_sentences.md
- Save today's delta for sending later:
  - <repo>/data/today_delta.json

Output: prints a JSON summary to stdout.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
DATA.mkdir(parents=True, exist_ok=True)

STATE_PATH = DATA / 'state.json'
DELTA_PATH = DATA / 'today_delta.json'

# Primary output files (expected by downstream sends)
VOCAB_PATH = BASE / 'english_vocab.md'
SENT_PATH = BASE / 'english_sentence.md'

# Back-compat copies (older paths used previously)
VOCAB_PATH_LEGACY = DATA / 'english_vocab.md'
SENT_PATH_LEGACY = DATA / 'english_sentences.md'

RSS_URL = 'https://rss.blog.naver.com/witjung.xml'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'


def kst_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))


def kst_date_str(dt: Optional[datetime] = None) -> str:
    dt = dt or kst_now()
    return dt.strftime('%Y-%m-%d')


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def http_get(url: str, timeout: int = 25) -> requests.Response:
    r = requests.get(url, headers={'User-Agent': UA}, timeout=timeout)
    r.raise_for_status()
    # Naver is UTF-8; force if misdetected
    enc = (r.encoding or '').lower()
    if (not enc) or enc in ('iso-8859-1', 'latin-1', 'windows-1252', 'ascii'):
        r.encoding = 'utf-8'
    return r


@dataclass
class RssItem:
    title: str
    link: str
    category: str
    pubDate: str


def parse_rss_latest() -> Optional[RssItem]:
    xml = http_get(RSS_URL, timeout=25).text
    root = ET.fromstring(xml)
    for it in root.findall('.//item'):
        title = (it.findtext('title') or '').strip()
        link = (it.findtext('link') or '').strip()
        cat = (it.findtext('category') or '').strip()
        pub = (it.findtext('pubDate') or '').strip()
        if not title or not link:
            continue
        if '영어' not in cat:
            continue
        if '입이 트이는 영어' not in title:
            continue
        return RssItem(title=title, link=link, category=cat, pubDate=pub)
    return None


def to_mobile_post_url(link: str) -> str:
    # example: https://blog.naver.com/witjung/224169684284?fromRss=true...
    m = re.search(r'/([0-9]{6,})', link)
    if not m:
        return link
    logno = m.group(1)
    return f'https://m.blog.naver.com/witjung/{logno}'


def extract_sections_from_mobile_html(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('div.se-main-container') or soup
    txt = container.get_text('\n', strip=True)
    # normalize
    txt = re.sub(r'[\t\r]+', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)

    def between(start_pat: str, end_pat: str) -> str:
        m = re.search(start_pat, txt)
        if not m:
            return ''
        s = m.end()
        rest = txt[s:]
        m2 = re.search(end_pat, rest)
        chunk = rest[: m2.start()] if m2 else rest
        chunk = chunk.strip()
        lines = [re.sub(r'\s+', ' ', l).strip() for l in chunk.split('\n')]
        lines = [l for l in lines if l and l not in ('관련 단어', '암기 문장')]
        return '\n'.join(lines).strip()

    # Stop early before tags/notice blocks that often follow the study content.
    end_common = r'(전체\s*대본|전체\s*스크립트|대본|※|#|입이\s*트이는|영어\s*오디오|다시듣기|\Z)'

    vocab_raw = between(r'관련\s*단어\s*\n?', r'(암기\s*문장|' + end_common + r')')
    sent_raw = between(r'암기\s*문장\s*\n?', r'(관련\s*단어|' + end_common + r')')

    # Post-clean
    vocab_lines: List[str] = []
    for l in vocab_raw.split('\n') if vocab_raw else []:
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        # keep "word: meaning" style lines primarily
        if ':' in l:
            vocab_lines.append(l)
    vocab = '\n'.join(vocab_lines).strip()

    sent_lines: List[str] = []
    for l in sent_raw.split('\n') if sent_raw else []:
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        # keep mostly-English lines
        if re.search(r'[가-힣]', l):
            continue
        if len(l) < 4:
            continue
        # must contain letters
        if not re.search(r'[A-Za-z]', l):
            continue
        sent_lines.append(l)
    sent = '\n'.join(sent_lines).strip()

    return vocab, sent


def prepend_block(path: Path, block: str) -> None:
    existing = path.read_text(encoding='utf-8') if path.exists() else ''
    path.write_text(block + ('\n\n' if existing and not existing.startswith('\n') else '\n') + existing, encoding='utf-8')


PARTICLES = {
    'up','down','out','in','on','off','over','away','back','around','through','into','onto','upon',
    'across','along','by','for','with','without','about','after','before'
}


def insert_bullets_under_heading(path: Path, heading_line: str, bullets: List[str]) -> None:
    """Insert bullet lines under a specific heading line.

    Example heading_line: '# ✍ 외울 문장 정리'
    Bullets are inserted immediately after the heading line.
    """
    content = path.read_text(encoding='utf-8') if path.exists() else ''
    lines = content.splitlines()
    out: List[str] = []
    inserted = False

    # Normalize bullets
    b_lines = [f"- {b.strip()}" for b in bullets if b and b.strip()]

    for line in lines:
        out.append(line)
        if (not inserted) and line.strip() == heading_line.strip():
            # keep a blank line after heading
            if not (len(out) >= 2 and out[-2] == ''):
                out.append('')
            out.extend(b_lines)
            inserted = True

    if not inserted:
        # If heading missing, create a minimal file.
        out = [heading_line.strip(), '', *b_lines, '', *lines]

    # Avoid an extra blank line between inserted bullets and existing bullets
    cleaned: List[str] = []
    for i, line in enumerate(out):
        if i > 0 and line == '' and cleaned and cleaned[-1] == '':
            continue
        cleaned.append(line)

    path.write_text('\n'.join(cleaned).rstrip() + '\n', encoding='utf-8')


def classify_vocab_term(term: str) -> str:
    """Return section heading: '## Words' | '## Phrasal Verbs' | '## Idioms'"""
    t = re.sub(r"\s+", " ", (term or '').strip().lower())
    if not t:
        return '## Words'
    tokens = [x for x in t.split(' ') if x]

    # Phrasal verbs: 2-3 word expression ending with a particle.
    if 2 <= len(tokens) <= 3 and tokens[-1] in PARTICLES:
        return '## Phrasal Verbs'

    # Idioms: multi-word (>=3) fixed expressions.
    if len(tokens) >= 3:
        return '## Idioms'

    # Two-word expressions are usually phrase-like; treat as idioms by default.
    if len(tokens) == 2:
        return '## Idioms'

    # Words: default.
    return '## Words'


def ensure_vocab_sections(lines: List[str]) -> List[str]:
    """Ensure vocab file has the 3 section headings under '# 📘 영어 단어 정리'."""
    if any(l.strip() == '## Words' for l in lines) and any(l.strip() == '## Phrasal Verbs' for l in lines) and any(
        l.strip() == '## Idioms' for l in lines
    ):
        return lines

    out: List[str] = []
    title = '# 📘 영어 단어 정리'
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if (not inserted) and line.strip() == title:
            out.append('')
            out.extend(['## Words', '', '## Phrasal Verbs', '', '## Idioms', ''])
            inserted = True

    if not inserted:
        # Create minimal structure
        out = [title, '', '## Words', '', '## Phrasal Verbs', '', '## Idioms', '', *lines]

    # Clean duplicate blank lines
    cleaned: List[str] = []
    for line in out:
        if line == '' and cleaned and cleaned[-1] == '':
            continue
        cleaned.append(line)
    return cleaned


def insert_vocab_bullets_by_section(path: Path, bullets: List[str]) -> None:
    """Insert vocab bullets into the correct section (Words/Phrasal Verbs/Idioms)."""
    content = path.read_text(encoding='utf-8') if path.exists() else ''
    lines = content.splitlines() if content else ['# 📘 영어 단어 정리', '']
    lines = ensure_vocab_sections(lines)

    # Prepare per-section bullet strings
    buckets: dict[str, List[str]] = {'## Words': [], '## Phrasal Verbs': [], '## Idioms': []}
    for b in bullets:
        b = (b or '').strip()
        if not b:
            continue
        term = b.split(':', 1)[0].strip() if ':' in b else b
        sec = classify_vocab_term(term)
        buckets[sec].append(f"- {b}")

    if not any(buckets.values()):
        return

    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip() in buckets and buckets[line.strip()]:
            # Insert immediately after the section heading line
            # Ensure a blank line before bullets
            if i + 1 < len(lines) and lines[i + 1].strip() != '':
                out.append('')
            out.extend(buckets[line.strip()])
            out.append('')
            # Consume following already-present blank line(s) to avoid double spacing
        i += 1

    # Final cleanup of duplicate blank lines
    cleaned: List[str] = []
    for line in out:
        if line == '' and cleaned and cleaned[-1] == '':
            continue
        cleaned.append(line)

    path.write_text('\n'.join(cleaned).rstrip() + '\n', encoding='utf-8')


def main() -> int:
    state = load_state()
    latest = parse_rss_latest()
    if not latest:
        out = {"ok": False, "reason": "no matching RSS item"}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    last_link = state.get('last_link')
    if last_link == latest.link:
        out = {"ok": True, "changed": False, "reason": "already processed", "title": latest.title, "link": latest.link}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    mobile_url = to_mobile_post_url(latest.link)
    html = http_get(mobile_url, timeout=25).text
    vocab, sent = extract_sections_from_mobile_html(html)

    stamp = kst_now().strftime('%Y-%m-%d %H:%M KST')
    header = f"## {kst_date_str()} | {latest.title}\n{latest.link}\n(수집: {stamp})\n"

    delta = {
        "date": kst_date_str(),
        "title": latest.title,
        "link": latest.link,
        "category": latest.category,
        "pubDate": latest.pubDate,
        "vocab": vocab,
        "sentences": sent,
    }
    DELTA_PATH.write_text(json.dumps(delta, ensure_ascii=False, indent=2), encoding='utf-8')

    if vocab.strip():
        # Insert only vocab lines as bullets under the existing heading.
        bullets = [l.strip() for l in vocab.split('\n') if l.strip()]
        insert_vocab_bullets_by_section(VOCAB_PATH, bullets)
        insert_vocab_bullets_by_section(VOCAB_PATH_LEGACY, bullets)

    if sent.strip():
        # Insert only the memorization sentences as bullets under the existing heading.
        bullets = [l.strip() for l in sent.split('\n') if l.strip()]
        insert_bullets_under_heading(SENT_PATH, '# ✍ 외울 문장 정리', bullets)
        insert_bullets_under_heading(SENT_PATH_LEGACY, '# ✍ 외울 문장 정리', bullets)

    state['last_link'] = latest.link
    state['last_run_kst'] = stamp
    save_state(state)

    out = {"ok": True, "changed": True, "title": latest.title, "link": latest.link, "hasVocab": bool(vocab.strip()), "hasSentences": bool(sent.strip())}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch '입이 트이는 영어' posts from the witjung Naver blog (영어 category).

Workflow (cron @ 08:30 KST):
- Read RSS: https://rss.blog.naver.com/witjung.xml
- Pick every matching item (category '영어', title '입이 트이는 영어') not yet processed
  (state.json keeps the processed post numbers), oldest first.
- For each post, extract '관련 단어' / '암기 문장' and add new bullets to the vocab/sentence files.
- Each post is filed under its blog publish date (KST):
  - published today  → data/today_delta.json (sent at 09:00, archived by archive_daily.py)
  - published earlier → merged into outputs/history/<publish date>.json (backfill)

Usage: fetch_ibi_tweineun.py [--dry-run]
Output: prints a JSON summary to stdout.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from email.utils import parsedate_to_datetime
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
HISTORY = BASE / 'outputs' / 'history'
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


def parse_rss_items() -> List[RssItem]:
    """All matching items in the feed, oldest first."""
    xml = http_get(RSS_URL, timeout=25).text
    root = ET.fromstring(xml)
    out: List[RssItem] = []
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
        out.append(RssItem(title=title, link=link, category=cat, pubDate=pub))
    out.sort(key=lambda x: pub_kst(x.pubDate) or kst_now())
    return out


def logno_of(link: str) -> str:
    m = re.search(r'/([0-9]{6,})', link or '')
    return m.group(1) if m else ''


def pub_kst(pub: str) -> Optional[datetime]:
    try:
        return parsedate_to_datetime(pub).astimezone(timezone(timedelta(hours=9)))
    except Exception:
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


def existing_bullets(path: Path) -> set:
    if not path.exists():
        return set()
    return {l.strip()[2:].strip().lower() for l in path.read_text(encoding='utf-8').splitlines() if l.strip().startswith('- ')}


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

    # Normalize bullets, skipping ones already in the file
    have = existing_bullets(path)
    b_lines = [f"- {b.strip()}" for b in bullets if b and b.strip() and b.strip().lower() not in have]
    if not b_lines:
        return

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
    have = existing_bullets(path)
    for b in bullets:
        b = (b or '').strip()
        if not b or b.lower() in have:
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


def archive_deltas(raw: dict) -> List[dict]:
    """Posts stored in an archive file (new 'deltas' list, or the legacy single 'today_delta')."""
    if raw.get('deltas'):
        return list(raw['deltas'])
    d = raw.get('today_delta') or {}
    return [d] if d.get('date') == raw.get('date') and d.get('link') else []


def seed_processed(state: dict) -> set:
    """Post numbers already handled: from state, plus every post recorded in the archive."""
    done = set(state.get('processed') or [])
    if state.get('last_link'):
        done.add(logno_of(state['last_link']))
    for f in HISTORY.glob('*.json'):
        try:
            raw = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        for d in archive_deltas(raw):
            done.add(logno_of(d.get('link', '')))
    done.discard('')
    return done


def attach_to_archive(date: str, delta: dict) -> None:
    """Merge a backfilled post into outputs/history/<date>.json, keeping whatever is there."""
    HISTORY.mkdir(parents=True, exist_ok=True)
    path = HISTORY / f'{date}.json'
    raw = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'date': date, 'today_study': {}, 'message': ''}
    deltas = [d for d in archive_deltas(raw) if logno_of(d.get('link', '')) != logno_of(delta['link'])]
    deltas.append(delta)
    deltas.sort(key=lambda d: pub_kst(d.get('pubDate', '')) or kst_now())
    raw['deltas'] = deltas
    raw['today_delta'] = deltas[0]
    raw['archivedAt'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def main() -> int:
    dry = '--dry-run' in sys.argv
    state = load_state()
    processed = seed_processed(state)
    items = parse_rss_items()
    if not items:
        print(json.dumps({"ok": False, "reason": "no matching RSS item"}, ensure_ascii=False))
        return 0

    todo = [it for it in items if logno_of(it.link) not in processed]
    today = kst_date_str()
    added, failed, today_posts = [], [], []

    for it in todo:
        pub = pub_kst(it.pubDate)
        date = pub.strftime('%Y-%m-%d') if pub else today
        if dry:
            added.append({"date": date, "title": it.title})
            continue
        try:
            html = http_get(to_mobile_post_url(it.link), timeout=25).text
        except Exception as e:
            failed.append({"title": it.title, "error": str(e)})
            continue
        vocab, sent = extract_sections_from_mobile_html(html)
        delta = {
            "date": date,
            "title": it.title,
            "link": it.link,
            "category": it.category,
            "pubDate": it.pubDate,
            "vocab": vocab,
            "sentences": sent,
        }

        if vocab.strip():
            bullets = [l.strip() for l in vocab.split('\n') if l.strip()]
            insert_vocab_bullets_by_section(VOCAB_PATH, bullets)
            insert_vocab_bullets_by_section(VOCAB_PATH_LEGACY, bullets)
        if sent.strip():
            bullets = [l.strip() for l in sent.split('\n') if l.strip()]
            insert_bullets_under_heading(SENT_PATH, '# ✍ 외울 문장 정리', bullets)
            insert_bullets_under_heading(SENT_PATH_LEGACY, '# ✍ 외울 문장 정리', bullets)

        if date == today:
            today_posts.append(delta)
        else:
            attach_to_archive(date, delta)

        processed.add(logno_of(it.link))
        state['processed'] = sorted(processed)
        state['last_link'] = it.link
        save_state(state)
        added.append({"date": date, "title": it.title, "hasVocab": bool(vocab.strip()), "hasSentences": bool(sent.strip())})
        time.sleep(0.5)

    if today_posts:
        # Combined view for today's sends; 'posts' keeps each post for the archive.
        latest = today_posts[-1]
        DELTA_PATH.write_text(json.dumps({
            **latest,
            "vocab": '\n'.join(p['vocab'] for p in today_posts if p['vocab']),
            "sentences": '\n'.join(p['sentences'] for p in today_posts if p['sentences']),
            "posts": today_posts,
        }, ensure_ascii=False, indent=2), encoding='utf-8')

    if not dry:
        state['processed'] = sorted(processed)
        state['last_run_kst'] = kst_now().strftime('%Y-%m-%d %H:%M KST')
        save_state(state)

    out = {"ok": not failed, "dryRun": dry, "changed": bool(added) and not dry, "today": len(today_posts),
           "backfilled": len([a for a in added if a['date'] != today]), "added": added, "failed": failed}
    print(json.dumps(out, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

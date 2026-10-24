#!/usr/bin/env python3
"""One-off backfill: add memorization sentences from '입이 트이는 영어' posts (2025-2026)
from Naver blog https://blog.naver.com/witjung (English category).

- Finds posts via PostList categoryNo=83 (영어)
- Filters titles containing '입이 트이는 영어'
- Fetches each post (mobile) and extracts only the '암기 문장' block
- Inserts sentences as '- sentence' bullets under '# ✍ 외울 문장 정리' in english_sentences.md
- Dedupes sentences already present.

NOTE: This is best-effort scraping; it will skip posts where the section isn't found.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent.parent
OUT_PATH = BASE / 'data' / 'english_sentences.md'

BLOG_ID = 'witjung'
# Use server-side search to enumerate posts reliably (works without JS rendering).
SEARCH_URL = 'https://blog.naver.com/PostSearchList.naver'
SEARCH_TEXT = '입이 트이는 영어'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'

START = datetime(2025, 9, 1)
END = datetime(2026, 2, 28, 23, 59, 59)


def http_get(url: str, timeout: int = 25) -> str:
    r = requests.get(url, headers={'User-Agent': UA}, timeout=timeout)
    r.raise_for_status()
    enc = (r.encoding or '').lower()
    if (not enc) or enc in ('iso-8859-1', 'latin-1', 'windows-1252', 'ascii'):
        r.encoding = 'utf-8'
    return r.text


def mobile_url_from_logno(logno: str) -> str:
    return f'https://m.blog.naver.com/{BLOG_ID}/{logno}'


def parse_search_page(html: str) -> List[Tuple[str, str]]:
    """Return list of (logno, title) from PostSearchList results."""
    soup = BeautifulSoup(html, 'html.parser')
    out: List[Tuple[str, str]] = []

    for a in soup.select('a[href*="logNo="]'):
        href = a.get('href', '')
        m = re.search(r'logNo=(\d+)', href)
        if not m:
            continue
        title = a.get_text(' ', strip=True)
        if not title:
            continue
        out.append((m.group(1), title))

    # de-dupe preserving order
    seen=set(); uniq=[]
    for logno,title in out:
        if logno in seen:
            continue
        seen.add(logno)
        uniq.append((logno,title))
    return uniq


def extract_memorization_sentences(mobile_html: str) -> List[str]:
    soup = BeautifulSoup(mobile_html, 'html.parser')
    container = soup.select_one('div.se-main-container') or soup
    txt = container.get_text('\n', strip=True)
    txt = re.sub(r'[\t\r]+', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)

    # find '암기 문장' block
    m = re.search(r'암기\s*문장\s*\n', txt)
    if not m:
        return []
    rest = txt[m.end():]
    # stop at tags/notice or next section
    end_pat = r'(관련\s*단어|전체\s*대본|전체\s*스크립트|대본|※|#|입이\s*트이는|영어\s*오디오|다시듣기|\Z)'
    m2 = re.search(end_pat, rest)
    chunk = rest[:m2.start()] if m2 else rest

    lines=[]
    for l in chunk.split('\n'):
        l=l.strip()
        if not l:
            continue
        if l.startswith('#'):
            break
        if '※' in l:
            break
        if re.search(r'[가-힣]', l):
            continue
        if not re.search(r'[A-Za-z]', l):
            continue
        # strip weird zero-widths
        l = l.replace('\u200b','').strip()
        # avoid overly long paragraphs
        if len(l) > 200:
            continue
        lines.append(l)

    # de-dupe within block
    out=[]
    for l in lines:
        if l not in out:
            out.append(l)
    return out


def load_existing_sentences(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    s=set()
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if line.startswith('- '):
            s.add(line[2:].strip())
    return s


def insert_bullets_under_heading(path: Path, heading_line: str, bullets: List[str]) -> None:
    content = path.read_text(encoding='utf-8') if path.exists() else ''
    lines = content.splitlines()
    out: List[str] = []
    inserted = False
    b_lines = [f"- {b.strip()}" for b in bullets if b and b.strip()]

    for line in lines:
        out.append(line)
        if (not inserted) and line.strip() == heading_line.strip():
            out.append('')
            out.extend(b_lines)
            inserted = True

    if not inserted:
        out = [heading_line.strip(), '', *b_lines, '', *lines]

    # collapse double blank lines
    cleaned=[]
    for line in out:
        if cleaned and cleaned[-1]=='' and line=='':
            continue
        cleaned.append(line)

    path.write_text('\n'.join(cleaned).rstrip()+'\n', encoding='utf-8')


def main() -> int:
    existing = load_existing_sentences(OUT_PATH)
    to_add: List[str] = []

    page = 1
    seen_logno=set()
    matched_posts=0
    processed_posts=0
    added_sentences=0

    while True:
        params = {
            'blogId': BLOG_ID,
            'SearchText': SEARCH_TEXT,
            'orderBy': 'date',
            'startDate': START.strftime('%Y-%m-%d'),
            'endDate': END.strftime('%Y-%m-%d'),
            'range': 'all',
            'cpage': str(page),
        }
        html = requests.get(SEARCH_URL, params=params, headers={'User-Agent': UA}, timeout=25).text
        posts = parse_search_page(html)
        if not posts:
            break

        new_on_page = 0
        for logno, title in posts:
            if logno in seen_logno:
                continue
            seen_logno.add(logno)
            new_on_page += 1

            if SEARCH_TEXT not in title:
                continue
            matched_posts += 1

            try:
                mob = http_get(mobile_url_from_logno(logno), timeout=25)
            except Exception:
                continue

            sents = extract_memorization_sentences(mob)
            if not sents:
                continue

            processed_posts += 1
            for s in sents:
                if s in existing:
                    continue
                existing.add(s)
                to_add.append(s)
                added_sentences += 1

            time.sleep(0.35)

        # If we didn't discover anything new on this page, stop.
        if new_on_page == 0:
            break

        page += 1
        if page > 400:  # safety
            break
        time.sleep(0.35)

    # One-off rewrite: replace the top list under the heading with the rebuilt bullets.
    heading = '# ✍ 외울 문장 정리'
    rebuilt = [heading, ''] + [f'- {s}' for s in to_add] + ['']
    OUT_PATH.write_text('\n'.join(rebuilt).rstrip() + '\n', encoding='utf-8')

    print(f"matched_posts={matched_posts} processed_posts={processed_posts} added_sentences={added_sentences} pages_scanned={page}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

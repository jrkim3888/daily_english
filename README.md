# Daily English (입트영 자동화 + 블로그)

[witjung 블로그](https://blog.naver.com/witjung)의 "입이 트이는 영어" 글에서 단어/문장을 모아
매일 Discord로 보내고, 날짜별 기록을 Astro 블로그(Cloudflare Pages)로 공개합니다.

## 구조

```
data/english_vocab.md        누적 단어 (Words / Phrasal Verbs / Idioms)
data/english_sentences.md    누적 문장
outputs/history/DATE.json    날짜별 아카이브 → 블로그 데이터
scripts/                     수집·선택·전송·아카이브 스크립트
site/                        Astro 블로그
```

## 설치

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Cron (KST) — openclaw에 등록

| 시간 | 명령 |
|---|---|
| 00:00 | `scripts/pick_today_study.sh` — 오늘 학습 세트(단어 5 + 문장 3) |
| 08:30 | `scripts/fetch_ibi_tweineun.sh` — 오늘 글 수집 → 아카이브 → push |
| 09:00 | `scripts/send_today_delta_to_discord.sh` — 오늘 추가분 1회 전송 |
| 10:00 / 12:30 / 16:00 / 19:00 / 22:00 / 23:55 | `scripts/send_daily_push_with_archive.sh` — 전송 → 아카이브 → push |

모든 스크립트는 자기 위치 기준으로 경로를 잡으므로 어느 디렉터리에서 실행해도 됩니다.
`openclaw` 경로가 PATH에 없으면 `OPENCLAW_BIN`으로 지정하세요.

## 블로그

- `scripts/publish_site.sh`가 `outputs/history`와 `data/*.md` 변경분만 커밋하고 push
- Cloudflare Pages가 push를 감지해 빌드
  - Root directory: `site`
  - Build command: `npm run build`
  - Output: `dist`
- 로컬 미리보기: `cd site && npm install && npm run dev`

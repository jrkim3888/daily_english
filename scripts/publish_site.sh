#!/usr/bin/env bash
# Commit archive/data changes and push; GitHub Actions deploys to Cloudflare Pages on push.
set -euo pipefail
source "$(dirname "$0")/_env.sh"
cd "$BASE"

git add outputs/history data/english_vocab.md data/english_sentences.md
if git diff --cached --quiet; then
  echo "publish: no changes"
  exit 0
fi

git commit -q -m "daily: $(TZ=Asia/Seoul date +%Y-%m-%d)"
# Site code may have been pushed from elsewhere; replay the data commit on top.
git pull -q --rebase --autostash origin main
git push -q origin main
echo "publish: pushed"

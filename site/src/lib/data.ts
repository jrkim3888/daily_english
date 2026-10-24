// Reads the archive produced by scripts/archive_daily.py at build time.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.env.DATA_ROOT ?? path.resolve(process.cwd(), '..');
const HISTORY = path.join(ROOT, 'outputs', 'history');
const DATA = path.join(ROOT, 'data');

export interface Vocab {
  term: string;
  meaning: string;
}

export interface Day {
  date: string;
  post?: { title: string; link: string };
  newVocab: Vocab[];
  newSentences: string[];
  reviewVocab: Vocab[];
  reviewSentences: string[];
}

export function parseVocab(line: string): Vocab {
  const i = line.indexOf(':');
  if (i < 0) return { term: line.trim(), meaning: '' };
  return { term: line.slice(0, i).trim(), meaning: line.slice(i + 1).trim() };
}

function lines(s: unknown): string[] {
  return String(s ?? '')
    .split('\n')
    .map((l) => l.replace(/^- /, '').trim())
    .filter(Boolean);
}

function cleanLink(link: string): string {
  return link.replace(/\?.*$/, '');
}

let cache: Day[] | undefined;

// Newest first.
export function getDays(): Day[] {
  if (cache) return cache;
  const files = fs.existsSync(HISTORY)
    ? fs.readdirSync(HISTORY).filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
    : [];
  cache = files
    .map((f) => {
      const raw = JSON.parse(fs.readFileSync(path.join(HISTORY, f), 'utf-8'));
      const date = f.replace('.json', '');
      const study = raw.today_study ?? {};
      // Older archives may carry a delta from a previous day; only keep same-day posts.
      const delta = raw.today_delta?.date === date ? raw.today_delta : {};
      return {
        date,
        post: delta.title ? { title: delta.title, link: cleanLink(delta.link ?? '') } : undefined,
        newVocab: lines(delta.vocab).filter((l) => l.includes(':')).map(parseVocab),
        newSentences: lines(delta.sentences),
        reviewVocab: (study.vocab ?? []).map((v: string) => parseVocab(String(v))),
        reviewSentences: (study.sentences ?? []).map((s: string) => String(s).trim()).filter(Boolean),
      } satisfies Day;
    })
    .sort((a, b) => b.date.localeCompare(a.date));
  return cache;
}

function bullets(file: string): { section: string; text: string }[] {
  const p = path.join(DATA, file);
  if (!fs.existsSync(p)) return [];
  const out: { section: string; text: string }[] = [];
  const seen = new Set<string>();
  let section = '';
  for (const raw of fs.readFileSync(p, 'utf-8').split('\n')) {
    const line = raw.trim();
    if (line.startsWith('## ')) section = line.slice(3).trim();
    if (!line.startsWith('- ')) continue;
    const text = line.slice(2).trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    out.push({ section, text });
  }
  return out;
}

export function getAllVocab(): (Vocab & { section: string })[] {
  return bullets('english_vocab.md')
    .filter((b) => b.text.includes(':'))
    .map((b) => ({ section: b.section || 'Words', ...parseVocab(b.text) }));
}

export function getAllSentences(): string[] {
  return bullets('english_sentences.md').map((b) => b.text);
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export function formatDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  const wd = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${y}년 ${m}월 ${d}일 (${wd})`;
}

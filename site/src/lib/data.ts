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

export interface Post {
  title: string;
  aired: string; // broadcast date YYYY-MM-DD ('' if unknown)
  link: string;
}

export interface Episode {
  post: Post;
  vocab: Vocab[];
  sentences: string[];
}

export interface Day {
  date: string;
  dayNo: number;
  episodes: Episode[]; // a day can have several posts
  post?: Post; // first episode, for single-title displays
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

const pad = (n: number) => String(n).padStart(2, '0');

// "EBS 라디오 입이 트이는 영어 - 10.6 Choosing a Pillow" → aired "2026-10-06", title "Choosing a Pillow".
// The title only carries month.day, so the year comes from the study date
// (an episode in a later month than the study date belongs to the previous year).
function parsePost(title: string, link: string, date: string): Post {
  const rest = title.replace(/^.*입이 트이는 영어\s*-\s*/, '').trim();
  const m = rest.match(/^(\d{1,2})\.(\d{1,2})\s+(.*)$/);
  let aired = '';
  if (m) {
    const [y, mo] = date.split('-').map(Number);
    const em = Number(m[1]);
    aired = `${em > mo ? y - 1 : y}-${pad(em)}-${pad(Number(m[2]))}`;
  }
  return { title: m ? m[3] : rest, aired, link: link.replace(/\?.*$/, '') };
}

let cache: Day[] | undefined;

// Newest first.
export function getDays(): Day[] {
  if (cache) return cache;
  const files = fs.existsSync(HISTORY)
    ? fs.readdirSync(HISTORY).filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort()
    : [];
  cache = files
    .map((f, i) => {
      const raw = JSON.parse(fs.readFileSync(path.join(HISTORY, f), 'utf-8'));
      const date = f.replace('.json', '');
      const study = raw.today_study ?? {};
      // 'deltas' lists every post filed under this date; older archives only have today_delta
      // (and may carry one from a previous day, which is skipped).
      const deltas: any[] = raw.deltas ?? (raw.today_delta?.date === date ? [raw.today_delta] : []);
      const episodes: Episode[] = deltas
        .filter((d) => d?.title)
        .map((d) => ({
          post: parsePost(d.title, d.link ?? '', date),
          vocab: lines(d.vocab).filter((l) => l.includes(':')).map(parseVocab),
          sentences: lines(d.sentences),
        }));
      return {
        date,
        dayNo: i + 1,
        episodes,
        post: episodes[0]?.post,
        newVocab: episodes.flatMap((e) => e.vocab),
        newSentences: episodes.flatMap((e) => e.sentences),
        reviewVocab: (study.vocab ?? []).map((v: string) => parseVocab(String(v))),
        reviewSentences: (study.sentences ?? []).map((s: string) => String(s).trim()).filter(Boolean),
      } satisfies Day;
    })
    .reverse();
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

// Split a sentence into plain / matched segments for the given vocab terms.
export function markTerms(sentence: string, terms: string[]): { text: string; mark: boolean }[] {
  const pats = terms
    .map((t) => t.replace(/\(.*?\)|~/g, '').replace(/\bone's\b/gi, '').trim())
    .filter((t) => t.length >= 3)
    .sort((a, b) => b.length - a.length)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+'));
  if (!pats.length) return [{ text: sentence, mark: false }];
  const re = new RegExp(`\\b(${pats.join('|')})\\b`, 'gi');
  const out: { text: string; mark: boolean }[] = [];
  let last = 0;
  for (const m of sentence.matchAll(re)) {
    if (m.index! > last) out.push({ text: sentence.slice(last, m.index), mark: false });
    out.push({ text: m[0], mark: true });
    last = m.index! + m[0].length;
  }
  if (last < sentence.length) out.push({ text: sentence.slice(last), mark: false });
  return out;
}

// Days grouped by "YYYY-MM", newest month first.
export function getMonths(): { key: string; year: number; month: number; days: Day[] }[] {
  const map = new Map<string, Day[]>();
  for (const d of getDays()) {
    const key = d.date.slice(0, 7);
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(d);
  }
  return [...map].map(([key, days]) => ({ key, year: Number(key.slice(0, 4)), month: Number(key.slice(5)), days }));
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const WEEKDAYS_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function ymd(date: string) {
  const [y, m, d] = date.split('-').map(Number);
  return { y, m, d, wd: new Date(Date.UTC(y, m - 1, d)).getUTCDay() };
}

// "Wed, Oct 14, 2026" — or long: "Wednesday, October 14, 2026"
export function formatDate(date: string, style: 'short' | 'long' | 'plain' = 'short'): string {
  if (!date) return '';
  const { y, m, d, wd } = ymd(date);
  if (style === 'long') return `${WEEKDAYS_LONG[wd]}, ${MONTHS_LONG[m - 1]} ${d}, ${y}`;
  if (style === 'plain') return `${MONTHS[m - 1]} ${d}, ${y}`;
  return `${WEEKDAYS[wd]}, ${MONTHS[m - 1]} ${d}, ${y}`;
}

export const plural = (n: number, word: string) => `${n.toLocaleString()} ${n === 1 ? word : word + 's'}`;

export interface SourceEntry extends Episode {
  date: string; // study day it was filed under
}

// Every episode grouped by broadcast month ("YYYY-MM"), newest first.
export function getSourceMonths(): { key: string; year: number; month: number; entries: SourceEntry[] }[] {
  const all: SourceEntry[] = getDays().flatMap((d) => d.episodes.map((e) => ({ ...e, date: d.date })));
  all.sort((a, b) => (b.post.aired || b.date).localeCompare(a.post.aired || a.date));
  const map = new Map<string, SourceEntry[]>();
  for (const e of all) {
    const key = (e.post.aired || e.date).slice(0, 7);
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(e);
  }
  return [...map]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([key, entries]) => ({ key, year: Number(key.slice(0, 4)), month: Number(key.slice(5)), entries }));
}

// First letter bucket for the A–Z navigator ("#" for anything else).
export function letterOf(s: string): string {
  const c = s.trim().charAt(0).toUpperCase();
  return c >= 'A' && c <= 'Z' ? c : '#';
}

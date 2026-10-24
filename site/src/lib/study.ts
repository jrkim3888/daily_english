// Client-side study interactions: flashcards, known marks, speech, blank quiz.
const store = {
  get(key: string): string[] {
    try { return JSON.parse(localStorage.getItem(key) ?? '[]'); } catch { return []; }
  },
  set(key: string, val: string[]) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch { /* private mode */ }
  },
};

function speak(text: string) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-US';
  u.rate = 0.92;
  const voice = speechSynthesis.getVoices().find((v) => v.lang === 'en-US' && /Samantha|Google|Natural/i.test(v.name));
  if (voice) u.voice = voice;
  speechSynthesis.speak(u);
}

document.querySelectorAll<HTMLElement>('[data-deck]').forEach((deck) => {
  const key = `known:${deck.dataset.deck}`;
  const cards = [...deck.querySelectorAll<HTMLElement>('.fc')];
  const count = deck.querySelector('[data-known-count]');
  const bar = deck.querySelector<HTMLElement>('[data-known-bar]');
  let known = new Set(store.get(key));

  const render = () => {
    cards.forEach((c) => {
      const on = known.has(c.dataset.term!);
      c.classList.toggle('known', on);
      c.querySelector('[data-action="known"]')?.setAttribute('aria-pressed', String(on));
    });
    const n = cards.filter((c) => known.has(c.dataset.term!)).length;
    if (count) count.textContent = String(n);
    if (bar) bar.style.width = `${cards.length ? (n / cards.length) * 100 : 0}%`;
  };

  const setFilter = (tag: string) => {
    cards.forEach((c) => (c.hidden = !!tag && c.dataset.tag !== tag));
    deck.querySelectorAll('[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String((b as HTMLElement).dataset.filter === tag)));
  };
  deck.querySelectorAll<HTMLElement>('[data-filter]').forEach((b) => b.addEventListener('click', () => setFilter(b.dataset.filter!)));
  // Stat tiles on the same page link here with a preset filter.
  document.querySelectorAll<HTMLElement>('a[href="#flashcards"]').forEach((a) =>
    a.addEventListener('click', () => setFilter(a.dataset.deckFilter ?? '')),
  );

  deck.addEventListener('click', (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>('[data-action]');
    if (!btn) return;
    const card = btn.closest<HTMLElement>('.fc');
    switch (btn.dataset.action) {
      case 'flip':
        card?.classList.toggle('flipped');
        break;
      case 'open-list':
        deck.querySelector<HTMLDialogElement>('[data-wordlist]')?.showModal();
        break;
      case 'close-list':
        btn.closest('dialog')?.close();
        break;
      case 'known': {
        const t = card!.dataset.term!;
        known.has(t) ? known.delete(t) : known.add(t);
        store.set(key, [...known]);
        render();
        break;
      }
      case 'flip-all': {
        const anyFront = cards.some((c) => !c.classList.contains('flipped'));
        cards.forEach((c) => c.classList.toggle('flipped', anyFront));
        break;
      }
      case 'shuffle': {
        const list = cards[0]?.parentElement;
        if (!list) return;
        cards.sort(() => Math.random() - 0.5).forEach((c, i) => {
          c.classList.remove('flipped');
          c.style.setProperty('--i', String(i));
          c.style.animation = 'none';
          void c.offsetWidth;
          c.style.animation = '';
          list.appendChild(c);
        });
        break;
      }
    }
  });
  const dialog = deck.querySelector<HTMLDialogElement>('[data-wordlist]');
  dialog?.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close();
  });
  render();
});

document.addEventListener('click', (e) => {
  const el = e.target as HTMLElement;
  const sp = el.closest<HTMLElement>('[data-action="speak"]');
  if (sp) return speak(sp.dataset.text ?? '');

  const blanks = el.closest<HTMLElement>('[data-action="blanks"]');
  if (blanks) {
    const section = blanks.closest('[data-sentences]')!;
    const on = section.classList.toggle('blanks');
    blanks.setAttribute('aria-pressed', String(on));
    section.querySelectorAll('.hl.revealed').forEach((m) => m.classList.remove('revealed'));
    return;
  }

  const hl = el.closest('.blanks .hl');
  if (hl) hl.classList.toggle('revealed');
});

// Client-side search for the vocab / sentence lists.
const input = document.querySelector<HTMLInputElement>('[data-filter]');
const count = document.querySelector<HTMLElement>('.count');

if (input) {
  const items = [...document.querySelectorAll<HTMLElement>(input.dataset.filter!)];
  const groups = [...document.querySelectorAll<HTMLElement>('[data-group]')];
  const text = items.map((el) => el.textContent!.toLowerCase());

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    let shown = 0;
    items.forEach((el, i) => {
      const hit = !q || text[i].includes(q);
      el.hidden = !hit;
      if (hit) shown++;
    });
    groups.forEach((g) => (g.hidden = !g.querySelector('li:not([hidden])')));
    if (count) count.textContent = q ? `${shown.toLocaleString()}개 일치` : '';
  });
}

(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Shared number tween (also used by dashboard-live.js)
  window.animateNumber = (el, to, delay = 0) => {
    if (!el || isNaN(to)) return;
    if (el.dataset.val !== undefined && +el.dataset.val === to) return;
    const from = +el.dataset.val || 0, first = el.dataset.val === undefined;
    el.dataset.val = to;
    if (reduce) { el.textContent = to.toLocaleString(); return; }
    cancelAnimationFrame(el._raf);
    const t0 = performance.now() + delay, dur = first ? 1400 : 900;
    const tick = n => {
      const p = Math.min(Math.max((n - t0) / dur, 0), 1), e = 1 - Math.pow(1 - p, 4);
      el.textContent = Math.round(from + (to - from) * e).toLocaleString();
      if (p < 1) el._raf = requestAnimationFrame(tick);
    };
    el._raf = requestAnimationFrame(tick);
    if (!first) { el.classList.remove('bump'); void el.offsetWidth; el.classList.add('bump'); }
  };

  // Staggered blur-in reveal
  const targets = $$('main > h1, main > p, main > .actions, .kpi-card, main .card, .two-col > *, .login-box');
  targets.forEach((el, i) => { el.classList.add('reveal'); el.style.setProperty('--i', Math.min(i, 10)); });
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: .06 });
  targets.forEach(t => io.observe(t));

  // KPI count-up on first paint
  $$('.kpi-card .value').forEach(el => {
    const n = parseFloat(el.textContent.replace(/,/g, ''));
    if (!isNaN(n)) { el.textContent = '0'; window.animateNumber(el, n, 250); }
  });

  // Static tables cascade (live telemetry body is animated by dashboard-live.js)
  $$('tbody:not(#latest-telemetry-body)').forEach(tb => $$('tr', tb).slice(0, 25).forEach((tr, i) => {
    tr.classList.add('row-in'); tr.style.setProperty('--r', i);
  }));

  // Cursor spotlight
  document.addEventListener('pointermove', e => {
    const c = e.target.closest?.('.card,.kpi-card'); if (!c) return;
    const r = c.getBoundingClientRect();
    c.style.setProperty('--mx', `${e.clientX - r.left}px`); c.style.setProperty('--my', `${e.clientY - r.top}px`);
  });

  // Sliding nav pill
  const nav = document.querySelector('.nav-links');
  if (nav) {
    const pill = Object.assign(document.createElement('span'), { className: 'nav-pill' });
    nav.prepend(pill);
    const move = a => { if (!a) return pill.style.opacity = 0; pill.style.opacity = 1;
      pill.style.width = a.offsetWidth + 'px'; pill.style.transform = `translateX(${a.offsetLeft}px)`; };
    const active = nav.querySelector('a.active');
    requestAnimationFrame(() => move(active));
    document.fonts?.ready.then(() => move(active));
    nav.addEventListener('pointerover', e => { const a = e.target.closest('a'); if (a) move(a); });
    nav.addEventListener('pointerleave', () => move(active));
  }

  // Button ripple
  document.addEventListener('click', e => {
    const b = e.target.closest('.btn,.btn-sm,button[type=submit]'); if (!b || reduce) return;
    const r = b.getBoundingClientRect(), s = Math.max(r.width, r.height) / 4;
    const d = Object.assign(document.createElement('span'), { className: 'ripple' });
    d.style.cssText = `width:${s}px;height:${s}px;left:${e.clientX - r.left - s / 2}px;top:${e.clientY - r.top - s / 2}px`;
    b.appendChild(d); setTimeout(() => d.remove(), 650);
  });

  // Toasts
  $$('.flash').forEach((f, i) => setTimeout(() => { f.classList.add('out'); setTimeout(() => f.remove(), 450); }, 4500 + i * 400));

  // Command palette (Ctrl/Cmd+K) built from the nav links
  const ov = document.getElementById('palov'); if (!ov) return;
  const q = ov.querySelector('input'), list = ov.querySelector('div');
  const items = $$('.nav-links a').map(a => ({ t: a.textContent.trim(), h: a.href }));
  let idx = 0, shown = items;
  const paint = () => {
    shown = items.filter(i => i.t.toLowerCase().includes(q.value.toLowerCase()));
    idx = Math.min(idx, Math.max(shown.length - 1, 0));
    list.innerHTML = shown.map((i, n) => `<a href="${i.h}" class="${n === idx ? 'on' : ''}">${i.t}</a>`).join('') || '<a>No results</a>';
  };
  const open = o => { ov.classList.toggle('on', o); if (o) { q.value = ''; idx = 0; paint(); setTimeout(() => q.focus(), 40); } };
  document.getElementById('kb')?.addEventListener('click', () => open(true));
  ov.addEventListener('click', e => { if (e.target === ov) open(false); });
  q.addEventListener('input', () => { idx = 0; paint(); });
  addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(true); }
    if (!ov.classList.contains('on')) return;
    if (e.key === 'Escape') open(false);
    if (e.key === 'ArrowDown') { idx = Math.min(idx + 1, shown.length - 1); paint(); }
    if (e.key === 'ArrowUp') { idx = Math.max(idx - 1, 0); paint(); }
    if (e.key === 'Enter' && shown[idx]) location.href = shown[idx].h;
  });
})();

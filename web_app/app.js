/* Apex Words — Mini App o'yin mantig'i.

   Asosiy oqim:
     1. data/index.json dan bosqichlar ro'yxati o'qiladi
     2. data/stage_NN.json dan puzzle'lar yuklanadi
     3. O'yinchi g'ildirakdagi harflarni tortib so'z yasaydi
     4. So'z yechimlar ro'yxatida bo'lsa -> to'rga tushadi
        Ro'yxatda yo'q, lekin bonus ro'yxatida bo'lsa -> +1 ochko
     5. Progress /api/state orqali serverga saqlanadi (bo'lmasa localStorage)

   Bonus so'zlar oldindan generatsiya qilingani uchun tekshiruv brauzerda
   ketadi — server so'rovi kerak emas, o'yin darhol javob beradi. */

'use strict';

const TG = window.Telegram && window.Telegram.WebApp;

/* ------------------------------ Yordamchilar ------------------------------ */

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

function haptic(type) {
  try {
    const h = TG && TG.HapticFeedback;
    if (!h) return;
    if (type === 'ok') h.notificationOccurred('success');
    else if (type === 'err') h.notificationOccurred('error');
    else h.impactOccurred('light');
  } catch (_) {}
}

/* --------------------------------- Holat ---------------------------------- */

const State = {
  index: null,          // bosqichlar ro'yxati
  stages: {},           // yuklangan bosqich fayllari keshi
  dict: {},             // SO'Z -> o'zbekcha tarjima
  progress: null,       // o'yinchi progressi
  puzzle: null,         // hozirgi puzzle
  found: new Set(),     // shu puzzle'da topilgan yechim so'zlari
  foundBonus: new Set() // shu puzzle'da topilgan bonus so'zlari
};

const HINT_COST = 5;
const START_COINS = 50;

function blankProgress() {
  return { coins: START_COINS, cur: { stage: 1, level: 1, puzzle: 0 }, solved: {}, learned: {} };
}

/* ------------------------------- Saqlash ---------------------------------- */

const Store = {
  online: true,
  timer: null,

  async load() {
    if (TG && TG.initData) {
      try {
        const r = await fetch('/api/state', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initData: TG.initData })
        });
        if (r.ok) {
          const d = await r.json();
          if (d && d.progress) return d.progress;
          return blankProgress();
        }
      } catch (_) {}
    }
    this.online = false;
    try {
      const raw = localStorage.getItem('apexwords');
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    return blankProgress();
  },

  // Har harakatdan keyin emas, 1.2 soniyada bir marta saqlaymiz.
  save() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this._flush(), 1200);
  },

  async _flush() {
    const p = State.progress;
    try { localStorage.setItem('apexwords', JSON.stringify(p)); } catch (_) {}
    if (!this.online || !(TG && TG.initData)) return;
    try {
      await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData: TG.initData, progress: p })
      });
    } catch (_) { this.online = false; }
  }
};

/* ------------------------ Ma'lumotlarni yuklash --------------------------- */

async function loadIndex() {
  const r = await fetch('data/index.json');
  State.index = await r.json();
}

async function loadDict() {
  try {
    const r = await fetch('data/dict.json');
    if (r.ok) State.dict = await r.json();
  } catch (_) { State.dict = {}; }
}

async function loadStage(n) {
  if (State.stages[n]) return State.stages[n];
  const info = State.index.stages.find((s) => s.stage === n);
  const r = await fetch('data/' + info.file);
  State.stages[n] = await r.json();
  return State.stages[n];
}

function levelKey(stage, level) { return stage + '-' + level; }

function levelInfo(stage, level) {
  const s = State.index.stages.find((x) => x.stage === stage);
  return s && s.levels.find((l) => l.level === level);
}

/* Daraja ochilganmi? Birinchisi doim ochiq; qolgani oldingisi tugagach ochiladi. */
function isUnlocked(stage, level) {
  if (stage === 1 && level === 1) return true;
  let ps = stage, pl = level - 1;
  if (pl < 1) { ps = stage - 1; pl = 5; }
  const info = levelInfo(ps, pl);
  if (!info) return true;
  return (State.progress.solved[levelKey(ps, pl)] || 0) >= info.puzzles;
}

/* ------------------------------ Puzzle ochish ----------------------------- */

async function openPuzzle(stage, level, idx) {
  const data = await loadStage(stage);
  const lvl = data.levels.find((l) => l.level === level);
  if (!lvl) return;

  if (idx >= lvl.puzzles.length) { finishLevel(stage, level); return; }

  State.puzzle = lvl.puzzles[idx];
  State.found = new Set();
  State.foundBonus = new Set();
  State.progress.cur = { stage, level, puzzle: idx };

  $('level-title').textContent = lvl.name + ' · ' + (idx + 1) + '/' + lvl.puzzles.length;
  renderGrid();
  renderWheel();
  updateCoins();
  updateBookCount();
  Store.save();
}

/* --------------------------------- To'r ----------------------------------- */

function renderGrid() {
  const grid = $('grid');
  grid.innerHTML = '';
  State.puzzle.words.forEach((w) => {
    const g = el('div', 'word-group');
    g.dataset.word = w;
    for (const ch of w) {
      const c = el('div', 'cell');
      c.dataset.ch = ch;
      g.appendChild(c);
    }
    grid.appendChild(g);
  });
}

function fillWord(word) {
  const g = $('grid').querySelector('.word-group[data-word="' + word + '"]');
  if (!g) return;
  [...g.children].forEach((c, i) => {
    setTimeout(() => {
      c.classList.remove('hinted');
      c.classList.add('filled');
      c.textContent = c.dataset.ch;
    }, i * 55);
  });
}

/* ------------------------------ G'ildirak --------------------------------- */

let letterEls = [];
let centers = [];

function renderWheel() {
  const box = $('letters');
  box.innerHTML = '';
  letterEls = [];

  const letters = State.puzzle.letters.split('');
  const n = letters.length;

  letters.forEach((ch, i) => {
    const b = el('div', 'letter', ch);
    b.dataset.i = i;
    // Doira bo'ylab teng oraliqda, birinchi harf tepada
    const ang = (-Math.PI / 2) + (i * 2 * Math.PI / n);
    b.style.left = (50 + 37 * Math.cos(ang)) + '%';
    b.style.top = (50 + 37 * Math.sin(ang)) + '%';
    box.appendChild(b);
    letterEls.push(b);
  });

  // measure() ni DARHOL chaqiramiz: getBoundingClientRect layout'ni majburlaydi,
  // shuning uchun o'lchamlar shu yerda tayyor bo'ladi. requestAnimationFrame
  // yolg'iz yetmaydi — sahifa ko'rinmayotgan bo'lsa (fondagi tab, Telegram hali
  // oynani ko'rsatmagan payt) rAF umuman ishga tushmaydi va g'ildirak
  // o'lchanmay qoladi: barmoq tortilganda hech qanday harf ushlanmaydi.
  measure();
  requestAnimationFrame(measure);   // shrift/animatsiya joylashgach aniqlashtirish
}

function measure() {
  const wheel = $('wheel');
  const wr = wheel.getBoundingClientRect();
  if (!wr.width || !letterEls.length) return;   // hali joylashmagan
  centers = letterEls.map((b) => {
    const r = b.getBoundingClientRect();
    return { x: r.left - wr.left + r.width / 2, y: r.top - wr.top + r.height / 2, r: r.width / 2 };
  });

  const cv = $('line');
  const dpr = window.devicePixelRatio || 1;
  cv.width = wr.width * dpr;
  cv.height = wr.height * dpr;
  cv.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
  drawLine();
}

window.addEventListener('resize', () => { if (State.puzzle) measure(); });

// Telegram oynani ochganda balandlik animatsiya bilan o'zgaradi — 'resize'
// hodisasi har doim ham kelmaydi, shuning uchun konteynerni kuzatamiz.
if (window.ResizeObserver) {
  new ResizeObserver(() => { if (State.puzzle) measure(); }).observe(document.getElementById('wheel'));
}

/* --------------------------- Tortish (drag) ------------------------------- */

let path = [];          // tanlangan harf indekslari
let dragging = false;
let ptr = null;         // sichqoncha/barmoq joylashuvi

function localPoint(e) {
  const wr = $('wheel').getBoundingClientRect();
  return { x: e.clientX - wr.left, y: e.clientY - wr.top };
}

function hitTest(p) {
  for (let i = 0; i < centers.length; i++) {
    const c = centers[i];
    const dx = p.x - c.x, dy = p.y - c.y;
    if (dx * dx + dy * dy <= (c.r * 1.15) ** 2) return i;
  }
  return -1;
}

function onDown(e) {
  if (!State.puzzle) return;
  if (!centers.length) measure();       // oxirgi himoya: o'lchanmagan bo'lsa hozir o'lchaymiz
  const p = localPoint(e);
  const i = hitTest(p);
  if (i < 0) return;
  e.preventDefault();
  dragging = true;
  ptr = p;
  path = [i];
  letterEls[i].classList.add('active');
  haptic('tap');
  updateCurrent();
  drawLine();
}

function onMove(e) {
  if (!dragging) return;
  e.preventDefault();
  ptr = localPoint(e);
  const i = hitTest(ptr);

  if (i >= 0) {
    const back = path.length >= 2 && i === path[path.length - 2];
    if (back) {
      // Orqaga qaytish — oxirgi harfni olib tashlaymiz
      const last = path.pop();
      letterEls[last].classList.remove('active');
      haptic('tap');
      updateCurrent();
    } else if (!path.includes(i)) {
      path.push(i);
      letterEls[i].classList.add('active');
      haptic('tap');
      updateCurrent();
    }
  }
  drawLine();
}

function onUp() {
  if (!dragging) return;
  dragging = false;
  const word = path.map((i) => State.puzzle.letters[i]).join('');
  clearPath();
  if (word.length >= 3) submit(word);
  else showCurrent('', null);
}

function clearPath() {
  path.forEach((i) => letterEls[i].classList.remove('active'));
  path = [];
  ptr = null;
  drawLine();
}

function updateCurrent() {
  showCurrent(path.map((i) => State.puzzle.letters[i]).join(''), null);
}

function showCurrent(text, cls) {
  const s = $('current-word').firstElementChild;
  s.textContent = text;
  s.className = cls || '';
}

function drawLine() {
  const cv = $('line');
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (path.length === 0) return;

  ctx.strokeStyle = getComputedStyle(document.documentElement)
    .getPropertyValue('--line').trim() || '#ff5722';
  ctx.lineWidth = 9;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.globalAlpha = 0.9;

  ctx.beginPath();
  ctx.moveTo(centers[path[0]].x, centers[path[0]].y);
  for (let k = 1; k < path.length; k++) ctx.lineTo(centers[path[k]].x, centers[path[k]].y);
  if (dragging && ptr) ctx.lineTo(ptr.x, ptr.y);
  ctx.stroke();
}

/* ------------------------------ So'zni tekshirish -------------------------- */

function submit(word) {
  const p = State.puzzle;

  if (p.words.includes(word)) {
    if (State.found.has(word)) return showCurrent(word, 'repeat');
    State.found.add(word);
    fillWord(word);
    addCoins(3);
    learn(word);
    haptic('ok');
    showCurrent(word, 'hit');
    toast(word, false);
    setTimeout(() => showCurrent('', null), 700);
    if (State.found.size === p.words.length) setTimeout(puzzleSolved, 900);
    return;
  }

  if (p.bonus.includes(word)) {
    if (State.foundBonus.has(word)) return showCurrent(word, 'repeat');
    State.foundBonus.add(word);
    addCoins(1);
    learn(word);
    updateBookCount();
    haptic('ok');
    showCurrent(word, 'hit');
    toast(word, true);
    setTimeout(() => showCurrent('', null), 700);
    return;
  }

  haptic('err');
  showCurrent(word, 'miss');
  setTimeout(() => showCurrent('', null), 500);
}

function learn(word) {
  State.progress.learned[word] = (State.progress.learned[word] || 0) + 1;
}

function addCoins(n) {
  State.progress.coins += n;
  updateCoins();
  Store.save();
}

function updateCoins() { $('coin-count').textContent = State.progress.coins; }

function updateBookCount() {
  const n = State.foundBonus.size;
  $('book-count').textContent = n;
  $('btn-book').style.opacity = State.puzzle && State.puzzle.bonus.length ? 1 : .45;
}

function toast(word, isBonus) {
  const t = $('toast');
  $('toast-word').textContent = word;
  const uz = State.dict[word];
  $('toast-uz').textContent = isBonus
    ? (uz ? uz + '  ·  +1 bonus' : '+1 bonus so\'z')
    : (uz || '');
  t.classList.toggle('bonus', !!isBonus);
  t.hidden = false;
  requestAnimationFrame(() => t.classList.add('show'));
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => { t.hidden = true; }, 200);
  }, 1500);
}

/* -------------------------- Puzzle / daraja tugashi ------------------------ */

function puzzleSolved() {
  const { stage, level, puzzle } = State.progress.cur;
  const key = levelKey(stage, level);
  State.progress.solved[key] = Math.max(State.progress.solved[key] || 0, puzzle + 1);
  addCoins(5);

  const info = levelInfo(stage, level);
  if (puzzle + 1 >= info.puzzles) finishLevel(stage, level);
  else openPuzzle(stage, level, puzzle + 1);
}

function finishLevel(stage, level) {
  const next = level < 5 ? { stage, level: level + 1 } : { stage: stage + 1, level: 1 };
  const hasNext = !!levelInfo(next.stage, next.level);

  $('done-title').textContent = 'Daraja tugadi!';
  $('done-sub').textContent = hasNext
    ? 'Keyingi daraja ochildi.'
    : 'Barcha mavjud darajalar tugadi. Yangi bosqichlar tez orada!';
  $('btn-next').textContent = hasNext ? 'Davom etish' : 'Menyu';
  $('done-overlay').hidden = false;

  $('btn-next').onclick = () => {
    $('done-overlay').hidden = true;
    if (hasNext) openPuzzle(next.stage, next.level, 0);
    else openMenu();
  };
  Store.save();
}

/* -------------------------------- Maslahat -------------------------------- */

function useHint() {
  if (!State.puzzle) return;
  if (State.progress.coins < HINT_COST) {
    showCurrent('Ochko yetarli emas', 'miss');
    setTimeout(() => showCurrent('', null), 900);
    haptic('err');
    return;
  }
  // Topilmagan so'zning ochilmagan birinchi katagini ochamiz
  const groups = [...$('grid').children]
    .filter((g) => !State.found.has(g.dataset.word));
  for (const g of groups) {
    const cell = [...g.children].find((c) => !c.classList.contains('filled') &&
                                             !c.classList.contains('hinted'));
    if (cell) {
      cell.classList.add('hinted');
      cell.textContent = cell.dataset.ch;
      addCoins(-HINT_COST);
      haptic('tap');
      return;
    }
  }
}

/* --------------------------------- Menyu ---------------------------------- */

function openMenu() {
  const body = $('menu-body');
  body.innerHTML = '';

  State.index.stages.forEach((s) => {
    const block = el('div', 'stage-block');
    block.appendChild(el('h3', null, s.stage + '-BOSQICH · ' + s.name));

    s.levels.forEach((l) => {
      const done = State.progress.solved[levelKey(s.stage, l.level)] || 0;
      const unlocked = isUnlocked(s.stage, l.level);

      const row = el('button', 'level-row' + (unlocked ? '' : ' locked'));
      row.appendChild(el('span', null, (unlocked ? '' : '🔒 ') + l.name));

      const bar = el('div', 'bar');
      const fill = el('i');
      fill.style.width = Math.round(100 * done / l.puzzles) + '%';
      bar.appendChild(fill);
      row.appendChild(bar);
      row.appendChild(el('span', 'num', done + '/' + l.puzzles));

      if (unlocked) {
        row.onclick = () => {
          $('menu-overlay').hidden = true;
          openPuzzle(s.stage, l.level, done >= l.puzzles ? 0 : done);
        };
      }
      block.appendChild(row);
    });
    body.appendChild(block);
  });

  $('menu-overlay').hidden = false;
}

function openBook() {
  const body = $('book-body');
  body.innerHTML = '';
  const words = [...State.foundBonus].sort();
  if (!words.length) {
    body.appendChild(el('div', 'book-empty',
      'Hali qo\'shimcha so\'z topilmadi.\nRo\'yxatda yo\'q, lekin haqiqiy ingliz so\'zini toping — har biri +1 ochko.'));
  } else {
    words.forEach((w) => {
      const row = el('div', 'book-word');
      row.appendChild(el('b', null, w));
      row.appendChild(el('span', null, State.dict[w] || ''));
      body.appendChild(row);
    });
  }
  $('book-overlay').hidden = false;
}

/* ------------------------------ Ishga tushirish ---------------------------- */

async function boot() {
  if (TG) {
    TG.ready();
    TG.expand();
    try { TG.setHeaderColor('#4b1d14'); TG.setBackgroundColor('#4b1d14'); } catch (_) {}
    try { TG.disableVerticalSwipes(); } catch (_) {}
  }

  await Promise.all([loadIndex(), loadDict()]);
  State.progress = await Store.load();

  const wheel = $('wheel');
  wheel.addEventListener('pointerdown', onDown);
  window.addEventListener('pointermove', onMove, { passive: false });
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onUp);

  $('btn-menu').onclick = openMenu;
  $('btn-book').onclick = openBook;
  $('btn-hint').onclick = useHint;
  $('hint-price').textContent = HINT_COST;
  $('btn-shuffle').onclick = () => {
    const l = State.puzzle.letters.split('');
    for (let i = l.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [l[i], l[j]] = [l[j], l[i]];
    }
    State.puzzle.letters = l.join('');
    renderWheel();
    haptic('tap');
  };

  document.querySelectorAll('[data-close]').forEach((b) => {
    b.onclick = () => { $(b.dataset.close).hidden = true; };
  });

  const c = State.progress.cur;
  await openPuzzle(c.stage || 1, c.level || 1, c.puzzle || 0);
}

boot().catch((e) => {
  document.getElementById('level-title').textContent = 'Xato: ' + e.message;
  console.error(e);
});

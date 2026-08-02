/* Apex Words — Mini App.

   Ikki ekran:
     #map-screen   — kirganda birinchi shu ochiladi: darajalar xaritasi.
                     Tugunlar ilon izi yo'l bo'ylab pastdan yuqoriga joylashadi,
                     ro'yxat qo'l bilan tortib aylantiriladi.
     #game-screen   — daraja tanlangach ochiladi: harflar g'ildiragi va to'r.

   Tarjima DARHOL ko'rsatilmaydi. Topilgan har so'z yonida lampa (💡) chiqadi;
   o'yinchi uni bosgandagina tarjima bir necha soniyaga ko'rinadi. Shunda o'yinchi
   avval o'zi eslashga urinadi. */

'use strict';

const TG = window.Telegram && window.Telegram.WebApp;

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
  index: null,
  stages: {},
  dict: {},
  progress: null,
  levels: [],           // barcha darajalar tekis ro'yxat sifatida
  puzzle: null,
  found: new Set(),
  foundBonus: new Set()
};

const HINT_COST = 5;
const START_COINS = 50;
const BUBBLE_MS = 3500;      // tarjima necha soniya ko'rinadi

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
          return (d && d.progress) || blankProgress();
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
  State.index = await (await fetch('data/index.json')).json();
  // Barcha darajalarni bitta tekis ro'yxatga yig'amiz — xarita shu bo'yicha quriladi
  State.levels = [];
  State.index.stages.forEach((s) => {
    s.levels.forEach((l) => {
      State.levels.push({
        stage: s.stage, stageName: s.name,
        level: l.level, name: l.name, puzzles: l.puzzles,
        first: l.level === 1
      });
    });
  });
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
  State.stages[n] = await (await fetch('data/' + info.file)).json();
  return State.stages[n];
}

const key = (stage, level) => stage + '-' + level;
const solvedIn = (stage, level) => State.progress.solved[key(stage, level)] || 0;

function isUnlocked(i) {
  if (i === 0) return true;
  const prev = State.levels[i - 1];
  return solvedIn(prev.stage, prev.level) >= prev.puzzles;
}

/* ============================ XARITA EKRANI ============================== */

const NODE_GAP = 132;      // tugunlar orasidagi masofa
const EDGE_PAD = 118;      // pastki va yuqori bo'sh joy

function renderMap() {
  const scroll = $('map-scroll');
  const inner = $('map-inner');
  const nodes = $('map-nodes');
  const svg = $('map-path');

  const n = State.levels.length;
  // Ekran hali joylashmagan bo'lsa clientWidth 0 bo'ladi va hamma tugun bitta
  // nuqtaga (x=0) yig'ilib qolardi. Oxirgi chora sifatida 360px olamiz,
  // haqiqiy o'lcham kelganda ResizeObserver xaritani qayta chizadi.
  const w = scroll.clientWidth || window.innerWidth || 360;
  const h = EDGE_PAD * 2 + (n - 1) * NODE_GAP;
  inner.style.height = h + 'px';
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  // 1-daraja PASTDA, keyingilari yuqoriga qarab ketadi
  const pts = State.levels.map((_, i) => ({
    x: w / 2 + Math.sin(i * 0.95) * Math.min(w * 0.27, 110),
    y: h - EDGE_PAD - i * NODE_GAP
  }));

  // Tugunlarni tutashtiruvchi uzuq chiziq
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i];
    const my = (a.y + b.y) / 2;
    d += ` C ${a.x} ${my}, ${b.x} ${my}, ${b.x} ${b.y}`;
  }
  svg.innerHTML =
    `<path d="${d}" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="6"
           stroke-linecap="round" stroke-dasharray="2 18"/>`;

  nodes.innerHTML = '';
  let curIndex = 0;

  State.levels.forEach((lv, i) => {
    const done = solvedIn(lv.stage, lv.level);
    const unlocked = isUnlocked(i);
    const complete = done >= lv.puzzles;
    if (unlocked && !complete && !curIndex) curIndex = i;

    // Bosqich nomi — har bosqichning birinchi darajasi tepasida
    if (lv.first) {
      const b = el('div', 'stage-banner', lv.stage + '-BOSQICH · ' + lv.stageName);
      b.style.top = (pts[i].y - NODE_GAP * 0.58) + 'px';
      nodes.appendChild(b);
    }

    const btn = el('button', 'node ' + (complete ? 'done' : unlocked ? 'current' : 'locked'));
    btn.style.left = pts[i].x + 'px';
    btn.style.top = pts[i].y + 'px';

    // Yechilgan puzzle ulushini halqa bilan ko'rsatamiz
    if (unlocked && done > 0 && !complete) {
      const R = 32, C = 2 * Math.PI * R;
      btn.insertAdjacentHTML('beforeend',
        `<svg class="ring" viewBox="0 0 ${R * 2 + 8} ${R * 2 + 8}">
           <circle class="bg" cx="${R + 4}" cy="${R + 4}" r="${R}"/>
           <circle class="fg" cx="${R + 4}" cy="${R + 4}" r="${R}"
                   stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - done / lv.puzzles)}"/>
         </svg>`);
    }

    if (complete) {
      const st = el('div', 'stars');
      const got = starsFor(done, lv.puzzles);
      for (let k = 0; k < 3; k++) st.appendChild(el('i', k < got ? 'on' : '', '★'));
      btn.appendChild(st);
    }

    btn.appendChild(el('span', 'num', String(i + 1)));
    btn.appendChild(el('span', 'name', lv.name));

    if (unlocked) {
      btn.onclick = () => {
        haptic('tap');
        openLevel(i);
      };
    }
    nodes.appendChild(btn);
  });

  $('map-coins').textContent = State.progress.coins;

  // Hozirgi darajani ko'rinadigan joyga surib qo'yamiz
  const centerOn = () => {
    const vh = scroll.clientHeight || window.innerHeight || 640;
    scroll.scrollTop = Math.max(0, pts[curIndex].y - vh * 0.55);
  };
  centerOn();
  requestAnimationFrame(centerOn);
}

/* Telegram oynasi ochilganda balandlik/kenglik animatsiya bilan o'zgaradi.
   'resize' hodisasi har doim ham kelmaydi, shuning uchun konteynerni kuzatamiz:
   o'lcham o'zgarsa xarita qayta chiziladi (aks holda tugunlar joyida qolmaydi). */
let mapW = 0, mapH = 0;
function watchMapSize() {
  const scroll = $('map-scroll');
  if (!window.ResizeObserver) return;
  new ResizeObserver(() => {
    if (!$('map-screen').classList.contains('active')) return;
    const w = scroll.clientWidth, h = scroll.clientHeight;
    if (w === mapW && h === mapH) return;      // haqiqiy o'zgarish bo'lsagina
    mapW = w; mapH = h;
    renderMap();
  }).observe(scroll);
}

function starsFor(done, total) {
  if (done >= total) return 3;
  if (done >= total * 0.6) return 2;
  return done > 0 ? 1 : 0;
}

function showScreen(id) {
  document.querySelectorAll('.screen').forEach((s) => s.classList.remove('active'));
  $(id).classList.add('active');
}

function openMap() {
  showScreen('map-screen');
  renderMap();
  Store.save();
}

/* ============================= O'YIN EKRANI ============================== */

async function openLevel(i) {
  const lv = State.levels[i];
  const done = solvedIn(lv.stage, lv.level);
  showScreen('game-screen');
  await openPuzzle(lv.stage, lv.level, done >= lv.puzzles ? 0 : done);
}

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
  const cells = [...g.querySelectorAll('.cell')];
  cells.forEach((c, i) => {
    setTimeout(() => {
      c.classList.remove('hinted');
      c.classList.add('filled');
      c.textContent = c.dataset.ch;
    }, i * 55);
  });
  // So'z to'lgach yoniga lampa qo'yamiz — tarjima faqat bosilganda chiqadi
  setTimeout(() => g.appendChild(makeLamp(word)), cells.length * 55 + 80);
}

function makeLamp(word) {
  const b = el('button', 'lamp', '💡');
  b.title = 'Tarjimasi';
  b.onclick = (e) => {
    e.stopPropagation();
    b.classList.add('used');
    showBubble(word, b);
    haptic('tap');
  };
  return b;
}

/* Tarjima pufagi — lampa ustida bir necha soniya turadi */
let bubbleTimer = null;
function showBubble(word, anchor) {
  const bub = $('bubble');
  $('bubble-word').textContent = word;
  $('bubble-uz').textContent = State.dict[word] || 'tarjima topilmadi';

  bub.hidden = false;
  bub.classList.remove('show');

  const r = anchor.getBoundingClientRect();
  // Avval ko'rsatib o'lchaymiz, keyin joylashtiramiz
  bub.style.left = '-9999px';
  bub.style.top = '0px';
  const bw = bub.offsetWidth, bh = bub.offsetHeight;
  let x = r.left + r.width / 2;
  x = Math.min(Math.max(x, bw / 2 + 8), window.innerWidth - bw / 2 - 8);
  bub.style.left = x + 'px';
  bub.style.top = Math.max(8, r.top - bh - 12) + 'px';

  requestAnimationFrame(() => bub.classList.add('show'));
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => {
    bub.classList.remove('show');
    setTimeout(() => { bub.hidden = true; }, 200);
  }, BUBBLE_MS);
}

/* ------------------------------ G'ildirak --------------------------------- */

let letterEls = [];
let centers = [];

function renderWheel() {
  const box = $('letters');
  box.innerHTML = '';
  letterEls = [];

  const letters = State.puzzle.letters.split('');
  letters.forEach((ch, i) => {
    const b = el('div', 'letter', ch);
    const ang = (-Math.PI / 2) + (i * 2 * Math.PI / letters.length);
    b.style.left = (50 + 37 * Math.cos(ang)) + '%';
    b.style.top = (50 + 37 * Math.sin(ang)) + '%';
    box.appendChild(b);
    letterEls.push(b);
  });

  // measure() ni DARHOL chaqiramiz: getBoundingClientRect layout'ni majburlaydi.
  // requestAnimationFrame yolg'iz yetmaydi — sahifa ko'rinmayotgan bo'lsa rAF
  // umuman ishga tushmaydi va g'ildirak o'lchanmay qoladi.
  measure();
  requestAnimationFrame(measure);
}

function measure() {
  const wr = $('wheel').getBoundingClientRect();
  if (!wr.width || !letterEls.length) return;
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

window.addEventListener('resize', () => {
  if (State.puzzle) measure();
  if ($('map-screen').classList.contains('active')) renderMap();
});

/* --------------------------- Tortish (drag) ------------------------------- */

let path = [];
let dragging = false;
let ptr = null;

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
  if (!centers.length) measure();
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
      letterEls[path.pop()].classList.remove('active');
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
  if (!path.length) return;
  ctx.strokeStyle = '#ff4f6f';
  ctx.lineWidth = 9;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.globalAlpha = .92;
  ctx.beginPath();
  ctx.moveTo(centers[path[0]].x, centers[path[0]].y);
  for (let k = 1; k < path.length; k++) ctx.lineTo(centers[path[k]].x, centers[path[k]].y);
  if (dragging && ptr) ctx.lineTo(ptr.x, ptr.y);
  ctx.stroke();
}

/* ---------------------------- So'zni tekshirish ---------------------------- */

function submit(word) {
  const p = State.puzzle;

  if (p.words.includes(word)) {
    if (State.found.has(word)) return flash(word, 'repeat');
    State.found.add(word);
    fillWord(word);
    addCoins(3);
    learn(word);
    haptic('ok');
    flash(word, 'hit', 700);
    if (State.found.size === p.words.length) setTimeout(puzzleSolved, 1100);
    return;
  }

  if (p.bonus.includes(word)) {
    if (State.foundBonus.has(word)) return flash(word, 'repeat');
    State.foundBonus.add(word);
    addCoins(1);
    learn(word);
    updateBookCount();
    haptic('ok');
    flash(word, 'hit', 700);
    toast('+1 bonus · ' + word);
    return;
  }

  haptic('err');
  flash(word, 'miss', 500);
}

function flash(word, cls, ms) {
  showCurrent(word, cls);
  if (ms) setTimeout(() => showCurrent('', null), ms);
}

function learn(word) {
  State.progress.learned[word] = (State.progress.learned[word] || 0) + 1;
}

function addCoins(n) {
  State.progress.coins += n;
  updateCoins();
  Store.save();
}

function updateCoins() {
  $('coin-count').textContent = State.progress.coins;
  $('map-coins').textContent = State.progress.coins;
}

function updateBookCount() {
  $('book-count').textContent = State.foundBonus.size;
  $('btn-book').style.opacity = (State.puzzle && State.puzzle.bonus.length) ? 1 : .5;
}

let toastTimer = null;
function toast(text) {
  const t = $('toast');
  t.textContent = text;
  t.hidden = false;
  requestAnimationFrame(() => t.classList.add('show'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => { t.hidden = true; }, 200);
  }, 1400);
}

/* -------------------------- Puzzle / daraja tugashi ------------------------ */

function puzzleSolved() {
  const { stage, level, puzzle } = State.progress.cur;
  const k = key(stage, level);
  State.progress.solved[k] = Math.max(State.progress.solved[k] || 0, puzzle + 1);
  addCoins(5);

  const lv = State.levels.find((l) => l.stage === stage && l.level === level);
  if (puzzle + 1 >= lv.puzzles) finishLevel(stage, level);
  else openPuzzle(stage, level, puzzle + 1);
}

function finishLevel(stage, level) {
  const i = State.levels.findIndex((l) => l.stage === stage && l.level === level);
  const next = State.levels[i + 1];

  $('done-title').textContent = 'Daraja tugadi!';
  $('done-sub').textContent = next
    ? '"' + next.name + '" darajasi ochildi.'
    : 'Barcha mavjud darajalar tugadi. Yangi bosqichlar tez orada!';
  $('btn-next').textContent = next ? 'Xaritaga qaytish' : 'Xaritaga qaytish';
  $('done-overlay').hidden = false;

  $('btn-next').onclick = () => {
    $('done-overlay').hidden = true;
    openMap();
  };
  Store.save();
}

/* -------------------------------- Maslahat -------------------------------- */

function useHint() {
  if (!State.puzzle) return;
  if (State.progress.coins < HINT_COST) {
    toast('Ochko yetarli emas');
    haptic('err');
    return;
  }
  const groups = [...$('grid').children].filter((g) => !State.found.has(g.dataset.word));
  for (const g of groups) {
    const cell = [...g.querySelectorAll('.cell')]
      .find((c) => !c.classList.contains('filled') && !c.classList.contains('hinted'));
    if (cell) {
      cell.classList.add('hinted');
      cell.textContent = cell.dataset.ch;
      addCoins(-HINT_COST);
      haptic('tap');
      return;
    }
  }
}

/* --------------------------- So'z ro'yxatlari ----------------------------- */

/* Tarjima yashirin turadi, lampa bosilganda ochiladi — grid'dagi bilan bir xil qoida */
function wordRow(word) {
  const row = el('div', 'book-word');
  row.appendChild(el('b', null, word));
  const uz = el('span', 'uz hidden', '• • •');
  row.appendChild(uz);
  const lamp = makeLampFor(word, uz);
  row.appendChild(lamp);
  return row;
}

function makeLampFor(word, uzEl) {
  const b = el('button', 'lamp', '💡');
  b.onclick = () => {
    b.classList.add('used');
    uzEl.classList.remove('hidden');
    uzEl.textContent = State.dict[word] || 'tarjima topilmadi';
    haptic('tap');
  };
  return b;
}

function openBook() {
  const body = $('book-body');
  body.innerHTML = '';
  const words = [...State.foundBonus].sort();
  if (!words.length) {
    body.appendChild(el('div', 'book-empty',
      'Hali qo\'shimcha so\'z topilmadi.\n\nRo\'yxatda yo\'q, lekin haqiqiy ingliz so\'zini toping — har biri +1 ochko.'));
  } else {
    words.forEach((w) => body.appendChild(wordRow(w)));
  }
  $('book-overlay').hidden = false;
}

function openLearned() {
  const body = $('learned-body');
  body.innerHTML = '';
  const words = Object.keys(State.progress.learned || {}).sort();
  if (!words.length) {
    body.appendChild(el('div', 'book-empty',
      'Hali so\'z topilmadi.\n\nO\'ynashni boshlang — topgan har bir so\'zingiz shu yerga yig\'iladi.'));
  } else {
    body.appendChild(el('div', 'book-empty', words.length + ' ta so\'z o\'rgandingiz'));
    words.forEach((w) => body.appendChild(wordRow(w)));
  }
  $('learned-overlay').hidden = false;
}

/* ------------------------------ Ishga tushirish ---------------------------- */

async function boot() {
  if (TG) {
    TG.ready();
    TG.expand();
    try { TG.setHeaderColor('#5fd8ff'); TG.setBackgroundColor('#2f9bf7'); } catch (_) {}
    try { TG.disableVerticalSwipes(); } catch (_) {}
  }

  await Promise.all([loadIndex(), loadDict()]);
  State.progress = await Store.load();

  const wheel = $('wheel');
  wheel.addEventListener('pointerdown', onDown);
  window.addEventListener('pointermove', onMove, { passive: false });
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onUp);

  $('btn-back').onclick = () => { haptic('tap'); openMap(); };
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

  $('tab-learned').onclick = openLearned;
  $('tab-info').onclick = () => { $('info-overlay').hidden = false; };
  $('tab-play').onclick = () => {};

  document.querySelectorAll('[data-close]').forEach((b) => {
    b.onclick = () => { $(b.dataset.close).hidden = true; };
  });

  watchMapSize();

  // Kirgan zahoti o'yin emas, XARITA ochiladi
  openMap();
}

boot().catch((e) => {
  document.body.insertAdjacentHTML('afterbegin',
    '<div style="padding:20px;font:14px sans-serif;color:#fff">Xato: ' + e.message + '</div>');
  console.error(e);
});

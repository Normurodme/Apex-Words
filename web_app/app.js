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
  levelIndex: 0,        // hozir o'ynalayotgan darajaning tartib raqami
  puzzle: null,
  found: new Set(),
  foundBonus: new Set()
};

/* --------------------------------- Ovoz ----------------------------------- */
/* Tashqi audio fayl ishlatilmaydi — ohanglar Web Audio bilan joyida
   sintezlanadi. Shu sababli hech narsa yuklanmaydi va kechikish bo'lmaydi. */

const Sound = {
  ctx: null,

  ready() {
    if (!State.progress || State.progress.muted) return null;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!this.ctx) {
      try { this.ctx = new AC(); } catch (_) { return null; }
    }
    // Brauzer audio kontekstni foydalanuvchi bosgunicha to'xtatib turadi
    if (this.ctx.state === 'suspended') this.ctx.resume().catch(() => {});
    return this.ctx;
  },

  /* seq: [chastota, boshlanish (s), davomiyligi (s), balandlik] */
  play(seq, type) {
    const ctx = this.ready();
    if (!ctx) return;
    const t0 = ctx.currentTime + 0.02;
    seq.forEach(([f, at, dur, vol]) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = type || 'triangle';
      osc.frequency.value = f;
      // Yumshoq kirish va chiqish — "chirt" etgan ovoz bo'lmasligi uchun
      g.gain.setValueAtTime(0.0001, t0 + at);
      g.gain.exponentialRampToValueAtTime(vol || 0.22, t0 + at + 0.015);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + dur);
      osc.connect(g).connect(ctx.destination);
      osc.start(t0 + at);
      osc.stop(t0 + at + dur + 0.05);
    });
  },

  /* So'z to'g'ri topilganda — yumshoq ikki nota */
  chime() {
    this.play([[698, 0, .13, .18], [1047, .07, .22, .20]], 'sine');
  },

  /* Puzzle yechilganda — quvnoq uch pog'ona */
  solved() {
    this.play([[587, 0, .13, .22], [784, .10, .13, .22],
               [1175, .21, .34, .26]], 'triangle');
  },

  /* Daraja tugaganda — keng, bayramona (puzzle ovozidan aniq farq qiladi) */
  fanfare() {
    this.play([
      [523, 0,   .16, .22], [659, .09, .16, .22], [784, .18, .16, .22],
      [1047, .28, .26, .26], [880, .48, .16, .22], [1047, .58, .16, .24],
      [1319, .70, .70, .28]
    ], 'triangle');
  },

  /* Bonus so'z — mayin qo'ng'iroqcha */
  ding() {
    this.play([[1568, 0, .1, .13], [2093, .06, .22, .10]], 'sine');
  },

  /* Kalit olinganda — "chiq" etgan sovg'a ovozi */
  reward() {
    this.play([[880, 0, .1, .2], [1175, .07, .1, .2],
               [1760, .15, .3, .22]], 'triangle');
  }
};

/*
  Fon musiqasi — o'yin davomida sekin, bir tekis takrorlanuvchi ohang.

  Tayyor audio fayl yuklanmaydi: 16 qadamli naqsh Web Audio bilan joyida
  chalinadi. Notalar oldindan (lookahead bilan) rejalashtiriladi, chunki
  setInterval aniq vaqt bermaydi va ritm "oqsab" qolardi.

  Ovoz ataylab juda past (0.04) — o'yin ovozlarini bosib ketmasligi va
  uzoq o'ynaganda charchatmasligi kerak.
*/
const Music = {
  GAIN: 0.035,
  BAR: 3.6,          // bitta akkord necha soniya turadi

  /* Yumshoq mazhur ketma-ketlik. Notalar bir vaqtda kirib, uzoq turadi va
     sekin so'nadi — ritm sezilmaydi, fon "nafas olayotgandek" bo'ladi. */
  CHORDS: [
    [293.66, 369.99, 440.00],   // D
    [246.94, 311.13, 369.99],   // Bm
    [329.63, 415.30, 493.88],   // E
    [220.00, 277.18, 329.63]    // A
  ],
  /* Ustidan sekin tushadigan yorug' notalar (qo'ng'iroqchalar) */
  SPARKLE: [1174.66, 1479.98, 1760.00, 1479.98],

  timer: null, bar: 0, nextTime: 0, on: false,

  start() {
    if (this.on) return;
    const ctx = Sound.ready();
    if (!ctx) return;                 // ovoz o'chirilgan bo'lsa boshlanmaydi
    this.on = true;
    this.nextTime = ctx.currentTime + 0.15;
    this.timer = setInterval(() => this.schedule(), 400);
    this.schedule();
  },

  stop() {
    this.on = false;
    clearInterval(this.timer);
    this.timer = null;
  },

  schedule() {
    const ctx = Sound.ready();
    if (!ctx || !this.on) { this.stop(); return; }

    // Bir yarim akkord oldinga rejalashtiramiz — brauzer sekinlashsa ham uzilmaydi
    while (this.nextTime < ctx.currentTime + this.BAR * 1.5) {
      const ch = this.CHORDS[this.bar % this.CHORDS.length];
      ch.forEach((f, k) => {
        // Har nota biroz surilib kiradi — birdaniga "taq" etib boshlanmasin
        this.note(ctx, f, this.nextTime + k * 0.12, this.BAR * 1.15,
                  this.GAIN, 'sine', 0.9);
      });
      // Har ikkinchi akkordda bitta yorug' nota
      if (this.bar % 2 === 0) {
        this.note(ctx, this.SPARKLE[(this.bar / 2) % this.SPARKLE.length],
                  this.nextTime + 0.5, 1.6, this.GAIN * 0.5, 'triangle', 0.25);
      }
      this.nextTime += this.BAR;
      this.bar++;
    }
  },

  /* attack — notaning ochilish vaqti. Uzun bo'lsa ovoz yumshoq "suzib" kiradi. */
  note(ctx, freq, at, dur, vol, type, attack) {
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(vol, at + (attack || 0.05));
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    osc.connect(g).connect(ctx.destination);
    osc.start(at);
    osc.stop(at + dur + 0.05);
  }
};

const START_COINS = 0;
const START_KEYS = 5;        // har yangi o'yinchiga beriladigan kalitlar
const BUBBLE_MS = 3500;      // tarjima necha soniya ko'rinadi

function blankProgress() {
  return {
    coins: START_COINS, keys: START_KEYS,
    cur: { stage: 1, level: 1, puzzle: 0 },
    solved: {}, learned: {}, muted: false
  };
}

/* ------------------------------- Saqlash ---------------------------------- */

/* Kelgan progressni to'liq shaklga keltiradi — eski yoki chala yozuvlar
   sababli State.progress.solved kabi maydonlar yo'q bo'lib qolmasin. */
function normalize(p) {
  const b = blankProgress();
  if (!p || typeof p !== 'object') return b;
  return {
    coins: Number.isFinite(p.coins) ? p.coins : b.coins,
    // Kalit tushunchasi keyinroq qo'shilgan: eski yozuvda bo'lmasa
    // boshlang'ich miqdor beriladi, aks holda o'yinchi kalitsiz qolardi.
    keys: Number.isFinite(p.keys) ? p.keys : b.keys,
    cur: (p.cur && typeof p.cur === 'object') ? p.cur : b.cur,
    solved: (p.solved && typeof p.solved === 'object') ? p.solved : {},
    learned: (p.learned && typeof p.learned === 'object') ? p.learned : {},
    muted: !!p.muted
  };
}

/*
  Ikki qurilmadagi progressni birlashtiradi.

  Telefon va kompyuterda bir vaqtda o'ynalsa, oddiy "oxirgi yozgan yutadi"
  qoidasi bir qurilmadagi yutuqni o'chirib yuboradi. Shuning uchun har maydon
  bo'yicha eng KATTA qiymat olinadi: hech qayerda yutuq yo'qolmaydi.
*/
function mergeProgress(a, b) {
  a = normalize(a);
  b = normalize(b);
  const out = {
    coins: Math.max(a.coins, b.coins),
    keys: Math.max(a.keys, b.keys),
    solved: Object.assign({}, a.solved),
    learned: Object.assign({}, a.learned),
    muted: b.muted            // ovoz — shu qurilmaning sozlamasi
  };
  for (const k in b.solved) {
    out.solved[k] = Math.max(out.solved[k] || 0, b.solved[k] || 0);
  }
  for (const w in b.learned) {
    out.learned[w] = Math.max(out.learned[w] || 0, b.learned[w] || 0);
  }
  // Qaysi tomonda ko'proq puzzle yechilgan bo'lsa, o'sha joydan davom etamiz
  const total = (p) => Object.values(p.solved).reduce((s, n) => s + n, 0);
  out.cur = total(a) >= total(b) ? a.cur : b.cur;
  return out;
}

const Store = {
  online: true,
  timer: null,
  pending: false,

  async fetchServer() {
    if (!(TG && TG.initData)) return null;
    try {
      const r = await fetch('/api/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData: TG.initData })
      });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      return d ? d.progress : null;
    } catch (_) {
      this.online = false;
      return null;
    }
  },

  local() {
    try {
      const raw = localStorage.getItem('apexwords');
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    return null;
  },

  async load() {
    const local = this.local();
    if (TG && TG.initData) {
      const server = await this.fetchServer();
      if (this.online) {
        // Ikkalasi ham bo'lsa birlashtiramiz — qurilmalar bir-birini o'chirmasin
        return mergeProgress(server, local);
      }
    } else {
      this.online = false;
    }
    return normalize(local);
  },

  /* Boshqa qurilmada o'ynalgan bo'lsa, qaytib kelganda yangilanadi */
  async resync() {
    if (!this.online || !(TG && TG.initData)) return false;
    const server = await this.fetchServer();
    if (!server) return false;
    const merged = mergeProgress(server, State.progress);
    const changed = JSON.stringify(merged) !== JSON.stringify(State.progress);
    State.progress = merged;
    if (changed) this.saveNow();
    return changed;
  },

  save() {
    this.pending = true;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this._flush(), 1200);
  },

  /* Kechiktirmasdan darhol yozadi */
  saveNow() {
    clearTimeout(this.timer);
    this._flush();
  },

  async _flush() {
    const p = State.progress;
    this.pending = false;
    try { localStorage.setItem('apexwords', JSON.stringify(p)); } catch (_) {}
    if (!this.online || !(TG && TG.initData)) return;
    try {
      await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData: TG.initData, progress: p })
      });
    } catch (_) { this.online = false; }
  },

  /*
    Ilova yopilayotganda oddiy fetch ulgurmaydi — brauzer sahifani
    to'xtatganda so'rovni bekor qiladi. sendBeacon esa fon rejimida ham
    yuborilishi kafolatlangan.
  */
  flushOnExit() {
    const p = State.progress;
    try { localStorage.setItem('apexwords', JSON.stringify(p)); } catch (_) {}
    if (!this.online || !(TG && TG.initData)) return;
    const body = JSON.stringify({ initData: TG.initData, progress: p });
    let sent = false;
    if (navigator.sendBeacon) {
      try {
        sent = navigator.sendBeacon('/api/save',
          new Blob([body], { type: 'application/json' }));
      } catch (_) {}
    }
    if (!sent) {
      try {
        fetch('/api/save', {
          method: 'POST', body, keepalive: true,
          headers: { 'Content-Type': 'application/json' }
        });
      } catch (_) {}
    }
    this.pending = false;
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

/* Har daraja uchun mavzuga mos belgi. Daraja nomlari o'zgarmas bo'lgani
   uchun oddiy jadval yetarli — puzzle fayllarini qayta yaratish shart emas.
   12 bosqichning hammasi oldindan yozib qo'yilgan. */
const LEVEL_ICON = {
  // 1. Countries
  England: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', Japan: '🇯🇵', Brazil: '🇧🇷', Egypt: '🇪🇬', Canada: '🇨🇦',
  // 2. Cities
  Paris: '🗼', Tokyo: '🏯', Dubai: '🕌', Rome: '🏛️', London: '🎡',
  // 3. Foods
  Pizza: '🍕', Sushi: '🍣', Burger: '🍔', Pasta: '🍝', Tacos: '🌮',
  // 4. Animals
  Lion: '🦁', Panda: '🐼', Eagle: '🦅', Shark: '🦈', Tiger: '🐯',
  // 5. Sports
  Soccer: '⚽', Football: '⚽', Tennis: '🎾', Boxing: '🥊', Cricket: '🏏', Hockey: '🏒',
  // 6. Fruits
  Apple: '🍎', Mango: '🥭', Banana: '🍌', Cherry: '🍒', Orange: '🍊',
  // 7. Towers
  Eiffel: '🗼', Pisa: '🏛️', 'Big Ben': '🕰️', Petronas: '🏙️', 'Burj Khalifa': '🌇',
  // 8. Cars
  Tesla: '⚡', Toyota: '🚗', Ferrari: '🏎️', Bugatti: '🏁', Mercedes: '🚙',
  // 9. Mythical
  Dragon: '🐉', Phoenix: '🔥', Unicorn: '🦄', Kraken: '🐙', Griffin: '🦅',
  // 10. Gems
  Diamond: '💎', Ruby: '❤️', Emerald: '💚', Pearl: '🤍', Sapphire: '💙',
  // 11. Legends
  Sherlock: '🕵️', Dracula: '🧛', Aladdin: '🧞', Hercules: '💪', 'Robin Hood': '🏹',
  // 12. Wonders
  Pyramid: '🔺', Colosseum: '🏟️', Petra: '🏜️', Stonehenge: '🗿', 'Taj Mahal': '🕌'
};

const NODE_GAP = 132;      // tugunlar orasidagi masofa
const EDGE_PAD = 118;      // yuqoridagi bo'sh joy
const BOTTOM_PAD = 150;    // pastda ko'proq: 1-bosqich nomi shu yerga sig'adi
const BANNER_GAP = 76;     // bosqich nomi uchun qo'shimcha oraliq

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

  // Har yangi bosqich oldida qo'shimcha oraliq qoldiramiz — bosqich nomi
  // o'sha bo'shliqqa tushadi va tugun yozuvlariga tegmaydi.
  const extra = State.levels.filter((lv, i) => lv.first && i > 0).length;
  const h = EDGE_PAD + BOTTOM_PAD + (n - 1) * NODE_GAP + extra * BANNER_GAP;
  inner.style.height = h + 'px';
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  // 1-daraja PASTDA, keyingilari yuqoriga qarab ketadi
  const pts = [];
  let y = h - BOTTOM_PAD;
  State.levels.forEach((lv, i) => {
    if (i > 0) y -= NODE_GAP + (lv.first ? BANNER_GAP : 0);
    pts.push({ x: w / 2 + Math.sin(i * 0.95) * Math.min(w * 0.27, 110), y });
  });

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
  // -1 = hali topilmadi. Oldin 0 dan boshlanardi va "0 yolg'on qiymat"
  // bo'lgani uchun 1-daraja joriy bo'lganda ham izlash to'xtamasdi;
  // hamma daraja tugagan holatda esa xarita eng pastga surilib qolardi.
  let curIndex = -1;

  State.levels.forEach((lv, i) => {
    const done = solvedIn(lv.stage, lv.level);
    const unlocked = isUnlocked(i);
    const complete = done >= lv.puzzles;
    if (unlocked && !complete && curIndex < 0) curIndex = i;

    // Bosqich nomi — birinchi darajasidan PASTDA, o'sha bosqichga kirish
    // joyida. Oldingi tugun bilan orasida BANNER_GAP bo'shlig'i bor, shuning
    // uchun yuqoridagi tugunning nomiga tegmaydi.
    if (lv.first) {
      const b = el('div', 'stage-banner', lv.stage + '-BOSQICH · ' + lv.stageName);
      b.style.top = (pts[i].y + (i === 0 ? BOTTOM_PAD * 0.5
                                         : NODE_GAP * 0.5 + BANNER_GAP * 0.5)) + 'px';
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

    // Mavzu belgisi FONDA, tugun ortida katta bo'lib turadi — nom yonidagi
    // mayda sticker o'rniga. Yozuvni bosmasligi uchun shaffof va pastda.
    const icon = LEVEL_ICON[lv.name];
    if (icon) {
      const deco = el('div', 'node-deco', icon);
      deco.style.left = pts[i].x + 'px';
      deco.style.top = pts[i].y + 'px';
      // Yo'lning qaysi tomonida bo'sh joy ko'proq — o'sha tomonga qo'yamiz
      deco.classList.add(pts[i].x < w / 2 ? 'right' : 'left');
      nodes.appendChild(deco);
    }

    if (unlocked) {
      btn.onclick = () => {
        haptic('tap');
        openLevel(i);
      };
    }
    nodes.appendChild(btn);
  });

  updateCoins();     // ball VA kalitlar — ikkalasi ham yangilansin

  // Hozirgi darajani ko'rinadigan joyga surib qo'yamiz.
  // Hammasi tugagan bo'lsa oxirgi darajaga suramiz, pastga emas.
  const focus = curIndex < 0 ? State.levels.length - 1 : curIndex;
  const centerOn = () => {
    const vh = scroll.clientHeight || window.innerHeight || 640;
    scroll.scrollTop = Math.max(0, pts[focus].y - vh * 0.55);
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

/*
  Ekran almashtirish.

  O'yin ekrani qobiqdan TASHQARIDA turadi: o'ynayotganda pastki menyu
  kerak emas. Qolgan uchtasi qobiq ichida — menyu ular uchun umumiy va
  bo'lim almashganda joyida qoladi.
*/
const SHELL_SCREENS = ['map-screen', 'task-screen', 'top-screen'];
const TAB_OF = { 'map-screen': 'tab-play', 'task-screen': 'tab-task',
                 'top-screen': 'tab-top' };

function showScreen(id) {
  const inShell = SHELL_SCREENS.includes(id);
  $('shell').hidden = !inShell;
  $('game-screen').classList.toggle('active', id === 'game-screen');
  $('pack-screen').classList.toggle('active', id === 'pack-screen');

  SHELL_SCREENS.forEach((s) => $(s).classList.toggle('active', s === id));
  document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
  if (inShell) $(TAB_OF[id]).classList.add('active');

  // Ekran almashganda ochiq oynalar yopiladi — aks holda yangi bo'lim
  // ustida osilib qoladi va foydalanuvchi "faqat qoida qoldi" deb o'ylaydi.
  ['info-overlay', 'solved-overlay', 'done-overlay', 'stage-overlay']
    .forEach((o) => { $(o).hidden = true; });
  hideBubble();

}

function openMap() {
  showScreen('map-screen');
  renderMap();
  Store.save();
}

/* ============================= O'YIN EKRANI ============================== */

/* ======================== DARAJA ICHI (50 puzzle) ======================== */

/*
  Xaritadagi tugun bosilganda darhol o'yin boshlanmaydi — avval shu darajaning
  50 ta puzzlesi ro'yxati ochiladi. Shunda o'yinchi istagan puzzleni qayta
  o'ynay oladi va qayerda turganini ko'radi.
*/
function openLevel(i) {
  if (i < 0 || i >= State.levels.length || !isUnlocked(i)) return;
  State.levelIndex = i;
  showScreen('pack-screen');
  renderPack();
}

/* Puzzle ochiqmi: yechilganlari va navbatdagisi ochiq, qolgani qulf */
function puzzleUnlocked(idx) {
  return idx <= solvedIn(State.levels[State.levelIndex].stage,
                         State.levels[State.levelIndex].level);
}

function renderPack() {
  const i = State.levelIndex;
  const lv = State.levels[i];
  const done = solvedIn(lv.stage, lv.level);

  $('pack-title').textContent = lv.name;
  updateCoins();
  $('pack-progress').textContent = done + ' / ' + lv.puzzles + ' yechildi';
  $('pack-nav-name').textContent = lv.stage + '-bosqich · ' + lv.stageName;

  // Qo'shni darajalarga o'tish. ORQAGA har doim mumkin — o'tilgan darajani
  // qayta o'ynash uchun; oldinga faqat ochilgan bo'lsa.
  $('btn-pack-prev').disabled = i <= 0;
  $('btn-pack-next').disabled = !(i + 1 < State.levels.length && isUnlocked(i + 1));

  const grid = $('pack-grid');
  grid.innerHTML = '';
  for (let k = 0; k < lv.puzzles; k++) {
    const state = k < done ? 'done' : (k === done ? 'now' : 'locked');
    const b = el('button', 'pz ' + state);
    b.appendChild(el('span', 'pz-no', String(k + 1)));
    if (state === 'done') b.appendChild(el('span', 'pz-tick', '✓'));
    if (state === 'locked') b.appendChild(el('span', 'pz-lock', '🔒'));
    if (state !== 'locked') {
      b.onclick = () => { haptic('tap'); openPuzzleAt(k); };
    }
    grid.appendChild(b);
  }

  // Navbatdagi puzzle ko'rinib tursin
  requestAnimationFrame(() => {
    const now = grid.querySelector('.pz.now') || grid.querySelector('.pz.done');
    if (now) now.scrollIntoView({ block: 'center' });
  });
}

async function openPuzzleAt(idx) {
  const lv = State.levels[State.levelIndex];
  showScreen('game-screen');
  await openPuzzle(lv.stage, lv.level, idx);
}

async function openPuzzle(stage, level, idx) {
  const data = await loadStage(stage);
  const lvl = data.levels.find((l) => l.level === level);
  if (!lvl) return;
  if (idx >= lvl.puzzles.length) { finishLevel(stage, level); return; }

  // NUSXA olamiz: "Aralashtirish" tugmasi letters ni o'zgartiradi, asl obyekt
  // esa keshlangan bosqich faylida yotibdi. To'g'ridan-to'g'ri ishlatilsa,
  // daraja qayta ochilganda harflar aralashgan holida qolib ketardi.
  State.puzzle = Object.assign({}, lvl.puzzles[idx]);
  State.found = new Set();
  State.foundBonus = new Set();
  hideBubble();
  State.progress.cur = { stage, level, puzzle: idx };

  $('level-title').textContent = lvl.name + ' · ' + (idx + 1) + '/' + lvl.puzzles.length;
  renderGrid();
  renderWheel();
  updateCoins();
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
let bubbleTimer = null, bubbleHideTimer = null;

/* Puzzle yoki ekran almashsa pufak osilib qolmasin: u lampaning joyiga
   qarab qo'yilgan, lampa esa allaqachon yo'q bo'lishi mumkin. */
function hideBubble() {
  clearTimeout(bubbleTimer);
  clearTimeout(bubbleHideTimer);
  const bub = $('bubble');
  bub.classList.remove('show');
  bub.hidden = true;
}

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
  clearTimeout(bubbleHideTimer);
  bubbleTimer = setTimeout(() => {
    bub.classList.remove('show');
    bubbleHideTimer = setTimeout(() => { bub.hidden = true; }, 200);
  }, BUBBLE_MS);
}

/* ------------------------------ G'ildirak --------------------------------- */

let letterEls = [];
let centers = [];

function renderWheel() {
  const box = $('letters');
  box.innerHTML = '';
  letterEls = [];
  // Tortish holatini ham tozalaymiz. Aks holda puzzle o'z-o'zidan almashgan
  // paytda (oxirgi so'z topilgach) barmoq hali g'ildirakda bo'lsa, path ichida
  // ESKI harf indekslari qolib ketadi va ular yangi g'ildirakda mavjud
  // bo'lmasligi mumkin — letterEls[i] undefined bo'lib xato beradi.
  path = [];
  dragging = false;
  ptr = null;
  showCurrent('', null);

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

/*
  Barmoq qaysi harf ustida.

  Sezish maydoni harfning o'zidan kattaroq (1.45), chunki barmoq uchi
  ko'rsatkichdan kengroq va aniq markazga tushmaydi. Eng YAQIN harf
  tanlanadi — ilgari birinchi mos kelgani olinardi va tez tortilganda
  noto'g'ri harf ilinib qolardi.
*/
function hitTest(p) {
  let best = -1, bestD = Infinity;
  for (let i = 0; i < centers.length; i++) {
    const c = centers[i];
    const dx = p.x - c.x, dy = p.y - c.y;
    const d = dx * dx + dy * dy;
    if (d <= (c.r * 1.45) ** 2 && d < bestD) { bestD = d; best = i; }
  }
  return best;
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
  // letterEls[i] yo'q bo'lishi mumkin: g'ildirak shu orada qayta chizilgan bo'lsa
  path.forEach((i) => letterEls[i] && letterEls[i].classList.remove('active'));
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

/*
  Chiziq.

  Avval to'g'ri chiziqlar ketma-ketligi edi va burchaklarda "singan" ko'rinardi.
  Endi nuqtalar orasidan SILLIQ egri o'tkaziladi: har bo'g'inning o'rtasi
  tayanch nuqta bo'ladi, harflarning markazi esa burilish nuqtasi.
  Ustiga yumshoq yorug'lik qo'shiladi — barmoq izi "yonib turgandek" bo'ladi.
*/
function drawLine() {
  const cv = $('line');
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (!path.length || path.some((i) => !centers[i])) return;

  const pts = path.map((i) => centers[i]);
  if (dragging && ptr) pts.push(ptr);

  const trace = () => {
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    if (pts.length === 2) {
      ctx.lineTo(pts[1].x, pts[1].y);
    } else {
      // Kvadratik egri: nuqta — burilish, keyingi o'rta nuqta — tugash joyi
      for (let k = 1; k < pts.length - 1; k++) {
        const mx = (pts[k].x + pts[k + 1].x) / 2;
        const my = (pts[k].y + pts[k + 1].y) / 2;
        ctx.quadraticCurveTo(pts[k].x, pts[k].y, mx, my);
      }
      const last = pts[pts.length - 1];
      ctx.quadraticCurveTo(last.x, last.y, last.x, last.y);
    }
  };

  const stroke = (w, color, alpha, blur) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = w;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    if (blur) { ctx.shadowColor = color; ctx.shadowBlur = blur; }
    trace();
    ctx.stroke();
    ctx.restore();
  };

  // Nafis chiziq: qalin marjon o'rniga ingichka, shaffof va yumshoq nurli.
  // Uch qatlam bir-birining ustiga tushib, shisha naycha taassurotini beradi.
  stroke(15, '#7be3ff', 0.22, 16);   // keng, xira gardish
  stroke(7,  '#ffffff', 0.30, 8);    // oq yumshoq qatlam
  stroke(4.5, '#2fb9ff', 0.92, 0);   // ingichka aniq o'zak

  // Bosilgan harflar ustida kichik nuqtalar — yo'l ko'rinib tursin
  ctx.save();
  ctx.fillStyle = '#ffffff';
  ctx.globalAlpha = 0.9;
  path.forEach((i) => {
    ctx.beginPath();
    ctx.arc(centers[i].x, centers[i].y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

/* ---------------------------- So'zni tekshirish ---------------------------- */

function submit(word) {
  const p = State.puzzle;

  if (p.words.includes(word)) {
    if (State.found.has(word)) return flash(word, 'repeat');
    State.found.add(word);
    fillWord(word);
    // Ochko ALOHIDA so'z uchun berilmaydi — butun puzzle yechilganda beriladi.
    // Aks holda ball juda tez o'sib ketardi va maslahat narxi ma'nosiz bo'lardi.
    learn(word);
    haptic('ok');
    flash(word, 'hit', 700);
    if (State.found.size === p.words.length) {
      Sound.chime();
      // Qaysi puzzle yechilganini HOZIR yozib olamiz. 1.1 soniya ichida
      // boshqa qurilma bilan sinxronlash State.progress.cur ni o'zgartirib
      // yuborishi mumkin — u holda noto'g'ri daraja belgilanardi.
      const { stage, level, puzzle } = State.progress.cur;
      setTimeout(() => puzzleSolved(stage, level, puzzle), 1100);
    }
    return;
  }

  if (p.bonus.includes(word)) {
    if (State.foundBonus.has(word)) return flash(word, 'repeat');
    State.foundBonus.add(word);
    // Bonus so'z ikki narsa beradi: ball va kalit
    State.progress.coins += 1;
    State.progress.keys += 1;
    updateCoins();
    Store.save();
    learn(word);
    haptic('ok');
    Sound.ding();
    flash(word, 'hit', 700);
    toast('🎁 BONUS · ' + word + '   +1 💎  +1 🗝️');
    return;
  }

  haptic('err');
  flash(word, 'miss', 500);
}

/* Bir nechta flash ustma-ust tushsa, oldingisining taymeri keyingisining
   yozuvini erta o'chirib yubormasligi uchun taymer saqlanadi. */
let flashTimer = null;
function flash(word, cls, ms) {
  showCurrent(word, cls);
  clearTimeout(flashTimer);
  if (ms) flashTimer = setTimeout(() => showCurrent('', null), ms);
}

function learn(word) {
  State.progress.learned[word] = (State.progress.learned[word] || 0) + 1;
}

function addCoins(n) {
  State.progress.coins += n;
  updateCoins();
  Store.save();
}

function addKeys(n) {
  State.progress.keys = Math.max(0, State.progress.keys + n);
  updateCoins();
  Store.save();
}

function updateCoins() {
  const c = State.progress.coins, k = State.progress.keys;
  ['coin-count', 'map-coins', 'pack-coins'].forEach((id) => {
    const e = $(id); if (e) e.textContent = c;
  });
  ['key-count', 'map-keys', 'pack-keys', 'task-keys'].forEach((id) => {
    const e = $(id); if (e) e.textContent = k;
  });
}


/* Ikkita taymer: biri yashirishni boshlaydi, ikkinchisi hidden qo'yadi.
   Ikkalasi ham tozalanishi shart — aks holda oldingi bildirishnomaning
   "hidden" taymeri yangisini ko'rinmas qilib qo'yadi. */
let toastTimer = null, toastHideTimer = null;
function toast(text) {
  const t = $('toast');
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  clearTimeout(toastHideTimer);
  requestAnimationFrame(() => t.classList.add('show'));
  toastTimer = setTimeout(() => {
    t.classList.remove('show');
    toastHideTimer = setTimeout(() => { t.hidden = true; }, 200);
  }, 1400);
}

/* -------------------------- Puzzle / daraja tugashi ------------------------ */

function puzzleSolved(stage, level, puzzle) {
  const k = key(stage, level);
  const yangi = (State.progress.solved[k] || 0) <= puzzle;   // birinchi marta yechildimi
  State.progress.solved[k] = Math.max(State.progress.solved[k] || 0, puzzle + 1);
  if (yangi) addCoins(5);                 // qayta o'ynaganda ochko takror berilmaydi
  else Store.save();

  const lv = State.levels.find((l) => l.stage === stage && l.level === level);
  if (puzzle + 1 >= lv.puzzles) { finishLevel(stage, level); return; }

  // Har puzzledan keyin qisqa oyna: davom etish yoki ro'yxatga qaytish
  Sound.solved();
  haptic('ok');
  $('solved-badge').textContent = LEVEL_ICON[lv.name] || '⭐';
  $('solved-sub').textContent = yangi ? '+5 💎' : 'Qayta yechildi';
  $('solved-overlay').hidden = false;

  $('btn-solved-next').onclick = () => {
    $('solved-overlay').hidden = true;
    openPuzzle(stage, level, puzzle + 1);
  };
  $('btn-solved-list').onclick = () => {
    $('solved-overlay').hidden = true;
    showScreen('pack-screen');
    renderPack();
  };
}

/* Shu bosqichning hamma darajalari tugadimi */
function stageComplete(stage) {
  return State.levels
    .filter((l) => l.stage === stage)
    .every((l) => solvedIn(l.stage, l.level) >= l.puzzles);
}

function finishLevel(stage, level) {
  const i = State.levels.findIndex((l) => l.stage === stage && l.level === level);
  const next = State.levels[i + 1];

  Sound.fanfare();
  haptic('ok');
  Store.save();

  // Butun bosqich tugagan bo'lsa — alohida, kattaroq oyna
  if (stageComplete(stage)) {
    showStageDone(stage, next, i);
    return;
  }

  $('done-title').textContent = 'Daraja tugadi!';
  $('done-sub').textContent = next
    ? '"' + next.name + '" darajasi ochildi. Hozir o\'tasizmi?'
    : 'Barcha mavjud darajalar tugadi. Yangi bosqichlar tez orada!';

  // Keyingi daraja bo'lmasa faqat xaritaga qaytish qoladi
  $('btn-next').hidden = !next;
  if (next) $('btn-next').textContent = next.name + ' ▶';
  $('done-overlay').hidden = false;

  $('btn-next').onclick = () => {
    $('done-overlay').hidden = true;
    openLevel(i + 1);
  };
  $('btn-stay').onclick = () => {
    $('done-overlay').hidden = true;
    openMap();
  };
}

/* Butun bosqich yakunlanganda: bu darajadan kattaroq voqea, shuning uchun
   alohida oyna va keyingi BOSQICHga o'tish taklifi. */
function showStageDone(stage, next, i) {
  const info = State.index.stages.find((s) => s.stage === stage);
  const stageName = info ? info.name : stage + '-bosqich';
  const nextStage = next && next.stage !== stage ? next : null;

  $('stage-badge').textContent = LEVEL_ICON[
    (State.levels.find((l) => l.stage === stage + 1) || {}).name] || '🏆';
  $('stage-title').textContent = stage + '-BOSQICH TUGADI!';
  $('stage-sub').textContent = nextStage
    ? '"' + stageName + '" to\'liq yakunlandi. Endi ' + (stage + 1) +
      '-bosqich — "' + nextStage.stageName + '" ochildi. O\'tasizmi?'
    : '"' + stageName + '" to\'liq yakunlandi! Yangi bosqichlar tez orada qo\'shiladi.';

  $('btn-stage-next').hidden = !nextStage;
  if (nextStage) $('btn-stage-next').textContent = nextStage.stageName + ' ▶';
  $('stage-overlay').hidden = false;

  $('btn-stage-next').onclick = () => {
    $('stage-overlay').hidden = true;
    openLevel(i + 1);
  };
  $('btn-stage-stay').onclick = () => {
    $('stage-overlay').hidden = true;
    openMap();
  };
}

/* -------------------------------- Maslahat -------------------------------- */

function useHint() {
  if (!State.puzzle) return;
  if (State.progress.keys < 1) {
    toast('🗝️ Kalit qolmadi — Vazifa bo\'limidan oling');
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
      addKeys(-1);
      toast('🗝️ Harf ochildi');
      // Kalit kamayganini o'yinchi ko'rishi kerak
      $('key-count').classList.remove('spend');
      void $('key-count').offsetWidth;      // animatsiyani qayta boshlash
      $('key-count').classList.add('spend');
      haptic('tap');
      return;
    }
  }
  // Ochiladigan harf qolmagan bo'lsa ochko olinmaydi
  toast('Ochiladigan harf qolmadi');
}

/* ============================== VAZIFALAR ============================== */

/*
  Kunlik zanjir va kanal vazifasi.

  Kun hisobi va bir martalik mukofotlar SERVERDA saqlanadi: telefon soatini
  o'zgartirib yoki sahifani yangilab qayta olishning oldi olinadi. Mijoz
  faqat serverdan kelgan kalitlarni hisobga qo'shadi.
*/
const DAILY_PLAN = [1, 1, 1, 2, 2, 2, 3];
let taskState = null;

async function api(path) {
  if (!(TG && TG.initData)) return null;
  try {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initData: TG.initData })
    });
    return await r.json();
  } catch (_) { return null; }
}

async function openTasks() {
  showScreen('task-screen');
  updateCoins();
  renderTasks();
  const s = await api('/api/tasks');
  if (s && !s.error) { taskState = s; renderTasks(); }
}

function renderTasks() {
  const s = taskState;
  const plan = (s && s.plan) || DAILY_PLAN;
  const streak = s ? s.streak : 0;
  const claimed = s ? s.claimed_today : false;

  // Bugun olingan bo'lsa zanjirning shu kuni to'lgan hisoblanadi
  const filled = claimed ? streak : streak;
  const nextDay = claimed ? streak : streak + 1;

  const box = $('streak-days');
  box.innerHTML = '';
  plan.forEach((k, i) => {
    const d = el('div', 'day' + (i < filled ? ' got' : '') +
                        (!claimed && i + 1 === nextDay ? ' next' : ''));
    d.appendChild(el('span', 'day-n', String(i + 1)));
    d.appendChild(el('span', 'day-k', '🗝️'.repeat(k)));
    box.appendChild(d);
  });

  const btn = $('btn-claim-daily');
  if (!(TG && TG.initData)) {
    $('streak-note').textContent = 'Kunlik mukofot Telegram ichida ishlaydi';
    btn.disabled = true;
    btn.textContent = 'Mavjud emas';
  } else if (claimed) {
    $('streak-note').textContent = streak + '-kun olindi. Ertaga qaytib keling!';
    btn.disabled = true;
    btn.textContent = 'Bugun olindi ✓';
  } else {
    const k = plan[Math.min(nextDay - 1, plan.length - 1)];
    $('streak-note').textContent = nextDay + '-kun uchun ' + k + ' ta kalit tayyor';
    btn.disabled = false;
    btn.textContent = 'Olish  +' + k + ' 🗝️';
  }

  const ch = $('btn-claim-channel');
  if (s && s.channel_done) {
    ch.disabled = true;
    ch.textContent = 'Olindi ✓';
  } else {
    ch.disabled = false;
    ch.textContent = 'Tekshirish';
  }

  // Pastki menyudagi nuqta: olinmagan mukofot borligini bildiradi
  $('task-dot').hidden = !(s && (!s.claimed_today || !s.channel_done));
}

async function claimDaily() {
  const btn = $('btn-claim-daily');
  btn.disabled = true;
  const r = await api('/api/claim-daily');
  if (!r || r.error) { toast('Bajarilmadi, keyinroq urinib ko\'ring'); renderTasks(); return; }
  if (r.already) { toast('Bugungi mukofot allaqachon olingan'); }
  else {
    addKeys(r.keys);
    Sound.reward();
    haptic('ok');
    toast('🗝️ +' + r.keys + ' kalit · ' + r.streak + '-kun');
  }
  const s = await api('/api/tasks');
  if (s && !s.error) taskState = s;
  renderTasks();
}

async function claimChannel() {
  const btn = $('btn-claim-channel');
  btn.disabled = true;
  btn.textContent = 'Tekshirilmoqda…';
  const r = await api('/api/claim-channel');
  if (!r || r.error) {
    toast('Tekshirib bo\'lmadi, keyinroq urinib ko\'ring');
  } else if (!r.joined) {
    toast('Avval kanalga qo\'shiling');
  } else if (r.granted) {
    addKeys(r.keys);
    Sound.reward();
    haptic('ok');
    toast('🗝️ +' + r.keys + ' kalit');
  } else {
    toast('Bu mukofot allaqachon olingan');
  }
  const s = await api('/api/tasks');
  if (s && !s.error) taskState = s;
  renderTasks();
}

/* ------------------------------- Reyting ---------------------------------- */

function avatar(name, photo) {
  const a = el('div', 'avatar');
  if (photo) {
    const img = document.createElement('img');
    // Ro'yxatni bloklamasin: ko'rinmaydigan rasmlar keyinroq yuklanadi
    img.loading = 'lazy';
    img.decoding = 'async';
    img.src = photo;
    img.alt = '';
    img.referrerPolicy = 'no-referrer';
    // Rasm ochilmasa (eski havola, tarmoq) ism harfi qoladi
    img.onerror = () => { img.remove(); a.textContent = initial(name); };
    a.appendChild(img);
  } else {
    a.textContent = initial(name);
  }
  return a;
}

function updateSoundBtn() {
  const b = $('btn-sound');
  const off = !!(State.progress && State.progress.muted);
  b.textContent = off ? '🔇' : '🔊';
  b.classList.toggle('off', off);
}

function initial(name) {
  const s = (name || '?').trim();
  return s ? s[0].toUpperCase() : '?';
}

/*
  Reyting.

  Bo'lim ochilganda ekran bo'sh turib qolmasligi kerak. Shuning uchun oxirgi
  natija xotirada saqlanadi va DARHOL chiziladi, so'rov esa orqa fonda ketadi.
  Yangi ma'lumot kelganda ro'yxat jimgina yangilanadi — ilgari har safar
  "Yuklanmoqda…" chiqib, keyin sakrab almashardi.
*/
let topCache = null;

async function openTop() {
  showScreen('top-screen');
  const body = $('top-body');
  const mine = $('my-rank');

  if (topCache) {
    renderTop(topCache);                      // keshdan darhol
  } else {
    body.innerHTML = '';
    mine.hidden = true;
    body.appendChild(el('div', 'book-empty', 'Yuklanmoqda…'));
  }

  if (!(TG && TG.initData)) {
    body.innerHTML = '';
    body.appendChild(el('div', 'book-empty',
      'Reyting faqat Telegram ichida ishlaydi.\n\nBotni oching va "O\'ynash" tugmasini bosing.'));
    return;
  }

  let data;
  try {
    const r = await fetch('/api/top', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initData: TG.initData })
    });
    if (!r.ok) throw new Error('status ' + r.status);
    data = await r.json();
  } catch (e) {
    if (topCache) return;                     // keshdagisi turaveradi
    body.innerHTML = '';
    body.appendChild(el('div', 'book-empty', 'Reyting yuklanmadi. Keyinroq urinib ko\'ring.'));
    return;
  }

  // O'zgarmagan bo'lsa qayta chizmaymiz — rasmlar bekorga qayta yuklanmasin
  const fresh = JSON.stringify(data);
  if (topCache && JSON.stringify(topCache) === fresh) return;
  topCache = data;
  renderTop(data);
}

function renderTop(data) {
  const body = $('top-body');
  const mine = $('my-rank');
  body.innerHTML = '';
  if (!data.top || !data.top.length) {
    body.appendChild(el('div', 'book-empty',
      'Reyting hali bo\'sh.\n\nBirinchi bo\'lib ochko to\'plang!'));
  } else {
    const medal = ['gold', 'silver', 'bronze'];
    data.top.forEach((p) => {
      const row = el('div', 'rank-row' + (p.me ? ' me' : '') +
                              (p.rank <= 3 ? ' ' + medal[p.rank - 1] : ''));
      row.appendChild(el('div', 'rank-no', p.rank <= 3 ? ['🥇', '🥈', '🥉'][p.rank - 1] : String(p.rank)));
      row.appendChild(avatar(p.name, p.photo));
      row.appendChild(el('div', 'rank-name', p.name));
      const sc = el('div', 'rank-score');
      sc.appendChild(el('span', 'coin-dot', '★'));
      sc.appendChild(el('span', null, String(p.score)));
      row.appendChild(sc);
      body.appendChild(row);
    });
  }

  if (data.me) {
    mine.innerHTML = '';
    mine.appendChild(el('span', null, 'Sizning o\'rningiz: ' + data.me.rank + '-o\'rin'));
    mine.appendChild(el('span', null, '★ ' + data.me.score));
    mine.hidden = false;
  }
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

  $('btn-back').onclick = () => {
    haptic('tap');
    showScreen('pack-screen');
    renderPack();
  };
  $('btn-pack-back').onclick = () => { haptic('tap'); openMap(); };
  $('btn-pack-prev').onclick = () => { haptic('tap'); openLevel(State.levelIndex - 1); };
  $('btn-pack-next').onclick = () => { haptic('tap'); openLevel(State.levelIndex + 1); };
  $('btn-hint').onclick = useHint;
  $('btn-shuffle').onclick = () => {
    if (!State.puzzle) return;
    const l = State.puzzle.letters.split('');
    for (let i = l.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [l[i], l[j]] = [l[j], l[i]];
    }
    State.puzzle.letters = l.join('');
    renderWheel();
    haptic('tap');
  };

  $('tab-task').onclick = () => { haptic('tap'); openTasks(); };
  $('btn-claim-daily').onclick = claimDaily;
  $('btn-claim-channel').onclick = claimChannel;
  $('btn-open-channel').onclick = () => {
    const url = 'https://t.me/apexwords';
    if (TG && TG.openTelegramLink) TG.openTelegramLink(url);
    else window.open(url, '_blank');
  };
  $('tab-top').onclick = () => { haptic('tap'); openTop(); };
  $('tab-play').onclick = () => { haptic('tap'); openMap(); };
  $('btn-top-refresh').onclick = openTop;
  $('btn-info').onclick = () => { $('info-overlay').hidden = false; };

  $('btn-sound').onclick = () => {
    State.progress.muted = !State.progress.muted;
    updateSoundBtn();
    if (State.progress.muted) {
      Music.stop();
    } else {
      Sound.chime();                             // yoqilganini eshittiramiz
      Music.start();
    }
    Store.save();
  };
  updateSoundBtn();

  document.querySelectorAll('[data-close]').forEach((b) => {
    b.onclick = () => { $(b.dataset.close).hidden = true; };
  });

  watchMapSize();

  /* Musiqa ilova ochilishi bilan boshlanadi. Brauzerlar ovozni foydalanuvchi
     biror joyni bosmaguncha to'sadi, shuning uchun birinchi teginishda ham
     qayta uriniladi. */
  Music.start();
  const kickOff = () => {
    Music.start();
    if (Music.on) {
      document.removeEventListener('pointerdown', kickOff);
      document.removeEventListener('touchstart', kickOff);
    }
  };
  document.addEventListener('pointerdown', kickOff);
  document.addEventListener('touchstart', kickOff);

  /* Progressni qurilmalar orasida bir xil ushlab turish.
     Ilova yashirilganda kutmasdan yoziladi (aks holda kechiktirilgan saqlash
     yo'qoladi), qaytib ochilganda esa serverdan yangilanadi — boshqa
     qurilmada o'ynalgan bo'lsa shu yerda ham ko'rinadi. */
  document.addEventListener('visibilitychange', async () => {
    if (document.hidden) {
      Music.stop();                    // fonda ovoz chalinib turmasin
      Store.flushOnExit();
      return;
    }
    Music.start();
    if (await Store.resync()) {
      updateCoins();
      // Ochiq turgan ekranni yangilaymiz — boshqa qurilmada o'ynalgan
      // bo'lsa yangi yechilgan puzzlelar shu yerda ham ko'rinsin
      if ($('map-screen').classList.contains('active')) renderMap();
      else if ($('pack-screen').classList.contains('active')) renderPack();
    }
  });
  window.addEventListener('pagehide', () => Store.flushOnExit());

  // Kirgan zahoti o'yin emas, XARITA ochiladi
  openMap();
}

boot().catch((e) => {
  document.body.insertAdjacentHTML('afterbegin',
    '<div style="padding:20px;font:14px sans-serif;color:#fff">Xato: ' + e.message + '</div>');
  console.error(e);
});

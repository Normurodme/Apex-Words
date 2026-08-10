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

/*
  Bitta qurilmada bir nechta Telegram akkaunti ishlatilishi mumkin, ammo
  localStorage ular uchun umumiy. Shuning uchun kalit o'yinchi ID'siga
  bog'lanadi. Aks holda ikkinchi akkaunt birinchisining progressini o'qib
  oladi va load() uni server javobi bilan birlashtirib, keyingi saqlashda
  o'ziniki sifatida serverga yozib yuboradi.
*/
const UID = (() => {
  try {
    return (TG && TG.initDataUnsafe && TG.initDataUnsafe.user &&
            TG.initDataUnsafe.user.id) || 0;
  } catch (_) { return 0; }
})();
const LS_KEY = UID ? 'apexwords:' + UID : 'apexwords';

/*
  Eski umumiy kalit tashlab yuboriladi, egasi kimligini bilishning iloji
  yo'q. Progress serverda saqlanadi, shuning uchun kirgan o'yinchi uni
  baribir qaytarib oladi.
*/
if (UID) {
  try { localStorage.removeItem('apexwords'); } catch (_) {}
}

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
  unlimited: false,     // cheksiz kalit (serverdan keladi)
  admin: false,         // barcha bosqichlar ochiq, ball reytingga kirmaydi
  puzzle: null,
  found: new Set(),
  foundBonus: new Set()
};

/* --------------------------------- Ovoz ----------------------------------- */
/* Tashqi audio fayl ishlatilmaydi — ohanglar Web Audio bilan joyida
   sintezlanadi. Shu sababli hech narsa yuklanmaydi va kechikish bo'lmaydi. */

/*
  Ovoz zanjiri.

  Avval har nota to'g'ridan-to'g'ri chiqishga ulanardi va quruq, "arzon"
  eshitilardi. Endi hamma narsa umumiy zanjirdan o'tadi:

      nota -> lowpass filtr -> [aks-sado] -> master -> chiqish

  Lowpass o'tkir yuqori chastotalarni yumshatadi, aks-sado (delay + feedback)
  esa xonada chalinayotgandek kenglik beradi. Shu ikkisi ovozni "yumshoq"
  qiladi — o'yin uzoq o'ynalganda charchatmaydi.
*/
/*
  CHOLG'U TOVUSHLARI.

  Shu paytgacha hamma ovoz oddiy sine/triangle to'lqin edi. Notalarni
  qancha o'zgartirmay, TEMBR bir xil qolaverdi va quloqqa doim o'sha
  "elektron bip" bo'lib eshitildi — o'zgarish sezilmasligining sababi
  aynan shu edi.

  Endi har cholg'u o'z OBERTON tarkibiga ega (PeriodicWave). Oberton
  nisbatlari tovushning xarakterini belgilaydi:

    harp    — toq obertonlar kuchli, tez so'nadi: torli, jarangdor
    marimba — juft obertonlar bo'g'iq: yog'och, yumshoq
    bell    — obertonlar notekis (inharmonik): metall qo'ng'iroq
    pad     — obertonlar kam va past: tinch fon

  Shu bilan bir xil nota to'rt xil cholg'uda butunlay boshqacha
  eshitiladi.
*/
const TIMBRE = {
  //        [DC, 1-oberton, 2, 3, 4, 5, 6, 7]
  harp:    [0, 1.00, 0.28, 0.52, 0.16, 0.24, 0.08, 0.10],
  marimba: [0, 1.00, 0.06, 0.40, 0.04, 0.14, 0.02, 0.05],
  bell:    [0, 1.00, 0.62, 0.18, 0.44, 0.12, 0.30, 0.20],
  pad:     [0, 1.00, 0.42, 0.14, 0.06, 0.03, 0.01, 0.01],
};

const Sound = {
  ctx: null, master: null, warm: null, wet: null, waves: {},
  musicGain: null,   // faqat fon musiqasi shu tugundan o'tadi

  /* Oberton jadvalidan to'lqin yasaydi va keshlaydi */
  wave(name) {
    if (this.waves[name]) return this.waves[name];
    const h = TIMBRE[name] || TIMBRE.harp;
    const real = new Float32Array(h.length);
    const imag = new Float32Array(h);       // sinus tarkibi
    const w = this.ctx.createPeriodicWave(real, imag, { disableNormalization: false });
    this.waves[name] = w;
    return w;
  },

  ready() {
    if (!State.progress || State.progress.muted) return null;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!this.ctx) {
      try { this.ctx = new AC(); } catch (_) { return null; }
      this.build();
    }
    if (this.ctx.state === 'suspended') this.ctx.resume().catch(() => {});
    return this.ctx;
  },

  build() {
    const c = this.ctx;

    this.master = c.createGain();
    this.master.gain.value = 0.75;
    this.master.connect(c.destination);

    /* Yumshatuvchi filtr. 2600 Hz juda past edi — ovozlar bo'g'iq chiqardi.
       4800 Hz o'tkirlikni oladi, lekin tiniqlikni saqlaydi. */
    this.warm = c.createBiquadFilter();
    this.warm.type = 'lowpass';
    this.warm.frequency.value = 4800;
    this.warm.Q.value = 0.4;
    this.warm.connect(this.master);

    /* Qisqa aks-sado. Kechikish 0.26 -> 0.14 s va qaytish 0.26 -> 0.16:
       ilgari notalar bir-biriga yopishib "loyqa" eshitilardi. */
    const delay = c.createDelay(1.0);
    delay.delayTime.value = 0.14;
    const fb = c.createGain();  fb.gain.value = 0.16;
    this.wet = c.createGain();  this.wet.gain.value = 0.16;
    delay.connect(fb).connect(delay);
    delay.connect(this.wet).connect(this.master);
    this.warm.connect(delay);

    /*
      Fon musiqasi uchun ALOHIDA ovoz tugmasi.

      Music.stop() faqat rejalashtiruvchini to'xtatadi, lekin oldindan
      rejalashtirilgan notalar (ikki o'lchov, ~4 soniya) baribir chalinardi.
      Tugma bosilgach ovoz shuncha vaqt davom etib, "ishlamayapti" bo'lib
      tuyulardi. Endi musiqa shu tugundan o'tadi va uni bir zumda nolga
      tushirish yetarli — allaqachon navbatga qo'yilgan notalar ham jim
      bo'ladi.
    */
    this.musicGain = c.createGain();
    this.musicGain.gain.value = 1;
    this.musicGain.connect(this.warm);
  },

  /*
    Bitta nota.

    Uchta narsa ovozni "arzon"likdan chiqaradi:
      1. LINEAR hujum. exponentialRamp nolga yaqin qiymatdan boshlanganda
         "chirt" beradi; linearRamp toza kiradi.
      2. Ikkinchi qatlam — oktava tepada, ancha past ovozda. Bitta sinus
         yalang'och eshitiladi, ikkitasi to'liq tuyuladi.
      3. Ozgina detune — ikki qatlam sekin "nafas oladi".
  */
  note({ freq, at, dur, vol = 0.2, timbre = 'harp', glide = 0, attack = 0.006 }) {
    const ctx = this.ctx;
    const mk = (f, v, det) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.setPeriodicWave(this.wave(timbre));
      osc.frequency.setValueAtTime(f, at);
      if (glide) osc.frequency.exponentialRampToValueAtTime(f * glide, at + dur * 0.8);
      if (det) osc.detune.value = det;

      const peak = Math.max(v, 0.0001);
      g.gain.setValueAtTime(0, at);
      g.gain.linearRampToValueAtTime(peak, at + attack);        // toza hujum
      g.gain.exponentialRampToValueAtTime(0.0001, at + dur);    // tabiiy so'nish
      osc.connect(g).connect(this.warm);
      osc.start(at);
      osc.stop(at + dur + 0.06);
    };
    mk(freq, vol, 0);
    // Ozgina surilgan ikkinchi ovoz — tovush "tirik" bo'lib eshitiladi
    mk(freq, vol * 0.35, 7);
  },

  /* seq: [chastota, boshlanish (s), davomiyligi (s), balandlik] */
  play(seq, timbre, glide) {
    const ctx = this.ready();
    if (!ctx) return;
    const t0 = ctx.currentTime + 0.02;
    seq.forEach(([f, at, dur, vol]) => {
      this.note({ freq: f, at: t0 + at, dur, vol: vol || 0.18,
                  timbre: timbre || 'marimba', glide: glide || 0 });
    });
  },

  /*
    So'z qabul qilindi.

    Bu ovoz eng ko'p eshitiladi — bir puzzleda o'nlab marta. Shuning uchun
    u qisqa, past va YUMSHOQ bo'lishi shart: elektron "bip" o'rniga
    yog'och ksilofonga o'xshash ikki nota. Kvarta oralig'i (do–fa)
    quloqqa tinch tuyuladi va takrorlanganda charchatmaydi.
  */
  chime() {
    this.play([[523.25, 0, .13, .12], [698.46, .055, .26, .11]], 'marimba');
  },

  /*
    Puzzle yechildi.

    So'z ovozidan aniq kattaroq bo'lishi kerak, lekin daraja
    bayramidan kichik. Uch nota bilan ko'tarilib, to'rtinchisida
    qo'ng'iroqday cho'ziladi — "sahifa yopildi" hissi.
  */
  solved() {
    // Arfa bo'ylab tez yugurish, so'ng tepada yumshoq qo'ng'iroq.
    // Ilgari to'rttala nota ham qo'ng'iroq edi va bonus ovoziga
    // o'xshab ketardi; endi ikki cholg'u aralashadi va aniq farq qiladi.
    this.play([[440.00, 0, .55, .10], [587.33, .05, .5, .10],
               [739.99, .10, .45, .11], [880.00, .15, .4, .11],
               [1108.73, .20, .35, .10]], 'harp');
    this.play([[1479.98, .30, .75, .12]], 'bell');
  },

  /*
    Daraja/bosqich tugadi — bayram.

    Ilgari bu ham boshqa ovozlar kabi bir xil tembr edi va farqi
    sezilmasdi. Endi u ANIQ boshqacha: pastdan yuqoriga uch pog'onali
    ko'tarilish, so'ng tepada ikki nota birga yangraydi (akkord) va
    uzoq cho'ziladi. Bu "yakun" hissini beradi.
  */
  fanfare() {
    this.play([
      [392, 0,    .16, .18], [523, .10, .16, .18], [659, .20, .16, .18],
      [784, .30,  .18, .20], [1047, .42, .22, .22],
      // Yakuniy akkord: uch nota bir vaqtda, uzoq so'nadi
      [784, .62, 1.10, .16], [1047, .62, 1.10, .18], [1319, .62, 1.15, .16],
      [1568, .70, 1.05, .12]
    ], 'bell');
  },

  /* Bonus so'z — mayda shisha qo'ng'iroqcha */
  ding() {
    this.play([[2093, 0, .07, .07], [3136, .04, .22, .045]], 'bell');
  },

  /* Mukofot olindi — pastdan yuqoriga sirg'aluvchi uchqun */
  reward() {
    this.play([[659, 0, .09, .14], [988, .07, .09, .15],
               [1319, .14, .11, .15], [1976, .22, .40, .13]], 'bell');
  },

  /* Noto'g'ri so'z — juda qisqa, pastga tushuvchi. Jazolovchi emas. */
  miss() {
    this.play([[311, 0, .13, .10]], 'marimba', 0.82);
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
  GAIN: 0.022,

  /*
    Cho'zilgan akkordlar OLIB TASHLANDI. Ular bir-birining ustiga tushib
    to'xtovsiz g'ing'illash hosil qilardi va tez charchatardi — asosiy
    shikoyat aynan shu edi.

    O'rniga musiqa qutisi uslubi: siyrak, alohida tomchi notalar. Har nota
    tez uriladi va uzoq so'nadi, orasi 1.5–3 soniya. Hech qachon ikkitadan
    ortiq nota bir vaqtda yangramaydi, shuning uchun "devor" hosil bo'lmaydi.

    Notalar mazhur pentatonikadan olinadi — bu shkalada istalgan ikki nota
    birga yoqimli eshitiladi, shuning uchun tasodifiy tanlansa ham hech
    qachon falsh chiqmaydi.
  */
  /*
    ERTAK VALSI.

    Tasodifiy notalar o'rniga haqiqiy ohang: to'rt akkordli aylanma
    (Am – F – C – G) va uning ustida arfa arpedjiosi. Uch qadamli
    o'lchov valsga xos silkinish beradi — bu o'yin ritmiga mos va
    tinglaganda "kuy" bo'lib eshitiladi, ilgarigidek tasodifiy
    tomchilar emas.

    Har akkordda: pastda uzun bas, o'rtada tinch pad, tepada arfa
    notalari. Uchtasining balandligi turlicha, shuning uchun ular
    bir-birini bosmaydi.
  */
  PROG: [
    { bass: 110.00, pad: [261.63, 329.63], harp: [440.00, 523.25, 659.25, 523.25, 659.25, 880.00] }, // Am
    { bass:  87.31, pad: [261.63, 349.23], harp: [349.23, 440.00, 523.25, 440.00, 523.25, 698.46] }, // F
    { bass: 130.81, pad: [329.63, 392.00], harp: [523.25, 659.25, 783.99, 659.25, 783.99, 1046.5] }, // C
    { bass:  98.00, pad: [293.66, 392.00], harp: [392.00, 493.88, 587.33, 493.88, 587.33, 783.99] }  // G
  ],
  BEAT: 0.62,        // bitta zarb; uchtasi bir o'lchov (vals)

  timer: null, nextTime: 0, on: false, since: 0, bar: 0,

  start() {
    if (this.on) return;
    // Faqat ATAYLAB yoqilgan bo'lsa chalinadi
    if (!State.progress || !State.progress.music) return;
    const ctx = Sound.ready();
    if (!ctx) return;
    this.on = true;
    this.bar = 0;
    this.nextTime = ctx.currentTime + 0.3;
    // Ovozni qaytaramiz (o'chirilganda nolga tushirilgan bo'lishi mumkin)
    const g = Sound.musicGain.gain;
    g.cancelScheduledValues(ctx.currentTime);
    g.setValueAtTime(g.value, ctx.currentTime);
    g.linearRampToValueAtTime(1, ctx.currentTime + 0.25);
    this.timer = setInterval(() => this.schedule(), 500);
    this.schedule();
  },

  stop() {
    this.on = false;
    clearInterval(this.timer);
    this.timer = null;
    // Navbatdagi notalarni ham jim qilamiz — aks holda ovoz yana
    // to'rt soniya davom etardi
    if (Sound.ctx && Sound.musicGain) {
      const t = Sound.ctx.currentTime;
      const g = Sound.musicGain.gain;
      g.cancelScheduledValues(t);
      g.setValueAtTime(g.value, t);
      g.linearRampToValueAtTime(0, t + 0.12);
    }
  },

  schedule() {
    const ctx = Sound.ready();
    if (!ctx || !this.on) { this.stop(); return; }

    const barLen = this.BEAT * 3;              // vals: bir o'lchovda uch zarb

    // Ikki o'lchov oldinga rejalashtiramiz — brauzer sekinlashsa ham uzilmaydi
    while (this.nextTime < ctx.currentTime + barLen * 2) {
      const c = this.PROG[this.bar % this.PROG.length];
      const t = this.nextTime;

      // 1-zarb: bas. Uzun va past, ohangning poydevori.
      this.voice(ctx, c.bass, t, barLen * 0.95, this.GAIN * 1.2, 'pad', 0.06);

      // 2- va 3-zarb: tinch pad akkordi — valsning "chap qo'li"
      c.pad.forEach((f, k) => {
        this.voice(ctx, f, t + this.BEAT * (k + 1), this.BEAT * 1.5,
                   this.GAIN * 0.55, 'pad', 0.10);
      });

      // Arfa: har o'lchovda oltita nota, yuqori registrda
      c.harp.forEach((f, k) => {
        this.voice(ctx, f, t + k * (barLen / 6), 1.6,
                   this.GAIN * (k === 5 ? 0.95 : 0.65), 'harp', 0.004);
      });

      this.nextTime += barLen;
      this.bar++;
    }
  },

  /* timbre — cholg'u nomi (harp / pad). attack qisqa bo'lsa torli,
     uzun bo'lsa fon bo'lib eshitiladi. */
  voice(ctx, freq, at, dur, vol, timbre, attack) {
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.setPeriodicWave(Sound.wave(timbre));
    osc.frequency.value = freq;
    g.gain.setValueAtTime(0, at);
    g.gain.linearRampToValueAtTime(vol, at + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    // Musiqa ALOHIDA tugundan o'tadi — bir zumda jim qilish uchun
    osc.connect(g).connect(Sound.musicGain);
    osc.start(at);
    osc.stop(at + dur + 0.06);
  }
};

const START_COINS = 0;
const START_KEYS = 5;        // har yangi o'yinchiga beriladigan kalitlar
const BUBBLE_MS = 3500;      // tarjima necha soniya ko'rinadi

function blankProgress() {
  return {
    coins: START_COINS, keys: START_KEYS,
    cur: { stage: 1, level: 1, puzzle: 0 },
    solved: {}, learned: {},
    muted: false,      // ovoz effektlari
    music: true        // fon musiqasi — STANDART HOLATDA YOQIQ.
                       // Doim chalinib turgan fon tez charchatadi va
                       // ko'pchilik o'yinni jim o'ynashni afzal ko'radi.
                       // Xohlagan o'yinchi 🎵 tugmasidan yoqadi.
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
    muted: !!p.muted,
    /* Fon musiqasi endi STANDART HOLATDA YOQIQ. Eski yozuvlarda bu maydon
       yo'q yoki oldingi majburiy tozalashdan keyin false bo'lib qolgan —
       ikkalasida ham qaytadan yoqamiz. O'yinchi 🎵 tugmasidan o'chirsa,
       tanlovi musicSet bayrog'i bilan eslab qolinadi. */
    music: p.musicSet ? !!p.music : true,
    musicSet: true
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
    muted: b.muted,           // ovoz — shu qurilmaning sozlamasi
    music: b.music
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
      // Cheksiz kalit bayrog'i SERVERDAN keladi — u progress ichida
      // saqlanmaydi, shuning uchun qurilmalar orasida ko'chmaydi
      State.unlimited = !!(d && d.unlimited);
      State.admin = !!(d && d.admin);
      return d ? d.progress : null;
    } catch (_) {
      this.online = false;
      return null;
    }
  },

  local() {
    try {
      const raw = localStorage.getItem(LS_KEY);
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
    try { localStorage.setItem(LS_KEY, JSON.stringify(p)); } catch (_) {}
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
    try { localStorage.setItem(LS_KEY, JSON.stringify(p)); } catch (_) {}
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

/*
  Ma'lumot fayllari uchun versiya belgisi.

  index.json va stage_*.json da ?v= yo'q edi, shuning uchun yangi
  bosqichlar chiqarilganda brauzer eski nusxani keshdan olib qolardi.

  Raqam QO'LDA yozilmaydi — shu skriptning o'z manzilidan olinadi.
  Ilgari u alohida turgan va orqada qolib ketgan edi (kod v25, ma'lumot
  v23), ya'ni yangi puzzlelar chiqarilsa ham eski nusxa ochilaverardi.
  Endi ikkalasi bir manbadan keladi va hech qachon ayrilmaydi.
*/
const DATA_V = (() => {
  const src = (document.currentScript && document.currentScript.src) || '';
  const m = src.match(/[?&]v=(\d+)/);
  return m ? m[1] : '1';
})();

async function loadIndex() {
  State.index = await (await fetch('data/index.json?v=' + DATA_V)).json();
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
    const r = await fetch('data/dict.json?v=' + DATA_V);
    if (r.ok) State.dict = await r.json();
  } catch (_) { State.dict = {}; }
}

async function loadStage(n) {
  if (State.stages[n]) return State.stages[n];
  const info = State.index.stages.find((s) => s.stage === n);
  State.stages[n] = await (await fetch('data/' + info.file + '?v=' + DATA_V)).json();
  return State.stages[n];
}

const key = (stage, level) => stage + '-' + level;
const solvedIn = (stage, level) => State.progress.solved[key(stage, level)] || 0;

function isUnlocked(i) {
  if (State.admin) return true;   // sinov uchun hamma bosqich ochiq
  if (i === 0) return true;
  const prev = State.levels[i - 1];
  return solvedIn(prev.stage, prev.level) >= prev.puzzles;
}

/* ============================ XARITA EKRANI ============================== */

/* Har daraja uchun mavzuga mos belgi. Daraja nomlari o'zgarmas bo'lgani
   uchun oddiy jadval yetarli — puzzle fayllarini qayta yaratish shart emas.
   12 bosqichning hammasi oldindan yozib qo'yilgan. */
/*
  BAYROQ EMOJILARI ISHLATILMAYDI.

  Windows ularni umuman chizmaydi: 🇯🇵 o'rniga "JP" harflari ko'rinadi
  (skrinshotda aynan shu edi). Sabab — bayroqlar "regional indicator"
  juftligidan yasaladi va Segoe UI Emoji ularni qo'llab-quvvatlamaydi.

  Shuning uchun har daraja uchun mamlakat bayrog'i emas, o'sha joyga xos
  TANIQLI belgi tanlandi: Kanada -> chinor bargi, Yaponiya -> Fudzi,
  Misr -> tuya. Bular Windows, Android va iOS'da bir xil chiziladi.
*/
const LEVEL_ICON = {
  // 1. Countries
  England: '🏰', Japan: '🗻', Brazil: '🌴', Egypt: '🐫', Canada: '🍁',
  // 2. Cities
  Paris: '🗼', Tokyo: '⛩️', Dubai: '🕌', Rome: '🏛️', London: '🎡',
  // 3. Foods
  Pizza: '🍕', Sushi: '🍣', Burger: '🍔', Pasta: '🍝', Tacos: '🌮',
  // 4. Animals
  Lion: '🦁', Panda: '🐼', Eagle: '🦅', Shark: '🦈', Tiger: '🐯',
  // 5. Sports
  Soccer: '⚽', Football: '⚽', Tennis: '🎾', Boxing: '🥊', Cricket: '🏏', Hockey: '🏒',
  // 6. Fruits
  Apple: '🍎', Mango: '🥭', Banana: '🍌', Cherry: '🍒', Orange: '🍊',
  // 7. Towers
  Eiffel: '🗼', Pisa: '🏛️', 'Big Ben': '🕰️', Petronas: '🌃', 'Burj Khalifa': '🌇',
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

/*
  Xarita va ro'yxat har ochilganda butun DOM'ni qayta qurardi: 10 ta tugun,
  SVG yo'l, 50 ta katak. Ko'zga bu miltillash bo'lib urilardi va sekin
  telefonda seziladigan to'xtash berardi.

  Endi holatdan qisqa "imzo" olinadi. Imzo o'zgarmagan bo'lsa — qayta
  chizishning ma'nosi yo'q va funksiya darhol qaytadi.
*/
let mapSig = '', packSig = '';

function renderMap(force) {
  const scroll = $('map-scroll');
  const inner = $('map-inner');
  const nodes = $('map-nodes');
  const svg = $('map-path');

  const sig = (scroll.clientWidth || 0) + '|' +
              JSON.stringify(State.progress.solved) + '|' + State.levels.length;
  if (!force && sig === mapSig && nodes.children.length) return;
  mapSig = sig;

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
  // Xaritadagi yo'l — siyoh bilan chizilgan nuqtali iz.
  // Ilgari oq edi va pergament fonda umuman ko'rinmasdi.
  svg.innerHTML =
    `<path d="${d}" fill="none" stroke="rgba(90,60,20,.5)" stroke-width="5"
           stroke-linecap="round" stroke-dasharray="2 16"/>`;

  /* Elementlar avval XOTIRADAGI fragmentga yig'iladi va oxirida bir marta
     DOM'ga qo'yiladi. Ilgari har tugun alohida qo'shilardi va brauzer har
     safar joylashuvni qayta hisoblab, birinchi chizilishni ~100 ms ga
     cho'zardi — bu ko'zga to'xtash bo'lib bilinardi. */
  const frag = document.createDocumentFragment();

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
      const b = el('div', 'stage-banner', 'CHAPTER ' + lv.stage + ' · ' + lv.stageName);
      b.style.top = (pts[i].y + (i === 0 ? BOTTOM_PAD * 0.5
                                         : NODE_GAP * 0.5 + BANNER_GAP * 0.5)) + 'px';
      frag.appendChild(b);
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
      frag.appendChild(deco);
    }

    if (unlocked) {
      btn.onclick = () => {
        haptic('tap');
        openLevel(i);
      };
    }
    frag.appendChild(btn);
  });

  // Bitta amalda almashtiramiz — brauzer joylashuvni faqat bir marta hisoblaydi
  nodes.replaceChildren(frag);

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
    renderMap(true);
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
  if (State.admin) return true;
  return idx <= solvedIn(State.levels[State.levelIndex].stage,
                         State.levels[State.levelIndex].level);
}

function renderPack() {
  const i = State.levelIndex;
  const lv = State.levels[i];
  const done = solvedIn(lv.stage, lv.level);

  const icon = LEVEL_ICON[lv.name];
  $('pack-title').textContent = (icon ? icon + '  ' : '') + lv.name;
  updateCoins();
  $('pack-progress').textContent = done + ' / ' + lv.puzzles;
  $('pack-bar').style.width = Math.round(done / lv.puzzles * 100) + '%';
  $('pack-nav-name').textContent = 'Chapter ' + lv.stage + ' · ' + lv.stageName;

  // Qo'shni darajalarga o'tish. ORQAGA har doim mumkin — o'tilgan darajani
  // qayta o'ynash uchun; oldinga faqat ochilgan bo'lsa.
  $('btn-pack-prev').disabled = i <= 0;
  $('btn-pack-next').disabled = !(i + 1 < State.levels.length && isUnlocked(i + 1));

  const grid = $('pack-grid');
  // Faqat holat o'zgarganda qayta quramiz — aks holda 50 ta katak har
  // safar yangidan yaratilib miltillashga sabab bo'lardi.
  const sig = i + '|' + done + '|' + lv.puzzles;
  if (sig === packSig && grid.children.length) return;
  packSig = sig;

  const frag = document.createDocumentFragment();
  for (let k = 0; k < lv.puzzles; k++) {
    const state = k < done ? 'done' : (k === done ? 'now' : 'locked');
    // Har o'ninchi katak — bosqich toshi. 50 ta bir xil katak ko'zni
    // toldiradi; oraliq belgilar ro'yxatga ritm beradi va o'yinchi
    // qayerda turganini tez topadi.
    const milestone = (k + 1) % 10 === 0;
    const b = el('button', 'pz ' + state + (milestone ? ' milestone' : ''));
    b.appendChild(el('span', 'pz-no', String(k + 1)));
    // Har bosqichning o'z belgisi katak ustida suv nishoni bo'lib turadi:
    // Kanadada chinor bargi, Misrda tuya, Yaponiyada sakura...
    if (icon) b.appendChild(el('span', 'pz-emblem', icon));
    // Adminda qulf yo'q: katak o'sha ko'rinishda qoladi, lekin ochiladi.
    const open = state !== 'locked' || State.admin;
    if (!open) b.appendChild(el('span', 'pz-mark', '🔒'));
    if (open) {
      b.onclick = () => { haptic('tap'); openPuzzleAt(k); };
    }
    frag.appendChild(b);
  }
  grid.replaceChildren(frag);

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
  $('bubble-uz').textContent = State.dict[word] || 'no translation';

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

  // Barmoq izi — qalamda tortilgan chiziq. Pergament fonga mos qizil
  // muhr rangida; ilgari ko'k-oq edi va yorug' qog'ozda yo'qolib ketardi.
  stroke(14, '#a52a35', 0.18, 10);   // keng, xira gardish
  stroke(8,  '#d05a5f', 0.55, 0);    // o'rta qatlam
  stroke(4,  '#8c1f2a', 0.95, 0);    // ingichka aniq o'zak

  // Bosilgan harflar ustida kichik nuqtalar — yo'l ko'rinib tursin
  ctx.save();
  ctx.fillStyle = '#fdf6e4';
  ctx.globalAlpha = 0.95;
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
  Sound.miss();
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
  // Cheksiz bo'lsa raqam o'rniga cheksizlik belgisi
  const keyText = State.unlimited ? '∞' : String(k);
  ['key-count', 'map-keys', 'pack-keys', 'task-keys'].forEach((id) => {
    const e = $(id); if (e) e.textContent = keyText;
  });
  // Kalit tugagani tugmadan ko'rinib tursin
  const kb = $('btn-hint');
  if (kb) kb.classList.toggle('empty', k < 1);
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
  $('solved-sub').textContent = yangi ? '+5 💎' : 'Replayed';
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

  $('done-title').textContent = 'Level complete!';
  $('done-sub').textContent = next
    ? '"' + next.name + '" is unlocked. Continue now?'
    : 'You finished every level available. New chapters are coming soon!';

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
  $('stage-title').textContent = 'CHAPTER ' + stage + ' COMPLETE!';
  $('stage-sub').textContent = nextStage
    ? '"' + stageName + '" is fully cleared. Chapter ' + (stage + 1) +
      ' — "' + nextStage.stageName + '" is now open. Continue?'
    : '"' + stageName + '" is fully cleared! New chapters are coming soon.';

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
  // Cheksiz kalitli o'yinchida chegara tekshirilmaydi
  if (!State.unlimited && State.progress.keys < 1) {
    toast('🗝️ Out of keys — collect more in Rewards');
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
      if (!State.unlimited) addKeys(-1);
      toast('🗝️ Letter revealed');
      // Kalit kamayganini o'yinchi ko'rishi kerak
      $('key-count').classList.remove('spend');
      void $('key-count').offsetWidth;      // animatsiyani qayta boshlash
      $('key-count').classList.add('spend');
      haptic('tap');
      return;
    }
  }
  // Ochiladigan harf qolmagan bo'lsa ochko olinmaydi
  toast('Nothing left to reveal');
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

/*
  Bo'limlar ochilganda kutish BO'LMASLIGI kerak.

  Ilgari so'rov aynan bosilgan paytda ketardi: avval eski holat ko'rinardi,
  keyin "Loading", keyin 3-4 soniyadan so'ng yangi natija. Endi ma'lumot
  ilova ochilishi bilan ORQA FONDA yuklanadi, shuning uchun o'yinchi
  bo'limga o'tganda u allaqachon tayyor turadi.
*/
let taskFetch = null, topFetch = null;

function prefetchSections() {
  if (!(TG && TG.initData)) return;
  taskFetch = api('/api/tasks').then((s) => {
    if (s && !s.error) { taskState = s; refreshTaskDot(); }
    return s;
  });
  topFetch = api('/api/top').then((d) => {
    if (d && !d.error) topCache = d;
    return d;
  });
}

/* Pastki menyudagi nuqta ma'lumot kelishi bilan yangilanadi */
function refreshTaskDot() {
  const s = taskState;
  $('task-dot').hidden = !(s && (!s.claimed_today || !s.channel_done));
}

async function openTasks() {
  showScreen('task-screen');
  updateCoins();
  renderTasks();                       // kesh bo'lsa darhol chiziladi

  // Oldindan boshlangan so'rov bo'lsa uni kutamiz, aks holda yangisini
  const s = await (taskFetch || api('/api/tasks'));
  taskFetch = null;
  if (s && !s.error) {
    const changed = JSON.stringify(s) !== JSON.stringify(taskState);
    taskState = s;
    if (changed) renderTasks();        // o'zgarmagan bo'lsa qayta chizmaymiz
  }
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
    $('streak-note').textContent = 'Daily rewards work inside Telegram';
    btn.disabled = true;
    btn.textContent = 'Unavailable';
  } else if (claimed) {
    $('streak-note').textContent = 'Day ' + streak + ' claimed. See you tomorrow!';
    btn.disabled = true;
    btn.textContent = 'Claimed today ✓';
  } else {
    const k = plan[Math.min(nextDay - 1, plan.length - 1)];
    $('streak-note').textContent = k + (k === 1 ? ' key' : ' keys') + ' waiting for day ' + nextDay;
    btn.disabled = false;
    btn.textContent = 'Claim  +' + k + ' 🗝️';
  }

  const ch = $('btn-claim-channel');
  if (s && s.channel_done) {
    ch.disabled = true;
    ch.textContent = 'Claimed ✓';
  } else {
    ch.disabled = false;
    ch.textContent = 'Verify';
  }

  refreshTaskDot();
}

async function claimDaily() {
  const btn = $('btn-claim-daily');
  btn.disabled = true;
  const r = await api('/api/claim-daily');
  if (!r || r.error) { toast('Something went wrong, try again later'); renderTasks(); return; }
  if (r.already) { toast('Today\'s reward is already claimed'); }
  else {
    addKeys(r.keys);
    Sound.reward();
    haptic('ok');
    toast('🗝️ +' + r.keys + ' keys · day ' + r.streak);
  }
  const s = await api('/api/tasks');
  if (s && !s.error) taskState = s;
  renderTasks();
}

async function claimChannel() {
  const btn = $('btn-claim-channel');
  btn.disabled = true;
  btn.textContent = 'Checking…';
  const r = await api('/api/claim-channel');
  if (!r || r.error) {
    toast('Could not verify, try again later');
  } else if (!r.joined) {
    toast('Join the channel first');
  } else if (r.granted) {
    addKeys(r.keys);
    Sound.reward();
    haptic('ok');
    toast('🗝️ +' + r.keys + ' keys');
  } else {
    toast('This reward is already claimed');
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

/*
  Ovoz tugmalarining holati.

  Ilgari faqat shaffoflik o'zgarardi va yoniq/o'chiq ekani bilinmasdi.
  Endi uch belgi birdan: BOSHQA belgi, ustidan qizil chiziq va yoniqda
  oltin gardish. Bir qarashda ko'rinadi.
*/
function updateSoundBtn() {
  const p = State.progress || {};

  const s = $('btn-sound');
  s.textContent = p.muted ? '🔇' : '🔊';
  s.classList.toggle('off', !!p.muted);
  s.classList.toggle('on', !p.muted);
  s.setAttribute('aria-pressed', p.muted ? 'false' : 'true');

  const m = $('btn-music');
  m.textContent = p.music ? '🎵' : '🎶';
  m.classList.toggle('off', !p.music);
  m.classList.toggle('on', !!p.music);
  m.setAttribute('aria-pressed', p.music ? 'true' : 'false');
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

  if (!(TG && TG.initData)) {
    body.innerHTML = '';
    mine.hidden = true;
    body.appendChild(el('div', 'empty-note',
      'Ranks work inside Telegram.\n\nOpen the bot and tap Play.'));
    return;
  }

  if (topCache) {
    renderTop(topCache);                      // keshdan darhol, kutishsiz
  } else {
    body.innerHTML = '';
    mine.hidden = true;
    body.appendChild(el('div', 'empty-note', 'Loading…'));
  }

  // Ilova ochilishida boshlangan so'rov odatda allaqachon tugagan bo'ladi
  const data = await (topFetch || api('/api/top'));
  topFetch = null;
  if (!data || data.error) {
    if (topCache) return;                     // keshdagisi turaveradi
    body.innerHTML = '';
    body.appendChild(el('div', 'empty-note', 'Could not load ranks. Try again later.'));
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
    body.appendChild(el('div', 'empty-note',
      'No ranks yet.\n\nBe the first to score!'));
  } else {
    const medal = ['gold', 'silver', 'bronze'];
    data.top.forEach((p) => {
      const row = el('div', 'rank-row' + (p.me ? ' me' : '') +
                              (p.rank <= 3 ? ' ' + medal[p.rank - 1] : ''));
      row.appendChild(el('div', 'rank-no', p.rank <= 3 ? ['🥇', '🥈', '🥉'][p.rank - 1] : String(p.rank)));
      row.appendChild(avatar(p.name, p.photo));
      row.appendChild(el('div', 'rank-name', p.name));
      const sc = el('div', 'rank-score');
      sc.appendChild(el('span', 'coin-dot', '💎'));
      sc.appendChild(el('span', null, String(p.score)));
      row.appendChild(sc);
      body.appendChild(row);
    });
  }

  if (data.me) {
    mine.innerHTML = '';
    mine.appendChild(el('span', null, 'Your place: #' + data.me.rank));
    mine.appendChild(el('span', null, '★ ' + data.me.score));
    mine.hidden = false;
  }
}

/* ------------------------------ Ishga tushirish ---------------------------- */

async function boot() {
  if (TG) {
    TG.ready();
    TG.expand();
    // Telegram sarlavhasi ham pergament rangida bo'lsin — ilova ekranga
    // yopishib turadi, chegara sezilmaydi
    try { TG.setHeaderColor('#eddaae'); TG.setBackgroundColor('#eddaae'); } catch (_) {}
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

  // 🔊 — ovoz effektlari (standart: yoqilgan)
  $('btn-sound').onclick = () => {
    State.progress.muted = !State.progress.muted;
    updateSoundBtn();
    if (State.progress.muted) Music.stop();
    else { Sound.chime(); Music.start(); }
    Store.save();
  };

  // 🎵 — fon musiqasi (standart: O'CHIQ, ataylab yoqiladi)
  $('btn-music').onclick = () => {
    State.progress.music = !State.progress.music;
    updateSoundBtn();
    if (State.progress.music) Music.start();
    else Music.stop();
    Store.save();
  };
  updateSoundBtn();

  document.querySelectorAll('[data-close]').forEach((b) => {
    b.onclick = () => { $(b.dataset.close).hidden = true; };
  });

  watchMapSize();

  // Vazifa va reyting ma'lumotini darhol so'raymiz — o'yinchi bo'limga
  // o'tgunicha javob kelib ulguradi va kutish sezilmaydi
  prefetchSections();

  /* Fon musiqasi o'z-o'zidan boshlanmaydi — faqat o'yinchi 🎵 tugmasidan
     yoqqan bo'lsa. Yoqilgan bo'lsa ham brauzer birinchi teginishgacha
     ovozni to'sadi, shuning uchun teginishda qayta uriniladi. */
  if (State.progress.music) {
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
  }

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

# Apex Words

Telegram Mini App — harflardan so'z yasab ingliz tilini o'rganish o'yini.
Harflar doira bo'ylab joylashadi, o'yinchi ularni barmog'i bilan tortib so'z
yasaydi. Topilgan har bir so'zning o'zbekcha tarjimasi ko'rsatiladi.

## Hozirgi holat (MVP)

| | |
|---|---|
| Bosqichlar | 2 (Countries, Cities) |
| Darajalar | 10 |
| Puzzle | 500 |
| Yechim so'zlari | 1 038 ta unikal — **hammasi tarjimali** |
| Bonus so'zlari | 208 ta unikal — **hammasi tarjimali** |
| Qiyinlik | 3 harfdan (`HOW/WHO`) 6 harfgacha (`INFORM`, `STRONG`) |

Qolgan 10 bosqich (7–9 harf) `build/generate_puzzles.py` dagi `LEVEL_PLAN`
jadvaliga qator qo'shish bilan generatsiya qilinadi.

## Ishga tushirish

```bash
cp .env.example .env
```

`.env` ichiga `BOT_TOKEN` ni yozing, so'ng:

```bash
pip install -r requirements.txt
python bot.py
```

Server `http://localhost:8080` da ochiladi. Telegram WebApp tugmasi faqat
`https://` manzil bilan ishlaydi, shuning uchun lokalda o'yinni to'g'ridan-to'g'ri
brauzerda oching — u Telegram topilmasa progressni `localStorage` ga saqlaydi.

## Tuzilma

```
bot.py                  aiogram bot + aiohttp (Mini App va /api)
web_app/                Mini App: index.html, style.css, app.js
web_app/data/           puzzle JSON'lari + dict.json (tarjimalar)
data/                   manba nusxalari + wordlist_*.txt
build/                  generatorlar (serverda kerak emas)
```

### build/ skriptlari

| Skript | Vazifasi |
|---|---|
| `build_dictionary.py` | NLTK + wordfreq dan so'z ro'yxatini yasaydi |
| `generate_puzzles.py` | 500 puzzle generatsiya qiladi va tekshiradi |
| `translations.py` | O'zbekcha tarjimalarni `dict.json` ga yozadi |
| `check_coverage.py` | Tarjimasiz so'z qolmaganini tekshiradi |

Tartib: `build_dictionary` → `generate_puzzles` → `translations` → `check_coverage`.

Generatorlar uchun qo'shimcha kutubxonalar:

```bash
pip install -r build/requirements-build.txt
```

## So'zlar qayerdan olingan

Hech bir so'z qo'lda o'ylab topilmagan. Ikki manba kesishmasi ishlatiladi:

- **wordfreq** — so'zning ishlatilish chastotasi (zipf). "Bu so'z oddiymi?"
- **NLTK `words`** — ~234 ming yozuvli Unix lug'ati. "Bu so'z bormi?"

Ustiga uch filtr qo'yiladi:

1. **Ko'plik va zamon shakllari chiqariladi.** `cat` bor, `cats` yo'q; `play` bor,
   `played`/`playing` yo'q. Suffiks qoidalari + noto'g'ri fe'llar ro'yxati.
2. **Atoqli otlar chiqariladi.** NLTK `names` korpusi va Brown korpusidagi
   bosh harf nisbati orqali: `russia` (1.00) o'chadi, `water` (0.02) qoladi.
3. **Qo'lda ko'rib chiqish.** Yechim so'zlarining butun ro'yxati o'qib chiqilgan;
   qisqartma, sleng va chet tili tokenlari `MANUAL_DROP` ga qo'shilgan.

Har puzzle generatsiyadan keyin avtomatik tekshiruvdan o'tadi: har so'z lug'atda
bormi, berilgan harflardan tuziladimi, harf to'plami takrorlanmaganmi.

## Deploy (Railway)

Bitta servis yetarli — aiohttp ham Mini App'ni, ham API'ni beradi (CORS muammosi yo'q).

1. Reponi Railway'ga ulang, `Dockerfile` avtomatik topiladi
2. O'zgaruvchilar: `BOT_TOKEN`, `WEBAPP_URL` (servisning o'z https manzili)
3. **Volume'ni `/data` ga ulang** — busiz konteyner qayta ishga tushganda
   o'yinchilar progressi yo'qoladi. `DB_PATH` ni qo'lda qo'yish shart emas:
   `/data` mavjud bo'lsa, baza avtomatik o'sha yerga yoziladi. Ishga tushish
   loglarida qaysi disk ishlatilayotgani ko'rinadi:
   `📁 Baza DOIMIY diskda` yoki `⚠️ Baza VAQTINCHALIK diskda`
4. BotFather'da `/newapp` orqali Main Mini App yarating (ixtiyoriy, qidiruvda
   "Open" tugmasi chiqishi uchun)

## Xavfsizlik

- `.env` `.gitignore` da — token repoga tushmaydi
- `/api/*` har so'rovda Telegram `initData` imzosini HMAC-SHA256 bilan tekshiradi;
  imzosiz so'rov 401 oladi, shuning uchun boshqa o'yinchining progressini
  o'qib/o'zgartirib bo'lmaydi
- `initData` 24 soatdan eski bo'lsa qabul qilinmaydi

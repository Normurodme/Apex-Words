"""
Apex Words — Telegram bot + Mini App serveri.

Bitta jarayonda ikkita narsa ishlaydi:
  * aiogram bot  — /start, Mini App tugmasi, menyu tugmasi
  * aiohttp web  — web_app/ statik fayllari va /api/* progress endpointlari

Bitta servis bo'lgani uchun CORS muammosi yo'q: Mini App o'zining originidan
API'ga murojaat qiladi.

Ishga tushirish:
    python bot.py
"""
from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
import hmac
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
import urllib.parse
from urllib.parse import parse_qsl

import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State as FState, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    MenuButtonWebApp,
    WebAppInfo,
)
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("apexwords")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
WEB_DIR = ROOT / "web_app"


def default_db_path() -> str:
    """
    Bazani qayerga yozishni tanlaydi.

    Railway konteynerining diski vaqtinchalik: qayta deploy qilinganda hamma narsa
    o'chadi. Doimiy saqlash uchun servisga Volume ulanadi va u odatda /data ga
    joylashtiriladi. Agar shunday katalog bo'lsa va unga yozish mumkin bo'lsa,
    bazani o'sha yerga yozamiz — DB_PATH o'zgaruvchisini qo'lda qo'yish
    esdan chiqsa ham o'yinchilar progressi saqlanib qoladi.
    """
    vol = Path("/data")
    if vol.is_dir() and os.access(vol, os.W_OK):
        return str(vol / "apex_words.db")
    return str(ROOT / "data" / "apex_words.db")


def resolve_db_path(raw: str | None = None, volume: str = "/data") -> str:
    """
    Bazaning yakuniy joyini tanlaydi.

    DB_PATH o'zgaruvchisi hurmat qilinadi, LEKIN bitta istisno bilan:
    agar u NISBIY yo'l bo'lsa (masalan "data/apex_words.db") va shu bilan
    birga /data volume ulangan bo'lsa, o'zgaruvchi e'tiborsiz qoldiriladi.

    Sababi: konteyner ichidagi nisbiy yo'l har deployda tozalanadigan diskka
    tushadi. Ya'ni o'yinchilarning darajasi va ochkolari har yangilanishda
    nolga qaytadi. Bu deyarli har doim xato — .env.example dan ko'chirilgan
    qiymat esdan chiqib qolgan bo'ladi. Volume ulangan turib ma'lumotni
    yo'qotishdan ko'ra, o'zgaruvchini bekor qilib ogohlantirgan afzal.
    """
    if raw is None:
        raw = os.getenv("DB_PATH", "")
    raw = raw.strip()
    if not raw:
        return default_db_path()

    vol = Path(volume)
    if not os.path.isabs(raw) and vol.is_dir() and os.access(vol, os.W_OK):
        fixed = str(vol / Path(raw).name)
        log.warning(
            "DB_PATH nisbiy yo'l ko'rsatyapti (%r) — bu konteyner ichi, "
            "har deployda o'chadi. /data volume ulangan, shuning uchun baza "
            "%s ga yozildi. Railway Variables dan DB_PATH ni butunlay "
            "o'chirsangiz bu ogohlantirish yo'qoladi.", raw, fixed)
        return fixed
    return raw


DB_PATH = resolve_db_path()

# initData shu muddatdan eski bo'lsa qabul qilinmaydi (takroriy hujumga qarshi)
INIT_DATA_TTL = 24 * 3600

if not BOT_TOKEN:
    raise SystemExit(
        "\n" + "=" * 64 +
        "\nISHGA TUSHMADI: BOT_TOKEN yo'q.\n"
        "  Lokalda : .env faylini yarating (.env.example dan nusxa oling)\n"
        "  Railway : Variables bo'limiga BOT_TOKEN qo'shing\n"
        + "=" * 64
    )


# ----------------------------- initData tekshiruvi ---------------------------

def verify_init_data(init_data: str) -> dict | None:
    """
    Telegram Mini App initData imzosini tekshiradi.

    Telegram rasmiy algoritmi: hash'dan tashqari barcha maydonlar "kalit=qiymat"
    ko'rinishida alifbo tartibida \\n bilan birlashtiriladi, so'ng
    HMAC-SHA256(secret, string) hisoblanadi. secret = HMAC("WebAppData", token).

    Bu tekshiruvsiz istalgan odam boshqa o'yinchining user_id sini yuborib
    uning progressini o'qishi/o'zgartirishi mumkin bo'lardi.
    """
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except ValueError:
        return None

    received = pairs.pop("hash", None)
    if not received:
        return None

    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None

    try:
        if time.time() - int(pairs.get("auth_date", "0")) > INIT_DATA_TTL:
            return None
    except ValueError:
        return None

    try:
        return json.loads(pairs.get("user", "null"))
    except json.JSONDecodeError:
        return None


# --------------------------------- Baza --------------------------------------

# Reyting balini cheklash uchun o'yin qoidalari.
#
# NIMA UCHUN KERAK: ball MIJOZDA hisoblanadi va /api/save orqali keladi.
# Imzo faqat "bu haqiqatan shu o'yinchi" degan kafolat beradi, "bu son
# to'g'ri" degan kafolat emas. Ya'ni istalgan odam o'z initData'si bilan
# {"coins": 999999999} yuborib Top 100 ni egallashi mumkin edi.
#
# Shuning uchun server balni yechilgan puzzlelardan kelib chiqib
# CHEGARALAYDI. Halol o'yinchiga bu sezilmaydi, "cheksiz ball" esa
# imkonsiz bo'ladi.
PUZZLES_PER_LEVEL = 50
MAX_LEVELS = 60
COINS_PER_PUZZLE = 5          # puzzle yechilganda
# O'lchandi: eng ko'p bonusli puzzlede 202 ta. Zaxira bilan olingan —
# lug'at kengaysa bu son o'sadi, chegara esa halol o'yinchini
# cheklab qo'ymasligi kerak. Tekshiruv: build/audit_words.py
MAX_BONUS_PER_PUZZLE = 400


def plausible_score(progress: dict) -> int:
    """
    Progressdan ishonarli ball hisoblaydi.

    Yuqori chegara: har yechilgan puzzle uchun 5 ochko + o'sha puzzledagi
    bonus so'zlar (eng ko'pi bilan MAX_BONUS_PER_PUZZLE ta, har biri 1).
    Yechilganlar soni ham chegaralanadi — mijoz "1000000 puzzle yechdim"
    deb yubora olmasin.
    """
    try:
        coins = int(progress.get("coins", 0))
    except (TypeError, ValueError):
        return 0
    if coins <= 0:
        return 0

    solved = progress.get("solved")
    total = 0
    if isinstance(solved, dict):
        for i, v in enumerate(solved.values()):
            if i >= MAX_LEVELS:
                break
            try:
                total += min(max(int(v), 0), PUZZLES_PER_LEVEL)
            except (TypeError, ValueError):
                continue

    ceiling = total * (COINS_PER_PUZZLE + MAX_BONUS_PER_PUZZLE)
    return min(coins, ceiling)


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    photo_url  TEXT,
    score      INTEGER NOT NULL DEFAULT 0,
    progress   TEXT NOT NULL DEFAULT '{}',
    last_daily TEXT,
    streak_day INTEGER NOT NULL DEFAULT 0,
    channel_ok INTEGER NOT NULL DEFAULT 0,
    ref_by     INTEGER,
    ref_count  INTEGER NOT NULL DEFAULT 0,
    ref_paid   INTEGER NOT NULL DEFAULT 0,
    pend_keys  INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

/*
  To'lovlar. charge_id — BIRLAMCHI KALIT va aynan shu narsa kalitlarni
  ikki marta berishdan saqlaydi: Telegram yangilanishni qayta yuborishi
  mumkin (tarmoq uzilsa getUpdates o'sha xabarni takrorlaydi), o'shanda
  ikkinchi yozuv rad etiladi va mukofot qayta berilmaydi.

  Bundan tashqari pulni qaytarish uchun charge_id kerak — ilgari u
  faqat logda qolardi va Railway logi bir necha kundan keyin o'chadi.
*/
CREATE TABLE IF NOT EXISTS payments (
    charge_id  TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    stars      INTEGER NOT NULL,
    keys       INTEGER NOT NULL,
    refunded   INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
"""

def _parse_ids(raw: str) -> set[int]:
    out = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


# Cheksiz kalitga ega o'yinchilar (sinov va yaratuvchilar uchun).
#
# Kalit soni MIJOZDA saqlanadi, shuning uchun bu bayroq serverdan
# beriladi: /api/state javobida qaytadi va mijoz kalitni kamaytirmaydi.
# Railway'da UNLIMITED_HINTS o'zgaruvchisi bilan qo'shimcha ID qo'shsa
# bo'ladi — kodni o'zgartirish shart emas.
UNLIMITED_HINTS = {6220077209, 6307658796} | _parse_ids(
    os.getenv("UNLIMITED_HINTS", ""))

# Adminlar. Ular uchun barcha bosqichlar ochiq va bali REYTINGGA
# KIRMAYDI — sinov paytida to'plangan ball haqiqiy o'yinchilarni
# birinchi o'rindan surib qo'ymasin.
#
# Ro'yxat bo'sh bo'lishi ham mumkin, shuning uchun SQL shartini
# qo'lda yasaymiz: "NOT IN ()" yozuvi SQLite'da xato beradi.
ADMINS = {6220077209} | _parse_ids(os.getenv("ADMIN_IDS", ""))
_ADMIN_SQL = (" AND user_id NOT IN (%s)" % ",".join(str(i) for i in sorted(ADMINS))
              if ADMINS else "")

# Kunlik mukofot: 1-3 kun 1 kalit, 4-6 kun 2 kalit, 7-kun 3 kalit.
# Sakkizinchi kuni sikl yangidan boshlanadi.
# Kunlik mukofot: 1-5 kunlar bittadan, 6-7 kunlar ikkitadan.
DAILY_KEYS = [1, 1, 1, 1, 1, 2, 2]


def next_streak_day(last_s: str | None, streak: int, today: date) -> int:
    """
    Keyingi olishda zanjirning nechanchi kuni bo'ladi.

    YAGONA MANBA. Ilgari bu hisob ikki joyda alohida yozilgan edi —
    mukofot berishda va vazifalar ekranida — va ular bir-biriga
    to'g'ri kelmasdi. 7-kun olingandan keyin ekranda "8-kun, +3 kalit"
    deb turar, server esa zanjirni noldan boshlab 1 kalit berardi.
    Ya'ni o'yinchiga va'da qilingan narsa berilmasdi.
    """
    last = None
    if last_s:
        try:
            last = date.fromisoformat(last_s)
        except ValueError:
            last = None
    # Zanjir faqat KECHA olingan bo'lsa va sikl tugamagan bo'lsa davom etadi
    if last and (today - last).days == 1 and 0 < streak < len(DAILY_KEYS):
        return streak + 1
    return 1
CHANNEL_KEYS = 5

# Taklif tizimi: har REF_PER do'st uchun REF_KEYS kalit.
REF_PER = 3
REF_KEYS = 5
# Taklif faqat shuncha soniya ichida yaratilgan yangi yozuvga tegishli
REF_NEW_WINDOW = 300

# Telegram Stars bilan sotib olish: STARS_PRICE yulduzga STARS_KEYS kalit.
# Valyuta "XTR" — Stars uchun provider_token TALAB QILINMAYDI va bo'sh
# qoldiriladi (oddiy to'lovlardan asosiy farqi shu).
STARS_KEYS = 10
STARS_PRICE = 10
CHANNEL = os.getenv("CHANNEL_USERNAME", "@apexwords").strip()

# Indeks ALOHIDA turadi va migratsiyadan KEYIN yaratiladi.
# SCHEMA ichida qoldirilsa, eski (score ustunisiz) bazada
# "no such column: score" xatosi chiqadi va bot umuman ishga tushmaydi —
# ya'ni haqiqiy o'yinchilari bor baza buziladi.
INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_players_score ON players(score DESC)"

# Reytingda ko'rsatiladigan o'yinchilar soni
TOP_LIMIT = 100

# Guruh/kanal reytingi uchun bazadan olinadigan o'yinchilar soni.
# TOP_LIMIT dan kattaroq: kichik guruhdagi a'zo umumiy jadvalda
# 100-o'rindan pastda bo'lishi mumkin, lekin guruhda birinchi bo'lishi.
SCAN_LIMIT = 500

MEDALS = ("🥇", "🥈", "🥉")

# Bo'tning havolasi. Ishga tushishda haqiqiy username bilan almashtiriladi;
# inline javoblarda har safar bot.me() ga murojaat qilmaslik uchun.
BOT_LINK = "https://t.me/ApexWordsBot"

# Mini App'ning to'g'ridan-to'g'ri havolasi (BotFather -> /newapp qisqa nomi).
# Guruh va inline tugmalarida shu ishlatiladi.
MINIAPP_SHORT = os.getenv("MINIAPP_SHORT", "Play").strip()
MINIAPP_LINK = f"{BOT_LINK}/{MINIAPP_SHORT}"

# Telegram'dan qaysi turdagi yangilanishlar so'raladi.
#
# ATAYLAB qo'lda yozilgan. aiogram bu ro'yxatni ishlovchilardan o'zi
# hisoblaydi, lekin natijasi ko'rinmaydi va inline undan tushib qolsa
# Telegram inline so'rovlarni UMUMAN yubormaydi — tashqaridan bu
# "bot chiqmayapti" bo'lib ko'rinadi, sababi esa hech qayerda bilinmaydi.
# Ro'yxatni qo'lda berib, logga chiqaramiz: shubha qolmaydi.
ALLOWED_UPDATES = [
    "message",
    "channel_post",          # kanalda /top ishlashi uchun
    "chat_member",           # qo'shilish/chiqishni darhol bilish uchun
    "pre_checkout_query",    # Stars to'lovi busiz bekor bo'ladi
    "callback_query",
    "inline_query",
    "chosen_inline_result",
    "my_chat_member",
]

# Guruh reytingi uchun nechta yuqori o'yinchi tekshiriladi.
# Har biri uchun Telegram'ga alohida so'rov ketadi, shuning uchun son
# cheklangan — aks holda katta bazada javob sekinlashadi.
# Guruh reytingi uchun umumiy ro'yxatdan nechta o'yinchi tekshiriladi.
# Ko'paytirildi (60 -> 250): ilgari 61-o'rindagi guruh a'zosi umuman
# ko'rinmasdi. Tekshiruvlar keshlanadi va sekin yuboriladi, shuning
# uchun bu javob vaqtiga sezilarli ta'sir qilmaydi.
GROUP_SCAN_LIMIT = 250

# Bir vaqtda nechta so'rov. Telegram sekundiga ~30 tadan ko'pini
# qabul qilmaydi; beshta bir vaqtda xavfsiz chegara.
GROUP_SCAN_CONCURRENCY = 5

# Kanaldagi jonli reyting: shuncha soniyada bir yangilanadi va shuncha
# marta takrorlanadi (30 s × 60 = yarim soat). Cheksiz emas — aks holda
# har /top dan keyin abadiy ishlaydigan vazifa qolib ketardi.
LIVE_EVERY = 30
LIVE_TICKS = 60
_live_boards: dict[int, asyncio.Task] = {}

# A'zolik natijasi shuncha soniya eslab qolinadi.
#
# IJOBIY va SALBIY javob uchun muddat HAR XIL, va bu ataylab.
# Ilgari ikkalasi ham 600 soniya edi va aynan shu xatoga olib kelardi:
# odam /top dan keyin kanalga qo'shilsa, "a'zo emas" javobi o'n
# daqiqagacha keshda turar, u esa ro'yxatda umuman ko'rinmasdi.
# Qo'shilish — tez-tez bo'ladigan va kutilgan hodisa, chiqib ketish
# esa kamdan-kam. Shuning uchun "yo'q" javobi qisqa muddat saqlanadi.
MEMBER_TTL = 600          # "a'zo" — uzoq
MEMBER_TTL_NEG = 45       # "a'zo emas" — qisqa
_member_cache: dict[tuple[int, int], tuple[bool, float]] = {}


# Bazaga nechta doimiy ulanish ochiladi.
#
# WAL rejimida SQLite bir vaqtda KO'P O'QUVCHI va bitta yozuvchini
# qo'llaydi, shuning uchun bir nechta ulanish o'qishni parallellashtiradi.
# To'rtta — kichik konteyner uchun muvozanatli son: ko'proq ochish
# yozuvchi navbatini uzaytiradi, foyda bermaydi.
# Ulanishlar soni.
#
# WAL rejimida O'QISHLAR bir-biriga to'sqinlik qilmaydi, yozuv esa
# baribir navbatga turadi. Ilova so'rovlarining ko'pchiligi o'qish
# (/api/state, /api/top, /api/tasks), shuning uchun ulanish ko'proq
# bo'lsa ular parallel ketadi. Cheksiz oshirishning ma'nosi yo'q:
# har ulanish alohida oqim (thread) ochadi.
POOL_SIZE = int(os.getenv("DB_POOL", "8"))


class DB:
    def __init__(self, path: str):
        self.path = path
        self._pool: asyncio.Queue | None = None

    async def _open(self):
        """
        Bitta tayyor ulanish ochadi.

        PRAGMA lar HAR ULANISHDA qayta qo'yiladi — ular ulanishga tegishli,
        faylga emas (journal_mode bundan mustasno, u faylda saqlanadi).
          busy_timeout — yozuvchi band bo'lsa xato o'rniga kutadi
          synchronous=NORMAL — WAL bilan xavfsiz va ancha tez
        """
        conn = await aiosqlite.connect(self.path)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.commit()
        return conn

    @asynccontextmanager
    async def conn(self):
        """
        Havzadan ulanish oladi va qaytaradi.

        Ilgari HAR SO'ROVDA yangi ulanish ochilardi. Yuk sinovi buni
        aniq ko'rsatdi: 50 ta bir vaqtdagi o'yinchida javob sekinlashib,
        100 tada xatolar boshlanardi, /api/state mediana 9 soniyaga
        chiqardi. Ulanish ochish — fayl ochish va alohida oqim yaratish
        demak, ya'ni eng qimmat qism aynan shu edi.
        """
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            self._pool.put_nowait(conn)

    async def init(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.executescript(SCHEMA)
            await self._migrate(db)      # yetishmayotgan ustunlarni qo'shadi
            await db.execute(INDEX_SQL)  # keyin indeks — ustun endi mavjud
            await db.commit()

        # Doimiy ulanishlar havzasi
        self._pool = asyncio.Queue()
        for _ in range(POOL_SIZE):
            self._pool.put_nowait(await self._open())

    async def close(self):
        """
        Havzadagi ulanishlarni yopadi.

        Har ulanish o'z OQIMIDA ishlaydi va u daemon emas — yopilmasa
        jarayon tugamaydi. Sinovlarda buni sezdik: hamma test o'tgan
        bo'lsa ham skript qaytmay osilib qolardi.
        """
        if not self._pool:
            return
        while not self._pool.empty():
            conn = self._pool.get_nowait()
            try:
                await conn.close()
            except Exception:
                pass
        self._pool = None
        if self.path.startswith("/data"):
            log.info("📁 Baza DOIMIY diskda: %s", self.path)
        elif Path("/data").is_dir():
            # Volume ulangan, lekin baza boshqa joyga yozilyapti. Deyarli har doim
            # bu DB_PATH ga nisbiy yo'l qo'yilgani uchun bo'ladi.
            log.error("❌ Volume /data ga ULANGAN, lekin baza boshqa joyda: %s\n"
                      "   Sabab: DB_PATH o'zgaruvchisi shu yo'lni ko'rsatyapti.\n"
                      "   Yechim: Railway Variables dan DB_PATH ni O'CHIRING "
                      "(kod /data ni o'zi topadi), yoki uni /data/apex_words.db "
                      "qilib yozing.\n"
                      "   Hozircha har deployda o'yinchilar progressi o'chadi.",
                      self.path)
        else:
            log.warning("⚠️  Baza VAQTINCHALIK diskda: %s — qayta deploy qilinganda "
                        "o'yinchilar progressi o'chadi. Railway'da servisga Volume "
                        "ulab, uni /data ga joylashtiring.", self.path)

    @staticmethod
    async def _migrate(db):
        """
        Eski bazaga yangi ustunlarni qo'shadi.

        CREATE TABLE IF NOT EXISTS mavjud jadvalni o'zgartirmaydi, shuning uchun
        reyting qo'shilgandan keyin ishga tushgan eski bazalarda photo_url va
        score ustunlari bo'lmaydi va har so'rov xato beradi.
        """
        async with db.execute("PRAGMA table_info(players)") as cur:
            cols = {row[1] for row in await cur.fetchall()}
        if "photo_url" not in cols:
            await db.execute("ALTER TABLE players ADD COLUMN photo_url TEXT")
            log.info("Bazaga photo_url ustuni qo'shildi")
        if "score" not in cols:
            await db.execute("ALTER TABLE players ADD COLUMN score INTEGER NOT NULL DEFAULT 0")
            log.info("Bazaga score ustuni qo'shildi")

        for name, ddl in (
            ("last_daily", "ALTER TABLE players ADD COLUMN last_daily TEXT"),
            ("streak_day", "ALTER TABLE players ADD COLUMN streak_day INTEGER NOT NULL DEFAULT 0"),
            ("channel_ok", "ALTER TABLE players ADD COLUMN channel_ok INTEGER NOT NULL DEFAULT 0"),
            ("ref_by", "ALTER TABLE players ADD COLUMN ref_by INTEGER"),
            ("ref_count", "ALTER TABLE players ADD COLUMN ref_count INTEGER NOT NULL DEFAULT 0"),
            ("ref_paid", "ALTER TABLE players ADD COLUMN ref_paid INTEGER NOT NULL DEFAULT 0"),
            ("pend_keys", "ALTER TABLE players ADD COLUMN pend_keys INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in cols:
                await db.execute(ddl)
                log.info("Bazaga %s ustuni qo'shildi", name)

        # Ustun 0 bilan qo'shiladi, eski o'yinchilarning ballari esa progress
        # JSON ichida turibdi. Ko'chirilmasa, ular keyingi safar o'ynab
        # saqlamaguncha reytingda umuman ko'rinmaydi.
        try:
            cur = await db.execute(
                "UPDATE players "
                "SET score = CAST(COALESCE(json_extract(progress, '$.coins'), 0) AS INTEGER) "
                "WHERE score = 0 AND progress IS NOT NULL AND progress != '{}'"
            )
            if cur.rowcount > 0:
                log.info("Reyting ballari progressdan ko'chirildi: %d o'yinchi", cur.rowcount)
        except Exception as e:
            # JSON1 kengaytmasi bo'lmasa qo'lda o'qib chiqamiz
            log.warning("json_extract ishlamadi (%s), qo'lda ko'chirilmoqda", e)
            async with db.execute(
                "SELECT user_id, progress FROM players WHERE score = 0"
            ) as c:
                rows = await c.fetchall()
            for uid, raw in rows:
                try:
                    coins = int(json.loads(raw or "{}").get("coins", 0))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if coins > 0:
                    await db.execute("UPDATE players SET score=? WHERE user_id=?",
                                     (coins, uid))

    async def get_progress(self, user: dict) -> dict:
        uid = user["id"]
        now = int(time.time())
        async with self.conn() as db:
            async with db.execute(
                "SELECT progress, username, first_name, photo_url "
                "FROM players WHERE user_id = ?", (uid,)
            ) as cur:
                row = await cur.fetchone()
            if row:
                # Ism va rasm FAQAT O'ZGARGANDA yangilanadi.
                #
                # Ilgari har kirishda UPDATE + commit ketardi. Bu eng
                # ko'p chaqiriladigan so'rov (/api/state) va o'sha yozuv
                # deyarli har doim keraksiz edi: ism kamdan-kam
                # o'zgaradi. SQLite'da yozuv navbatga turadi — ya'ni bu
                # bitta keraksiz yozuv boshqa o'yinchilarni ham kutdirardi.
                if (row[1], row[2], row[3]) != (user.get("username"),
                                                user.get("first_name"),
                                                user.get("photo_url")):
                    await db.execute(
                        "UPDATE players SET username=?, first_name=?, "
                        "photo_url=?, updated_at=? WHERE user_id=?",
                        (user.get("username"), user.get("first_name"),
                         user.get("photo_url"), now, uid),
                    )
                    await db.commit()
                try:
                    return json.loads(row[0]) or {}
                except json.JSONDecodeError:
                    return {}

            await db.execute(
                "INSERT INTO players (user_id, username, first_name, photo_url, "
                "progress, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (uid, user.get("username"), user.get("first_name"),
                 user.get("photo_url"), "{}", now, now),
            )
            await db.commit()
            return {}

    async def save_progress(self, uid: int, progress: dict):
        # Ball alohida ustunda saqlanadi: reytingni JSON ichidan qidirib emas,
        # indeks bo'yicha saralab olish uchun.
        score = plausible_score(progress)
        async with self.conn() as db:
            await db.execute(
                "UPDATE players SET progress=?, score=?, updated_at=? WHERE user_id=?",
                (json.dumps(progress, ensure_ascii=False), score, int(time.time()), uid),
            )
            await db.commit()

    async def task_state(self, uid: int) -> dict:
        """Vazifalar bo'limi uchun holat."""
        # Bitta so'rov: ilgari zanjir uchun alohida, taklif hisobi uchun
        # alohida so'rov ketardi — bir xil qatordan.
        async with self.conn() as db:
            async with db.execute(
                "SELECT last_daily, streak_day, channel_ok, ref_count "
                "FROM players WHERE user_id=?", (uid,),
            ) as cur:
                row = await cur.fetchone()
        last, streak, ch, ref_count = row if row else (None, 0, 0, 0)
        ref_count = ref_count or 0
        ref_left = REF_PER - (ref_count % REF_PER)
        today_d = date.today()
        today = today_d.isoformat()
        nxt = next_streak_day(last, streak or 0, today_d)
        return {
            "ref_count": ref_count,
            "ref_left": ref_left,
            "ref_per": REF_PER,
            "ref_keys": REF_KEYS,
            "ref_link": f"{BOT_LINK}?start=ref_{uid}",
            "streak": streak or 0,
            "claimed_today": last == today,
            # Keyingi kun ham, mukofot ham SERVER hisoblaydi va mijoz
            # shuni ko'rsatadi — ikki tomonda alohida hisoblanганda
            # ular bir-biriga to'g'ri kelmay qolardi.
            "next_day": nxt,
            "next_keys": DAILY_KEYS[nxt - 1],
            "channel_done": bool(ch),
            "channel_keys": CHANNEL_KEYS,
            "plan": DAILY_KEYS,
        }

    async def claim_daily(self, uid: int) -> dict:
        """
        Kunlik mukofotni beradi.

        Kun chegarasi SERVER vaqti bo'yicha hisoblanadi — telefon soatini
        o'zgartirib bir kunda bir necha marta olishning oldi olinadi.
        """
        today = date.today()
        async with self.conn() as db:
            async with db.execute(
                "SELECT last_daily, streak_day FROM players WHERE user_id=?", (uid,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return {"error": "no player"}

            last_s, streak = row[0], row[1] or 0
            if last_s == today.isoformat():
                return {"already": True, "streak": streak}

            # Kecha olingan bo'lsa zanjir davom etadi, aks holda uziladi.
            # Hisob task_state bilan BIR XIL funksiyadan olinadi.
            streak = next_streak_day(last_s, streak, today)
            keys = DAILY_KEYS[streak - 1]
            await db.execute(
                "UPDATE players SET last_daily=?, streak_day=?, updated_at=? WHERE user_id=?",
                (today.isoformat(), streak, int(time.time()), uid),
            )
            await db.commit()
        return {"ok": True, "streak": streak, "keys": keys}

    async def add_referral(self, new_uid: int, ref_uid: int) -> dict:
        """
        Taklifni qayd etadi va kerak bo'lsa mukofot yozib qo'yadi.

        Mukofot DARHOL berilmaydi: kalitlar soni progress JSON ichida,
        mijozda saqlanadi. Shuning uchun server "kutayotgan kalit"ni
        pend_keys ustuniga yozadi, Mini App esa ochilganda uni oladi.

        Qaytadi: {"ok": bool, "count": int, "granted": int}
        """
        if new_uid == ref_uid:
            return {"ok": False, "reason": "self"}

        async with self.conn() as db:
            # Taklif qiluvchi bazada bormi
            async with db.execute(
                "SELECT 1 FROM players WHERE user_id=?", (ref_uid,)
            ) as cur:
                if not await cur.fetchone():
                    return {"ok": False, "reason": "no_referrer"}

            # Bir odam faqat BIR MARTA hisoblanadi. Aks holda havolani
            # qayta-qayta bosib cheksiz kalit yig'sa bo'lardi.
            async with db.execute(
                "SELECT ref_by, created_at FROM players WHERE user_id=?", (new_uid,)
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                return {"ok": False, "reason": "no_player"}
            if row[0] is not None:
                return {"ok": False, "reason": "already"}

            now = int(time.time())
            # FAQAT YANGI o'yinchi hisoblanadi. Busiz allaqachon o'ynab
            # yurgan odamga havola yuborib ham mukofot olsa bo'lardi —
            # taklif esa yangi o'yinchi olib kelgani uchun beriladi.
            # Yozuv /start ishlovchisida shu zahoti yaratiladi, shuning
            # uchun haqiqiy yangi o'yinchi bu oynadan chiqib ketmaydi.
            if now - (row[1] or 0) > REF_NEW_WINDOW:
                return {"ok": False, "reason": "not_new"}
            await db.execute(
                "UPDATE players SET ref_by=?, updated_at=? WHERE user_id=?",
                (ref_uid, now, new_uid),
            )
            await db.execute(
                "UPDATE players SET ref_count=ref_count+1, updated_at=? WHERE user_id=?",
                (now, ref_uid),
            )
            async with db.execute(
                "SELECT ref_count, ref_paid FROM players WHERE user_id=?", (ref_uid,)
            ) as cur:
                count, paid = await cur.fetchone()

            # Har REF_PER do'stga bir marta to'lanadi. Sikl ishlatilgan:
            # eski bazada bir nechta to'lanmagan bosqich qolgan bo'lishi mumkin.
            granted = 0
            while count - paid >= REF_PER:
                paid += REF_PER
                granted += REF_KEYS
            if granted:
                await db.execute(
                    "UPDATE players SET ref_paid=?, pend_keys=pend_keys+?, "
                    "updated_at=? WHERE user_id=?",
                    (paid, granted, now, ref_uid),
                )
            await db.commit()
        return {"ok": True, "count": count, "granted": granted}

    async def grant_keys(self, uid: int, n: int):
        """
        Kalitni "kutayotgan" ro'yxatga qo'shadi.

        To'lov bo'tga keladi, kalit esa Mini App ichida saqlanadi —
        shuning uchun server uni to'g'ridan-to'g'ri bera olmaydi.
        Taklif mukofoti bilan bir xil yo'l: pend_keys, keyin
        /api/claim-keys.
        """
        async with self.conn() as db:
            await db.execute(
                "UPDATE players SET pend_keys=pend_keys+?, updated_at=? "
                "WHERE user_id=?", (n, int(time.time()), uid))
            await db.commit()

    async def record_payment(self, charge_id: str, uid: int, stars: int,
                             keys: int) -> bool:
        """
        To'lovni yozadi. True — BIRINCHI marta, False — takror.

        INSERT OR IGNORE bilan: charge_id birlamchi kalit bo'lgani uchun
        takroriy yetkazib berish jimgina rad etiladi.
        """
        async with self.conn() as db:
            cur = await db.execute(
                "INSERT OR IGNORE INTO payments "
                "(charge_id, user_id, stars, keys, created_at) "
                "VALUES (?,?,?,?,?)",
                (charge_id, uid, stars, keys, int(time.time())))
            await db.commit()
            return cur.rowcount > 0

    async def last_payment(self, uid: int) -> tuple | None:
        """O'yinchining oxirgi qaytarilmagan to'lovi."""
        async with self.conn() as db:
            async with db.execute(
                "SELECT charge_id, stars, keys FROM payments "
                "WHERE user_id=? AND refunded=0 ORDER BY created_at DESC LIMIT 1",
                (uid,)
            ) as cur:
                return await cur.fetchone()

    async def mark_refunded(self, charge_id: str):
        async with self.conn() as db:
            await db.execute("UPDATE payments SET refunded=1 WHERE charge_id=?",
                             (charge_id,))
            await db.commit()

    async def ref_state(self, uid: int) -> tuple[int, int]:
        """(nechta do'st taklif qilingan, keyingi mukofotgacha nechta qoldi)"""
        async with self.conn() as db:
            async with db.execute(
                "SELECT ref_count FROM players WHERE user_id=?", (uid,)
            ) as cur:
                row = await cur.fetchone()
        count = (row[0] if row else 0) or 0
        return count, REF_PER - (count % REF_PER)

    async def take_pending_keys(self, uid: int) -> int:
        """
        Kutayotgan kalitlarni beradi va hisobni nolga tushiradi.

        O'qish va nolga tushirish BITTA yozuv tranzaksiyasi ichida ketadi.
        BEGIN IMMEDIATE darhol yozuv qulfini oladi, shuning uchun ikkita
        qurilma bir vaqtda ochilsa ham kalit ikki marta berilmaydi:
        ikkinchisi birinchisini kutadi va noldan boshqa narsa ko'rmaydi.
        """
        async with self.conn() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute(
                    "SELECT pend_keys FROM players WHERE user_id=?", (uid,)
                ) as cur:
                    row = await cur.fetchone()
                keys = (row[0] if row else 0) or 0
                if keys:
                    await db.execute(
                        "UPDATE players SET pend_keys=0, updated_at=? WHERE user_id=?",
                        (int(time.time()), uid),
                    )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        return keys

    async def claim_channel(self, uid: int) -> bool:
        """Kanal mukofotini bir marta belgilaydi. True — endi berildi."""
        async with self.conn() as db:
            async with db.execute(
                "SELECT channel_ok FROM players WHERE user_id=?", (uid,)
            ) as cur:
                row = await cur.fetchone()
            if not row or row[0]:
                return False
            await db.execute(
                "UPDATE players SET channel_ok=1, updated_at=? WHERE user_id=?",
                (int(time.time()), uid),
            )
            await db.commit()
        return True

    # Reyting keshi: (vaqt, ro'yxat). Har so'rovda baza qayta o'qilmasin.
    _top_cache: tuple[float, list] | None = None
    _TOP_TTL = 20.0        # soniya

    async def top_rows(self) -> list:
        """
        Eng yuqori ballli o'yinchilar. Natija qisqa muddatga keshlanadi.

        Reyting hamma uchun BIR XIL, shuning uchun uni har so'rovda
        bazadan o'qishning ma'nosi yo'q. Yigirma soniyalik kesh javobni
        bir zumda qaytaradi va ro'yxat baribir deyarli jonli qoladi.
        """
        now = time.monotonic()
        if self._top_cache and now - self._top_cache[0] < self._TOP_TTL:
            return self._top_cache[1]

        async with self.conn() as db:
            async with db.execute(
                "SELECT first_name, photo_url, score, user_id FROM players "
                "WHERE score > 0" + _ADMIN_SQL +
                " ORDER BY score DESC, updated_at ASC LIMIT ?",
                (TOP_LIMIT,),
            ) as cur:
                rows = await cur.fetchall()
        self._top_cache = (now, rows)
        return rows

    _scan_cache: tuple[float, list] | None = None

    async def scan_rows(self) -> list:
        """
        Guruh/kanal reytingi uchun kengroq ro'yxat.

        top_rows() faqat TOP_LIMIT (100) tani beradi. Guruh reytingi
        o'sha ro'yxatdan qidirgani uchun umumiy jadvalda 100-o'rindan
        pastdagi a'zo HECH QACHON ko'rinmasdi — guruh kichik bo'lsa ham.
        Bu yerda chegara kengroq: skanerlash baribir GROUP_SCAN_LIMIT
        bilan cheklanadi.
        """
        now = time.monotonic()
        if self._scan_cache and now - self._scan_cache[0] < self._TOP_TTL:
            return self._scan_cache[1]
        async with self.conn() as db:
            async with db.execute(
                "SELECT first_name, photo_url, score, user_id FROM players "
                "WHERE score > 0" + _ADMIN_SQL +
                " ORDER BY score DESC, updated_at ASC LIMIT ?",
                (SCAN_LIMIT,),
            ) as cur:
                rows = await cur.fetchall()
        self._scan_cache = (now, rows)
        return rows

    def invalidate_top(self):
        self._top_cache = None
        self._scan_cache = None

    async def leaderboard(self, uid: int) -> dict:
        """
        Eng yuqori ballli TOP_LIMIT o'yinchi va so'rovchining o'z o'rni.

        Tashqariga faqat ism, rasm va ball chiqadi — user_id va username emas.
        """
        rows = await self.top_rows()          # keshdan, deyarli bir zumda

        # O'z bali va o'rni BITTA so'rovda.
        #
        # Ilgari ikkita alohida so'rov ketardi: avval ball, keyin undan
        # yuqoridagilar soni. Reyting eng ko'p ochiladigan bo'limlardan
        # biri, shuning uchun bu tejash sezilarli.
        #
        # Adminlar sanalmaydi — aks holda ko'rsatilgan raqam ro'yxatdagi
        # haqiqiy joyga to'g'ri kelmay qolardi.
        async with self.conn() as db:
            async with db.execute(
                "WITH me AS (SELECT COALESCE(MAX(score), 0) AS s FROM players "
                "            WHERE user_id=?) "
                "SELECT me.s, (SELECT COUNT(*) FROM players "
                "              WHERE score > me.s" + _ADMIN_SQL + ") FROM me",
                (uid,)
            ) as cur:
                my_score, above = await cur.fetchone()
            my_rank = above + 1

        top = [
            {
                "rank": i + 1,
                "name": (name or "Player")[:32],
                "photo": photo or "",
                "score": score,
                "me": row_uid == uid,
            }
            for i, (name, photo, score, row_uid) in enumerate(rows)
        ]
        return {"top": top, "me": {"rank": my_rank, "score": my_score}}

    async def stats(self) -> tuple[int, int]:
        async with self.conn() as db:
            async with db.execute("SELECT COUNT(*) FROM players") as cur:
                total = (await cur.fetchone())[0]
            day = int(time.time()) - 86400
            async with db.execute(
                "SELECT COUNT(*) FROM players WHERE updated_at > ?", (day,)
            ) as cur:
                active = (await cur.fetchone())[0]
        return total, active


db = DB(DB_PATH)


# ---------------------------------- API --------------------------------------

async def api_state(request: web.Request) -> web.Response:
    """Mini App ochilganda progressni qaytaradi."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)

    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    progress = await db.get_progress(user)
    return web.json_response({
        "progress": progress or None,
        # Kalit chegarasi shu bayroqqa qarab olib tashlanadi
        "unlimited": user["id"] in UNLIMITED_HINTS,
        # Admin: barcha bosqichlar ochiq
        "admin": user["id"] in ADMINS,
    })


# So'rov chastotasi chegarasi.
#
# Imzo tekshiruvi "bu kim" degan savolga javob beradi, "u qancha
# so'rasin" degan savolga emas. Bitta buzilgan yoki yomon yozilgan
# mijoz sekundiga yuzlab saqlash yuborib butun serverni band qila
# olardi — barcha o'yinchilar uchun.
#
# Oddiy token-chelak: har o'yinchiga RATE_BURST ta zaxira, sekundiga
# RATE_PER_SEC ta to'ldiriladi. Halol o'yin 25 soniyada bitta saqlash
# yuboradi, shuning uchun chegara sezilmaydi.
RATE_PER_SEC = 3.0
RATE_BURST = 30.0
_buckets: dict[int, tuple[float, float]] = {}


def rate_ok(uid: int) -> bool:
    now = time.monotonic()
    tokens, last = _buckets.get(uid, (RATE_BURST, now))
    tokens = min(RATE_BURST, tokens + (now - last) * RATE_PER_SEC)
    if tokens < 1.0:
        _buckets[uid] = (tokens, now)
        return False
    _buckets[uid] = (tokens - 1.0, now)

    # Kesh cheksiz o'smasin: uzoq vaqt so'ramaganlar tashlanadi
    if len(_buckets) > 20_000:
        cutoff = now - 300
        for k in [k for k, (_, t) in _buckets.items() if t < cutoff]:
            _buckets.pop(k, None)
    return True


async def api_save(request: web.Request) -> web.Response:
    """Progressni saqlaydi."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)

    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    if not rate_ok(user["id"]):
        return web.json_response({"error": "too many requests"}, status=429)

    progress = body.get("progress")
    if not isinstance(progress, dict):
        return web.json_response({"error": "bad progress"}, status=400)

    # Cheksiz o'sib ketmasligi uchun chegara (learned ro'yxati kattalashadi)
    if len(json.dumps(progress)) > 200_000:
        return web.json_response({"error": "too large"}, status=413)

    await db.save_progress(user["id"], progress)
    return web.json_response({"ok": True})


async def api_top(request: web.Request) -> web.Response:
    """TOP 100 o'yinchi va so'rovchining o'z o'rni."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)

    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    return web.json_response(await db.leaderboard(user["id"]))


async def api_tasks(request: web.Request) -> web.Response:
    """Vazifalar bo'limining holati."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)
    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response(await db.task_state(user["id"]))


async def api_claim_daily(request: web.Request) -> web.Response:
    """Kunlik kalitlarni beradi."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)
    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response(await db.claim_daily(user["id"]))


async def api_claim_keys(request: web.Request) -> web.Response:
    """
    Taklif uchun kutayotgan kalitlarni beradi.

    Kalitlar soni progress ichida, MIJOZDA saqlanadi. Bot esa do'st
    qo'shilganini server tomonda biladi. Shuning uchun mukofot avval
    pend_keys ga yoziladi, Mini App ochilganda esa shu yerdan olinadi
    va progressga qo'shiladi.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)
    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response({"keys": await db.take_pending_keys(user["id"])})


async def api_buy_hints(request: web.Request) -> web.Response:
    """
    Stars bilan kalit sotib olish uchun hisob-faktura havolasi.

    Mini App bu havolani TG.openInvoice ga beradi. To'lov Telegram
    tomonda o'tadi, kalit esa successful_payment kelganda beriladi —
    ya'ni mijoz "to'ladim" desa emas, TELEGRAM tasdiqlasa.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)
    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    bot = request.app["bot"]
    if bot is None:
        return web.json_response({"error": "unavailable"}, status=503)

    try:
        link = await bot.create_invoice_link(
            title=f"{STARS_KEYS} hint keys",
            description=f"{STARS_KEYS} keys to reveal letters in Apex Words.",
            payload=f"keys:{STARS_KEYS}:{user['id']}",
            currency="XTR",
            # Stars uchun provider_token bo'sh bo'lishi SHART
            provider_token="",
            prices=[LabeledPrice(label=f"{STARS_KEYS} keys",
                                 amount=STARS_PRICE)],
        )
    except Exception as e:
        log.warning("Hisob-faktura yaratilmadi: %s", e)
        return web.json_response({"error": "invoice_failed"}, status=502)

    return web.json_response({"link": link, "keys": STARS_KEYS,
                              "stars": STARS_PRICE})


async def api_claim_channel(request: web.Request) -> web.Response:
    """
    Kanalga a'zolikni tekshiradi va bir marta kalit beradi.

    A'zolik Telegram'dan SO'RALADI — mijozga ishonib bo'lmaydi, aks holda
    kanalga qo'shilmasdan ham mukofot olinardi.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)
    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

    bot = request.app["bot"]
    if bot is None:
        return web.json_response({"error": "check_failed"}, status=503)
    try:
        member = await bot.get_chat_member(CHANNEL, user["id"])
        joined = member.status in ("creator", "administrator", "member")
    except Exception as e:
        # Bot kanalda admin bo'lmasa tekshirib bo'lmaydi — sababni logga yozamiz
        log.warning("Kanal a'zoligini tekshirib bo'lmadi (%s): %s", CHANNEL, e)
        return web.json_response({"error": "check_failed"}, status=503)

    if not joined:
        return web.json_response({"joined": False})

    granted = await db.claim_channel(user["id"])
    return web.json_response({"joined": True, "granted": granted,
                              "keys": CHANNEL_KEYS if granted else 0})


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})


@web.middleware
async def no_cache(request: web.Request, handler):
    """
    Statik fayllarga keshlash qoidasini MAJBURAN qo'yadi.

    aiohttp'ning add_static() faqat ETag va Last-Modified yuboradi,
    Cache-Control esa umuman qo'yilmaydi. Bunday javobni brauzer va ayniqsa
    Telegram WebView "evristik keshlash" bilan o'zicha, ba'zan bir necha
    kunga saqlab qo'yadi va qayta so'ramaydi. Natijada yangi deploy
    o'yinchiga umuman yetib bormaydi — ?v=N ni oshirish ham yordam bermaydi,
    chunki eski index.html o'zi keshda qolib, eski ?v= ni ko'rsatib turaveradi.

    Shuning uchun:
      HTML          -> no-store  (hech qachon saqlanmasin)
      qolgan fayllar-> no-cache  (saqlansa ham, har safar ETag bilan
                                  tekshirilsin; o'zgarmagan bo'lsa 304 keladi)
    """
    resp = await handler(request)
    path = request.path.lower()
    if path.endswith(".html") or path in ("/", ""):
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    elif not path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-cache, must-revalidate")
    return resp


def make_app(bot=None) -> web.Application:
    app = web.Application(middlewares=[no_cache])
    # Kanal a'zoligini tekshirish uchun API'ga bot kerak
    app["bot"] = bot
    app.router.add_get("/health", health)
    app.router.add_post("/api/state", api_state)
    app.router.add_post("/api/save", api_save)
    app.router.add_post("/api/top", api_top)
    app.router.add_post("/api/tasks", api_tasks)
    app.router.add_post("/api/claim-daily", api_claim_daily)
    app.router.add_post("/api/claim-channel", api_claim_channel)
    app.router.add_post("/api/claim-keys", api_claim_keys)
    app.router.add_post("/api/buy-hints", api_buy_hints)
    app.router.add_get("/", index)
    app.router.add_static("/", WEB_DIR, show_index=False)
    return app


# ---------------------------------- Bot --------------------------------------

dp = Dispatcher()


def html_escape(s: str) -> str:
    """Foydalanuvchi ismi HTML tegi bo'lib ketmasin."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_tag() -> str:
    """
    Har deployda o'zgaradigan qisqa belgi.

    Telegram Mini App'ni QURILMADA keshlaydi va bu keshni server sarlavhalari
    (no-store) har doim ham buzmaydi: ilova o'sha URL uchun eski nusxani
    saqlab qoladi. Natijada yangi dizayn chiqarilsa ham o'yinchi eskisini
    ko'raveradi.

    Yechim — URL'ning o'ziga o'zgaruvchan qism qo'shish. web_app/ ichidagi
    fayllarning eng so'nggi o'zgarish vaqtini olamiz: fayl o'zgarsa belgi
    ham o'zgaradi va Telegram uni butunlay boshqa sahifa deb biladi.
    """
    try:
        newest = max(p.stat().st_mtime for p in WEB_DIR.rglob("*") if p.is_file())
        return str(int(newest))
    except ValueError:
        return "0"


BUILD = build_tag()


def play_url() -> str:
    sep = "&" if "?" in WEBAPP_URL else "?"
    return f"{WEBAPP_URL}{sep}b={BUILD}"


def play_keyboard() -> InlineKeyboardMarkup | None:
    """Shaxsiy chat uchun: Mini App'ni to'g'ridan-to'g'ri ochadigan tugma."""
    if not WEBAPP_URL.startswith("https://"):
        return None      # Telegram WebApp tugmasi faqat https bilan ishlaydi
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎮 Play", web_app=WebAppInfo(url=play_url()))
    ]])


def link_keyboard() -> InlineKeyboardMarkup:
    """
    Guruh va inline natijalar uchun tugma.

    web_app turidagi tugma FAQAT shaxsiy chatda ishlaydi. Guruhga yoki
    inline natijaga qo'yilsa Telegram xabarni butunlay rad etadi
    (BUTTON_TYPE_INVALID) — ya'ni javob umuman ko'rinmaydi. Shuning
    uchun bu yerda oddiy havola tugmasi ishlatiladi: u Mini App'ning
    to'g'ridan-to'g'ri manziliga olib boradi va hamma joyda ishlaydi.
    """
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎮 Play Apex Words", url=MINIAPP_LINK)
    ]])


def _user_row(u) -> dict:
    return {"id": u.id, "username": u.username, "first_name": u.first_name,
            "photo_url": None}


async def handle_referral(message: Message, payload: str):
    """
    /start ref_<id> havolasini qayta ishlaydi.

    Taklif SHU YERDA hisoblanadi, Mini App'da emas: havolani bosgan
    odam o'yinni umuman ochmasligi ham mumkin, lekin bo'tga kirgani
    aniq. Mukofot esa taklif QILUVCHIga tegadi.
    """
    if not payload.startswith("ref_"):
        return
    try:
        ref_uid = int(payload[4:])
    except ValueError:
        return

    me = message.from_user
    await db.get_progress(_user_row(me))      # yozuv borligiga ishonch
    res = await db.add_referral(me.id, ref_uid)
    if not res.get("ok"):
        return

    # Taklif qiluvchiga xabar beramiz. U bo'tni bloklagan bo'lishi
    # mumkin — bu butun /start ni yiqitmasligi kerak.
    count = res["count"]
    try:
        text = (f"🎉 <b>{html_escape(me.first_name or 'A friend')}</b> "
                f"joined through your link!\n\n"
                f"Invited friends: <b>{count}</b>")
        if res["granted"]:
            text += (f"\n\n🗝️ <b>+{res['granted']} keys</b> are waiting — "
                     "open the game to collect them.")
        else:
            left = REF_PER - (count % REF_PER)
            text += f"\n{left} more to earn <b>{REF_KEYS} 🗝️</b>."
        await message.bot.send_message(ref_uid, text,
                                       reply_markup=play_keyboard())
    except Exception as e:
        log.info("Taklif qiluvchiga xabar bormadi (%s): %s", ref_uid, e)


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # /start har doim ishlaydi va yarim qolgan sehrgarni tozalaydi —
    # aks holda /post ichida qolib ketgan admin chiqib keta olmasdi.
    if await state.get_state():
        _drafts.pop(message.from_user.id, None)
        await state.clear()

    # Havolaning "?start=" qismi: /start ref_12345
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        try:
            await handle_referral(message, parts[1].strip())
        except Exception as e:
            log.warning("Taklifni qayd etib bo'lmadi: %s", e)

    name = message.from_user.first_name or "friend"
    text = (
        f"Hey <b>{name}</b>! 👋\n\n"
        "<b>Apex Words</b> — swipe letters into words and grow your English.\n\n"
        "• Drag across the letters to build a word\n"
        "• Words on the board snap into place\n"
        "• Real words that aren't listed earn a <b>bonus</b>\n"
        "• Tap 💡 on any word you found to see what it means\n"
        "• Collect free keys every day in <b>Rewards</b>\n\n"
        "<b>12 chapters · 60 levels · 3,000 puzzles</b> — from three-letter "
        "warm-ups to nine-letter challenges.\n"
        "Climb the <b>Top 100</b>, or send /top in any group to see who "
        "leads among your friends.\n"
        f"Invite {REF_PER} friends with /invite and get <b>{REF_KEYS} 🗝️</b>."
    )
    kb = play_keyboard()
    if kb:
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(
            text + "\n\n⚠️ WEBAPP_URL is not set to an https address yet — "
            "the play button stays hidden."
        )


# --------------------------- Stars bilan to'lov -------------------------------


@dp.pre_checkout_query()
async def on_pre_checkout(q: PreCheckoutQuery):
    """
    To'lovdan oldingi so'nggi tasdiq.

    Telegram bu so'rovga 10 SONIYA ichida javob kutadi, aks holda
    to'lov bekor bo'ladi. Shuning uchun bu yerda hech qanday og'ir ish
    qilinmaydi — kalit successful_payment kelganda beriladi.
    """
    try:
        await q.answer(ok=True)
    except Exception as e:
        log.warning("pre_checkout javobi ketmadi: %s", e)


@dp.message(lambda m: m.successful_payment is not None)
async def on_paid(message: Message):
    """To'lov o'tdi — kalitlarni yozib qo'yamiz."""
    sp = message.successful_payment
    uid = message.from_user.id

    # Nechta kalit — payload'dan. Payload BIZ yuborgan qiymat, shuning
    # uchun unga ishonsa bo'ladi; baribir eng yomon holatga chegara bor.
    keys = STARS_KEYS
    try:
        parts = (sp.invoice_payload or "").split(":")
        if len(parts) >= 2 and parts[0] == "keys":
            keys = max(1, min(int(parts[1]), 1000))
    except (ValueError, TypeError):
        pass

    await db.get_progress(_user_row(message.from_user))

    # Bir to'lov — bir marta. Telegram xabarni qayta yuborsa, ikkinchi
    # yozuv rad etiladi va kalit takror berilmaydi.
    first = await db.record_payment(
        sp.telegram_payment_charge_id, uid, sp.total_amount, keys)
    if not first:
        log.info("Stars to'lovi TAKROR keldi, e'tiborsiz qoldirildi: %s",
                 sp.telegram_payment_charge_id)
        return

    await db.grant_keys(uid, keys)
    log.info("Stars to'lovi: user=%s stars=%s keys=%s charge=%s",
             uid, sp.total_amount, keys, sp.telegram_payment_charge_id)

    await message.answer(
        f"⭐ Payment received — <b>{keys} 🗝️</b> added.\n"
        "Open the game and they will appear right away.",
        reply_markup=play_keyboard())


@dp.message(Command("refund"), lambda m: m.chat.type == "private")
async def cmd_refund(message: Message):
    """
    Stars to'lovini qaytarish (admin).

    Telegram raqamli tovar sotuvchidan qaytarish imkonini talab qiladi.
    Foydalanish: /refund <user_id> <charge_id>
    """
    if message.from_user.id not in ADMINS:
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.answer(
            "Usage: <code>/refund &lt;user_id&gt;</code>\n"
            "The last payment of that user is refunded. To pick a specific "
            "one: <code>/refund &lt;user_id&gt; &lt;charge_id&gt;</code>")
        return

    uid = int(parts[1])
    if len(parts) >= 3:
        charge, stars, keys = parts[2], None, None
    else:
        # Charge id bazadan olinadi. Ilgari uni logdan qidirishga
        # to'g'ri kelardi, Railway logi esa bir necha kundan keyin o'chadi.
        row = await db.last_payment(uid)
        if not row:
            await message.answer("No refundable payment found for that user.")
            return
        charge, stars, keys = row

    try:
        await message.bot.refund_star_payment(
            user_id=uid, telegram_payment_charge_id=charge)
        await db.mark_refunded(charge)
        extra = f"\n{stars} ⭐ returned ({keys} 🗝️ were granted)." if stars else ""
        await message.answer(f"✅ Refunded.{extra}")
    except Exception as e:
        await message.answer(f"❌ Refund failed.\n\n<code>{html_escape(str(e))}</code>")


# ------------------------ Kanalga post yuborish -------------------------------
#
# Faqat adminlar uchun. Ketma-ketlik:
#   /post @kanal -> matn -> rasm/video yoki /skip -> ko'rib chiqish ->
#   tasdiq -> kanalga ketadi.
#
# TASDIQ BOSQICHI ATAYLAB QO'SHILGAN. Kanalga yuborilgan post ochiq va
# uni orqaga qaytarib bo'lmaydi, shuning uchun oxirgi qadamda admin
# postni AYNAN kanalda ko'rinadigan holida ko'radi va bir marta
# tasdiqlaydi. Adashib yuborilgan post obunachilarga darhol boradi.


class PostFlow(StatesGroup):
    text = FState()
    media = FState()
    confirm = FState()


# Tayyorlangan postlar: admin_id -> {chat, text, media, kind}
_drafts: dict[int, dict] = {}


def _post_kb() -> InlineKeyboardMarkup:
    """Kanaldagi post ostidagi tugma."""
    return link_keyboard()


@dp.message(Command("post"), lambda m: m.chat.type == "private")
async def cmd_post(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in ADMINS:
        return                      # adminlarga tegishli emas — jimgina

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Usage: <code>/post @channel</code>\n\n"
            "Example: <code>/post @ApexWords</code>")
        return

    target = parts[1].strip().split()[0]
    if not target.startswith("@") and not target.lstrip("-").isdigit():
        target = "@" + target

    # Kanal bor va bot u yerga yoza oladimi — DARHOL tekshiramiz.
    # Aks holda xato butun sehrgar oxirida, matn yozilgandan keyin
    # chiqar va mehnat bekorga ketardi.
    try:
        chat = await message.bot.get_chat(target)
    except Exception as e:
        await message.answer(
            f"Can't reach <code>{html_escape(target)}</code>.\n"
            f"Make sure the bot is an admin there.\n\n<code>{html_escape(str(e))}</code>")
        return

    _drafts[uid] = {"chat": chat.id, "title": chat.title or target,
                    "text": "", "media": None, "kind": None}
    await state.set_state(PostFlow.text)
    await message.answer(
        f"📢 Posting to <b>{html_escape(chat.title or target)}</b>\n\n"
        "Send me the <b>post text</b>.\n"
        "<i>/cancel to stop</i>")


@dp.message(Command("cancel"), StateFilter(PostFlow.text, PostFlow.media,
                                           PostFlow.confirm))
async def cmd_post_cancel(message: Message, state: FSMContext):
    _drafts.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("Cancelled.")


@dp.message(PostFlow.text)
async def post_got_text(message: Message, state: FSMContext):
    draft = _drafts.get(message.from_user.id)
    if not draft:
        await state.clear()
        return
    # HTML formatlash saqlansin: Telegram bergan entity'lardan qayta quramiz
    body = message.html_text if message.text else (message.caption or "")
    if not body.strip():
        await message.answer("Please send the post text.")
        return
    draft["text"] = body
    await state.set_state(PostFlow.media)
    await message.answer(
        "Got it. Now send a <b>photo</b> or <b>video</b> for the post.\n"
        "<i>/skip to post text only · /cancel to stop</i>")


@dp.message(Command("skip"), PostFlow.media)
async def post_skip_media(message: Message, state: FSMContext):
    await _show_preview(message, state)


@dp.message(PostFlow.media)
async def post_got_media(message: Message, state: FSMContext):
    draft = _drafts.get(message.from_user.id)
    if not draft:
        await state.clear()
        return

    if message.photo:
        # photo — bir necha o'lchamdagi ro'yxat, oxirgisi eng kattasi
        draft["media"] = message.photo[-1].file_id
        draft["kind"] = "photo"
    elif message.video:
        draft["media"] = message.video.file_id
        draft["kind"] = "video"
    elif message.animation:
        draft["media"] = message.animation.file_id
        draft["kind"] = "animation"
    else:
        await message.answer(
            "That's not a photo or video. Send one, or /skip.")
        return

    # Rasm/video bilan yuborilganda matn "caption" bo'ladi va uning
    # chegarasi 1024 belgi — oddiy xabarnikidan (4096) ancha kam.
    if len(draft["text"]) > 1024:
        await message.answer(
            f"⚠️ With media the caption limit is <b>1024</b> characters, "
            f"your text is <b>{len(draft['text'])}</b>.\n"
            "Send /skip to post it as text only, or /cancel and shorten it.")
        return

    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext):
    draft = _drafts.get(message.from_user.id)
    if not draft:
        await state.clear()
        return
    await state.set_state(PostFlow.confirm)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Send", callback_data="post:go"),
        InlineKeyboardButton(text="✖️ Cancel", callback_data="post:no"),
    ]])
    await message.answer(
        f"Preview for <b>{html_escape(draft['title'])}</b> — "
        f"{'with ' + draft['kind'] if draft['kind'] else 'text only'}:")
    await _deliver(message.bot, message.chat.id, draft)
    await message.answer("Send this to the channel?", reply_markup=kb)


async def _deliver(bot, chat_id: int, draft: dict):
    """Postni berilgan chatga yuboradi (ko'rib chiqish ham, kanal ham)."""
    kb = _post_kb()
    if draft["kind"] == "photo":
        return await bot.send_photo(chat_id, draft["media"],
                                    caption=draft["text"], reply_markup=kb)
    if draft["kind"] == "video":
        return await bot.send_video(chat_id, draft["media"],
                                    caption=draft["text"], reply_markup=kb)
    if draft["kind"] == "animation":
        return await bot.send_animation(chat_id, draft["media"],
                                        caption=draft["text"], reply_markup=kb)
    return await bot.send_message(chat_id, draft["text"], reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("post:"))
async def post_confirm(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    draft = _drafts.get(uid)
    if cq.data == "post:no" or not draft:
        _drafts.pop(uid, None)
        await state.clear()
        await cq.message.edit_text("Cancelled.")
        await cq.answer()
        return

    try:
        await _deliver(cq.bot, draft["chat"], draft)
        await cq.message.edit_text(
            f"✅ Posted to <b>{html_escape(draft['title'])}</b>.")
    except Exception as e:
        log.warning("Postni kanalga yuborib bo'lmadi: %s", e)
        await cq.message.edit_text(
            f"❌ Could not post.\n\n<code>{html_escape(str(e))}</code>")
    finally:
        _drafts.pop(uid, None)
        await state.clear()
    await cq.answer()


@dp.message(lambda m: m.text and m.text.split("@")[0] in ("/invite", "/ref")
            and m.chat.type == "private")
async def cmd_invite(message: Message):
    """Taklif havolasi va hisobi."""
    uid = message.from_user.id
    await db.get_progress(_user_row(message.from_user))
    count, left = await db.ref_state(uid)
    link = f"{BOT_LINK}?start=ref_{uid}"

    # switch_inline_query — Telegram chat tanlash oynasini ochadi va
    # tanlangan chatga TUGMALI karta yuboradi. Ilgari t.me/share/url
    # ishlatilardi: u faqat matn yuborardi va do'st havolani qo'lda
    # ochishi kerak edi.
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📤 Invite a friend",
                             switch_inline_query="invite")
    ]])
    await message.answer(
        f"👥 <b>Invite friends</b>\n\n"
        f"Every <b>{REF_PER}</b> friends who join through your link "
        f"earn you <b>{REF_KEYS} 🗝️</b>.\n\n"
        f"Invited so far: <b>{count}</b>\n"
        f"Next reward in: <b>{left}</b>\n\n"
        f"Your link:\n<code>{link}</code>",
        reply_markup=kb)


async def members_of(bot, chat_id: int, candidates: list):
    """
    Berilgan o'yinchilardan qaysilari SHU guruhda a'zo ekanini aniqlaydi.

    Telegram bo'tga guruh a'zolarini sanab berishga ruxsat bermaydi,
    shuning uchun teskarisini qilamiz: har o'yinchi uchun alohida
    so'raymiz. Uch narsa muhim:

      1. SO'ROVLAR SONI CHEKLANADI. Ilgari hammasi bir vaqtda
         yuborilardi (60 ta). Telegram sekundiga ~30 so'rovdan ko'pini
         qabul qilmaydi va ortig'iga 429 qaytaradi. Xato esa "a'zo emas"
         deb talqin qilinardi — natijada ro'yxat bo'sh chiqib,
         "bu guruhda hech kim o'ynamaydi" deb yozilardi. Aynan shu
         "yaxshi ishlamayapti" edi.

      2. XATO va "A'ZO EMAS" AJRATILADI. Ilgari ikkalasi ham False
         edi va farqi yo'qolardi.

      3. NATIJA KESHLANADI. Bir guruhda /top qayta-qayta chaqirilsa
         Telegram'ni bekorga charchatmaymiz.
    """
    now = time.time()
    sem = asyncio.Semaphore(GROUP_SCAN_CONCURRENCY)
    failed = 0

    async def check(uid: int):
        nonlocal failed
        key = (chat_id, uid)
        hit = _member_cache.get(key)
        if hit and now - hit[1] < (MEMBER_TTL if hit[0] else MEMBER_TTL_NEG):
            return hit[0]
        async with sem:
            for attempt in (1, 2):
                try:
                    m = await bot.get_chat_member(chat_id, uid)
                    ok = m.status in ("creator", "administrator",
                                      "member", "restricted")
                    _member_cache[key] = (ok, now)
                    return ok
                except TelegramRetryAfter as e:
                    await asyncio.sleep(min(e.retry_after, 3))
                except TelegramBadRequest:
                    # "user not found" — haqiqatan a'zo emas
                    _member_cache[key] = (False, now)
                    return False
                except Exception:
                    if attempt == 2:
                        failed += 1
                    else:
                        await asyncio.sleep(0.4)
            return False

    flags = await asyncio.gather(*(check(r[3]) for r in candidates))

    # Kesh cheksiz o'smasin
    if len(_member_cache) > 5000:
        _member_cache.clear()

    return [r for r, ok in zip(candidates, flags) if ok], failed


@dp.message(lambda m: m.text and m.text.split("@")[0] in ("/top", "/rank", "/leaders")
            # Kanal posti bog'langan muhokama guruhiga o'zi ko'chadi.
            # U ham "/top" matni bilan keladi va javob IKKI marta
            # yuborilardi — biri kanalda, biri guruhda.
            and not getattr(m, "is_automatic_forward", False))
async def cmd_top(message: Message):
    """
    Guruhdagi o'yinchilar reytingi.

    Telegram bo'tga guruh a'zolarini sanab berishga ruxsat bermaydi.
    Shuning uchun teskarisini qilamiz: umumiy reytingdan yuqoridagi
    o'yinchilarni olib, har biri SHU GURUHDA bormi deb so'raymiz.
    Tekshiruvlar parallel ketadi va soni cheklangan — aks holda katta
    bazada javob sekinlashadi.
    """
    chat = message.chat
    if chat.type == "private":
        rows = await db.top_rows()
        if not rows:
            await message.answer("No players yet. Be the first!")
            return
        lines = [f"{MEDALS[i] if i < 3 else f'{i + 1}.'} "
                 f"<b>{html_escape(name or 'Player')}</b> — {score} 💎"
                 for i, (name, _photo, score, _uid) in enumerate(rows[:10])]
        await message.answer("🏆 <b>Top players</b>\n\n" + "\n".join(lines),
                             reply_markup=play_keyboard())
        return

    await send_scoped_top(message)


async def scoped_top_text(bot, chat_id: int, is_channel: bool) -> str:
    """
    Shu chatdagi (guruh yoki kanaldagi) reyting matnini quradi.

    Yuborishdan ALOHIDA turadi, chunki kanalda o'sha matn bir necha
    marta qayta hisoblanib, mavjud xabarni tahrirlashda ishlatiladi.

    Umumiy reytingdan yuqoridagi o'yinchilarni olamiz va har biri shu
    chatda bormi deb so'raymiz — Telegram a'zolarni sanab berishga
    ruxsat bermaydi, shuning uchun teskarisidan boramiz.
    """
    who = "subscribers" if is_channel else "members"
    where = "channel" if is_channel else "group"

    rows = await db.scan_rows()
    if not rows:
        return "No players yet. Be the first!"

    members, failed = await members_of(bot, chat_id, rows[:GROUP_SCAN_LIMIT])

    if not members:
        # Hamma so'rov xato bergan bo'lsa, "hech kim o'ynamaydi" deyish
        # NOTO'G'RI bo'ladi — biz shunchaki bilmaymiz. Farqini aytamiz.
        if failed:
            return (f"Couldn't check the {who} right now. "
                    "Please try again in a moment.")
        return (f"Nobody in this {where} plays Apex Words yet.\n"
                "Tap Play and be the first!")

    lines = [f"{MEDALS[i] if i < 3 else f'{i + 1}.'} "
             f"<b>{html_escape(name or 'Player')}</b> — {score} 💎"
             for i, (name, _photo, score, _uid) in enumerate(members[:20])]
    # Sarlavhada GURUH NOMI ishlatilmaydi.
    #
    # Ilgari "Top players in <guruh nomi>" deb yozilardi. Guruh nomi
    # boshqa o'yinniki bo'lsa ("Chess"), xabar "Top players in Chess"
    # bo'lib chiqib, ApexWords boti shaxmat reytingini ko'rsatayotgandek
    # tuyulardi. Endi o'yin nomi oldinda turadi va chalkashlik yo'q —
    # xabar guruhning o'zida yuborilgani uchun "here" allaqachon aniq.
    head = "🏆 <b>Apex Words</b> — top players here"
    if is_channel:
        head += f"\n<i>live · updated {time.strftime('%H:%M')} UTC</i>"
    return head + "\n\n" + "\n".join(lines)


async def send_scoped_top(message: Message):
    """Guruh uchun: reytingni bir marta yuboradi."""
    text = await scoped_top_text(message.bot, message.chat.id, False)
    await message.answer(text, reply_markup=link_keyboard())


@dp.channel_post(lambda m: m.text and m.text.split("@")[0] in ("/top", "/rank", "/leaders"))
async def channel_top(message: Message):
    """
    Kanaldagi obunachilar reytingi.

    Ikki shart bor va ikkalasi ham bo'tga bog'liq emas:
      1. Bot kanalda ADMIN bo'lishi kerak — aks holda Telegram
         channel_post yangilanishini umuman yubormaydi.
      2. ALLOWED_UPDATES ichida "channel_post" turishi shart, aks holda
         yangilanish so'ralmaydi va buyruq javobsiz qoladi.

    Buyruqning o'zi o'chiriladi va ro'yxat bir muddat jonli yangilanib
    turadi — kanalda "/top" yozuvi qolib ketmasligi kerak.
    """
    bot, chat_id = message.bot, message.chat.id

    # Buyruq postini o'chiramiz. Bot "delete messages" huquqiga ega
    # bo'lmasa bu ishlamaydi — reyting baribir chiqsin.
    try:
        await message.delete()
    except Exception as e:
        log.info("Kanalda /top xabarini o'chirib bo'lmadi: %s", e)

    # Oldingi jonli ro'yxat to'xtatiladi: bitta kanalda ikkita
    # yangilanuvchi xabar qolib ketmasin.
    old = _live_boards.pop(chat_id, None)
    if old:
        old.cancel()

    text = await scoped_top_text(bot, chat_id, True)
    sent = await message.answer(text, reply_markup=link_keyboard())
    _live_boards[chat_id] = asyncio.create_task(
        live_board(bot, chat_id, sent.message_id))


async def live_board(bot, chat_id: int, message_id: int):
    """
    Kanaldagi reytingni davriy yangilab turadi.

    Matn o'zgarmagan bo'lsa tahrirlash YUBORILMAYDI: Telegram bir xil
    matnga "message is not modified" xatosini qaytaradi va bu bekorga
    so'rov sarflagan bo'lardi.
    """
    last = None
    try:
        for _ in range(LIVE_TICKS):
            await asyncio.sleep(LIVE_EVERY)
            try:
                text = await scoped_top_text(bot, chat_id, True)
            except Exception as e:
                log.warning("Jonli reyting hisoblanmadi (%s): %s", chat_id, e)
                continue
            if text == last:
                continue
            try:
                await bot.edit_message_text(
                    text, chat_id=chat_id, message_id=message_id,
                    reply_markup=link_keyboard())
                last = text
            except TelegramBadRequest as e:
                # Xabar o'chirilgan yoki tahrirlab bo'lmaydi — to'xtaymiz
                log.info("Jonli reyting to'xtadi (%s): %s", chat_id, e)
                return
            except TelegramRetryAfter as e:
                await asyncio.sleep(min(e.retry_after, 30))
    except asyncio.CancelledError:
        raise
    finally:
        if _live_boards.get(chat_id) is asyncio.current_task():
            _live_boards.pop(chat_id, None)


@dp.chat_member()
async def on_chat_member(ev: ChatMemberUpdated):
    """
    Kimdir guruh/kanalga qo'shildi yoki chiqdi.

    A'zolik keshi SHU YERDA darhol yangilanadi. Busiz odam qo'shilgandan
    keyin ham eski javob keshda turar va u reytingda ko'rinmasdi —
    aynan shu xato sezilgan edi.
    """
    try:
        ok = ev.new_chat_member.status in (
            "creator", "administrator", "member", "restricted")
        _member_cache[(ev.chat.id, ev.new_chat_member.user.id)] = (ok, time.time())
    except Exception as e:
        log.info("chat_member yangilanishi o'qilmadi: %s", e)


@dp.inline_query()
async def on_inline(query: InlineQuery):
    """
    Inline rejim.

    Bo'tning inline rejimi BotFather'da yoqilgan bo'lsa ham, kodda
    ishlovchi bo'lmasa Telegram hech narsa ko'rsatmaydi — foydalanuvchi
    bot nomini yozganda ro'yxat bo'sh chiqadi.

    Ishlovchi ichida xato chiqsa ham natija BERILMAY qoladi va tashqaridan
    "bot chiqmayapti" bo'lib ko'rinadi — farqi bilinmaydi. Shuning uchun
    hamma narsa try ichida va eng yomon holatda ham bitta natija
    qaytariladi. So'rov kelgani logga yoziladi: shunda muammo
    BotFather sozlamasidami yoki koddami — darhol ajratiladi.
    """
    log.info("Inline so'rov: user=%s chat_type=%s matn=%r",
             query.from_user.id, getattr(query, "chat_type", "?"), query.query)
    try:
        await _answer_inline(query)
    except Exception as e:
        log.exception("Inline so'rovga javob berilmadi: %s", e)
        try:
            await query.answer([_inline_play_card(BOT_LINK)], cache_time=5,
                               is_personal=True)
        except Exception:
            pass


def _inline_play_card(link: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="play",
        title="🎮 Play Apex Words",
        description="Swipe letters into words and grow your English",
        input_message_content=InputTextMessageContent(
            message_text=(
                "🎮 <b>Apex Words</b>\n"
                "Swipe letters into words and grow your English."
            ),
            parse_mode=ParseMode.HTML,
        ),
        # Xabar ostidagi tugma. Ilgari faqat oddiy havola matn bo'lib
        # turardi — bosiladigan tugma yo'q edi.
        reply_markup=link_keyboard(),
    )


def _inline_invite_card(uid: int, name: str) -> InlineQueryResultArticle:
    """
    Taklif kartasi — do'stga TUGMALI xabar bo'lib boradi.

    Ilgari taklif t.me/share/url orqali oddiy matn bo'lib ketardi:
    do'st havolani ko'chirib olishi kerak edi. Inline natija esa
    xabar ostiga tugma qo'yadi va bir bosishda botga olib boradi.

    Havolada taklif qiluvchining ID'si bor, shuning uchun karta
    SHAXSIY: har o'yinchi o'z havolasini oladi.
    """
    link = f"{BOT_LINK}?start=ref_{uid}"
    who = html_escape(name or "A friend")
    return InlineQueryResultArticle(
        id=f"invite{uid}",
        title="👥 Invite a friend",
        description=f"They join, you get keys — every {REF_PER} friends "
                    f"= {REF_KEYS} 🗝️",
        input_message_content=InputTextMessageContent(
            message_text=(
                f"🎮 <b>{who}</b> invites you to <b>Apex Words</b>\n\n"
                "Swipe letters into words and learn English — "
                "3,000 puzzles, completely free."
            ),
            parse_mode=ParseMode.HTML,
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎮 Start playing", url=link)
        ]]),
    )


async def _answer_inline(query: InlineQuery):
    """
    Inline natijalar: taklif kartasi va o'yin kartasi.

    Reyting kartasi ATAYLAB yo'q: inline so'rovda Telegram qaysi
    guruhdan kelganini aytmaydi (chat_id berilmaydi, faqat chat_type).
    Shuning uchun u yerda faqat UMUMIY reyting ko'rsatish mumkin edi,
    guruhniki emas. Guruhda esa odamga o'z guruhining reytingi kerak.
    Guruh reytingini /top beradi, u chat_id ni biladi.
    """
    u = query.from_user
    results = [
        _inline_invite_card(u.id, u.first_name),
        _inline_play_card(BOT_LINK),
    ]
    # is_personal SHART: natijada o'yinchining o'z havolasi bor,
    # shuning uchun uni boshqalarga keshlab berish mumkin emas.
    await query.answer(results, cache_time=30, is_personal=True)


@dp.message(lambda m: m.text and m.text.startswith("/stats"))
async def cmd_stats(message: Message):
    total, active = await db.stats()
    await message.answer(
        f"👥 Players: <b>{total}</b>\n"
        f"🔥 Active in 24h: <b>{active}</b>"
    )


# --------------------------------- Boshlash -----------------------------------

def log_startup_config():
    """
    Ishga tushishda sozlamalarni chop etadi.

    Railway'da nimadir ishlamasa, log birinchi qaraladigan joy. Shuning uchun
    har bir muhim o'zgaruvchi holati aniq yoziladi. Token to'liq chop etilmaydi —
    log saqlanib qolishi mumkin.
    """
    log.info("=" * 56)
    log.info("Apex Words ishga tushmoqda")
    log.info("  BOT_TOKEN   : %s (id: %s)",
             "bor" if BOT_TOKEN else "YO'Q",
             BOT_TOKEN.split(":")[0] if ":" in BOT_TOKEN else "shakli noto'g'ri")
    if WEBAPP_URL.startswith("https://"):
        log.info("  WEBAPP_URL  : %s", WEBAPP_URL)
    elif WEBAPP_URL:
        log.warning("  WEBAPP_URL  : %s  <-- https:// EMAS, o'yin tugmasi chiqmaydi",
                    WEBAPP_URL)
    else:
        log.warning("  WEBAPP_URL  : YO'Q  <-- o'yin tugmasi chiqmaydi")
    log.info("  PORT        : %s", PORT)
    log.info("  Mini App    : %s", "topildi" if (WEB_DIR / "index.html").exists()
             else "web_app/index.html YO'Q")
    log.info("=" * 56)


async def main():
    log_startup_config()
    await db.init()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Tokenni darhol tekshiramiz. Aks holda xato faqat polling boshlangach
    # chiqadi va logda tushunarsiz TelegramUnauthorizedError ko'rinadi.
    try:
        me = await bot.get_me()
        log.info("Bot ulandi: @%s (%s)", me.username, me.full_name)
        # Inline javoblarda ishlatiladigan havola
        global BOT_LINK, MINIAPP_LINK
        if me.username:
            BOT_LINK = f"https://t.me/{me.username}"
            MINIAPP_LINK = f"{BOT_LINK}/{MINIAPP_SHORT}"
        log.info("Mini App havolasi: %s", MINIAPP_LINK)
        # Inline rejim BotFather'da yoqilganini API bermaydi, shuning uchun
        # kamida BIZ nima so'rayotganimizni ko'rsatib qo'yamiz. Agar bu
        # ro'yxatda inline_query bor, lekin "Inline so'rov:" qatori hech
        # qachon chiqmasa — sabab aniq: BotFather'da /setinline yoqilmagan.
        log.info("So'raladigan yangilanishlar: %s", ", ".join(ALLOWED_UPDATES))
        log.info("Inline so'rov kelsa logda \"Inline so'rov:\" qatori chiqadi. "
                 "Chiqmasa — BotFather -> /setinline yoqilmagan.")
    except Exception as e:
        await bot.session.close()
        raise SystemExit(
            "\n" + "=" * 64 +
            f"\nISHGA TUSHMADI: Telegram tokenni qabul qilmadi.\n"
            f"  Xato: {type(e).__name__}: {e}\n"
            "  Sabab odatda: token noto'g'ri, yoki @BotFather da /revoke\n"
            "  qilinib eski token qolib ketgan.\n"
            "  Yechim: @BotFather dan yangi tokenni oling va Railway'dagi\n"
            "  BOT_TOKEN o'zgaruvchisini yangilang.\n"
            + "=" * 64
        )

    runner = web.AppRunner(make_app(bot))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Web server: http://0.0.0.0:%d", PORT)

    if WEBAPP_URL.startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Play",
                                             web_app=WebAppInfo(url=play_url()))
            )
            log.info("Menyu tugmasi sozlandi: %s", play_url())
        except Exception as e:
            log.warning("Menyu tugmasi sozlanmadi: %s", e)
    else:
        log.warning("WEBAPP_URL https emas (%r) — Mini App tugmasi o'chirilgan. "
                    "Brauzerda http://localhost:%d ochib sinang.", WEBAPP_URL, PORT)

    try:
        await dp.start_polling(bot, handle_signals=False,
                               allowed_updates=ALLOWED_UPDATES)
    finally:
        # Kanaldagi jonli reytinglar yarim soatgacha ishlaydi. Bekor
        # qilinmasa, ular yopilayotgan sessiya orqali so'rov yuborishga
        # urinib, logni "Session is closed" xatolari bilan to'ldirardi.
        for task in list(_live_boards.values()):
            task.cancel()
        _live_boards.clear()
        await runner.cleanup()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        # SystemExit ni shunchaki 'pass' qilib bo'lmaydi: u holda xato sababi
        # hech qayerda chop etilmaydi va Railway logida faqat jimgina
        # to'xtash ko'rinadi. Xabarni chiqarib, nolga teng bo'lmagan kod bilan
        # chiqamiz — shunda Railway ham buni muvaffaqiyatsizlik deb biladi.
        if e.code is not None and not isinstance(e.code, int):
            print(e.code, file=sys.stderr, flush=True)
            raise SystemExit(1)
        raise
    except Exception:
        log.exception("Kutilmagan xato — jarayon to'xtadi")
        raise SystemExit(1)

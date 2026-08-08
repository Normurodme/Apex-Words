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
import hmac
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
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
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
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

# Kunlik mukofot: 1-3 kun 1 kalit, 4-6 kun 2 kalit, 7-kun 3 kalit.
# Sakkizinchi kuni sikl yangidan boshlanadi.
DAILY_KEYS = [1, 1, 1, 2, 2, 2, 3]
CHANNEL_KEYS = 5
CHANNEL = os.getenv("CHANNEL_USERNAME", "@apexwords").strip()

# Indeks ALOHIDA turadi va migratsiyadan KEYIN yaratiladi.
# SCHEMA ichida qoldirilsa, eski (score ustunisiz) bazada
# "no such column: score" xatosi chiqadi va bot umuman ishga tushmaydi —
# ya'ni haqiqiy o'yinchilari bor baza buziladi.
INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_players_score ON players(score DESC)"

# Reytingda ko'rsatiladigan o'yinchilar soni
TOP_LIMIT = 100

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

# A'zolik natijasi shuncha soniya eslab qolinadi
MEMBER_TTL = 600
_member_cache: dict[tuple[int, int], tuple[bool, float]] = {}


class DB:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.executescript(SCHEMA)
            await self._migrate(db)      # yetishmayotgan ustunlarni qo'shadi
            await db.execute(INDEX_SQL)  # keyin indeks — ustun endi mavjud
            await db.commit()
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
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT progress FROM players WHERE user_id = ?", (uid,)
            ) as cur:
                row = await cur.fetchone()
            if row:
                # Ism va rasm har kirishda yangilanadi — Telegram'da o'zgargan
                # bo'lishi mumkin, reyting esa eski ma'lumot bilan qolmasin.
                await db.execute(
                    "UPDATE players SET username=?, first_name=?, photo_url=?, "
                    "updated_at=? WHERE user_id=?",
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
        try:
            score = max(0, int(progress.get("coins", 0)))
        except (TypeError, ValueError):
            score = 0
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE players SET progress=?, score=?, updated_at=? WHERE user_id=?",
                (json.dumps(progress, ensure_ascii=False), score, int(time.time()), uid),
            )
            await db.commit()

    async def task_state(self, uid: int) -> dict:
        """Vazifalar bo'limi uchun holat."""
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT last_daily, streak_day, channel_ok FROM players WHERE user_id=?",
                (uid,),
            ) as cur:
                row = await cur.fetchone()
        last, streak, ch = row if row else (None, 0, 0)
        today = date.today().isoformat()
        return {
            "streak": streak or 0,
            "claimed_today": last == today,
            "next_keys": DAILY_KEYS[min(streak or 0, 6)] if last != today
                         else DAILY_KEYS[min((streak or 1) - 1, 6)],
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
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT last_daily, streak_day FROM players WHERE user_id=?", (uid,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return {"error": "no player"}

            last_s, streak = row[0], row[1] or 0
            if last_s == today.isoformat():
                return {"already": True, "streak": streak}

            # Kecha olingan bo'lsa zanjir davom etadi, aks holda uziladi
            last = None
            if last_s:
                try:
                    last = date.fromisoformat(last_s)
                except ValueError:
                    last = None
            if last and (today - last).days == 1 and streak < 7:
                streak += 1
            else:
                streak = 1          # uzilgan yoki 7 kun tugagan -> yangidan

            keys = DAILY_KEYS[min(streak - 1, 6)]
            await db.execute(
                "UPDATE players SET last_daily=?, streak_day=?, updated_at=? WHERE user_id=?",
                (today.isoformat(), streak, int(time.time()), uid),
            )
            await db.commit()
        return {"ok": True, "streak": streak, "keys": keys}

    async def claim_channel(self, uid: int) -> bool:
        """Kanal mukofotini bir marta belgilaydi. True — endi berildi."""
        async with aiosqlite.connect(self.path) as db:
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

        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT first_name, photo_url, score, user_id FROM players "
                "WHERE score > 0 ORDER BY score DESC, updated_at ASC LIMIT ?",
                (TOP_LIMIT,),
            ) as cur:
                rows = await cur.fetchall()
        self._top_cache = (now, rows)
        return rows

    def invalidate_top(self):
        self._top_cache = None

    async def leaderboard(self, uid: int) -> dict:
        """
        Eng yuqori ballli TOP_LIMIT o'yinchi va so'rovchining o'z o'rni.

        Tashqariga faqat ism, rasm va ball chiqadi — user_id va username emas.
        """
        rows = await self.top_rows()          # keshdan, deyarli bir zumda

        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT score FROM players WHERE user_id=?", (uid,)
            ) as cur:
                r = await cur.fetchone()
            my_score = r[0] if r else 0

            # O'z o'rnim: mendan ko'p ballga ega o'yinchilar soni + 1
            async with db.execute(
                "SELECT COUNT(*) FROM players WHERE score > ?", (my_score,)
            ) as cur:
                my_rank = (await cur.fetchone())[0] + 1

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
        async with aiosqlite.connect(self.path) as db:
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
    })


async def api_save(request: web.Request) -> web.Response:
    """Progressni saqlaydi."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)

    user = verify_init_data(body.get("initData", ""))
    if not user:
        return web.json_response({"error": "unauthorized"}, status=401)

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


@dp.message(CommandStart())
async def cmd_start(message: Message):
    name = message.from_user.first_name or "friend"
    text = (
        f"Hey <b>{name}</b>! 👋\n\n"
        "<b>Apex Words</b> — swipe letters into words and grow your English.\n\n"
        "• Drag across the letters to build a word\n"
        "• Words on the board snap into place\n"
        "• Real words that aren't listed earn a <b>bonus</b>\n"
        "• Tap 💡 on any word you found to see what it means\n"
        "• Collect free keys every day in <b>Rewards</b>\n\n"
        "2 chapters, 10 levels and 500 puzzles are ready to play."
    )
    kb = play_keyboard()
    if kb:
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(
            text + "\n\n⚠️ WEBAPP_URL is not set to an https address yet — "
            "the play button stays hidden."
        )


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
        if hit and now - hit[1] < MEMBER_TTL:
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


@dp.message(lambda m: m.text and m.text.split("@")[0] in ("/top", "/rank", "/leaders"))
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

    rows = await db.top_rows()
    if not rows:
        await message.answer("No players yet. Be the first!")
        return

    bot = message.bot
    candidates = rows[:GROUP_SCAN_LIMIT]
    members, failed = await members_of(bot, chat.id, candidates)

    if not members:
        # Hamma so'rov xato bergan bo'lsa, "hech kim o'ynamaydi" deyish
        # NOTO'G'RI bo'ladi — biz shunchaki bilmaymiz. Farqini aytamiz.
        if failed:
            await message.answer(
                "Couldn't check the members right now. Please try again in a moment.")
            return
        await message.answer(
            "Nobody in this group plays Apex Words yet.\n"
            "Tap Play and be the first!", reply_markup=link_keyboard())
        return

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
    await message.answer(
        "🏆 <b>Apex Words</b> — top players here\n\n"
        + "\n".join(lines), reply_markup=link_keyboard())


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


async def _answer_inline(query: InlineQuery):
    """
    Inline natijalar.

    FAQAT bitta karta — o'yinga taklif. Reyting kartasi ATAYLAB
    olib tashlandi: inline so'rovda Telegram qaysi guruhdan kelganini
    aytmaydi (chat_id berilmaydi, faqat chat_type). Shuning uchun u
    yerda faqat UMUMIY reyting ko'rsatish mumkin edi, guruhniki emas.
    Guruhda esa odamga o'z guruhining reytingi kerak — umumiysi
    chalg'itadi. Guruh reytingini /top beradi, u chat_id ni biladi.
    """
    await query.answer([_inline_play_card(BOT_LINK)],
                       cache_time=300, is_personal=False)


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
        await runner.cleanup()
        await bot.session.close()


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

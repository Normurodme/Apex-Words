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
from pathlib import Path
from urllib.parse import parse_qsl

import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    MenuButtonWebApp,
    WebAppInfo,
)
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

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


DB_PATH = os.getenv("DB_PATH", "").strip() or default_db_path()

# initData shu muddatdan eski bo'lsa qabul qilinmaydi (takroriy hujumga qarshi)
INIT_DATA_TTL = 24 * 3600

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("apexwords")

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
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
"""

# Indeks ALOHIDA turadi va migratsiyadan KEYIN yaratiladi.
# SCHEMA ichida qoldirilsa, eski (score ustunisiz) bazada
# "no such column: score" xatosi chiqadi va bot umuman ishga tushmaydi —
# ya'ni haqiqiy o'yinchilari bor baza buziladi.
INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_players_score ON players(score DESC)"

# Reytingda ko'rsatiladigan o'yinchilar soni
TOP_LIMIT = 100


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

    async def leaderboard(self, uid: int) -> dict:
        """
        Eng yuqori ballli TOP_LIMIT o'yinchi va so'rovchining o'z o'rni.

        Tashqariga faqat ism, rasm va ball chiqadi — user_id va username emas.
        """
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT first_name, photo_url, score, user_id FROM players "
                "WHERE score > 0 ORDER BY score DESC, updated_at ASC LIMIT ?",
                (TOP_LIMIT,),
            ) as cur:
                rows = await cur.fetchall()

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
                "name": (name or "O'yinchi")[:32],
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
    return web.json_response({"progress": progress or None})


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


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/api/state", api_state)
    app.router.add_post("/api/save", api_save)
    app.router.add_post("/api/top", api_top)
    app.router.add_get("/", index)
    app.router.add_static("/", WEB_DIR, show_index=False)
    return app


# ---------------------------------- Bot --------------------------------------

dp = Dispatcher()


def play_keyboard() -> InlineKeyboardMarkup | None:
    if not WEBAPP_URL.startswith("https://"):
        return None      # Telegram WebApp tugmasi faqat https bilan ishlaydi
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎮 O'ynash", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


@dp.message(CommandStart())
async def cmd_start(message: Message):
    name = message.from_user.first_name or "do'stim"
    text = (
        f"Salom, <b>{name}</b>! 👋\n\n"
        "<b>Apex Words</b> — harflardan so'z yasab ingliz tilini o'rganasiz.\n\n"
        "• Harflarni barmog'ingiz bilan tortib so'z yasang\n"
        "• Ro'yxatdagi so'zni topsangiz — katakka tushadi\n"
        "• Ro'yxatda yo'q, lekin haqiqiy ingliz so'zi bo'lsa — <b>+1 bonus</b>\n"
        "• Har topilgan so'zning o'zbekcha tarjimasi ko'rsatiladi\n\n"
        "Hozircha 2 bosqich, 10 daraja, 500 puzzle tayyor."
    )
    kb = play_keyboard()
    if kb:
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(
            text + "\n\n⚠️ WEBAPP_URL hali https manzilga sozlanmagan — "
            "o'yin tugmasi ko'rinmaydi."
        )


@dp.message(lambda m: m.text and m.text.startswith("/stats"))
async def cmd_stats(message: Message):
    total, active = await db.stats()
    await message.answer(
        f"👥 Jami o'yinchi: <b>{total}</b>\n"
        f"🔥 Oxirgi 24 soatda: <b>{active}</b>"
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

    runner = web.AppRunner(make_app())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Web server: http://0.0.0.0:%d", PORT)

    if WEBAPP_URL.startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="O'ynash",
                                             web_app=WebAppInfo(url=WEBAPP_URL))
            )
            log.info("Menyu tugmasi sozlandi: %s", WEBAPP_URL)
        except Exception as e:
            log.warning("Menyu tugmasi sozlanmadi: %s", e)
    else:
        log.warning("WEBAPP_URL https emas (%r) — Mini App tugmasi o'chirilgan. "
                    "Brauzerda http://localhost:%d ochib sinang.", WEBAPP_URL, PORT)

    try:
        await dp.start_polling(bot, handle_signals=False)
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

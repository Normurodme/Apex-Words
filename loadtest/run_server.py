"""
Yuk sinovi uchun serverni lokal ishga tushiradi.

Telegram'ga UMUMAN ulanmaydi: polling yo'q, menyu tugmasi qo'yilmaydi,
token soxta (lekin imzo tekshiruvi uchun to'g'ri shaklda). Ya'ni sinov
haqiqiy botning hisobiga va o'yinchilar bazasiga tegmaydi.

Ishga tushirish:
    python loadtest/run_server.py [port]
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8901

# Sinov bazasi vaqtinchalik katalogda — haqiqiysiga tegmaydi
DB = Path(tempfile.gettempdir()) / "apex_loadtest.db"
for suffix in ("", "-wal", "-shm"):
    Path(str(DB) + suffix).unlink(missing_ok=True)
os.environ["DB_PATH"] = str(DB)
os.environ.setdefault("BOT_TOKEN", "111111:LOADTESTLOADTESTLOADTESTLOADTEST")
os.environ["WEBAPP_URL"] = ""          # menyu tugmasi qo'yilmasin

import bot as B   # noqa: E402
from aiohttp import web   # noqa: E402


async def main():
    await B.db.init()
    runner = web.AppRunner(B.make_app(None))
    await runner.setup()
    # backlog kattaroq: bir vaqtda ko'p ulanish kelganda navbat to'lmasin
    await web.TCPSite(runner, "127.0.0.1", PORT, backlog=2048).start()
    print(f"Yuk sinovi serveri: http://127.0.0.1:{PORT}  (baza: {DB})")
    print("To'xtatish: Ctrl+C")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

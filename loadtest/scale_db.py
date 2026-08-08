"""
Baza kattalashganda so'rovlar sekinlashadimi — shuni o'lchaydi.

"Bir vaqtda nechta o'yinchi" va "jami nechta o'yinchi" — bu ikki xil
savol. Birinchisini loadtest.py o'lchaydi, ikkinchisini bu skript:
bazaga ko'p yozuv qo'yib, eng muhim so'rovlar vaqtini tekshiradi.

Ishga tushirish:
    python loadtest/scale_db.py            # 10k, 50k, 200k
    python loadtest/scale_db.py 500000
"""
import asyncio
import json
import os
import random
import string
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

DB = Path(tempfile.gettempdir()) / "apex_scale.db"
for s in ("", "-wal", "-shm"):
    Path(str(DB) + s).unlink(missing_ok=True)
os.environ["DB_PATH"] = str(DB)
os.environ.setdefault("BOT_TOKEN", "111111:SCALETESTSCALETESTSCALETESTSCALE")

import aiosqlite   # noqa: E402
import bot as B    # noqa: E402


def fake_progress(n: int) -> str:
    """Haqiqiy hajmga yaqin progress: o'rgangan so'zlar ro'yxati eng katta qism."""
    learned = {"".join(random.choices(string.ascii_uppercase, k=5)): 1
               for _ in range(n)}
    return json.dumps({
        "coins": random.randint(0, 5000), "keys": random.randint(0, 50),
        "cur": {"stage": 3, "level": 2, "puzzle": 17},
        "solved": {f"{s}-{l}": 50 for s in range(1, 4) for l in range(1, 6)},
        "learned": learned, "muted": False, "music": True,
    }, ensure_ascii=False)


async def seed(total: int, have: int):
    """Bazaga yangi o'yinchilar qo'shadi."""
    now = int(time.time())
    async with aiosqlite.connect(DB) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=OFF")     # faqat sinov uchun
        batch = []
        for i in range(have, total):
            batch.append((10_000_000 + i, f"u{i}", f"Player {i}", None,
                          random.randint(0, 100000), fake_progress(
                              random.randint(20, 400)),
                          None, 0, 0, now, now))
            if len(batch) >= 2000:
                await db.executemany(
                    "INSERT OR REPLACE INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    batch)
                await db.commit()
                batch.clear()
        if batch:
            await db.executemany(
                "INSERT OR REPLACE INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                batch)
            await db.commit()


async def timed(label, coro, runs=5):
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter()
        await coro()
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return f"{label} {ts[len(ts) // 2]:>7.1f} ms"


async def main():
    sizes = [int(a) for a in sys.argv[1:]] or [10_000, 50_000, 200_000]
    await B.db.init()

    print("=" * 78)
    print("Baza kattalashganda so'rov vaqtlari")
    print("=" * 78)

    have = 0
    for n in sizes:
        await seed(n, have)
        have = n
        B.db.invalidate_top()

        user = {"id": 10_000_005, "first_name": "T", "username": "t",
                "photo_url": None}
        a = await timed("kirish (/api/state) ", lambda: B.db.get_progress(user))
        b = await timed("saqlash (/api/save) ",
                        lambda: B.db.save_progress(10_000_005, json.loads(fake_progress(200))))
        B.db.invalidate_top()
        c = await timed("reyting, keshsiz    ", lambda: B.db.top_rows(), runs=3)
        d = await timed("reyting, keshdan    ", lambda: B.db.top_rows())

        size = Path(DB).stat().st_size / 1024 / 1024
        print(f"\n  {n:,} o'yinchi   (baza {size:.0f} MB)")
        for line in (a, b, c, d):
            print("    " + line)

    await B.db.close()
    print("\n" + "=" * 78)
    print("Eslatma: /api/state va /api/save birlamchi kalit bo'yicha ishlaydi,")
    print("shuning uchun ular baza hajmiga deyarli bog'liq emas. Reyting esa")
    print("indeksdan o'qiladi va 20 soniya keshlanadi.")


asyncio.run(main())

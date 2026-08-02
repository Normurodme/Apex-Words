"""
bot.py ni Telegram'ga ULANMASDAN sinaydi: initData imzo tekshiruvi va /api/*.

Polling ishga tushmaydi, shuning uchun botning haqiqiy hisobiga tegmaydi.

Ishga tushirish:
    python build/test_backend.py
"""
import asyncio, hashlib, hmac, json, os, sys, time, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["DB_PATH"] = str(ROOT / "data" / "test_apex.db")

import bot as B
from aiohttp.test_utils import TestClient, TestServer


def make_init_data(user_id: int, token: str) -> str:
    user = json.dumps({"id": user_id, "first_name": "Test", "username": "t"})
    fields = {"auth_date": str(int(time.time())), "query_id": "AAA", "user": user}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


async def main():
    tok = B.BOT_TOKEN
    ok = []

    # Har safar toza bazadan boshlaymiz — aks holda oldingi ishga tushirishdan
    # qolgan yozuvlar "yangi o'yinchi" testini yiqitadi.
    for suffix in ("", "-wal", "-shm"):
        Path(os.environ["DB_PATH"] + suffix).unlink(missing_ok=True)

    # --- imzo tekshiruvi ---
    good = make_init_data(555001, tok)
    u = B.verify_init_data(good)
    ok.append(("to'g'ri imzo qabul qilindi", u is not None and u["id"] == 555001))
    ok.append(("bo'sh initData rad etildi", B.verify_init_data("") is None))
    ok.append(("buzilgan imzo rad etildi",
               B.verify_init_data(good.replace("hash=", "hash=0")) is None))
    forged = make_init_data(555002, "9999:WRONGTOKEN")
    ok.append(("boshqa token bilan yasalgan imzo rad etildi",
               B.verify_init_data(forged) is None))
    old = urllib.parse.parse_qs(good)
    stale_fields = {"auth_date": str(int(time.time()) - 90000), "query_id": "AAA",
                    "user": old["user"][0]}
    check = "\n".join(f"{k}={stale_fields[k]}" for k in sorted(stale_fields))
    secret = hmac.new(b"WebAppData", tok.encode(), hashlib.sha256).digest()
    stale_fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    ok.append(("eski initData rad etildi",
               B.verify_init_data(urllib.parse.urlencode(stale_fields)) is None))

    # --- API ---
    await B.db.init()
    client = TestClient(TestServer(B.make_app()))
    await client.start_server()

    r = await client.get("/health")
    ok.append(("/health 200", r.status == 200))

    r = await client.get("/")
    ok.append(("/ index.html beradi", r.status == 200 and "Apex Words" in await r.text()))

    r = await client.get("/data/index.json")
    ok.append(("/data/index.json beradi", r.status == 200))

    r = await client.post("/api/state", json={"initData": "soxta"})
    ok.append(("imzosiz /api/state 401", r.status == 401))

    r = await client.post("/api/state", json={"initData": good})
    body = await r.json()
    ok.append(("yangi o'yinchi bo'sh progress oladi",
               r.status == 200 and body.get("progress") is None))

    prog = {"coins": 77, "cur": {"stage": 1, "level": 2, "puzzle": 5}, "solved": {"1-1": 50}}
    r = await client.post("/api/save", json={"initData": good, "progress": prog})
    ok.append(("/api/save 200", r.status == 200))

    r = await client.post("/api/state", json={"initData": good})
    body = await r.json()
    ok.append(("progress qaytib keldi", body["progress"]["coins"] == 77))

    r = await client.post("/api/save", json={"initData": good,
                                             "progress": {"x": "y" * 300000}})
    ok.append(("juda katta progress rad etildi", r.status == 413))

    # --- Reyting ---
    r = await client.post("/api/top", json={"initData": "soxta"})
    ok.append(("imzosiz /api/top 401", r.status == 401))

    # Ikkinchi o'yinchi, ko'proq ball bilan
    other = make_init_data(555003, tok)
    await client.post("/api/state", json={"initData": other})
    await client.post("/api/save", json={
        "initData": other,
        "progress": {"coins": 500, "solved": {}, "learned": {}},
    })

    r = await client.post("/api/top", json={"initData": good})
    top = await r.json()
    names = [p["rank"] for p in top["top"]]
    ok.append(("/api/top 200", r.status == 200))
    ok.append(("reyting ball bo'yicha saralangan",
               [p["score"] for p in top["top"]] == sorted(
                   (p["score"] for p in top["top"]), reverse=True)))
    ok.append(("o'rinlar 1 dan boshlanadi", names[:2] == [1, 2]))
    ok.append(("ball progressdagi coins bilan bir xil",
               top["top"][0]["score"] == 500))
    ok.append(("so'rovchi o'zini 'me' bayrog'i bilan ko'radi",
               any(p["me"] for p in top["top"])))
    ok.append(("o'z o'rnim hisoblandi", top["me"]["rank"] == 2 and top["me"]["score"] == 77))
    ok.append(("user_id tashqariga chiqmaydi",
               all("user_id" not in p for p in top["top"])))

    # --- Eski sxemadagi baza migratsiya qilinadimi ---
    old_db = ROOT / "data" / "test_old.db"
    old_db.unlink(missing_ok=True)
    import aiosqlite
    async with aiosqlite.connect(old_db) as d:
        await d.execute(
            "CREATE TABLE players (user_id INTEGER PRIMARY KEY, username TEXT,"
            " first_name TEXT, progress TEXT NOT NULL DEFAULT '{}',"
            " created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
        await d.execute("INSERT INTO players VALUES (1,'a','A','{}',0,0)")
        await d.commit()
    old = B.DB(str(old_db))
    await old.init()
    async with aiosqlite.connect(old_db) as d:
        async with d.execute("PRAGMA table_info(players)") as cur:
            cols = {row[1] for row in await cur.fetchall()}
    ok.append(("eski bazaga score/photo_url ustunlari qo'shildi",
               {"score", "photo_url"} <= cols))
    old_db.unlink(missing_ok=True)

    await client.close()
    Path(os.environ["DB_PATH"]).unlink(missing_ok=True)

    bad = [n for n, v in ok if not v]
    for n, v in ok:
        print(("  OK   " if v else "  XATO ") + n)
    print(f"\n{len(ok)-len(bad)}/{len(ok)} test o'tdi")
    return 1 if bad else 0


sys.exit(asyncio.run(main()))

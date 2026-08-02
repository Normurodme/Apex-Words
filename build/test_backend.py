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

    await client.close()
    Path(os.environ["DB_PATH"]).unlink(missing_ok=True)

    bad = [n for n, v in ok if not v]
    for n, v in ok:
        print(("  OK   " if v else "  XATO ") + n)
    print(f"\n{len(ok)-len(bad)}/{len(ok)} test o'tdi")
    return 1 if bad else 0


sys.exit(asyncio.run(main()))

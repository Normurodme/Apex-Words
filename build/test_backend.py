"""
bot.py ni Telegram'ga ULANMASDAN sinaydi: initData imzo tekshiruvi va /api/*.

Polling ishga tushmaydi, shuning uchun botning haqiqiy hisobiga tegmaydi.

Ishga tushirish:
    python build/test_backend.py
"""
import asyncio, hashlib, hmac, inspect, json, os, sys, time, urllib.parse
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

    # Har safar toza bazadan boshlaymiz â€” aks holda oldingi ishga tushirishdan
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

    # --- Reyting keshi ---
    import time as _t
    B.db._top_cache = None
    t0 = _t.perf_counter()
    r1 = await B.db.top_rows()
    cold = _t.perf_counter() - t0
    t0 = _t.perf_counter()
    r2 = await B.db.top_rows()
    warm = _t.perf_counter() - t0
    ok.append(("reyting keshdan qaytadi (natija bir xil)", r1 == r2))
    ok.append(("keshdan olish bazadan tezroq", warm <= cold))
    B.db.invalidate_top()
    ok.append(("kesh bekor qilinadi", B.db._top_cache is None))

    # --- Admin reytingga kirmaydi ---
    #
    # Admin sinov paytida ko'p ball to'playdi. U reytingda qolsa haqiqiy
    # o'yinchilarni birinchi o'rindan surib qo'yardi.
    admin_id = next(iter(B.ADMINS))
    admin_u = {"id": admin_id, "first_name": "Admin", "username": "adm",
               "photo_url": None}
    await B.db.get_progress(admin_u)
    await B.db.save_progress(admin_id, {"coins": 999999, "solved": {"1-1": 50}})
    B.db.invalidate_top()
    top_names = [r[0] for r in await B.db.top_rows()]
    ok.append(("admin reytingda ko'rinmaydi", "Admin" not in top_names))
    ok.append(("boshqa o'yinchilar reytingda qoladi", len(top_names) >= 1))

    # O'rin ham adminsiz sanaladi, aks holda ro'yxatdagi joy bilan
    # ko'rsatilgan raqam bir-biriga to'g'ri kelmay qolardi.
    lb = await B.db.leaderboard(555001)
    ok.append(("o'rin adminni sanamaydi", lb["me"]["rank"] == 1))

    r = await client.post("/api/state", json={"initData": good})
    ok.append(("oddiy o'yinchida admin bayrog'i yo'q",
               (await r.json()).get("admin") is False))

    # Yuqoridagi top_rows() chaqiruvi keshni 20 soniyaga to'ldirdi.
    # Tozalanmasa, quyidagi reyting testlari keyin qo'shilgan
    # o'yinchini ko'rmay qoladi.
    B.db.invalidate_top()

    # --- Taklif tizimi ---
    host = 700000
    await B.db.get_progress({"id": host, "first_name": "Host",
                             "username": "h", "photo_url": None})

    # O'zini o'zi taklif qilib bo'lmaydi
    r = await B.db.add_referral(host, host)
    ok.append(("o'zini taklif qilish rad etildi", r["ok"] is False))

    # Bazada yo'q odam taklif qila olmaydi
    await B.db.get_progress({"id": 700001, "first_name": "F1",
                             "username": "f1", "photo_url": None})
    r = await B.db.add_referral(700001, 999999999)
    ok.append(("noma'lum taklifchi rad etildi", r["ok"] is False))

    # Birinchi ikki do'st — mukofot yo'q
    r1 = await B.db.add_referral(700001, host)
    await B.db.get_progress({"id": 700002, "first_name": "F2",
                             "username": "f2", "photo_url": None})
    r2 = await B.db.add_referral(700002, host)
    ok.append(("birinchi do'st hisoblandi", r1["ok"] and r1["count"] == 1))
    ok.append(("2 do'stda mukofot yo'q", r2["granted"] == 0))

    # Bir odam ikki marta hisoblanmaydi — aks holda havolani qayta-qayta
    # bosib cheksiz kalit yig'sa bo'lardi
    again = await B.db.add_referral(700001, host)
    ok.append(("bitta do'st ikki marta sanalmaydi", again["ok"] is False))

    # Uchinchi do'st — mukofot
    await B.db.get_progress({"id": 700003, "first_name": "F3",
                             "username": "f3", "photo_url": None})
    r3 = await B.db.add_referral(700003, host)
    ok.append(("3-do'stda mukofot berildi", r3["granted"] == B.REF_KEYS))

    # Eskidan o'ynab yurgan odam taklif sifatida sanalmaydi
    old_uid = 700009
    await B.db.get_progress({"id": old_uid, "first_name": "Old",
                             "username": "o", "photo_url": None})
    async with B.db.conn() as _d:
        await _d.execute("UPDATE players SET created_at=? WHERE user_id=?",
                         (int(time.time()) - B.REF_NEW_WINDOW - 60, old_uid))
        await _d.commit()
    r_old = await B.db.add_referral(old_uid, host)
    ok.append(("eski o'yinchi taklif sifatida sanalmaydi",
               r_old["ok"] is False and r_old["reason"] == "not_new"))

    count, left = await B.db.ref_state(host)
    ok.append(("taklif hisobi to'g'ri", count == 3))
    ok.append(("keyingi mukofotgacha qoldi", left == B.REF_PER))

    # Kutayotgan kalit bir marta beriladi
    got = await B.db.take_pending_keys(host)
    ok.append(("kutayotgan kalitlar berildi", got == B.REF_KEYS))
    twice = await B.db.take_pending_keys(host)
    ok.append(("kalitlar ikkinchi marta berilmaydi", twice == 0))

    host_init = make_init_data(host, tok)
    r = await client.post("/api/claim-keys", json={"initData": host_init})
    ok.append(("/api/claim-keys 200", r.status == 200))
    ok.append(("bo'sh bo'lsa 0 kalit", (await r.json())["keys"] == 0))
    r = await client.post("/api/claim-keys", json={"initData": "soxta"})
    ok.append(("imzosiz /api/claim-keys 401", r.status == 401))

    r = await client.post("/api/tasks", json={"initData": host_init})
    ts = await r.json()
    ok.append(("vazifalarda taklif havolasi bor",
               ts.get("ref_link", "").endswith("start=ref_%d" % host)))
    ok.append(("vazifalarda taklif hisobi bor", ts.get("ref_count") == 3))

    # --- /post sehrgari ---
    msg_names = [h.callback.__name__ for h in B.dp.message.handlers]
    ok.append(("/post buyrug'i bor", "cmd_post" in msg_names))
    ok.append(("/post tasdiq tugmasi bor",
               "post_confirm" in [h.callback.__name__
                                  for h in B.dp.callback_query.handlers]))
    # Sehrgar bosqichlari UMUMIY buyruqlardan OLDIN turishi shart, aks
    # holda /post ichida "/top" yozilsa reyting chiqib, sehrgar buzilardi.
    ok.append(("sehrgar bosqichlari /top dan oldin",
               msg_names.index("post_got_text") < msg_names.index("cmd_top")))

    # --- Kanal reytingi ---
    ok.append(("chat_member ishlovchisi bor",
               len(B.dp.chat_member.handlers) >= 1))
    ok.append(("chat_member so'raladigan turlar ichida",
               "chat_member" in B.ALLOWED_UPDATES))
    # "A'zo emas" javobi qisqa saqlanishi SHART: odam qo'shilgandan keyin
    # ham eski javob keshda tursa, u ro'yxatda ko'rinmay qolardi.
    ok.append(("salbiy kesh qisqa muddatli",
               B.MEMBER_TTL_NEG < B.MEMBER_TTL))
    # Guruh reytingi umumiy 100 talik ro'yxat bilan cheklanmasligi kerak
    ok.append(("guruh skaneri kengroq ro'yxat oladi",
               B.SCAN_LIMIT > B.TOP_LIMIT))
    ok.append(("scan_rows ishlaydi", isinstance(await B.db.scan_rows(), list)))
    B.db.invalidate_top()

    # --- Inline rejim, guruh va kanal reytingi ro'yxatdan o'tganmi ---
    handlers = B.dp.inline_query.handlers
    ok.append(("inline rejim ishlovchisi bor", len(handlers) >= 1))
    msg_src = "".join(str(h.callback.__name__) for h in B.dp.message.handlers)
    ok.append(("/top buyrug'i ro'yxatdan o'tgan", "cmd_top" in msg_src))
    ch_src = "".join(str(h.callback.__name__) for h in B.dp.channel_post.handlers)
    ok.append(("kanalda /top ishlovchisi bor", "channel_top" in ch_src))
    # Ishlovchi bo'lsa ham, bu tur so'ralmasa Telegram uni yubormaydi.
    ok.append(("channel_post so'raladigan turlar ichida",
               "channel_post" in B.ALLOWED_UPDATES))
    ok.append(("html_escape teglarni zararsizlantiradi",
               B.html_escape("<b>x</b>&") == "&lt;b&gt;x&lt;/b&gt;&amp;"))

    # web_app tugmasi FAQAT shaxsiy chatda ishlaydi. Guruh va inline
    # javoblarda u xabarni butunlay rad ettiradi, shuning uchun u yerda
    # oddiy havola tugmasi bo'lishi shart.
    lk = B.link_keyboard().inline_keyboard[0][0]
    ok.append(("guruh tugmasi havola turida (web_app emas)",
               lk.url is not None and lk.web_app is None))
    ok.append(("havola Mini App'ga ishora qiladi", "/" in lk.url.split("t.me/")[1]))
    card = B._inline_play_card(B.BOT_LINK)
    ok.append(("inline natijada tugma bor", card.reply_markup is not None))

    # Inline'da reyting kartasi BO'LMASLIGI kerak: inline so'rovda
    # chat_id berilmaydi, ya'ni guruh reytingini ko'rsatib bo'lmaydi,
    # umumiysi esa guruhda chalg'itadi.
    src = inspect.getsource(B._answer_inline)
    ok.append(("inline'da reyting kartasi yo'q",
               "_inline_play_card" in src and "id=\"top\"" not in src))
    ok.append(("guruh sarlavhasida guruh nomi ishlatilmaydi",
               "chat.title" not in inspect.getsource(B.cmd_top).split("private")[-1]))
    ok.append(("inline tugmasi ham havola turida",
               card.reply_markup.inline_keyboard[0][0].url is not None))

    # --- Cheksiz kalit ---
    # Bayroq SERVERDAN kelishi kerak: kalit soni mijozda saqlanadi va
    # unga ishonib bo'lmaydi.
    r = await client.post("/api/state", json={"initData": good})
    body = await r.json()
    ok.append(("oddiy o'yinchida cheksiz kalit yo'q", body.get("unlimited") is False))

    vip = make_init_data(sorted(B.UNLIMITED_HINTS)[0], tok)
    r = await client.post("/api/state", json={"initData": vip})
    ok.append(("ro'yxatdagi ID cheksiz kalit oladi",
               (await r.json()).get("unlimited") is True))
    ok.append(("ikkita ID kiritilgan", len(B.UNLIMITED_HINTS) >= 2))
    ok.append(("o'zgaruvchi orqali qo'shsa bo'ladi",
               B._parse_ids("111, 222;333") == {111, 222, 333}))

    # --- Guruh a'zoligini aniqlash ---
    # Telegram 429 qaytarsa yoki tarmoq uzilsa, bu "a'zo emas" degani EMAS.
    # Ilgari ikkalasi ham False edi va ro'yxat bo'sh chiqib, "hech kim
    # o'ynamaydi" deb yozilardi.
    class FakeBot:
        def __init__(self, mode):
            self.mode, self.calls, self.peak, self.live = mode, 0, 0, 0

        async def get_chat_member(self, chat_id, uid):
            self.calls += 1
            self.live += 1
            self.peak = max(self.peak, self.live)
            await asyncio.sleep(0.01)
            self.live -= 1
            if self.mode == "error":
                raise RuntimeError("tarmoq uzildi")
            class M:
                status = "member" if uid % 2 == 0 else "left"
            return M()

    cands = [("N" + str(i), "", 100 - i, i) for i in range(20)]

    fb = FakeBot("ok")
    B._member_cache.clear()
    mem, failed = await B.members_of(fb, -100, cands)
    ok.append(("faqat a'zolar qoladi", len(mem) == 10 and failed == 0))
    ok.append((f"so'rovlar cheklangan (eng ko'pi {fb.peak})",
               fb.peak <= B.GROUP_SCAN_CONCURRENCY))

    before = fb.calls
    mem2, _ = await B.members_of(fb, -100, cands)
    ok.append(("natija keshlanadi (takror so'rov yo'q)",
               fb.calls == before and len(mem2) == 10))

    fe = FakeBot("error")
    B._member_cache.clear()
    mem3, failed3 = await B.members_of(fe, -200, cands)
    ok.append(("xato 'a'zo emas' deb hisoblanmaydi",
               mem3 == [] and failed3 == len(cands)))

    # --- Kunlik zanjir ---
    r = await client.post("/api/tasks", json={"initData": good})
    t0 = await r.json()
    ok.append(("/api/tasks 200", r.status == 200))
    ok.append(("boshida zanjir 0 va bugun olinmagan",
               t0["streak"] == 0 and not t0["claimed_today"]))

    r = await client.post("/api/claim-daily", json={"initData": good})
    d1 = await r.json()
    ok.append(("1-kun 1 kalit beradi", d1.get("streak") == 1 and d1.get("keys") == 1))

    r = await client.post("/api/claim-daily", json={"initData": good})
    d2 = await r.json()
    ok.append(("bir kunda ikki marta olib bo'lmaydi", d2.get("already") is True))

    # Zanjir mantig'ini to'g'ridan-to'g'ri bazada sinaymiz
    from datetime import date, timedelta
    import aiosqlite as _sq

    async def set_daily(day_offset, streak):
        async with _sq.connect(os.environ["DB_PATH"]) as d:
            await d.execute("UPDATE players SET last_daily=?, streak_day=? WHERE user_id=?",
                            ((date.today() + timedelta(days=day_offset)).isoformat(),
                             streak, 555001))
            await d.commit()

    await set_daily(-1, 3)                      # kecha 3-kun olingan
    r = await client.post("/api/claim-daily", json={"initData": good})
    d4 = await r.json()
    ok.append(("kecha olingan bo'lsa zanjir davom etadi (4-kun, 2 kalit)",
               d4.get("streak") == 4 and d4.get("keys") == 2))

    await set_daily(-1, 6)
    r = await client.post("/api/claim-daily", json={"initData": good})
    d7 = await r.json()
    ok.append(("7-kun 3 kalit beradi", d7.get("streak") == 7 and d7.get("keys") == 3))

    await set_daily(-1, 7)                      # 7 kun to'ldi -> yangidan
    r = await client.post("/api/claim-daily", json={"initData": good})
    d8 = await r.json()
    ok.append(("8-kuni zanjir 1 dan boshlanadi",
               d8.get("streak") == 1 and d8.get("keys") == 1))

    await set_daily(-3, 5)                      # uch kun kelinmadi -> uziladi
    r = await client.post("/api/claim-daily", json={"initData": good})
    dbreak = await r.json()
    ok.append(("zanjir uzilsa 1 dan boshlanadi", dbreak.get("streak") == 1))

    r = await client.post("/api/tasks", json={"initData": good})
    tf = await r.json()
    ok.append(("olingandan keyin claimed_today true", tf["claimed_today"] is True))

    # --- Kanal vazifasi ---
    r = await client.post("/api/claim-channel", json={"initData": "soxta"})
    ok.append(("imzosiz /api/claim-channel 401", r.status == 401))
    r = await client.post("/api/claim-channel", json={"initData": good})
    ok.append(("bot yo'q bo'lsa kanal tekshiruvi 503", r.status == 503))
    ok.append(("kanal mukofoti bir marta beriladi",
               await B.db.claim_channel(555001) is True
               and await B.db.claim_channel(555001) is False))

    # --- Baza yo'li: nisbiy DB_PATH volume'ni bosib ketmasligi kerak ---
    import tempfile
    with tempfile.TemporaryDirectory() as vol:
        ok.append(("nisbiy DB_PATH volume foydasiga bekor qilinadi",
                   B.resolve_db_path("data/apex_words.db", vol)
                   == str(Path(vol) / "apex_words.db")))
        ok.append(("mutlaq DB_PATH hurmat qilinadi",
                   B.resolve_db_path("/mnt/boshqa/x.db", vol) == "/mnt/boshqa/x.db"))
    yoq = Path(tempfile.gettempdir()) / "apex_yoq_katalog_12345"
    ok.append(("volume bo'lmasa nisbiy yo'l o'zgarmaydi",
               B.resolve_db_path("data/x.db", str(yoq)) == "data/x.db"))

    # --- Keshlash sarlavhalari ---
    # Bular bo'lmasa Telegram WebView eski nusxani ushlab qoladi va yangi
    # deploy o'yinchiga umuman yetib bormaydi.
    r = await client.get("/")
    ok.append(("/ no-store bilan keladi",
               "no-store" in (r.headers.get("Cache-Control") or "")))
    r = await client.get("/index.html")
    ok.append(("/index.html no-store bilan keladi",
               "no-store" in (r.headers.get("Cache-Control") or "")))
    for path in ("/app.js", "/style.css", "/data/index.json"):
        r = await client.get(path)
        cc = r.headers.get("Cache-Control") or ""
        ok.append((f"{path} keshni tekshiradi",
                   "no-cache" in cc or "no-store" in cc))

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
        # Ballari progress ichida turgan eski o'yinchilar
        await d.execute("INSERT INTO players VALUES (2,'b','B',?,0,0)",
                        (json.dumps({"coins": 340, "solved": {"1-1": 7}}),))
        await d.execute("INSERT INTO players VALUES (3,'c','C','buzilgan json',0,0)")
        await d.commit()
    old = B.DB(str(old_db))
    await old.init()
    await old.close()      # ulanish oqimlari qolib ketmasin
    async with aiosqlite.connect(old_db) as d:
        async with d.execute("PRAGMA table_info(players)") as cur:
            cols = {row[1] for row in await cur.fetchall()}
        async with d.execute("SELECT user_id, score FROM players ORDER BY user_id") as cur:
            scores = dict(await cur.fetchall())
    ok.append(("eski bazaga score/photo_url ustunlari qo'shildi",
               {"score", "photo_url"} <= cols))
    ok.append(("eski o'yinchining bali progressdan ko'chirildi", scores.get(2) == 340))
    ok.append(("bo'sh progress 0 bo'lib qoldi", scores.get(1) == 0))
    ok.append(("buzilgan json migratsiyani yiqitmadi", scores.get(3) == 0))

    # Migratsiya ikkinchi marta ishlaganda ham xato bermasligi kerak
    again = B.DB(str(old_db))
    await again.init()
    await again.close()
    ok.append(("migratsiya takroran ishlayveradi", True))
    old_db.unlink(missing_ok=True)

    await client.close()
    # Havzadagi ulanishlar yopilmasa jarayon tugamaydi (oqimlar daemon emas)
    await B.db.close()
    Path(os.environ["DB_PATH"]).unlink(missing_ok=True)

    bad = [n for n, v in ok if not v]
    for n, v in ok:
        print(("  OK   " if v else "  XATO ") + n)
    print(f"\n{len(ok)-len(bad)}/{len(ok)} test o'tdi")
    return 1 if bad else 0


sys.exit(asyncio.run(main()))

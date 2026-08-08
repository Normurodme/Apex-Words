"""
Apex Words — yuk sinovi.

Har "o'yinchi" haqiqiy sessiyani takrorlaydi:
    /api/state  -> progressni oladi (bir marta, kirganda)
    /api/tasks  -> vazifalar bo'limi (bir marta)
    /api/top    -> reyting (bir marta)
    /api/save   -> har puzzle yechilganda (bir necha marta)

Saqlash eng ko'p chaqiriladigan so'rov, shuning uchun nisbat shunga
yaqin qilib olingan.

Ishga tushirish (avval boshqa terminalda run_server.py):
    python loadtest/loadtest.py               # bosqichma-bosqich
    python loadtest/loadtest.py 200 30        # 200 ta bir vaqtda, 30 s
"""
import asyncio
import hashlib
import hmac
import json
import statistics
import sys
import time
import urllib.parse

import aiohttp

BASE = "http://127.0.0.1:8901"
TOKEN = "111111:LOADTESTLOADTESTLOADTESTLOADTEST"

# Puzzlelar orasidagi tanaffus.
#
# Standart 0.35 s — bu ATAYLAB haqiqatdan tez: server chegarasini
# topish uchun. Haqiqiy o'yinchi bitta puzzleni ~25 soniyada yechadi,
# ya'ni serverga taxminan 70 barobar kam yuk beradi. "real" rejimi
# aynan shu tezlikni takrorlaydi va nechta HAQIQIY o'yinchini
# ko'tara olishini ko'rsatadi.
THINK = 0.35


def init_data(uid: int) -> str:
    user = json.dumps({"id": uid, "first_name": f"U{uid}", "username": f"u{uid}"})
    f = {"auth_date": str(int(time.time())), "query_id": "AAA", "user": user}
    check = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    f["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(f)


class Stats:
    def __init__(self):
        self.lat = []
        self.ok = 0
        self.err = 0
        self.by_path = {}

    def add(self, path, ms, ok):
        self.lat.append(ms)
        self.by_path.setdefault(path, []).append(ms)
        if ok:
            self.ok += 1
        else:
            self.err += 1


async def call(sess, stats, path, payload):
    t0 = time.perf_counter()
    try:
        async with sess.post(BASE + path, json=payload) as r:
            await r.read()
            ok = r.status == 200
    except Exception:
        ok = False
    stats.add(path, (time.perf_counter() - t0) * 1000, ok)
    return ok


async def player(sess, stats, uid, until, delay=0.0):
    """
    Bitta o'yinchining sessiyasi.

    delay — kirish vaqtini surish. Barcha o'yinchi bir zumda kirsa,
    o'lchov barqaror holatni emas, "olomon hujumi"ni ko'rsatadi:
    boshlanish so'rovlari (/api/state, /api/tasks, /api/top) bir
    sekundda to'planib, p95 ni sun'iy ko'taradi. Ikkalasi ham muhim,
    lekin ular alohida o'lchanishi kerak.
    """
    if delay:
        await asyncio.sleep(delay)
    idata = init_data(uid)
    await call(sess, stats, "/api/state", {"initData": idata})
    await call(sess, stats, "/api/tasks", {"initData": idata})
    await call(sess, stats, "/api/top", {"initData": idata})

    solved, coins = 0, 0
    while time.time() < until:
        solved += 1
        coins += 5
        await call(sess, stats, "/api/save", {
            "initData": idata,
            "progress": {
                "coins": coins, "keys": 5,
                "cur": {"stage": 1, "level": 1, "puzzle": solved},
                "solved": {"1-1": solved}, "learned": {}, "muted": False,
            },
        })
        await asyncio.sleep(THINK)
        if solved % 8 == 0:
            await call(sess, stats, "/api/top", {"initData": idata})


async def stage(users: int, seconds: int, uid_base: int, ramp: float = 0.0):
    stats = Stats()
    until = time.time() + seconds + ramp
    conn = aiohttp.TCPConnector(limit=0)     # mijoz tomonda cheklov yo'q
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as sess:
        t0 = time.perf_counter()
        await asyncio.gather(*(
            player(sess, stats, uid_base + i, until,
                   delay=(i / users) * ramp if ramp else 0.0)
            for i in range(users)))
        dur = time.perf_counter() - t0

    total = stats.ok + stats.err
    lat = sorted(stats.lat)
    p50 = statistics.median(lat) if lat else 0
    p95 = lat[int(len(lat) * 0.95)] if lat else 0
    p99 = lat[int(len(lat) * 0.99)] if lat else 0
    rps = total / dur if dur else 0

    print(f"  {users:>4} ta bir vaqtda | {total:>6} so'rov | {rps:>7.1f} so'rov/s "
          f"| p50 {p50:>6.1f} ms | p95 {p95:>7.1f} ms | p99 {p99:>7.1f} ms "
          f"| xato {stats.err}")
    return {"users": users, "rps": rps, "p95": p95, "err": stats.err,
            "by_path": {k: statistics.median(v) for k, v in stats.by_path.items()}}


async def main():
    global THINK
    args = [a for a in sys.argv[1:] if a != "real"]
    if "real" in sys.argv:
        THINK = 25.0                      # haqiqiy o'yin tezligi
        levels = [int(args[0])] if args else [500, 1500, 3000]
        secs = int(args[1]) if len(args) > 1 else 30
        print(f"HAQIQIY TEZLIK rejimi: har puzzle orasida {THINK:.0f} s")
    elif len(args) > 1:
        levels = [int(args[0])]
        secs = int(args[1])
    else:
        levels = [10, 50, 100, 200, 400, 800]
        secs = 12

    print("=" * 96)
    print("Apex Words — yuk sinovi")
    print("=" * 96)
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(BASE + "/health") as r:
                if r.status != 200:
                    raise RuntimeError
        except Exception:
            sys.exit(f"XATO: {BASE} javob bermayapti. "
                     f"Avval: python loadtest/run_server.py")

    # Haqiqiy tezlikda kirishlar yoyiladi — bu barqaror holatni ko'rsatadi.
    # Tez rejimda yoyish yo'q: u chegarani topish uchun.
    ramp = 20.0 if THINK > 5 else 0.0

    results = []
    base = 900000
    for i, n in enumerate(levels):
        results.append(await stage(n, secs, base + i * 5000, ramp))
        await asyncio.sleep(1)

    print("\n" + "=" * 96)
    print("So'rov turlari bo'yicha mediana (oxirgi bosqich):")
    for p, ms in sorted(results[-1]["by_path"].items()):
        print(f"  {p:<22} {ms:>7.1f} ms")

    best = max(results, key=lambda r: r["rps"])
    print(f"\nEng yuqori o'tkazuvchanlik: {best['rps']:.0f} so'rov/s "
          f"({best['users']} ta bir vaqtda)")
    bad = [r for r in results if r["err"] or r["p95"] > 1000]
    if bad:
        print(f"Muammo boshlangan nuqta: {bad[0]['users']} ta bir vaqtda "
              f"(p95 {bad[0]['p95']:.0f} ms, xato {bad[0]['err']})")
    else:
        print("Sinalgan barcha darajalarda xato yo'q va p95 < 1 s")


if __name__ == "__main__":
    asyncio.run(main())

"""
Puzzlelarda uchraydigan, lekin tarjimasi yo'q so'zlarni avtomatik tarjima
qiladi va data/uz_auto.json ga yozadi.

NIMA UCHUN ALOHIDA FAYL.
  translations.py dagi UZ lug'ati QO'LDA yozilgan va u ustuvor. Avtomatik
  tarjima esa xato bo'lishi mumkin (masalan "bat" -> ko'rshapalak yoki
  beysbol tayoqchasi). Ikkalasini alohida saqlash qo'lda tuzatilgan
  narsani avtomatika ustidan yozib yuborishining oldini oladi.

NIMA UCHUN KESH.
  Tarjima tarmoq orqali ketadi va sekin. Natija faylga yoziladi, shuning
  uchun skript qayta ishga tushirilsa faqat YANGI so'zlar so'raladi.

Ishga tushirish:
    python build/autotranslate.py            # yetishmaganini tarjima qiladi
    python build/autotranslate.py --limit 500
"""
from __future__ import annotations

import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "uz_auto.json"

BATCH = 40          # bir so'rovda nechta so'z
WORKERS = 6         # bir vaqtda nechta so'rov

# SO'ROV MUDDATI.
#
# Bu qator bo'lmagani uchun skript qotib qolgan edi: bitta javobsiz
# so'rov butun jarayonni CHEKSIZ to'xtatib turadi. deep_translator
# timeout parametrini tashqariga chiqarmaydi, shuning uchun chegara
# soket darajasida qo'yiladi — u barcha tarmoq amallariga tegishli.
socket.setdefaulttimeout(25)
# Tanaffus endi kerak emas: so'rovlar parallel ketadi va ular orasida
# sun'iy kutish faqat umumiy vaqtni cho'zardi.


def puzzle_words() -> set[str]:
    """Barcha bosqichlardagi yechim va bonus so'zlar."""
    words: set[str] = set()
    for f in sorted((DATA / "puzzles").glob("stage_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for lvl in data["levels"]:
            for p in lvl["puzzles"]:
                words.update(p["words"])
                words.update(p.get("bonus", []))
    return words


def load_manual() -> dict:
    """translations.py dagi qo'lda yozilgan lug'at."""
    sys.path.insert(0, str(ROOT / "build"))
    import translations
    return translations.UZ


def main() -> int:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    manual = load_manual()
    cache = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    need = sorted(puzzle_words() - set(manual) - set(cache))
    if limit:
        need = need[:limit]

    print(f"Puzzle so'zlari    : {len(puzzle_words()):,}")
    print(f"Qo'lda tarjima     : {len(manual):,}")
    print(f"Avtomatik keshda   : {len(cache):,}")
    print(f"Tarjima kerak      : {len(need):,}")
    if not need:
        print("Hammasi tayyor.")
        return 0

    from deep_translator import GoogleTranslator
    tr = GoogleTranslator(source="en", target="uz")

    def fetch(chunk: list[str]) -> list:
        """
        Bir bo'lakni tarjima qiladi. Yiqilsa — IKKIGA BO'LADI.

        Ilgari yiqilgan bo'lak bittalab qayta so'ralardi: 40 so'z uchun
        40 ta alohida so'rov. Ikkiga bo'lish esa ~log2 qadamda aybdor
        so'zni ajratadi va qolganlarini bitta so'rovda oladi.
        """
        if not chunk:
            return []
        try:
            return tr.translate_batch([w.lower() for w in chunk])
        except Exception:
            if len(chunk) == 1:
                return [None]
            mid = len(chunk) // 2
            return fetch(chunk[:mid]) + fetch(chunk[mid:])

    chunks = [need[i:i + BATCH] for i in range(0, len(need), BATCH)]
    done = 0
    t0 = time.time()

    # PARALLEL. Ish tarmoqqa bog'liq: jarayonning deyarli butun vaqti
    # javob kutishga ketadi. Ketma-ket bajarilganda 240 ta so'rov
    # birin-ketin kutilardi; bir nechta oqim bilan ular ustma-ust tushadi.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch, c): c for c in chunks}
        for fut in as_completed(futures):
            chunk = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                print(f"  bo'lak o'tkazib yuborildi: {e}")
                res = []

            for w, uz in zip(chunk, res):
                if not uz:
                    continue
                uz = uz.strip().lower()
                if not uz:
                    continue
                # Tarjima inglizchaga TENG bo'lsa ham yozamiz.
                #
                # Ilgari bunday so'zlar tashlab yuborilardi va ular hech qachon
                # keshga tushmasdi — har ishga tushirishda qaytadan so'ralardi
                # va o'yinchi "tarjima topilmadi" ko'rardi. Aslida ko'p so'z
                # o'zbekchada ham xuddi shunday yoziladi (radio, taksi, futbol),
                # ya'ni bu haqiqiy tarjima. Yozib qo'ygan afzal.
                cache[w] = uz
            done += len(chunk)

            # Vaqti-vaqti bilan saqlaymiz: uzilib qolsa ish yo'qolmaydi
            if done % (BATCH * 5) < BATCH or done >= len(need):
                CACHE.write_text(json.dumps(cache, ensure_ascii=False,
                                            indent=0, sort_keys=True),
                                 encoding="utf-8")
            el = time.time() - t0
            rate = done / el if el else 0
            left = (len(need) - done) / rate if rate else 0
            print(f"  {done:>5}/{len(need)}  (keshda {len(cache):,})  "
                  f"{rate:.0f} so'z/s  taxminan {left / 60:.1f} daq qoldi",
                  flush=True)

    CACHE.write_text(json.dumps(cache, ensure_ascii=False,
                                indent=0, sort_keys=True), encoding="utf-8")
    print(f"\nTayyor. Keshda jami {len(cache):,} tarjima -> {CACHE.name}")
    print(f"Vaqt: {(time.time() - t0) / 60:.1f} daqiqa")
    return 0


if __name__ == "__main__":
    sys.exit(main())

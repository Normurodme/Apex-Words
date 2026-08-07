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
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "uz_auto.json"

BATCH = 40          # bir so'rovda nechta so'z
PAUSE = 0.6         # so'rovlar orasidagi tanaffus (soniya)


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

    done = 0
    for i in range(0, len(need), BATCH):
        chunk = need[i:i + BATCH]
        res = None
        try:
            res = tr.translate_batch([w.lower() for w in chunk])
        except Exception:
            # Guruh so'rovi bitta yomon so'z tufayli butunlay yiqiladi.
            # Shunda bittalab o'tamiz: qolganlari baribir tarjima bo'ladi.
            res = []
            for w in chunk:
                try:
                    res.append(tr.translate(w.lower()))
                except Exception:
                    res.append(None)
                time.sleep(0.15)

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

        # Har bo'lakdan keyin saqlaymiz: uzilib qolsa ish yo'qolmaydi
        CACHE.write_text(json.dumps(cache, ensure_ascii=False,
                                    indent=0, sort_keys=True), encoding="utf-8")
        print(f"  {done:>5}/{len(need)}  (keshda {len(cache):,})")
        time.sleep(PAUSE)

    print(f"\nTayyor. Keshda jami {len(cache):,} tarjima -> {CACHE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

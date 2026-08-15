"""
Bonus qamrovi: harflardan tuziladigan so'z qabul qilinmay qolyaptimi?

Savol oddiy: o'yinchi to'g'ri inglizcha so'z yozsa, o'yin uni qabul
qiladimi? Bonus ro'yxati generatsiya paytidagi lug'atdan tuziladi,
lug'atning o'zi esa chastota bo'sag'asi bilan cheklangan. Demak
bo'sag'adan pastdagi haqiqiy so'zlar "noto'g'ri" deb rad etiladi.

Bu skript KENGROQ manbadan (NLTK words) foydalanib, har puzzle uchun
qabul qilinmaydigan so'zlarni topadi va ularni chastota bo'yicha
saralaydi — ya'ni o'yinchi ko'p uchratadigan so'zlar birinchi chiqadi.

    python build/audit_coverage.py            # xulosa
    python build/audit_coverage.py 3.0        # bo'sag'ani o'zgartirib
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import nltk

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
nltk.data.path.insert(0, str(ROOT / "build" / "nltk_data"))

from nltk.corpus import words as nltk_words     # noqa: E402
from wordfreq import zipf_frequency             # noqa: E402

MIN_LEN, MAX_LEN = 3, 9
# Qanchalik ko'p ishlatiladigan so'zgacha tekshiramiz. FULL_ZIPF (3.05)
# dan PAST: aynan bo'sag'adan tushib qolganlarni ko'rish maqsad.
THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 2.5


def signature(w: str) -> str:
    return "".join(sorted(w))


def main() -> int:
    import build_dictionary as B   # BLOCKLIST/MANUAL_DROP shu yerdan

    print("Kengroq lug'at tayyorlanmoqda...")
    ref = set()
    for w in nltk_words.words():
        if not w.islower() or not w.isalpha() or not w.isascii():
            continue
        if not (MIN_LEN <= len(w) <= MAX_LEN):
            continue
        if w in B.BLOCKLIST:
            continue
        if zipf_frequency(w, "en") >= THRESHOLD:
            ref.add(w.upper())
    print(f"  {len(ref):,} ta so'z (zipf >= {THRESHOLD})")

    idx = defaultdict(list)
    for w in ref:
        idx[signature(w)].append(w)

    index = json.loads((DATA / "puzzles" / "index.json").read_text(encoding="utf-8"))
    missing = Counter()
    affected = 0
    n_pz = 0

    for st in index["stages"]:
        f = DATA / "puzzles" / f"stage_{st['stage']:02d}.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        for lvl in data["levels"]:
            for pz in lvl["puzzles"]:
                n_pz += 1
                letters = pz["letters"].upper()
                known = {w.upper() for w in pz["words"]} | \
                        {w.upper() for w in pz["bonus"]}

                found = set()
                seen = set()
                for size in range(MIN_LEN, len(letters) + 1):
                    for combo in combinations(letters, size):
                        sig = "".join(sorted(combo))
                        if sig in seen:
                            continue
                        seen.add(sig)
                        found.update(idx.get(sig, ()))

                gap = found - known
                if gap:
                    affected += 1
                    for w in gap:
                        missing[w] += 1

    print()
    print("=" * 66)
    print("Bonus qamrovi")
    print("=" * 66)
    print(f"  puzzle                     : {n_pz:,}")
    print(f"  qabul qilinmaydigan so'zi bor: {affected:,} "
          f"({affected / max(n_pz, 1) * 100:.1f}%)")
    print(f"  har xil so'z               : {len(missing):,}")

    # NLTK words korpusida ko'p axlat bor: qisqartma, dialekt, arxaik
    # bo'lak ("rea", "aer", "nei"). Haqiqiy so'zmi yoki yo'qmi — buni
    # WordNet ayta oladi: u LUG'AT, korpus emas.
    from nltk.corpus import wordnet as wn

    def real(w: str) -> bool:
        try:
            return bool(wn.synsets(w.lower()))
        except Exception:
            return False

    genuine = {w: c for w, c in missing.items() if real(w)}
    print(f"  shundan WordNet tanigani     : {len(genuine):,} "
          f"({len(genuine) / max(len(missing), 1) * 100:.0f}%)")

    if genuine:
        print("\n  HAQIQIY so'zlar orasida eng ko'p uchraydigan 40 tasi:")
        for w, c in Counter(genuine).most_common(40):
            print(f"    {w:<12} {c:>4}   {zipf_frequency(w.lower(), 'en'):.2f}")

    if missing:
        print("\n  Umumiy ro'yxatning boshi (axlat ham shu yerda):")
        for w, c in missing.most_common(15):
            mark = " " if real(w) else "  (WordNet tanimaydi)"
            print(f"    {w:<12} {c:>4}   "
                  f"{zipf_frequency(w.lower(), 'en'):.2f}{mark}")

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "build"))
    sys.exit(main())

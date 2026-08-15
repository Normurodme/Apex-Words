"""
Tarjimalarni tekshiradi.

Ma'noni dastur o'zi baholay olmaydi, lekin MEXANIK nuqsonlarni aniq
topadi: rus harflari, tarjimasiz qolgan so'zlar, o'zbek alifbosida yo'q
belgilar, tutuq belgisining har xil ko'rinishlari, bir xil tarjima
ostiga yig'ilib qolgan turli so'zlar va ko'p ma'noli so'zlar.

    python build/audit_translations.py            # xulosa
    python build/audit_translations.py --full     # to'liq ro'yxatlar
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FULL = "--full" in sys.argv

# O'zbek lotin alifbosi + tutuq belgisi + tinish belgilari.
#
# ';' — MA'NOLARNI AJRATUVCHI. Lug'atda ikki ma'noli so'zlar aynan shu
# belgi bilan yoziladi ("bank; qirg'oq"), shuning uchun u ruxsat etilgan.
UZ_OK = set("abcdefghijklmnopqrstuvxyzABCDEFGHIJKLMNOPQRSTUVXYZ"
            "'‘’ʻ- ();/,.0123456789")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# Turkcha/nemischa harflar — avtomatik tarjimadan sizib o'tadi va
# o'zbekcha emas: "büstü", "klişe".
FOREIGN = "äöüßşğıçñáéíóúâêîôûàèìòùåæøþðœ"

# To'g'ri tutuq belgisi. O'zbek imlosida oʻ/gʻ uchun U+02BB (ʻ) tavsiya
# etiladi, amalda esa ko'pincha oddiy apostrof (') ishlatiladi. Muhimi —
# BUTUN lug'atda BIR XIL bo'lishi.
APOSTROPHES = {"'": "oddiy apostrof", "‘": "chap qo'shtirnoq",
               "’": "o'ng qo'shtirnoq", "ʻ": "tutuq belgisi (U+02BB)"}


def load_puzzle_words():
    """Puzzlelarda ishlatilgan yechim va bonus so'zlar."""
    index = json.loads((DATA / "puzzles" / "index.json").read_text(encoding="utf-8"))
    sol, bon = Counter(), Counter()
    for st in index["stages"]:
        f = DATA / "puzzles" / f"stage_{st['stage']:02d}.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        for lvl in data["levels"]:
            for pz in lvl["puzzles"]:
                for w in pz["words"]:
                    sol[w.upper()] += 1
                for w in pz["bonus"]:
                    bon[w.upper()] += 1
    return sol, bon


def main() -> int:
    dic: dict[str, str] = json.loads((DATA / "dict.json").read_text(encoding="utf-8"))
    sol, bon = load_puzzle_words()
    used = set(sol) | set(bon)

    print("=" * 70)
    print("Tarjimalar tekshiruvi")
    print("=" * 70)
    print(f"  lug'atdagi yozuvlar : {len(dic):,}")
    print(f"  yechim so'zlari     : {len(sol):,} xil")
    print(f"  bonus so'zlar       : {len(bon):,} xil")

    problems: dict[str, list] = defaultdict(list)

    # --- 1. Qamrov ---
    for w in used:
        if w not in dic:
            problems["tarjimasi yo'q"].append(w)
    for w in dic:
        if w not in used:
            problems["ishlatilmaydi (ortiqcha)"].append(w)

    # --- 2. Mexanik nuqsonlar ---
    apos_use = Counter()
    same_as_english = []
    for w, t in dic.items():
        t = t or ""
        if not t.strip():
            problems["bo'sh tarjima"].append(w)
            continue
        if CYRILLIC.search(t):
            # Kirill 'о' lotin 'o' dan ko'zga farq qilmaydi — shuning
            # uchun uni faqat shunday tekshiruv topa oladi.
            problems["rus harflari"].append(f"{w} -> {t}")
        # Qavs ichi — inglizcha izoh ("chizilgan (draw)"). U ataylab
        # inglizcha, shuning uchun harf tekshiruvidan chiqariladi.
        body = re.sub(r"\([^)]*\)", "", t)
        if any(c in FOREIGN for c in body.lower()):
            problems["chet el harflari (turkcha/nemischa)"].append(f"{w} -> {t}")
        bad = {c for c in body if c not in UZ_OK and not unicodedata.combining(c)}
        if bad:
            problems["o'zbek alifbosida yo'q belgi"].append(
                f"{w} -> {t}  [{''.join(sorted(bad))}]")
        if t.strip().lower() == w.lower():
            same_as_english.append(w)
        if len(t) > 40:
            problems["juda uzun (izoh kabi)"].append(f"{w} -> {t}")
        for a in APOSTROPHES:
            if a in t:
                apos_use[a] += 1
    if same_as_english:
        problems["ingliz so'zining o'zi qolgan"] = same_as_english

    # --- 3. Ko'p ma'nolilik ---
    # Ma'nolar ';' bilan ajratiladi
    multi = [w for w, t in dic.items() if ";" in t]
    # Bir xil tarjima ostidagi turli inglizcha so'zlar
    by_uz: dict[str, list[str]] = defaultdict(list)
    for w, t in dic.items():
        by_uz[t.strip().lower()].append(w)
    collisions = {t: ws for t, ws in by_uz.items() if len(ws) >= 6}

    # --- Natija ---
    print("\n  MEXANIK TEKSHIRUV")
    for k in ("tarjimasi yo'q", "bo'sh tarjima", "rus harflari",
              "chet el harflari (turkcha/nemischa)",
              "o'zbek alifbosida yo'q belgi", "ingliz so'zining o'zi qolgan",
              "juda uzun (izoh kabi)", "ishlatilmaydi (ortiqcha)"):
        items = problems.get(k, [])
        mark = "OK  " if not items else "!!  "
        print(f"    {mark}{k:34} {len(items):>5}")
        if items and FULL:
            for x in sorted(items)[:40]:
                print(f"          {x}")

    print("\n  TUTUQ BELGISI (bir xil bo'lishi kerak)")
    for a, cnt in apos_use.most_common():
        print(f"    {APOSTROPHES[a]:32} {cnt:>5}")

    print("\n  KO'P MA'NOLILIK")
    print(f"    ikki ma'no berilgan (vergul/slash) : {len(multi):>5}")
    print(f"    bir xil tarjimali guruhlar (>=6)   : {len(collisions):>5}")
    if collisions:
        top = sorted(collisions.items(), key=lambda kv: -len(kv[1]))[:12]
        for t, ws in top:
            print(f"      {t!r}: {len(ws)} ta — {', '.join(sorted(ws)[:8])}"
                  + (" ..." if len(ws) > 8 else ""))

    hard = sum(len(problems.get(k, [])) for k in
               ("tarjimasi yo'q", "bo'sh tarjima", "rus harflari",
                "chet el harflari (turkcha/nemischa)",
                "o'zbek alifbosida yo'q belgi"))
    print()
    if hard:
        print(f"JIDDIY MUAMMO: {hard}")
        return 1
    print("Jiddiy mexanik muammo topilmadi ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())

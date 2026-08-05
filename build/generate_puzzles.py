"""
Apex Words — puzzle generatori.

Har puzzle Word Cookies mantig'ida quriladi:

  1. "Baza so'z" tanlanadi, masalan  STONE
  2. Uning harflari o'yinchiga beriladi:  S T O N E
  3. Shu harflardan tuziladigan BARCHA core so'zlar topiladi:
        ton, one, net, note, tone, nose, stone ...
     Shulardan bir qismi katakli to'rga yechim sifatida qo'yiladi.
  4. Qolgan barcha haqiqiy so'zlar (full ro'yxatdan) bonus bo'ladi:
     o'yinchi ularni topsa +1 ochko oladi, lekin to'rda katak yo'q.

So'zlarning birortasi qo'lda yozilmaydi — hammasi build_dictionary.py chiqargan
ro'yxatlardan olinadi va har biri "berilgan harflardan tuziladimi" tekshiruvidan
o'tadi (Counter(word) <= Counter(letters)).

Ishga tushirish:
    python build/generate_puzzles.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "puzzles"

SEED = 20260802          # takrorlanuvchi natija uchun
PUZZLES_PER_LEVEL = 50

# --- Qiyinlik progressiyasi -------------------------------------------------
#
# Har daraja uchun: baza so'z uzunligi -> nechta puzzle.
# 1-bosqich 3 harfdan boshlanadi, 2-bosqich oxirida 6 harfga chiqadi.
# Qolgan 10 bosqich keyin shu jadvalning davomi sifatida qo'shiladi (7..9 harf).
#
LEVEL_PLAN = [
    # (bosqich, daraja, daraja nomi, [(baza_uzunligi, nechta), ...])
    # 3 harfli baza so'zlar tabiiy ravishda kam (anagrammasi bor 3 harfli so'zlar
    # havzasi ~29 ta), shuning uchun 1-daraja ularning hammasini ishlatib,
    # qolganini 4 harfli bazalar bilan to'ldiradi.
    (1, 1, "England", [(3, 20), (4, 30)]),
    (1, 2, "Japan",   [(4, 50)]),
    (1, 3, "Brazil",  [(4, 35), (5, 15)]),
    (1, 4, "Egypt",   [(5, 50)]),
    (1, 5, "Canada",  [(5, 50)]),
    (2, 1, "Paris",   [(5, 50)]),
    (2, 2, "Tokyo",   [(5, 25), (6, 25)]),
    (2, 3, "Dubai",   [(6, 50)]),
    (2, 4, "Rome",    [(6, 50)]),
    (2, 5, "London",  [(6, 50)]),

    # --- 3..12 bosqichlar ---
    #
    # Taqsimot O'LCHOV bilan tuzilgan. Har uzunlik uchun nechta yaroqli
    # baza borligi oldindan sanaldi (CORE_ZIPF = 3.60 da):
    #
    #     3h: 28   4h: 293   5h: 621   6h: 833   7h: 810   8h: 722   9h: 566
    #
    # Rejadagi ehtiyoj shu havzadan oshmasligi kerak:
    #
    #     3h: 20   4h: 230   5h: 300   6h: 700   7h: 750   8h: 600   9h: 400
    #                                                          jami = 3000
    #
    # Ilgari uzun bazalar juda ko'p rejalashtirilgan edi (8h uchun 1135 ta
    # kerak bo'lib qolgan, havzada esa 722) va generator 8-bosqichda
    # to'xtagan. Endi qiyinlik sekinroq o'sadi: har uzunlikda ikki-uch
    # bosqich turiladi va shu bilan havza yetadi.
    (3, 1, "Pizza",  [(5, 50)]),
    (3, 2, "Sushi",  [(6, 50)]),
    (3, 3, "Burger", [(6, 50)]),
    (3, 4, "Pasta",  [(6, 50)]),
    (3, 5, "Tacos",  [(6, 50)]),

    (4, 1, "Lion",  [(6, 50)]),
    (4, 2, "Panda", [(6, 50)]),
    (4, 3, "Eagle", [(6, 50)]),
    (4, 4, "Shark", [(6, 50)]),
    (4, 5, "Tiger", [(6, 50)]),

    (5, 1, "Soccer",  [(6, 50)]),
    (5, 2, "Tennis",  [(6, 50)]),
    (5, 3, "Boxing",  [(6, 50)]),
    (5, 4, "Cricket", [(7, 50)]),
    (5, 5, "Hockey",  [(7, 50)]),

    (6, 1, "Apple",  [(7, 50)]),
    (6, 2, "Mango",  [(7, 50)]),
    (6, 3, "Banana", [(7, 50)]),
    (6, 4, "Cherry", [(7, 50)]),
    (6, 5, "Orange", [(7, 50)]),

    (7, 1, "Eiffel",       [(7, 50)]),
    (7, 2, "Pisa",         [(7, 50)]),
    (7, 3, "Big Ben",      [(7, 50)]),
    (7, 4, "Petronas",     [(7, 50)]),
    (7, 5, "Burj Khalifa", [(7, 50)]),

    (8, 1, "Tesla",    [(7, 50)]),
    (8, 2, "Toyota",   [(7, 50)]),
    (8, 3, "Ferrari",  [(7, 50)]),
    (8, 4, "Bugatti",  [(8, 50)]),
    (8, 5, "Mercedes", [(8, 50)]),

    (9, 1, "Dragon",  [(8, 50)]),
    (9, 2, "Phoenix", [(8, 50)]),
    (9, 3, "Unicorn", [(8, 50)]),
    (9, 4, "Kraken",  [(8, 50)]),
    (9, 5, "Griffin", [(8, 50)]),

    (10, 1, "Diamond",  [(8, 50)]),
    (10, 2, "Ruby",     [(8, 50)]),
    (10, 3, "Emerald",  [(8, 50)]),
    (10, 4, "Pearl",    [(8, 50)]),
    (10, 5, "Sapphire", [(8, 50)]),

    (11, 1, "Sherlock",   [(9, 50)]),
    (11, 2, "Dracula",    [(9, 50)]),
    (11, 3, "Aladdin",    [(9, 50)]),
    (11, 4, "Hercules",   [(9, 50)]),
    (11, 5, "Robin Hood", [(9, 50)]),

    (12, 1, "Pyramid",    [(9, 50)]),
    (12, 2, "Colosseum",  [(9, 50)]),
    (12, 3, "Petra",      [(9, 50)]),
    (12, 4, "Stonehenge", [(9, 50)]),
    (12, 5, "Taj Mahal",  [(9, 50)]),
]

STAGE_NAMES = {
    1: "Countries", 2: "Cities",   3: "Foods",   4: "Animals",
    5: "Sports",    6: "Fruits",   7: "Towers",  8: "Cars",
    9: "Mythical", 10: "Gems",    11: "Legends", 12: "Wonders",
}

# Baza uzunligiga qarab to'rdagi yechim so'zlari soni: (eng kami, eng ko'pi)
SOLUTION_RANGE = {
    3: (2, 3),
    4: (3, 5),
    5: (4, 6),
    6: (5, 8),
    7: (6, 9),
    8: (7, 10),
    9: (7, 10),
}

MIN_WORD_LEN = 3


def load_list(name: str) -> list[str]:
    p = DATA / name
    if not p.exists():
        sys.exit(f"XATO: {p} topilmadi. Avval 'python build/build_dictionary.py' ni ishga tushiring.")
    return p.read_text(encoding="utf-8").split()


def signature(word: str) -> str:
    """So'zning harf 'imzosi' — harflari alfavit tartibida. cat va act -> 'act'."""
    return "".join(sorted(word))


def build_index(wordlist: list[str]) -> dict[str, list[str]]:
    """imzo -> shu imzoga ega so'zlar (anagrammalar bir joyda)."""
    idx = defaultdict(list)
    for w in wordlist:
        idx[signature(w)].append(w)
    return idx


def words_from_letters(letters: str, index: dict[str, list[str]]) -> list[str]:
    """
    Berilgan harflardan tuziladigan barcha so'zlar.

    Harflarning barcha kombinatsiyalarini (uzunligi 3 dan boshlab) olib,
    imzosi bo'yicha indeksdan qidiradi. 6 harf uchun bu bor-yo'g'i 42 ta
    qidiruv — barcha lug'atni aylanib chiqishdan ancha tez.
    """
    found = []
    seen_sigs = set()
    n = len(letters)
    for size in range(MIN_WORD_LEN, n + 1):
        for combo in combinations(letters, size):
            sig = "".join(sorted(combo))
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            found.extend(index.get(sig, ()))
    return found


def verify(word: str, letters: str) -> bool:
    """Nazorat tekshiruvi: so'z haqiqatan shu harflardan tuziladimi."""
    return not (Counter(word) - Counter(letters))


def main():
    rng = random.Random(SEED)

    print("=" * 62)
    print("Apex Words — puzzle generatori")
    print("=" * 62)

    core = load_list("wordlist_core.txt")
    full = load_list("wordlist_full.txt")
    core_set, full_set = set(core), set(full)
    print(f"\nLug'at: core {len(core):,} / full {len(full):,}")

    core_idx = build_index(core)
    full_idx = build_index(full)

    from wordfreq import zipf_frequency
    freq = {w: zipf_frequency(w, "en") for w in full}

    # --- 1-qadam: har uzunlik uchun yaroqli baza so'zlar havzasini tayyorlash ---
    print("\nBaza so'zlar havzasi tayyorlanmoqda...")
    pools: dict[int, list[dict]] = {}
    needed_lengths = sorted({L for _, _, _, plan in LEVEL_PLAN for L, _ in plan})

    for L in needed_lengths:
        lo, hi = SOLUTION_RANGE[L]
        pool = []
        used_sigs = set()

        # Baza CORE ro'yxatdan olinadi.
        #
        # Uni full'dan olib ko'rdim — havza kengayadi, lekin puzzle buziladi:
        # klassik qoidaga ko'ra har puzzleda HAMMA harfni ishlatadigan so'z
        # bo'lishi shart, u esa aynan bazaning o'zi. Baza core'da bo'lmasa,
        # o'sha eng uzun so'z to'rga tusha olmaydi.
        #
        # Havza yetishi uchun buning o'rniga CORE_ZIPF bo'sag'asi
        # sozlandi (o'lchov: 3.60 da 3873 yaroqli baza, 3000 kerak).
        for base in (w for w in core if len(w) == L):
            sig = signature(base)
            if sig in used_sigs:        # anagrammalardan faqat bittasi
                continue

            all_core = words_from_letters(base, core_idx)
            if len(all_core) < lo:
                continue

            # To'rga tushadigan yechimlar: eng uzunlari + eng ko'p ishlatiladiganlari.
            # Baza so'zning o'zi doim bor (u eng uzun).
            ranked = sorted(all_core, key=lambda w: (-len(w), -freq.get(w, 0), w))
            solutions = ranked[:hi]
            if len(solutions) < lo:
                continue

            # Bonus: shu harflardan chiqadigan qolgan hamma haqiqiy so'z
            bonus = sorted(set(words_from_letters(base, full_idx)) - set(solutions))

            used_sigs.add(sig)
            pool.append({
                "base": base,
                "letters": base,
                "solutions": sorted(solutions, key=lambda w: (len(w), w)),
                "bonus": bonus,
            })
        pools[L] = pool
        print(f"  {L} harf: {len(pool):,} ta yaroqli baza")

    # --- 2-qadam: darajalarga taqsimlash ---
    print("\nDarajalar yig'ilmoqda...")
    cursor = {L: 0 for L in needed_lengths}
    for L in needed_lengths:
        # Havzani qiyinlik bo'yicha tartiblaymiz, keyin darajalar ketma-ket oladi.
        pools[L].sort(key=lambda p: difficulty(p, freq))

    stages: dict[int, dict] = {}
    total = 0
    for stage_no, level_no, level_name, plan in LEVEL_PLAN:
        picked = []
        for L, count in plan:
            pool = pools[L]
            start = cursor[L]
            chunk = pool[start:start + count]
            if len(chunk) < count:
                sys.exit(
                    f"XATO: {L} harfli baza so'zlar yetmadi "
                    f"({level_name}: {count} kerak, {len(chunk)} bor). "
                    f"CORE_ZIPF ni pasaytiring yoki SOLUTION_RANGE ni yumshating."
                )
            cursor[L] = start + count
            picked.extend(chunk)

        picked.sort(key=lambda p: difficulty(p, freq))

        puzzles = []
        for i, p in enumerate(picked, 1):
            letters = list(p["letters"])
            rng.shuffle(letters)                 # g'ildirakda tasodifiy joylashsin
            puzzles.append({
                "id": f"{stage_no}-{level_no}-{i}",
                "letters": "".join(letters).upper(),
                "words": [w.upper() for w in p["solutions"]],
                "bonus": [w.upper() for w in p["bonus"]],
            })

        stages.setdefault(stage_no, {
            "stage": stage_no,
            "name": STAGE_NAMES[stage_no],
            "levels": [],
        })["levels"].append({
            "level": level_no,
            "name": level_name,
            "puzzles": puzzles,
        })
        total += len(puzzles)
        lens = [len(p["letters"]) for p in puzzles]
        sols = [len(p["words"]) for p in puzzles]
        print(f"  {stage_no}-{level_no} {level_name:9s} "
              f"{len(puzzles)} puzzle | harf {min(lens)}-{max(lens)} | "
              f"yechim {min(sols)}-{max(sols)} | bonus jami "
              f"{sum(len(p['bonus']) for p in puzzles)}")

    # --- 3-qadam: nazorat tekshiruvi ---
    print("\nNazorat tekshiruvi...")
    errors = validate(stages, core_set, full_set)
    if errors:
        for e in errors[:20]:
            print("  XATO:", e)
        sys.exit(f"\n{len(errors)} ta xato topildi — fayllar yozilmadi.")
    print("  Hamma puzzle tekshiruvdan o'tdi ✓")

    # --- 4-qadam: yozish ---
    # Ikki joyga yoziladi: data/puzzles (manba) va web_app/data (nginx tarqatadi).
    web_out = ROOT / "web_app" / "data"
    OUT.mkdir(parents=True, exist_ok=True)
    web_out.mkdir(parents=True, exist_ok=True)

    index = []
    for stage_no, payload in sorted(stages.items()):
        blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        name = f"stage_{stage_no:02d}.json"
        (OUT / name).write_text(blob, encoding="utf-8")
        (web_out / name).write_text(blob, encoding="utf-8")
        kb = len(blob.encode("utf-8")) / 1024
        print(f"  yozildi: {name}  ({kb:.0f} KB)")
        index.append({
            "stage": stage_no,
            "name": payload["name"],
            "file": name,
            "levels": [{"level": l["level"], "name": l["name"],
                        "puzzles": len(l["puzzles"])} for l in payload["levels"]],
        })

    # Bosqichlar ro'yxati — Mini App menyusi shuni o'qiydi
    idx_blob = json.dumps({"stages": index}, ensure_ascii=False, indent=1)
    (OUT / "index.json").write_text(idx_blob, encoding="utf-8")
    (web_out / "index.json").write_text(idx_blob, encoding="utf-8")
    print(f"  yozildi: index.json")

    print(f"\nJami {total} puzzle. Tayyor.")


def difficulty(p: dict, freq: dict) -> tuple:
    """
    Puzzle qiyinligi. Kichik son = oson.

    Uch omil: yechim so'zlari soni, eng uzun so'z uzunligi va so'zlarning
    noyobligi (kam ishlatiladigan so'z = qiyin).
    """
    sols = p["solutions"]
    rarity = sum(6.0 - freq.get(w, 3.0) for w in sols) / len(sols)
    longest = max(len(w) for w in sols)
    return (len(sols) + longest * 0.8 + rarity * 1.6, p["base"])


def validate(stages: dict, core_set: set, full_set: set) -> list[str]:
    """Har bir puzzle'ni mustaqil qayta tekshiradi."""
    errors = []
    seen_ids = set()
    seen_letters = set()

    for stage_no, payload in stages.items():
        for lvl in payload["levels"]:
            for p in lvl["puzzles"]:
                pid, letters = p["id"], p["letters"].lower()

                if pid in seen_ids:
                    errors.append(f"{pid}: id takrorlandi")
                seen_ids.add(pid)

                sig = signature(letters)
                if sig in seen_letters:
                    errors.append(f"{pid}: '{letters}' harf to'plami takrorlandi")
                seen_letters.add(sig)

                if not p["words"]:
                    errors.append(f"{pid}: yechim so'zlari yo'q")

                # Eng uzun yechim barcha harflarni ishlatishi kerak —
                # aks holda g'ildirakda ortiqcha harf qoladi.
                if max(len(w) for w in p["words"]) != len(letters):
                    errors.append(f"{pid}: '{letters}' harflarining hammasini "
                                  f"ishlatadigan yechim yo'q")

                for w in p["words"]:
                    lw = w.lower()
                    if lw not in core_set:
                        errors.append(f"{pid}: '{w}' core lug'atda yo'q")
                    if not verify(lw, letters):
                        errors.append(f"{pid}: '{w}' '{letters}' harflaridan tuzilmaydi")

                for w in p["bonus"]:
                    lw = w.lower()
                    if lw not in full_set:
                        errors.append(f"{pid}: bonus '{w}' full lug'atda yo'q")
                    if not verify(lw, letters):
                        errors.append(f"{pid}: bonus '{w}' harflardan tuzilmaydi")
                    if w in p["words"]:
                        errors.append(f"{pid}: '{w}' ham yechim, ham bonus")
    return errors


if __name__ == "__main__":
    sys.exit(main())

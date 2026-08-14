"""
Barcha puzzle so'zlarini va bonuslarni tekshiradi.

generate_puzzles.py o'zining ichki tekshiruvini yuritadi, lekin u
yaratish paytidagi lug'atga qaraydi. Bu skript esa MUSTAQIL: diskdagi
tayyor fayllarni o'qib, o'yinchi ko'radigan holatni tekshiradi.
Lug'at qayta qurilgandan keyin puzzlelar yangilanmasa, farq shu yerda
ko'rinadi.

    python build/audit_words.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MIN_LEN = 3
MAX_LEN = 9

PRONOUNS = {w.upper() for w in (
    "i me my mine myself you your yours yourself yourselves he him his "
    "himself she her hers herself it its itself we us our ours ourselves "
    "they them their theirs themselves who whom whose whoever whatever "
    "whichever which what that this these those anyone anybody anything "
    "someone somebody something everyone everybody everything nobody "
    "nothing none oneself one each either neither both few many several "
    "all any most some the an a").split()}


def load(name):
    return {w.upper() for w in (DATA / name).read_text(encoding="utf-8").split()}


def buildable(word: str, letters: str) -> bool:
    return not (Counter(word) - Counter(letters))


def main() -> int:
    core = load("wordlist_core.txt")
    full = load("wordlist_full.txt")
    dic = json.loads((DATA / "dict.json").read_text(encoding="utf-8"))
    index = json.loads((DATA / "puzzles" / "index.json").read_text(encoding="utf-8"))

    problems: list[str] = []
    n_pz = n_words = n_bonus = 0
    lens = Counter()
    seen_sig: dict[str, str] = {}

    for st in index["stages"]:
        f = DATA / "puzzles" / f"stage_{st['stage']:02d}.json"
        if not f.exists():
            problems.append(f"{f.name} topilmadi")
            continue
        data = json.loads(f.read_text(encoding="utf-8"))

        levels = data["levels"]
        if len(levels) != len(st["levels"]):
            problems.append(f"{f.name}: daraja soni index bilan mos emas")

        for lvl in levels:
            for i, pz in enumerate(lvl["puzzles"]):
                n_pz += 1
                pid = f"{st['stage']}-{lvl['level']}-{i + 1}"
                letters = pz["letters"].upper()
                words = [w.upper() for w in pz["words"]]
                bonus = [w.upper() for w in pz["bonus"]]
                n_words += len(words)
                n_bonus += len(bonus)

                if not (MIN_LEN <= len(letters) <= MAX_LEN):
                    problems.append(f"{pid}: harflar soni {len(letters)}")

                # --- Yechim so'zlari ---
                if not words:
                    problems.append(f"{pid}: yechim yo'q")
                for w in words:
                    lens[len(w)] += 1
                    if w not in core:
                        problems.append(f"{pid}: yechim '{w}' core lug'atda yo'q")
                    if not buildable(w, letters):
                        problems.append(f"{pid}: '{w}' harflardan tuzilmaydi")
                    if not (MIN_LEN <= len(w) <= MAX_LEN):
                        problems.append(f"{pid}: '{w}' uzunligi {len(w)}")
                    if w in PRONOUNS:
                        problems.append(f"{pid}: olmosh '{w}' yechim sifatida")
                    if w not in dic:
                        problems.append(f"{pid}: yechim '{w}' tarjimasiz")

                if len(set(words)) != len(words):
                    problems.append(f"{pid}: yechimlar ichida takror bor")

                # Klassik qoida: hamma harfni ishlatadigan so'z bo'lishi shart
                if not any(len(w) == len(letters) for w in words):
                    problems.append(f"{pid}: hamma harfni ishlatadigan so'z yo'q")

                # --- Bonus so'zlar ---
                for w in bonus:
                    if w not in full:
                        problems.append(f"{pid}: bonus '{w}' full lug'atda yo'q")
                    if not buildable(w, letters):
                        problems.append(f"{pid}: bonus '{w}' harflardan tuzilmaydi")
                    if w not in dic:
                        problems.append(f"{pid}: bonus '{w}' tarjimasiz")

                if len(set(bonus)) != len(bonus):
                    problems.append(f"{pid}: bonuslar ichida takror bor")
                both = set(words) & set(bonus)
                if both:
                    problems.append(f"{pid}: ham yechim ham bonus: {sorted(both)}")

                # Bir xil harf to'plami ikki marta ishlatilmasin
                sig = "".join(sorted(letters))
                if sig in seen_sig:
                    problems.append(f"{pid}: harflar {seen_sig[sig]} bilan bir xil")
                else:
                    seen_sig[sig] = pid

    # --- Umumiy ---
    print("=" * 66)
    print("So'zlar tekshiruvi")
    print("=" * 66)
    print(f"  puzzle          : {n_pz:,}")
    print(f"  yechim so'zlari : {n_words:,}")
    print(f"  bonus so'zlar   : {n_bonus:,}  (o'rtacha {n_bonus / max(n_pz, 1):.1f})")
    print(f"  core / full     : {len(core):,} / {len(full):,}")
    print(f"  tarjima         : {len(dic):,}")
    print("\n  Yechim uzunliklari:")
    for L in sorted(lens):
        print(f"    {L} harf: {lens[L]:,}")

    # Olmoshlar bonus sifatida ishlashi kerak
    pron_bonus = sum(1 for st in index["stages"]
                     for lvl in json.loads((DATA / "puzzles" /
                                            f"stage_{st['stage']:02d}.json")
                                           .read_text(encoding="utf-8"))["levels"]
                     for pz in lvl["puzzles"]
                     for w in pz["bonus"] if w.upper() in PRONOUNS)
    print(f"\n  olmosh bonus sifatida: {pron_bonus:,}")
    if pron_bonus == 0:
        problems.append("olmoshlar bonus sifatida umuman uchramaydi")

    print()
    if problems:
        print(f"MUAMMO TOPILDI: {len(problems)}")
        for p in problems[:60]:
            print("  -", p)
        if len(problems) > 60:
            print(f"  ... yana {len(problems) - 60} ta")
        return 1
    print("Hammasi joyida ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())

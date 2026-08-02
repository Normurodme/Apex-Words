"""
Puzzle'lardagi har bir so'zning o'zbekcha tarjimasi bormi — shuni tekshiradi.

Ishga tushirish:
    python build/check_coverage.py          # qisqa hisobot
    python build/check_coverage.py --list   # tarjimasi yo'q so'zlarni chiqaradi
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUZ = ROOT / "data" / "puzzles"


def main():
    show = "--list" in sys.argv

    dict_path = ROOT / "web_app" / "data" / "dict.json"
    uz = json.loads(dict_path.read_text(encoding="utf-8")) if dict_path.exists() else {}

    sol, bon = set(), set()
    for f in sorted(PUZ.glob("stage_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for lvl in data["levels"]:
            for p in lvl["puzzles"]:
                sol.update(p["words"])
                bon.update(p["bonus"])
    bon -= sol

    miss_sol = sorted(w for w in sol if not uz.get(w))
    miss_bon = sorted(w for w in bon if not uz.get(w))

    print(f"Lug'atda tarjima: {len(uz):,}")
    print(f"Yechim so'zlari : {len(sol):,}  |  tarjimasi yo'q: {len(miss_sol):,}")
    print(f"Bonus so'zlari  : {len(bon):,}  |  tarjimasi yo'q: {len(miss_bon):,}")

    if show:
        if miss_sol:
            print(f"\n--- YECHIM, tarjimasiz ({len(miss_sol)}) ---")
            for i in range(0, len(miss_sol), 16):
                print(" ".join(miss_sol[i:i + 16]))
        if miss_bon:
            print(f"\n--- BONUS, tarjimasiz ({len(miss_bon)}) ---")
            for i in range(0, len(miss_bon), 16):
                print(" ".join(miss_bon[i:i + 16]))

    # Yechim so'zlarining hammasi tarjima qilingan bo'lishi shart
    return 1 if miss_sol else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Smarter diff: find strings unique to each save.
Goal: isolate chest-related class names/identifiers.
"""
import re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

STR_RE = re.compile(rb"[\x20-\x7e]{4,}")

def strings(data):
    return [m.group().decode("ascii", "replace") for m in STR_RE.finditer(data)]

def string_counter(data):
    return Counter(strings(data))

def main():
    A = load("A.sav")
    B = load("B.sav")
    C = load("C.sav")

    sa = string_counter(A)
    sb = string_counter(B)
    sc = string_counter(C)

    # Strings whose count INCREASED from A→B
    print("=" * 70)
    print("Strings whose count INCREASED from A → B (+1 chest 'Front_Church')")
    print("=" * 70)
    increased_ab = []
    for s, n_b in sb.items():
        n_a = sa.get(s, 0)
        if n_b > n_a:
            increased_ab.append((s, n_a, n_b))
    increased_ab.sort(key=lambda t: (-t[2], t[0]))
    for s, n_a, n_b in increased_ab[:80]:
        if len(s) >= 5:
            print(f"  A={n_a:3d} → B={n_b:3d}  {s!r}")

    print()
    print("=" * 70)
    print("Strings whose count INCREASED from B → C (+1 more chest 'Next_to_tent')")
    print("=" * 70)
    increased_bc = []
    for s, n_c in sc.items():
        n_b = sb.get(s, 0)
        if n_c > n_b:
            increased_bc.append((s, n_b, n_c))
    increased_bc.sort(key=lambda t: (-t[2], t[0]))
    for s, n_b, n_c in increased_bc[:80]:
        if len(s) >= 5:
            print(f"  B={n_b:3d} → C={n_c:3d}  {s!r}")

    # Strings present in B but ABSENT from A (truly new)
    print()
    print("=" * 70)
    print("Strings present in B but ABSENT from A (brand-new identifiers)")
    print("=" * 70)
    new_in_b = sorted(set(sb) - set(sa))
    for s in new_in_b:
        if len(s) >= 5:
            print(f"  {s!r}")

    print()
    print("=" * 70)
    print("Strings present in C but ABSENT from B")
    print("=" * 70)
    new_in_c = sorted(set(sc) - set(sb))
    for s in new_in_c:
        if len(s) >= 5:
            print(f"  {s!r}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Structure-record diff experiment.

Goal: identify the binary layout of a placed structure (chest) record by
comparing 3 snapshots of the same world:
  A = empty (no chests)
  B = A + 1 chest (Front_Church)
  C = B + 1 chest (Next_to_tent)

Strategy:
1. Locate longest common prefix between A and B → that's where divergence starts.
2. Locate longest common suffix between A and B → that's where they reconverge.
3. The "interesting bytes" are between those two boundaries in B.
4. Repeat for B vs C.
5. Compare the two interesting regions — if they share structural patterns
   (same length-prefixed name strings, same NameProperty markers, similar
    layout) we have a candidate actor record format.
"""
import sys, os, re, json
from pathlib import Path

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def common_prefix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i

def common_suffix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[len(a)-1-i] == b[len(b)-1-i]:
        i += 1
    return i

def hexdump(data, max_lines=40):
    lines = []
    for i in range(0, min(len(data), max_lines * 16), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<48}  |{ascii_part}|")
    if len(data) > max_lines * 16:
        lines.append(f"... ({len(data) - max_lines * 16} more bytes)")
    return "\n".join(lines)

def find_strings(data, min_len=4):
    """Find printable ASCII runs in the binary."""
    pat = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    return [(m.start(), m.group().decode("ascii", "replace")) for m in pat.finditer(data)]

def diff_pair(name_a, a, name_b, b):
    print(f"\n{'='*70}\n{name_a} ({len(a):,} B)  →  {name_b} ({len(b):,} B)   Δ = {len(b)-len(a):+,} B\n{'='*70}")
    p = common_prefix(a, b)
    s = common_suffix(a, b)
    # Make sure prefix+suffix don't overlap in the smaller file
    if p + s > min(len(a), len(b)):
        s = min(len(a), len(b)) - p
    print(f"Common prefix:  {p:,} B  (0x{p:x})")
    print(f"Common suffix:  {s:,} B")

    # Region in B that's "new"
    b_region = b[p : len(b) - s]
    a_region = a[p : len(a) - s]
    print(f"A's divergent region:  {len(a_region):,} B  @ offset 0x{p:x}")
    print(f"B's divergent region:  {len(b_region):,} B  @ offset 0x{p:x}")

    # Show the strings inside B's new region
    b_strings = find_strings(b_region, min_len=5)
    print(f"\nStrings in B's divergent region ({len(b_strings)} found):")
    for off, s_ in b_strings[:60]:
        print(f"  +0x{off:04x}  {s_!r}")

    return p, s, a_region, b_region

def main():
    A = load("A.sav")
    B = load("B.sav")
    C = load("C.sav")

    p_ab, s_ab, a_reg, b_reg = diff_pair("A", A, "B", B)
    p_bc, s_bc, b2_reg, c_reg = diff_pair("B", B, "C", C)

    # Save divergent regions for manual hex inspection
    open(HERE / "B_minus_A_region.bin", "wb").write(b_reg)
    open(HERE / "C_minus_B_region.bin", "wb").write(c_reg)
    print(f"\nWrote B_minus_A_region.bin ({len(b_reg)} B)")
    print(f"Wrote C_minus_B_region.bin ({len(c_reg)} B)")

    # Check whether C's new region starts identically to B's at any offset
    # (i.e. is C's new chest record bytewise similar to B's new chest record?)
    print(f"\n{'='*70}\nCross-comparison: do the two new regions share structure?\n{'='*70}")
    # Look for the longest substring of c_reg that appears in b_reg
    print("\nFirst 256 bytes of B_minus_A region:")
    print(hexdump(b_reg[:256], 16))
    print("\nFirst 256 bytes of C_minus_B region:")
    print(hexdump(c_reg[:256], 16))

if __name__ == "__main__":
    main()

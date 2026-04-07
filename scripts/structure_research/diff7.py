#!/usr/bin/env python3
"""
Diff the two ACTUAL chest records (589-byte ones, body starts with 17 00 00 00).
Compare:
  (a) B's chest vs C's first chest  → should be byte-identical (same chest, same place)
  (b) C's first chest vs C's second chest → diff = position delta
"""
import struct
from pathlib import Path

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_all(data, needle):
    out, i = [], 0
    while True:
        i = data.find(needle, i)
        if i == -1:
            return out
        out.append(i)
        i += 1

CHEST_SIG = b"\x17\x00\x00\x00"

def get_chest_records(data):
    chests = []
    for off in find_all(data, b"SPWN"):
        length = struct.unpack_from("<I", data, off + 4)[0]
        if length < 100 or length > 10000:
            continue
        body = data[off + 8 : off + 8 + length]
        if body.startswith(CHEST_SIG):
            chests.append((off, length, bytes(body)))
    return chests

def diff_records(a_body, b_body, label_a, label_b):
    print(f"\n{'='*70}\n{label_a}  vs  {label_b}\n{'='*70}")
    n = min(len(a_body), len(b_body))
    diffs = [(i, a_body[i], b_body[i]) for i in range(n) if a_body[i] != b_body[i]]
    print(f"len(a)={len(a_body)}  len(b)={len(b_body)}")
    print(f"{len(diffs)} differing bytes")

    runs = []
    cur = None
    for i, _, _ in diffs:
        if cur is None or i != cur[1] + 1:
            if cur:
                runs.append(cur)
            cur = [i, i]
        else:
            cur[1] = i
    if cur:
        runs.append(cur)

    for start, end in runs:
        length = end - start + 1
        bs = a_body[start:end+1]
        cs = b_body[start:end+1]
        print(f"\n  0x{start:03x}-0x{end:03x} ({length}B)")
        print(f"    {label_a}: {bs.hex(' ')}")
        print(f"    {label_b}: {cs.hex(' ')}")
        if length % 8 == 0 and length >= 8:
            n_d = length // 8
            try:
                a_d = struct.unpack(f"<{n_d}d", bs)
                c_d = struct.unpack(f"<{n_d}d", cs)
                print(f"    {label_a} doubles: {[f'{x:14.4f}' for x in a_d]}")
                print(f"    {label_b} doubles: {[f'{x:14.4f}' for x in c_d]}")
            except struct.error:
                pass

def main():
    B = load("B.sav")
    C = load("C.sav")

    b_chests = get_chest_records(B)
    c_chests = get_chest_records(C)
    print(f"B chests: {len(b_chests)}  C chests: {len(c_chests)}")
    for i, (off, length, _) in enumerate(b_chests):
        print(f"  B chest #{i}: offset 0x{off:x}, body length {length}")
    for i, (off, length, _) in enumerate(c_chests):
        print(f"  C chest #{i}: offset 0x{off:x}, body length {length}")

    if len(b_chests) >= 1 and len(c_chests) >= 2:
        diff_records(b_chests[0][2], c_chests[0][2],
                     "B.chest[0]", "C.chest[0]")
        diff_records(c_chests[0][2], c_chests[1][2],
                     "C.chest[0]", "C.chest[1]")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Walk all SPWN records in B and C. Show their class-ref bytes (offset 0x44+)
to see if chests have a unique signature distinguishable from trees/rocks.
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

def get_spwn_records(data):
    records = []
    for off in find_all(data, b"SPWN"):
        length = struct.unpack_from("<I", data, off + 4)[0]
        if length < 100 or length > 10000:
            continue
        body = data[off + 8 : off + 8 + length]
        records.append((off, length, bytes(body)))
    return records

def classify_record(body):
    """Return a short signature from the class-ref region."""
    # The bytes at offset 0x44 onward seem to be class table indices.
    # Show 16 bytes from 0x44 — this should differ per actor class.
    return body[0x44:0x54].hex(' ')

def main():
    for name in ["A.sav", "B.sav", "C.sav"]:
        data = load(name)
        recs = get_spwn_records(data)
        print(f"\n{'='*70}\n{name}: {len(recs)} SPWN records\n{'='*70}")
        from collections import Counter
        sigs = Counter()
        for off, length, body in recs:
            sig = classify_record(body)
            sigs[sig] += 1
        # Group by class signature
        for sig, count in sigs.most_common():
            print(f"  {count}x  class-ref: {sig}")

        # Also: for each unique signature, show one full record's first 80 bytes
        print(f"\n  Per-class first record dump:")
        seen = set()
        for off, length, body in recs:
            sig = classify_record(body)
            if sig in seen:
                continue
            seen.add(sig)
            print(f"\n    sig={sig}  (offset 0x{off:x}, len={length})")
            print(f"    bytes 0x00-0x80:")
            for i in range(0, 0x80, 16):
                chunk = body[i:i+16]
                print(f"      {i:04x}  {chunk.hex(' ')}  |{''.join(chr(b) if 32<=b<127 else '.' for b in chunk)}|")

if __name__ == "__main__":
    main()

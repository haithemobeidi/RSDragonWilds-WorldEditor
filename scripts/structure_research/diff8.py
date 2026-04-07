#!/usr/bin/env python3
"""
Compare C (2 personal chests) vs D (2 personal chests + 1 ash chest).
Find the new SPWN record(s) and capture the ash chest's class signature
so we can add it to KNOWN_STRUCTURES.
"""
import struct
from pathlib import Path
from collections import Counter

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

def get_spwn(data):
    out = []
    for off in find_all(data, b"SPWN"):
        if off + 8 > len(data):
            continue
        length = struct.unpack_from("<I", data, off + 4)[0]
        if 100 < length < 10000:
            body = bytes(data[off + 8 : off + 8 + length])
            out.append((off, length, body))
    return out

def main():
    C = load("C.sav")
    D = load("D_with_ash_chest.sav")

    c_recs = get_spwn(C)
    d_recs = get_spwn(D)

    print(f"C: {len(c_recs)} SPWN records")
    print(f"D: {len(d_recs)} SPWN records")

    # Group D's records by (length, first4, class_ref_24)
    def fingerprint(body):
        return (len(body), body[:4], body[0x44:0x44+24])

    c_fps = Counter(fingerprint(b) for _, _, b in c_recs)
    d_fps = Counter(fingerprint(b) for _, _, b in d_recs)

    # Print all unique fingerprints in D
    print("\nAll fingerprints in D (length, first4, class_ref_24):")
    for fp, count in d_fps.most_common():
        in_c = c_fps.get(fp, 0)
        marker = "  ← NEW" if in_c == 0 else f"  (was {in_c} in C)"
        length, first4, class_ref = fp
        print(f"  count={count}  len={length}  first4={first4.hex(' ')}  classref={class_ref.hex(' ')}{marker}")

    # For any fingerprints that are NEW in D, dump the first matching record
    print("\n" + "=" * 70)
    print("NEW SPWN records (present in D, absent from C)")
    print("=" * 70)
    new_fps = [fp for fp in d_fps if fp not in c_fps]
    for fp in new_fps:
        for off, length, body in d_recs:
            if fingerprint(body) == fp:
                print(f"\noffset 0x{off:x}, body length {length}, first4 {body[:4].hex(' ')}")
                # Hex dump first 0xa0 bytes
                for i in range(0, min(0xa0, length), 16):
                    chunk = body[i:i+16]
                    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                    print(f"  {i:04x}  {chunk.hex(' '):<48}  |{ascii_part}|")

                # Try interpreting transform doubles at offset 0x14
                if length >= 0x14 + 48:
                    try:
                        doubles = struct.unpack_from("<6d", body, 0x14)
                        print(f"  Transform doubles @ 0x14:")
                        for i, d in enumerate(doubles):
                            print(f"    [{i}] {d:14.4f}")
                    except struct.error:
                        pass
                break  # only first example per fingerprint

if __name__ == "__main__":
    main()

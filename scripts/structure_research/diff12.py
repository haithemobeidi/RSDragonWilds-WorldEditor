#!/usr/bin/env python3
"""
Scanner approach: find all FString-23 occurrences, classify each as "main GUID"
(start of a piece record) vs "reference GUID" by checking what follows it.

A main GUID is followed by: 3 doubles (position) + 3 floats (extras) + uint32 (ref_count).
A ref GUID is followed by something else.
"""
import struct
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_pces(data):
    i = data.find(b"Pces")
    length = struct.unpack_from("<I", data, i + 4)[0]
    return data[i + 8 : i + 8 + length]

def is_plausible_position(x, y, z):
    """A real world position should be roughly in the same range as our chest data."""
    return all(-1e6 < c < 1e6 for c in (x, y, z))

def is_plausible_extra(e):
    """Extras are rotation/scale-ish — small floats, mostly 0-360 or 1.0-ish or up to a few thousand."""
    return -1e5 < e < 1e5

def main():
    for name in ["D_with_ash_chest", "E_with_cabin"]:
        data = load(f"{name}.sav")
        body = find_pces(data)
        print(f"\n{'='*70}\n{name}.sav — Pces body {len(body)} B\n{'='*70}")

        # Find all FString-23 positions
        records = []
        i = 0
        while i < len(body) - 27 - 36 - 4:
            if body[i:i+4] == b"\x17\x00\x00\x00":
                gchunk = body[i+4:i+27]
                if all(0x20 <= b <= 0x7e or b == 0 for b in gchunk) and gchunk[-1] == 0:
                    try:
                        guid = gchunk[:-1].decode("ascii")
                    except UnicodeDecodeError:
                        i += 1
                        continue
                    # Check the 36 bytes after the GUID for a position+extra pattern
                    pos_off = i + 27
                    try:
                        px, py, pz = struct.unpack_from("<3d", body, pos_off)
                        e1, e2, e3 = struct.unpack_from("<3f", body, pos_off + 24)
                        ref_count = struct.unpack_from("<I", body, pos_off + 36)[0]
                    except struct.error:
                        i += 1
                        continue

                    if is_plausible_position(px, py, pz) and ref_count <= 20:
                        # Likely a main record start
                        # Read the 4 bytes before for record index
                        index = struct.unpack_from("<I", body, i - 4)[0] if i >= 4 else 0
                        records.append({
                            "fstring_offset": i,
                            "index": index,
                            "guid": guid,
                            "pos": (px, py, pz),
                            "extra": (e1, e2, e3),
                            "ref_count": ref_count,
                        })
            i += 1

        print(f"Found {len(records)} candidate main records")
        guids = Counter(r["guid"] for r in records)
        print(f"\nDistinct main GUIDs: {len(guids)}")
        for g, c in guids.most_common():
            print(f"  {c:3d}x  {g}")

        # Show all records compactly
        print(f"\nAll {len(records)} records:")
        for r in records:
            print(f"  [id={r['index']:4d}] {r['guid'][:22]}  pos=({r['pos'][0]:9.1f},{r['pos'][1]:9.1f},{r['pos'][2]:9.1f})  extras=({r['extra'][0]:7.1f},{r['extra'][1]:7.1f},{r['extra'][2]:5.1f})  refs={r['ref_count']}")

if __name__ == "__main__":
    main()

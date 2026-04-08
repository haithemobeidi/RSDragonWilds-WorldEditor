#!/usr/bin/env python3
"""
Different approach: find ALL length-prefixed 23-byte strings in the Pces body.
Each one is either a "main GUID" (start of a record) or a "ref" (component anchor).
For each one, show the 4 bytes BEFORE it (potential record index uint32).
"""
import struct
from pathlib import Path

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_pces(data):
    i = data.find(b"Pces")
    length = struct.unpack_from("<I", data, i + 4)[0]
    return data[i + 8 : i + 8 + length]

def find_all_fstrings_23(body):
    """Find every offset where uint32=23 is followed by 23 ASCII bytes ending in NUL."""
    out = []
    i = 0
    while i < len(body) - 27:
        if body[i:i+4] == b"\x17\x00\x00\x00":
            chunk = body[i+4:i+27]
            if all(0x20 <= b <= 0x7e or b == 0 for b in chunk) and chunk[-1] == 0:
                # Probably a valid FString of length 23
                try:
                    s = chunk[:-1].decode("ascii")
                    out.append((i, s))
                except UnicodeDecodeError:
                    pass
        i += 1
    return out

def main():
    for name in ["D_with_ash_chest", "E_with_cabin"]:
        data = load(f"{name}.sav")
        body = find_pces(data)
        print(f"\n{'='*70}\n{name}.sav — Pces body {len(body)} B\n{'='*70}")

        fstrings = find_all_fstrings_23(body)
        print(f"Found {len(fstrings)} FString-23 occurrences")
        print()
        print("Index  Offset  Pre-4 (uint32)  GUID")
        for off, s in fstrings[:80]:
            pre4 = body[off-4:off] if off >= 4 else b""
            pre_u32 = struct.unpack("<I", pre4)[0] if len(pre4) == 4 else 0
            print(f"  0x{off:04x}    0x{off-4:04x}={pre_u32:6d}  {s}")

if __name__ == "__main__":
    main()

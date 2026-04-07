#!/usr/bin/env python3
"""
Locate the SPWN chunk and dump its contents from B and C.
Compare them to understand placed-actor record layout.
"""
import struct
from pathlib import Path

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_all(data, needle):
    """Yield all offsets where needle appears."""
    i = 0
    while True:
        i = data.find(needle, i)
        if i == -1:
            return
        yield i
        i += 1

def hexdump(data, base=0, max_lines=64):
    lines = []
    for i in range(0, min(len(data), max_lines * 16), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{base+i:08x}  {hex_part:<48}  |{ascii_part}|")
    if len(data) > max_lines * 16:
        lines.append(f"... ({len(data) - max_lines * 16} more bytes)")
    return "\n".join(lines)

def show_chunk(label, data):
    """A 4-byte chunk tag is usually followed by a uint32 length."""
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    print(f"Total size: {len(data):,} bytes")
    # Find all chunk tags (4 ASCII uppercase letters followed by binary)
    tags = ["INFO", "CINF", "GLOB", "CNIX", "PNIX", "CDEF", "CDVE",
            "LVLS", "SPWN", "PROP", "CLST", "PRCS", "Pces", "Cmplm",
            "SATS", "SAVE", "METAL"]
    found = []
    for t in tags:
        for off in find_all(data, t.encode()):
            # Read the 4 bytes that follow as a uint32 length (little-endian)
            if off + 8 <= len(data):
                length = struct.unpack_from("<I", data, off + 4)[0]
                found.append((off, t, length))
    found.sort()
    print(f"\nChunk tags found ({len(found)}):")
    for off, t, length in found:
        marker = ""
        if length < 200000 and length > 0:
            marker = "  ← plausible chunk length"
        print(f"  0x{off:08x}  {t}  next4=0x{length:08x} ({length:,}){marker}")

def main():
    A = load("A.sav")
    B = load("B.sav")
    C = load("C.sav")

    show_chunk("A.sav (empty)", A)
    show_chunk("B.sav (+1 chest)", B)
    show_chunk("C.sav (+2 chests)", C)

    # Find SPWN in B and C
    print("\n\n" + "=" * 70)
    print("SPWN chunk dumps")
    print("=" * 70)
    for label, data in [("B", B), ("C", C)]:
        for off in find_all(data, b"SPWN"):
            length = struct.unpack_from("<I", data, off + 4)[0]
            print(f"\n--- {label}.sav SPWN @ 0x{off:x}, declared length 0x{length:x} ({length:,} B) ---")
            # Show 384 bytes from the chunk start
            print(hexdump(data[off : off + 384], base=off, max_lines=24))

if __name__ == "__main__":
    main()

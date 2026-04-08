#!/usr/bin/env python3
"""
Compare the Pces chunk in D (508 B, no cabin) vs E (7,822 B, +33 cabin pieces).
Goal: identify the per-piece record format.

Strategy:
1. Locate the Pces chunk in both files (it's a 4-byte tag + 4-byte length + body)
2. Show D's full Pces body (small — only 508 B)
3. Show the start of E's Pces body
4. Find any obvious repeating record patterns (look for class strings,
   common 4-byte markers, repeating block sizes)
"""
import struct
from pathlib import Path

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_pces(data):
    """Find the Pces chunk; return (offset, length, body)."""
    i = data.find(b"Pces")
    if i == -1:
        return None
    length = struct.unpack_from("<I", data, i + 4)[0]
    body = data[i + 8 : i + 8 + length]
    return (i, length, body)

def hexdump(data, base=0, max_lines=80):
    lines = []
    for i in range(0, min(len(data), max_lines * 16), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{base+i:08x}  {hex_part:<48}  |{ascii_part}|")
    if len(data) > max_lines * 16:
        lines.append(f"... ({len(data) - max_lines * 16} more bytes)")
    return "\n".join(lines)

def find_strings(data, min_len=5):
    import re
    pat = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    return [(m.start(), m.group().decode("ascii", "replace")) for m in pat.finditer(data)]

def main():
    D = load("D_with_ash_chest.sav")
    E = load("E_with_cabin.sav")

    d_pces = find_pces(D)
    e_pces = find_pces(E)

    print(f"D Pces: offset 0x{d_pces[0]:x}, length {d_pces[1]} B")
    print(f"E Pces: offset 0x{e_pces[0]:x}, length {e_pces[1]} B")
    print(f"Delta: {e_pces[1] - d_pces[1]} B (+{e_pces[1] - d_pces[1]} for 33 pieces = ~{(e_pces[1] - d_pces[1]) / 33:.1f} B/piece)")

    # === Full dump of D's Pces (small) ===
    print("\n" + "=" * 70)
    print(f"D Pces body ({d_pces[1]} bytes) — full hex dump")
    print("=" * 70)
    print(hexdump(d_pces[2], max_lines=64))

    # Strings in D Pces
    d_strings = find_strings(d_pces[2])
    print(f"\nStrings in D Pces ({len(d_strings)}):")
    for off, s in d_strings[:30]:
        print(f"  +0x{off:04x}  {s!r}")

    # === E's Pces — first 0x300 bytes ===
    print("\n" + "=" * 70)
    print(f"E Pces body — first 0x300 bytes")
    print("=" * 70)
    print(hexdump(e_pces[2][:0x300], max_lines=48))

    # Strings in E Pces
    e_strings = find_strings(e_pces[2])
    print(f"\nStrings in E Pces ({len(e_strings)} found, showing first 60):")
    for off, s in e_strings[:60]:
        print(f"  +0x{off:04x}  {s!r}")

if __name__ == "__main__":
    main()

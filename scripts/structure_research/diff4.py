#!/usr/bin/env python3
"""
Count SPWN chunks per file. Dump the new SPWN(s) that B has but A doesn't.
Then dump the new SPWN(s) that C has but B doesn't.
"""
import struct
from pathlib import Path

HERE = Path(__file__).parent

def load(name):
    return open(HERE / name, "rb").read()

def find_all(data, needle):
    out = []
    i = 0
    while True:
        i = data.find(needle, i)
        if i == -1:
            return out
        out.append(i)
        i += 1

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

def get_spwn_records(data):
    """Return list of (offset, length, body, prop_offset, prop_length, prop_body)."""
    records = []
    for off in find_all(data, b"SPWN"):
        length = struct.unpack_from("<I", data, off + 4)[0]
        if length < 100 or length > 10000:
            continue
        body = data[off + 8 : off + 8 + length]
        # The PROP block usually follows immediately
        prop_off = off + 8 + length
        if prop_off + 8 < len(data) and data[prop_off:prop_off+4] == b"PROP":
            prop_len = struct.unpack_from("<I", data, prop_off + 4)[0]
            prop_body = data[prop_off + 8 : prop_off + 8 + prop_len]
        else:
            prop_len = 0
            prop_body = b""
        records.append((off, length, body, prop_off, prop_len, prop_body))
    return records

def main():
    A = load("A.sav")
    B = load("B.sav")
    C = load("C.sav")

    a_recs = get_spwn_records(A)
    b_recs = get_spwn_records(B)
    c_recs = get_spwn_records(C)

    print(f"A: {len(a_recs)} SPWN records")
    print(f"B: {len(b_recs)} SPWN records  (Δ +{len(b_recs)-len(a_recs)})")
    print(f"C: {len(c_recs)} SPWN records  (Δ +{len(c_recs)-len(b_recs)})")

    # Look for SPWN bodies in B that are not in A
    a_bodies = {(r[1], bytes(r[2])) for r in a_recs}
    b_bodies = {(r[1], bytes(r[2])) for r in b_recs}
    c_bodies = {(r[1], bytes(r[2])) for r in c_recs}

    new_in_b = [(l, body) for (l, body) in b_bodies if (l, body) not in a_bodies]
    new_in_c = [(l, body) for (l, body) in c_bodies if (l, body) not in b_bodies]

    print(f"\nSPWN bodies new in B (vs A): {len(new_in_b)}")
    print(f"SPWN bodies new in C (vs B): {len(new_in_c)}")

    # Distinct SPWN body sizes per file
    from collections import Counter
    print("\nSPWN body sizes per file:")
    print(f"  A: {Counter(r[1] for r in a_recs)}")
    print(f"  B: {Counter(r[1] for r in b_recs)}")
    print(f"  C: {Counter(r[1] for r in c_recs)}")

    # Find SPWN records in B whose body is NOT byte-identical to anything in A
    # (meaning they were freshly added). Print them.
    print("\n" + "=" * 70)
    print("SPWN records that exist in B but whose body bytes don't appear in A")
    print("=" * 70)
    for off, length, body, p_off, p_len, p_body in b_recs:
        if (length, bytes(body)) not in a_bodies:
            print(f"\n--- B SPWN @ 0x{off:x}, len={length} ---")
            print(hexdump(body, base=0, max_lines=40))
            print(f"\n  → following PROP @ 0x{p_off:x}, len={p_len}")
            if p_body:
                print(hexdump(p_body, base=0, max_lines=24))
            break  # just show the first one

    print("\n" + "=" * 70)
    print("SPWN records that exist in C but whose body bytes don't appear in B")
    print("=" * 70)
    for off, length, body, p_off, p_len, p_body in c_recs:
        if (length, bytes(body)) not in b_bodies:
            print(f"\n--- C SPWN @ 0x{off:x}, len={length} ---")
            print(hexdump(body, base=0, max_lines=40))
            print(f"\n  → following PROP @ 0x{p_off:x}, len={p_len}")
            if p_body:
                print(hexdump(p_body, base=0, max_lines=24))
            break

if __name__ == "__main__":
    main()
